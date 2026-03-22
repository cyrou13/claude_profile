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

    if not sessions:
        return "<p>Aucune session trouvee.</p>"

    html = ""

    # --- Aggregate analytics ---
    total_duration = sum(s.duration_minutes for s in sessions)
    total_msgs = sum(s.user_messages + s.assistant_messages for s in sessions)
    total_lines = sum(s.lines_added for s in sessions)
    total_commits = sum(s.git_commits for s in sessions)
    total_errors = sum(s.tool_errors for s in sessions)
    with_agent = sum(1 for s in sessions if s.uses_task_agent)

    # Outcomes
    outcomes: dict[str, int] = {}
    for s in sessions:
        oc = s.outcome or "unknown"
        outcomes[oc] = outcomes.get(oc, 0) + 1

    # Top tools across all sessions
    tool_totals: dict[str, int] = {}
    for s in sessions:
        for tool, count in s.tool_counts.items():
            tool_totals[tool] = tool_totals.get(tool, 0) + count
    top_tools = sorted(tool_totals.items(), key=lambda x: -x[1])[:10]

    # Top languages
    lang_totals: dict[str, int] = {}
    for s in sessions:
        for lang, count in s.languages.items():
            lang_totals[lang] = lang_totals.get(lang, 0) + count
    top_langs = sorted(lang_totals.items(), key=lambda x: -x[1])[:8]

    # Friction analysis
    friction_totals: dict[str, int] = {}
    for s in sessions:
        for friction, count in s.friction_counts.items():
            friction_totals[friction] = friction_totals.get(friction, 0) + count

    # Goal categories
    goal_cat_totals: dict[str, int] = {}
    for s in sessions:
        for cat, count in s.goal_categories.items():
            goal_cat_totals[cat] = goal_cat_totals.get(cat, 0) + count
    top_goals = sorted(goal_cat_totals.items(), key=lambda x: -x[1])[:10]

    # Helpfulness distribution
    help_dist: dict[str, int] = {}
    for s in sessions:
        if s.helpfulness:
            help_dist[s.helpfulness] = help_dist.get(s.helpfulness, 0) + 1

    # Summary cards
    html += '<div class="grid">'
    html += f'<article><header><small>Sessions</small></header><p style="font-size:2em;font-weight:bold;margin:0">{len(sessions)}</p></article>'
    html += f'<article><header><small>Duree totale</small></header><p style="font-size:2em;font-weight:bold;margin:0">{total_duration / 60:.0f}h</p></article>'
    html += f'<article><header><small>Messages</small></header><p style="font-size:2em;font-weight:bold;margin:0">{total_msgs:,}</p></article>'
    html += f'<article><header><small>Lignes ajoutees</small></header><p style="font-size:2em;font-weight:bold;margin:0">{total_lines:,}</p></article>'
    html += '</div>'

    # Second row: efficiency metrics
    avg_duration = total_duration / len(sessions) if sessions else 0
    avg_msgs = total_msgs / len(sessions) if sessions else 0
    lines_per_hour = total_lines / (total_duration / 60) if total_duration > 0 else 0
    error_rate = total_errors / sum(tool_totals.values()) * 100 if tool_totals else 0

    html += '<div class="grid">'
    html += f'<article><header><small>Duree moyenne</small></header><p style="font-size:1.5em;font-weight:bold;margin:0">{avg_duration:.0f} min</p></article>'
    html += f'<article><header><small>Msgs/session</small></header><p style="font-size:1.5em;font-weight:bold;margin:0">{avg_msgs:.0f}</p></article>'
    html += f'<article><header><small>Lignes/heure</small></header><p style="font-size:1.5em;font-weight:bold;margin:0">{lines_per_hour:.0f}</p></article>'
    html += f'<article><header><small>Taux erreur tools</small></header><p style="font-size:1.5em;font-weight:bold;margin:0">{error_rate:.1f}%</p><small>{total_errors} erreurs / {sum(tool_totals.values())} appels</small></article>'
    html += '</div>'

    # Outcomes bar
    html += '<h3>Outcomes</h3>'
    outcome_colors = {
        "fully_achieved": ("var(--pico-ins-color,#43a047)", "Reussi"),
        "mostly_achieved": ("var(--pico-ins-color,#66bb6a)", "Quasi reussi"),
        "partially_achieved": ("#f9a825", "Partiel"),
        "not_achieved": ("var(--pico-del-color,#e53935)", "Echoue"),
    }
    total_with_outcome = sum(v for k, v in outcomes.items() if k != "unknown")
    if total_with_outcome > 0:
        html += '<div style="display:flex;height:24px;border-radius:4px;overflow:hidden;margin-bottom:0.5rem">'
        for key, (color, label) in outcome_colors.items():
            count = outcomes.get(key, 0)
            if count > 0:
                pct = count / total_with_outcome * 100
                html += f'<div style="width:{pct}%;background:{color};display:flex;align-items:center;justify-content:center" title="{label}: {count}"><small style="color:#fff;font-size:0.7em">{count}</small></div>'
        html += '</div>'
        html += '<small>'
        html += ' &middot; '.join(
            f'{label}: {outcomes.get(key, 0)}'
            for key, (_, label) in outcome_colors.items()
            if outcomes.get(key, 0) > 0
        )
        html += '</small>'

    # Helpfulness
    if help_dist:
        help_order = ["extremely_helpful", "very_helpful", "helpful", "slightly_helpful", "not_helpful"]
        help_labels = {"extremely_helpful": "Excellent", "very_helpful": "Tres utile", "helpful": "Utile", "slightly_helpful": "Peu utile", "not_helpful": "Inutile"}
        html += '<h3>Utilite perçue de Claude</h3><div style="display:flex;gap:1rem;flex-wrap:wrap">'
        for h in help_order:
            if h in help_dist:
                html += f'<span><strong>{help_dist[h]}</strong> <small>{help_labels.get(h, h)}</small></span>'
        html += '</div>'

    # Top tools + top languages side by side
    html += '<div class="grid">'

    if top_tools:
        max_tool = top_tools[0][1] if top_tools else 1
        html += '<article><header><strong>Top outils</strong></header>'
        for tool, count in top_tools:
            pct = int(count / max_tool * 100)
            html += f'<div style="display:flex;align-items:center;gap:0.5rem;margin:2px 0"><code style="width:100px;font-size:0.8em">{tool}</code><div style="flex:1;background:var(--pico-muted-border-color);border-radius:2px;height:12px"><div style="width:{pct}%;height:100%;background:var(--pico-primary);border-radius:2px"></div></div><small>{count}</small></div>'
        html += '</article>'

    if top_langs:
        max_lang = top_langs[0][1] if top_langs else 1
        html += '<article><header><strong>Langages</strong></header>'
        for lang, count in top_langs:
            pct = int(count / max_lang * 100)
            html += f'<div style="display:flex;align-items:center;gap:0.5rem;margin:2px 0"><code style="width:100px;font-size:0.8em">{lang}</code><div style="flex:1;background:var(--pico-muted-border-color);border-radius:2px;height:12px"><div style="width:{pct}%;height:100%;background:var(--pico-primary);border-radius:2px"></div></div><small>{count}</small></div>'
        html += '</article>'

    html += '</div>'

    # Goal categories + friction side by side
    if top_goals or friction_totals:
        html += '<div class="grid">'
        if top_goals:
            html += '<article><header><strong>Types de taches</strong></header><ul style="list-style:none;padding:0">'
            for cat, count in top_goals:
                label = cat.replace("_", " ").title()
                html += f'<li><strong>{count}</strong> <small>{label}</small></li>'
            html += '</ul></article>'
        if friction_totals:
            html += '<article><header><strong>Points de friction</strong></header><ul style="list-style:none;padding:0">'
            for friction, count in sorted(friction_totals.items(), key=lambda x: -x[1]):
                label = friction.replace("_", " ").title()
                html += f'<li><strong>{count}</strong> <small>{label}</small></li>'
            html += '</ul></article>'
        html += '</div>'

    # Features usage
    html += f'<p><small>Sub-agents utilises dans <strong>{with_agent}</strong>/{len(sessions)} sessions &middot; <strong>{total_commits}</strong> commits git</small></p>'

    # --- Session table (last 50) ---
    display_sessions = sessions[:50]
    html += "<h3>Dernieres sessions</h3>"
    html += "<table><thead><tr><th>Date</th><th>Projet</th><th>Duree</th><th>Msgs</th><th>Code</th><th>Outcome</th><th>Prompt initial</th></tr></thead><tbody>"
    for s in display_sessions:
        date = s.start_time.strftime("%d/%m %H:%M") if s.start_time else "-"
        oc = s.outcome or "-"
        cls = "success" if oc == "fully_achieved" else ("error" if oc == "not_achieved" else "")
        oc_short = {"fully_achieved": "OK", "mostly_achieved": "~OK", "partially_achieved": "Partiel", "not_achieved": "Echec"}.get(oc, oc)
        total_msg = s.user_messages + s.assistant_messages
        code_info = f"+{s.lines_added}" if s.lines_added else "-"
        prompt = (s.first_prompt or s.summary or "")[:60]

        # Tools summary for detail
        top_session_tools = sorted(s.tool_counts.items(), key=lambda x: -x[1])[:5]
        tools_str = ", ".join(f"{t}:{c}" for t, c in top_session_tools)
        langs_str = ", ".join(s.languages.keys()) if s.languages else ""
        friction_str = s.friction_detail or ""

        html += f'<tr><td><small>{date}</small></td><td><code>{s.project_name}</code></td><td>{s.duration_minutes:.0f}m</td><td>{total_msg}</td><td><small>{code_info}</small></td><td><span class="{cls}"><small>{oc_short}</small></span></td>'
        html += f'<td><details><summary><small>{prompt}</small></summary>'
        if s.summary:
            html += f'<p><small>{s.summary}</small></p>'
        if tools_str:
            html += f'<p><small><strong>Tools:</strong> {tools_str}</small></p>'
        if langs_str:
            html += f'<p><small><strong>Langages:</strong> {langs_str}</small></p>'
        if friction_str:
            html += f'<p><small style="color:var(--pico-del-color)"><strong>Friction:</strong> {friction_str}</small></p>'
        html += '</details></td></tr>'
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
