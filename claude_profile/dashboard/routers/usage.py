"""Usage stats API endpoints — returns HTML partials for HTMX."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from claude_profile.dashboard.services.stats_parser import (
    filter_sessions_by_profile,
    parse_sessions,
    parse_stats_cache,
)
from claude_profile.profiles.isolation import get_profile_by_name

router = APIRouter()


@router.get("/summary", response_class=HTMLResponse)
async def usage_summary(request: Request) -> str:
    config = request.app.state.config
    data = parse_stats_cache(config.claude_home)
    t = data.get("totals", {})
    models = data.get("model_usage", [])
    daily = data.get("daily_activity", [])

    # Cards
    html = '<div class="grid">'
    for label, key in [("Messages", "messages"), ("Sessions", "sessions"), ("Tool Calls", "tool_calls"), ("Tokens", "tokens")]:
        val = f"{t.get(key, 0):,}"
        html += f'<article><header><small>{label}</small></header><p style="font-size:2em;font-weight:bold;margin:0">{val}</p></article>'
    html += "</div>"

    # Model table
    if models:
        html += "<h3>Repartition par modele</h3><table><thead><tr><th>Modele</th><th>Tokens</th></tr></thead><tbody>"
        for m in models:
            html += f'<tr><td><code>{m["model_id"]}</code></td><td>{m["output_tokens"]:,}</td></tr>'
        html += "</tbody></table>"

    # Bar chart
    if daily:
        recent = daily[-30:]
        max_msg = max((d["message_count"] for d in recent), default=1)
        html += "<h3>Activite quotidienne</h3><div class='chart'>"
        for d in recent:
            pct = int(d["message_count"] / max_msg * 100) if max_msg else 0
            html += f'<div class="bar-wrap" title="{d["date"]}: {d["message_count"]:,} msgs"><div class="bar" style="height:{pct}%"></div></div>'
        html += "</div>"

    return html


@router.get("/sessions", response_class=HTMLResponse)
async def sessions_list(request: Request, profile: str | None = None) -> str:
    config = request.app.state.config
    sessions = parse_sessions(config.claude_home)

    if profile:
        p = get_profile_by_name(config, profile)
        if p:
            sessions = filter_sessions_by_profile(sessions, p.projects)

    sessions.sort(key=lambda s: s.start_time or "", reverse=True)
    sessions = sessions[:50]

    if not sessions:
        return "<p>Aucune session trouvee.</p>"

    html = "<table><thead><tr><th>Date</th><th>Projet</th><th>Duree</th><th>Messages</th><th>Outcome</th><th>Resume</th></tr></thead><tbody>"
    for s in sessions:
        date = s.start_time.strftime("%d/%m/%Y") if s.start_time else "-"
        oc = s.outcome or "-"
        cls = "success" if oc == "fully_achieved" else ("error" if oc == "not_achieved" else "")
        summary = (s.summary or "")[:80]
        total_msg = s.user_messages + s.assistant_messages
        html += f'<tr><td>{date}</td><td><code>{s.project_name}</code></td><td>{s.duration_minutes:.0f}min</td><td>{total_msg}</td><td><span class="{cls}">{oc}</span></td><td><small>{summary}</small></td></tr>'
    html += "</tbody></table>"
    return html


@router.get("/profiles", response_class=HTMLResponse)
async def profiles_usage(request: Request) -> str:
    config = request.app.state.config
    sessions = parse_sessions(config.claude_home)

    if not config.profiles:
        return "<p>Aucun profil configure.</p>"

    html = '<div class="grid">'
    for p in config.profiles:
        profile_sessions = filter_sessions_by_profile(sessions, p.projects)
        total_duration = sum(s.duration_minutes for s in profile_sessions)
        total_messages = sum(s.user_messages + s.assistant_messages for s in profile_sessions)
        html += f"""<article>
            <header><strong>{p.name}</strong></header>
            <p>{p.description or ''}</p>
            <p><strong>{len(p.projects)}</strong> projets &middot; <strong>{len(profile_sessions)}</strong> sessions &middot; <strong>{total_duration:.0f}</strong> min &middot; <strong>{total_messages}</strong> messages</p>
        </article>"""
    html += "</div>"
    return html
