"""Recommendations API endpoints — returns HTML partials for HTMX."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from claude_profile.dashboard.services.recommender import generate_recommendations
from claude_profile.dashboard.services.stats_parser import parse_sessions, parse_stats_cache

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def get_recommendations(request: Request) -> str:
    config = request.app.state.config
    stats = parse_stats_cache(config.claude_home)
    sessions = parse_sessions(config.claude_home)

    recs = generate_recommendations(
        totals=stats.get("totals", {}),  # type: ignore[arg-type]
        model_usage=stats.get("model_usage", []),  # type: ignore[arg-type]
        sessions=sessions,
    )

    if not recs:
        return "<p>Aucune recommandation pour le moment.</p>"

    html = ""
    for r in recs:
        html += f"""<article class="rec-{r.priority}">
            <header><strong>[{r.category}] {r.title}</strong> <small class="{r.priority}">{r.priority}</small></header>
            <p>{r.description}</p>
        </article>"""
    return html
