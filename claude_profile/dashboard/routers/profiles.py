"""Profile management API endpoints — returns HTML partials for HTMX."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from claude_profile.config import load_config, load_state, save_config, save_state
from claude_profile.dashboard.services.stats_parser import (
    _normalize_name,
    filter_sessions_by_profile,
    parse_sessions,
)
from claude_profile.profiles.isolation import list_unassigned_projects
from claude_profile.utils.claude_paths import list_projects


def _detect_project_info(scan_dirs: list[str], project_name: str) -> dict[str, str]:
    """Detect project metadata from the filesystem."""
    info: dict[str, str] = {"path": "", "git": "", "techs": "", "claude_md": ""}

    # Find the project directory
    norm = _normalize_name(project_name)
    for scan_dir in scan_dirs:
        base = Path(scan_dir).expanduser()
        if not base.exists():
            continue
        for d in base.iterdir():
            if d.is_dir() and _normalize_name(d.name) == norm:
                info["path"] = str(d)
                info["git"] = "oui" if (d / ".git").exists() else ""

                techs = []
                if (d / "pyproject.toml").exists() or (d / "setup.py").exists() or (d / "requirements.txt").exists():
                    techs.append("Python")
                if (d / "package.json").exists():
                    techs.append("JS/TS")
                if (d / "Dockerfile").exists() or (d / "docker-compose.yml").exists() or (d / "docker-compose.yaml").exists():
                    techs.append("Docker")
                if (d / "Cargo.toml").exists():
                    techs.append("Rust")
                if (d / "go.mod").exists():
                    techs.append("Go")
                info["techs"] = ", ".join(techs)

                if (d / "CLAUDE.md").exists():
                    lines = len((d / "CLAUDE.md").read_text().splitlines())
                    info["claude_md"] = f"{lines}L"

                return info

    return info

router = APIRouter()


@router.post("/assign", response_class=HTMLResponse)
async def assign_project(request: Request, project: str, profile: str) -> str:
    """Assign a project to a profile."""
    config = load_config()

    target = next((p for p in config.profiles if p.name == profile), None)
    if not target:
        return f"<p>Profil '{profile}' introuvable.</p>"

    # Remove from other profiles first
    for p in config.profiles:
        if project in p.projects:
            p.projects.remove(project)

    # Add to target
    if project not in target.projects:
        target.projects.append(project)

    save_config(config)
    # Update app state with fresh config
    request.app.state.config = load_config()
    return await profiles_full(request)


@router.post("/remove", response_class=HTMLResponse)
async def remove_project(request: Request, project: str, profile: str) -> str:
    """Remove a project from a profile (makes it unassigned)."""
    config = load_config()

    target = next((p for p in config.profiles if p.name == profile), None)
    if not target:
        return f"<p>Profil '{profile}' introuvable.</p>"

    if project in target.projects:
        target.projects.remove(project)

    save_config(config)
    request.app.state.config = load_config()
    return await profiles_full(request)


@router.post("/hide", response_class=HTMLResponse)
async def hide_project(request: Request, project: str) -> str:
    """Hide an unassigned project (add to a special 'hidden' list in state)."""
    state = load_state()
    if project not in state.hidden_projects:
        state.hidden_projects.append(project)
    save_state(state)
    return await profiles_full(request)


@router.post("/activate", response_class=HTMLResponse)
async def activate_profile(request: Request, profile: str) -> str:
    """Activate a profile."""
    from claude_profile.profiles.manager import activate_profile as do_activate

    config = load_config()
    target = next((p for p in config.profiles if p.name == profile), None)
    if not target:
        return f"<p>Profil '{profile}' introuvable.</p>"

    do_activate(config, profile)
    state = load_state()
    state.active_profile = profile
    save_state(state)
    request.app.state.config = load_config()
    return await profiles_full(request)


@router.post("/deactivate", response_class=HTMLResponse)
async def deactivate_profile(request: Request) -> str:
    """Deactivate the current profile."""
    from claude_profile.profiles.manager import deactivate_profile

    config = load_config()
    deactivate_profile(config)
    state = load_state()
    state.active_profile = None
    save_state(state)
    request.app.state.config = load_config()
    return await profiles_full(request)


@router.get("/full", response_class=HTMLResponse)
async def profiles_full(request: Request) -> str:
    """Render the full profiles panel HTML."""
    config = request.app.state.config
    sessions = parse_sessions(config.claude_home)
    state = load_state()

    profile_names = [p.name for p in config.profiles]
    all_discovered = list_projects(config.claude_home)

    html = ""

    # Active profile banner
    if state.active_profile:
        html += f"""<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem">
            <article style="border-left:4px solid var(--pico-primary);flex:1;margin:0">
                <strong>Profil actif :</strong> {state.active_profile}
            </article>
            <button class="outline secondary" style="height:fit-content"
                hx-post="/api/profiles/deactivate"
                hx-target="#profiles-content"
                hx-swap="innerHTML">Desactiver</button>
        </div>"""

    # Each profile
    for p in config.profiles:
        is_active = p.name == state.active_profile
        profile_sessions = filter_sessions_by_profile(sessions, p.projects)
        total_duration = sum(s.duration_minutes for s in profile_sessions)
        total_messages = sum(s.user_messages + s.assistant_messages for s in profile_sessions)
        total_tokens = sum(s.input_tokens + s.output_tokens for s in profile_sessions)
        total_lines = sum(s.lines_added for s in profile_sessions)

        achieved = sum(1 for s in profile_sessions if s.outcome == "fully_achieved")
        partial = sum(1 for s in profile_sessions if s.outcome == "partially_achieved")
        failed = sum(1 for s in profile_sessions if s.outcome == "not_achieved")

        active_style = "border-left:4px solid var(--pico-primary);" if is_active else ""
        badge = " (actif)" if is_active else ""

        html += f'<article style="{active_style}">'
        # Header with activate button
        html += '<div style="display:flex;justify-content:space-between;align-items:start">'
        html += f'<div><header style="margin:0"><strong>{p.name}{badge}</strong><br><small>{p.description or ""}</small></header></div>'
        if not is_active:
            html += f"""<button class="outline" style="height:fit-content;font-size:0.8em"
                hx-post="/api/profiles/activate?profile={p.name}"
                hx-target="#profiles-content"
                hx-swap="innerHTML">Activer</button>"""
        html += '</div>'

        # Stats
        html += f'<p><strong>{len(profile_sessions)}</strong> sessions &middot; <strong>{total_duration:.0f}</strong> min &middot; <strong>{total_messages}</strong> msgs &middot; <strong>{total_tokens:,}</strong> tokens &middot; <strong>{total_lines}</strong> lignes</p>'

        # Outcome bar
        total_with_outcome = achieved + partial + failed
        if total_with_outcome > 0:
            pct_ok = int(achieved / total_with_outcome * 100)
            pct_partial = int(partial / total_with_outcome * 100)
            pct_fail = 100 - pct_ok - pct_partial
            html += '<div style="display:flex;height:8px;border-radius:4px;overflow:hidden;margin-bottom:0.5rem">'
            html += f'<div style="width:{pct_ok}%;background:var(--pico-ins-color,#43a047)"></div>'
            html += f'<div style="width:{pct_partial}%;background:#f9a825"></div>'
            html += f'<div style="width:{pct_fail}%;background:var(--pico-del-color,#e53935)"></div>'
            html += '</div>'

        # Project table with session details
        html += f'<details open><summary><strong>{len(p.projects)}</strong> projets</summary>'
        html += '<table style="font-size:0.85em;margin-top:0.3rem"><thead><tr><th>Projet</th><th>Tech</th><th>Git</th><th>CLAUDE.md</th><th>Sessions</th><th>Duree</th><th>Msgs</th><th>Lignes</th><th></th></tr></thead><tbody>'

        for proj in sorted(p.projects):
            norm_proj = _normalize_name(proj)
            proj_sessions = sorted(
                [s for s in profile_sessions if _normalize_name(s.project_name) == norm_proj],
                key=lambda s: s.start_time or "",
                reverse=True,
            )
            count = len(proj_sessions)
            total_dur = sum(s.duration_minutes for s in proj_sessions)
            total_msgs = sum(s.user_messages + s.assistant_messages for s in proj_sessions)
            total_lines = sum(s.lines_added for s in proj_sessions)

            proj_info = _detect_project_info(config.sync.scan_dirs, proj)
            tech_badges = ""
            for tech in (proj_info["techs"].split(", ") if proj_info["techs"] else []):
                tech_badges += f'<span style="background:var(--pico-muted-border-color);padding:1px 5px;border-radius:6px;font-size:0.8em">{tech}</span> '
            git_badge = '<span class="success">git</span>' if proj_info["git"] else '<small style="opacity:0.3">-</small>'
            claude_badge = f'<small>{proj_info["claude_md"]}</small>' if proj_info["claude_md"] else '<small style="opacity:0.3">-</small>'
            remove_btn = f"""<a href="#" style="color:var(--pico-del-color);text-decoration:none;font-weight:bold"
                   hx-post="/api/profiles/remove?project={proj}&profile={p.name}"
                   hx-target="#profiles-content" hx-swap="innerHTML"
                   hx-confirm="Retirer {proj} du profil {p.name} ?"
                   title="Retirer">&times;</a>"""

            if count > 0:
                # Row with expandable sessions
                html += f'<tr><td colspan="9" style="padding:0">'
                html += f'<details style="margin:0"><summary style="display:flex;align-items:center;padding:0.3rem 0.5rem;gap:0;cursor:pointer">'
                html += f'<span style="flex:1"><code>{proj}</code></span>'
                html += f'<span style="width:80px">{tech_badges}</span>'
                html += f'<span style="width:40px;text-align:center">{git_badge}</span>'
                html += f'<span style="width:55px;text-align:center">{claude_badge}</span>'
                html += f'<span style="width:55px;text-align:center"><strong>{count}</strong></span>'
                html += f'<span style="width:55px;text-align:center">{total_dur:.0f}m</span>'
                html += f'<span style="width:50px;text-align:center">{total_msgs}</span>'
                html += f'<span style="width:55px;text-align:center">+{total_lines}</span>'
                html += f'<span style="width:25px;text-align:center">{remove_btn}</span>'
                html += '</summary>'

                # Nested sessions table
                html += '<div style="padding:0 0.5rem 0.5rem 1.5rem">'
                html += '<table style="font-size:0.85em;margin:0"><thead><tr><th>Date</th><th>Duree</th><th>Msgs</th><th>Code</th><th>Outcome</th><th>Resume / Prompt</th></tr></thead><tbody>'
                for s in proj_sessions[:20]:
                    date = s.start_time.strftime("%d/%m %H:%M") if s.start_time else "-"
                    oc = s.outcome or "-"
                    oc_short = {"fully_achieved": "OK", "mostly_achieved": "~OK", "partially_achieved": "Partiel", "not_achieved": "Echec"}.get(oc, oc)
                    cls = "success" if oc == "fully_achieved" else ("error" if oc == "not_achieved" else "")
                    total_msg = s.user_messages + s.assistant_messages
                    code = f"+{s.lines_added}" if s.lines_added else "-"
                    summary = (s.first_prompt or s.summary or "")[:100]
                    html += f'<tr><td>{date}</td><td>{s.duration_minutes:.0f}m</td><td>{total_msg}</td><td>{code}</td><td><span class="{cls}">{oc_short}</span></td><td><small>{summary}</small></td></tr>'
                html += '</tbody></table>'
                if count > 20:
                    html += f'<small style="opacity:0.5">... et {count - 20} autres</small>'
                html += '</div></details></td></tr>'
            else:
                html += f'<tr>'
                html += f'<td><code>{proj}</code></td>'
                html += f'<td>{tech_badges or "<small style=\"opacity:0.3\">-</small>"}</td>'
                html += f'<td>{git_badge}</td>'
                html += f'<td>{claude_badge}</td>'
                html += f'<td style="opacity:0.3">0</td><td style="opacity:0.3">-</td><td style="opacity:0.3">-</td><td style="opacity:0.3">-</td>'
                html += f'<td>{remove_btn}</td>'
                html += '</tr>'

        html += '</tbody></table></details>'

        html += '</article>'

    # Unassigned projects
    unassigned = list_unassigned_projects(config)
    hidden = state.hidden_projects
    visible_unassigned = {k: v for k, v in unassigned.items() if k not in hidden}

    if visible_unassigned:
        html += '<article>'
        html += f'<header><strong>Projets non assignes</strong> ({len(visible_unassigned)})</header>'
        html += '<p><small>Ces projets existent dans <code>~/.claude/projects/</code> mais ne sont dans aucun profil. Assigne-les ou masque-les.</small></p>'

        for name in sorted(visible_unassigned.keys()):
            proj_sessions = [s for s in sessions if s.project_name == name]
            count = len(proj_sessions)
            info = f"{count} sessions" if count > 0 else "aucune session"

            # Detect real path for context
            raw_dir = visible_unassigned[name]

            html += f'<div style="display:flex;align-items:center;gap:0.5rem;margin:4px 0;padding:4px 8px;border:1px solid var(--pico-muted-border-color);border-radius:8px">'
            html += f'<code style="flex:1">{name}</code>'
            html += f'<small style="opacity:0.5">{info}</small>'

            # Assign dropdown for each profile
            for prof in config.profiles:
                html += f"""<button class="outline" style="font-size:0.7em;padding:2px 8px;margin:0;height:auto"
                    hx-post="/api/profiles/assign?project={name}&profile={prof.name}"
                    hx-target="#profiles-content"
                    hx-swap="innerHTML">&rarr; {prof.name}</button>"""

            html += '</div>'

        html += '</article>'

    return html
