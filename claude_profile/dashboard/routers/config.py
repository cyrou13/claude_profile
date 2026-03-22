"""Config overview API endpoint — returns HTML partial for HTMX."""

from __future__ import annotations

import html as html_escape

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from claude_profile.dashboard.services.claude_config_parser import parse_claude_config

router = APIRouter()


@router.get("/overview", response_class=HTMLResponse)
async def config_overview(request: Request) -> str:
    """Render full Claude Code configuration overview."""
    config = request.app.state.config
    cc = parse_claude_config(config.claude_home, config.sync.scan_dirs)

    html = ""

    # --- Summary cards ---
    html += '<div class="grid">'
    html += f'<article><header><small>Skills</small></header><p style="font-size:2em;font-weight:bold;margin:0">{len(cc.skills)}</p></article>'
    html += f'<article><header><small>Agents</small></header><p style="font-size:2em;font-weight:bold;margin:0">{len(cc.agents)}</p></article>'
    html += f'<article><header><small>Commandes</small></header><p style="font-size:2em;font-weight:bold;margin:0">{len(cc.commands)}</p></article>'
    html += f'<article><header><small>MCP Servers</small></header><p style="font-size:2em;font-weight:bold;margin:0">{len(cc.mcp_servers)}</p></article>'
    html += '</div>'

    # --- CLAUDE.md global ---
    html += '<article>'
    html += f'<header><strong>CLAUDE.md global</strong> <small>({cc.global_claude_md_lines} lignes)</small></header>'
    # Show sections
    sections: list[str] = []
    for line in cc.global_claude_md.splitlines():
        if line.startswith("## "):
            sections.append(line[3:].strip())
    if sections:
        html += '<div style="display:flex;flex-wrap:wrap;gap:0.3rem">'
        for s in sections:
            html += f'<span style="background:var(--pico-muted-border-color);padding:2px 8px;border-radius:12px;font-size:0.85em">{html_escape.escape(s)}</span>'
        html += '</div>'
    html += '<details><summary>Voir le contenu</summary>'
    html += f'<pre style="max-height:400px;overflow:auto;font-size:0.8em"><code>{html_escape.escape(cc.global_claude_md)}</code></pre>'
    html += '</details></article>'

    # --- Skills ---
    html += '<article>'
    html += f'<header><strong>Skills</strong> ({len(cc.skills)})</header>'
    html += '<table><thead><tr><th>Nom</th><th>Description</th><th>Scripts</th></tr></thead><tbody>'
    for skill in cc.skills:
        scripts_badge = '<span class="success">oui</span>' if skill.has_scripts else '<small style="opacity:0.4">-</small>'
        html += f'<tr><td><code>/{skill.name}</code></td><td><small>{html_escape.escape(skill.description)}</small></td><td>{scripts_badge}</td></tr>'
    html += '</tbody></table></article>'

    # --- Agents ---
    html += '<article>'
    html += f'<header><strong>Agents</strong> ({len(cc.agents)})</header>'
    html += '<table><thead><tr><th>Nom</th><th>Modele</th><th>Outils</th><th>Description</th></tr></thead><tbody>'
    for agent in cc.agents:
        model_badge = f'<code>{agent.model}</code>' if agent.model else '<small style="opacity:0.4">defaut</small>'
        tools_str = ", ".join(agent.tools[:5]) if agent.tools else "-"
        if len(agent.tools) > 5:
            tools_str += f" +{len(agent.tools) - 5}"
        desc = html_escape.escape(agent.description[:80]) if agent.description else ""
        html += f'<tr><td><code>{html_escape.escape(agent.name)}</code></td><td>{model_badge}</td><td><small>{tools_str}</small></td><td><small>{desc}</small></td></tr>'
    html += '</tbody></table></article>'

    # --- Commands ---
    html += '<article>'
    html += f'<header><strong>Commandes</strong> ({len(cc.commands)})</header>'
    html += '<table><thead><tr><th>Nom</th><th>Description</th></tr></thead><tbody>'
    for cmd in cc.commands:
        html += f'<tr><td><code>/{cmd.name}</code></td><td><small>{html_escape.escape(cmd.description)}</small></td></tr>'
    html += '</tbody></table></article>'

    # --- MCP Servers ---
    if cc.mcp_servers:
        html += '<article>'
        html += f'<header><strong>MCP Servers</strong> ({len(cc.mcp_servers)})</header>'
        html += '<div style="display:flex;flex-wrap:wrap;gap:0.3rem">'
        for server in cc.mcp_servers:
            html += f'<span style="background:var(--pico-muted-border-color);padding:4px 12px;border-radius:12px;font-size:0.85em"><code>{html_escape.escape(server)}</code></span>'
        html += '</div></article>'

    # --- Project CLAUDE.md files ---
    if cc.project_claude_mds:
        html += '<article>'
        html += f'<header><strong>CLAUDE.md par projet</strong> ({len(cc.project_claude_mds)})</header>'
        html += '<table><thead><tr><th>Projet</th><th>Lignes</th><th>Apercu</th></tr></thead><tbody>'
        for pmd in cc.project_claude_mds:
            preview = html_escape.escape(pmd.preview.replace("\n", " ")[:100])
            html += f'<tr><td><code>{html_escape.escape(pmd.project_name)}</code></td><td>{pmd.line_count}</td><td><small>{preview}</small></td></tr>'
        html += '</tbody></table></article>'

    # --- Settings highlights ---
    if cc.settings:
        html += '<article>'
        html += '<header><strong>Settings</strong></header>'
        # Show key settings
        interesting_keys = ["model", "permissions", "apiKeyHelper", "env", "hooks"]
        html += '<dl>'
        for key in interesting_keys:
            if key in cc.settings:
                val = cc.settings[key]
                if isinstance(val, dict):
                    html += f'<dt><code>{key}</code></dt><dd>'
                    for k, v in list(val.items())[:10]:
                        html += f'<small><code>{html_escape.escape(str(k))}</code>: {html_escape.escape(str(v)[:80])}</small><br>'
                    html += '</dd>'
                elif isinstance(val, list):
                    html += f'<dt><code>{key}</code></dt><dd><small>{len(val)} elements</small></dd>'
                else:
                    html += f'<dt><code>{key}</code></dt><dd><small>{html_escape.escape(str(val)[:100])}</small></dd>'
        html += '</dl>'
        html += '<details><summary>Voir tout (JSON)</summary>'
        import json
        html += f'<pre style="max-height:300px;overflow:auto;font-size:0.75em"><code>{html_escape.escape(json.dumps(cc.settings, indent=2, default=str))}</code></pre>'
        html += '</details></article>'

    return html
