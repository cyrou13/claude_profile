"""Usage stats API endpoints — returns HTML partials for HTMX."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from claude_profile.dashboard.services.stats_parser import (
    filter_sessions_by_profile,
    parse_sessions,
    parse_stats_cache,
)
from claude_profile.config import load_state
from claude_profile.profiles.isolation import get_profile_by_name, list_unassigned_projects

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
    state = load_state()

    if not config.profiles:
        return "<p>Aucun profil configure. Ajoute des profils dans <code>~/.config/claude-profile/config.toml</code></p>"

    html = ""

    # Active profile banner
    if state.active_profile:
        html += f'<article style="border-left:4px solid var(--pico-primary)"><strong>Profil actif :</strong> {state.active_profile}</article>'

    for p in config.profiles:
        is_active = p.name == state.active_profile
        profile_sessions = filter_sessions_by_profile(sessions, p.projects)
        total_duration = sum(s.duration_minutes for s in profile_sessions)
        total_messages = sum(s.user_messages + s.assistant_messages for s in profile_sessions)
        total_tokens = sum(s.input_tokens + s.output_tokens for s in profile_sessions)
        total_lines = sum(s.lines_added for s in profile_sessions)

        # Outcomes
        achieved = sum(1 for s in profile_sessions if s.outcome == "fully_achieved")
        partial = sum(1 for s in profile_sessions if s.outcome == "partially_achieved")
        failed = sum(1 for s in profile_sessions if s.outcome == "not_achieved")

        active_mark = ' style="border-left:4px solid var(--pico-primary)"' if is_active else ""
        badge = " (actif)" if is_active else ""

        html += f'<article{active_mark}>'
        html += f'<header><strong>{p.name}{badge}</strong><br><small>{p.description or ""}</small></header>'

        # Stats summary
        html += f'<p><strong>{len(profile_sessions)}</strong> sessions &middot; <strong>{total_duration:.0f}</strong> min &middot; <strong>{total_messages}</strong> messages &middot; <strong>{total_tokens:,}</strong> tokens &middot; <strong>{total_lines}</strong> lignes ajoutees</p>'

        # Outcome bar
        total_with_outcome = achieved + partial + failed
        if total_with_outcome > 0:
            pct_ok = int(achieved / total_with_outcome * 100)
            pct_partial = int(partial / total_with_outcome * 100)
            pct_fail = 100 - pct_ok - pct_partial
            html += '<div style="display:flex;height:8px;border-radius:4px;overflow:hidden;margin-bottom:0.5rem">'
            html += f'<div style="width:{pct_ok}%;background:var(--pico-ins-color,#43a047)" title="{achieved} reussis"></div>'
            html += f'<div style="width:{pct_partial}%;background:var(--pico-ins-color,#f9a825)" title="{partial} partiels"></div>'
            html += f'<div style="width:{pct_fail}%;background:var(--pico-del-color,#e53935)" title="{failed} echoues"></div>'
            html += '</div>'
            html += f'<small class="success">{achieved} reussis</small> &middot; <small>{partial} partiels</small> &middot; <small class="error">{failed} echoues</small>'

        # Project list
        html += f'<details><summary><strong>{len(p.projects)}</strong> projets</summary><ul>'
        for proj in sorted(p.projects):
            proj_sessions = [s for s in profile_sessions if s.project_name == proj]
            count = len(proj_sessions)
            proj_msgs = sum(s.user_messages + s.assistant_messages for s in proj_sessions)
            if count > 0:
                html += f'<li><code>{proj}</code> — {count} sessions, {proj_msgs} messages</li>'
            else:
                html += f'<li><code>{proj}</code> <small style="opacity:0.5">(aucune session)</small></li>'
        html += '</ul></details>'

        html += '</article>'

    # Unassigned projects
    unassigned = list_unassigned_projects(config)
    if unassigned:
        html += '<article><header><strong>Projets non assignes</strong></header>'
        html += '<p><small>Ces projets ont des sessions mais ne sont rattaches a aucun profil.</small></p><ul>'
        for name in sorted(unassigned.keys()):
            proj_sessions = [s for s in sessions if s.project_name == name]
            count = len(proj_sessions)
            if count > 0:
                html += f'<li><code>{name}</code> — {count} sessions</li>'
            else:
                html += f'<li><code>{name}</code></li>'
        html += '</ul></article>'

    return html
