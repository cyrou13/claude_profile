"""Veille (watch) API endpoints — returns HTML partials for HTMX."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from claude_profile.dashboard.services.veille_fetcher import VeilleFetcher

router = APIRouter()


@router.get("/releases", response_class=HTMLResponse)
async def latest_releases(request: Request) -> str:
    report = VeilleFetcher.load_cache()
    if not report or not report.releases:
        return '<p>Aucune release en cache. Clique "Rafraichir".</p>'

    html = ""
    for r in report.releases[:10]:
        date = r.published_at.strftime("%d/%m/%Y")
        html += f"""<article>
            <header><strong>{r.repo}</strong> &mdash; <code>{r.tag}</code> <small>{date}</small></header>
            <p>{r.name}</p>
            {'<a href="' + r.url + '" target="_blank">Voir sur GitHub</a>' if r.url else ''}
        </article>"""
    return html


@router.get("/community", response_class=HTMLResponse)
async def community_repos(request: Request) -> str:
    report = VeilleFetcher.load_cache()
    if not report or not report.community_repos:
        return '<p>Aucun repo communautaire en cache. Clique "Rafraichir".</p>'

    html = "<table><thead><tr><th>Repo</th><th>Stars</th><th>Description</th></tr></thead><tbody>"
    for r in report.community_repos[:10]:
        desc = (r.description or "")[:60]
        html += f'<tr><td><a href="{r.url}" target="_blank">{r.full_name}</a></td><td>{r.stars}</td><td><small>{desc}</small></td></tr>'
    html += "</tbody></table>"
    return html


@router.get("/feed", response_class=HTMLResponse)
async def feed_entries(request: Request) -> str:
    report = VeilleFetcher.load_cache()
    if not report or not report.feed_entries:
        return '<p>Aucun article en cache. Clique "Rafraichir".</p>'

    html = ""
    for e in report.feed_entries[:10]:
        html += f"""<article>
            <header><strong>{e.title}</strong></header>
            <a href="{e.link}" target="_blank">{e.link}</a>
        </article>"""
    return html


@router.get("/refresh", response_class=HTMLResponse)
async def refresh_veille(request: Request) -> str:
    config = request.app.state.config
    fetcher = VeilleFetcher(config.veille)
    report = await fetcher.fetch_all()
    n = len(report.releases) + len(report.feed_entries) + len(report.community_repos)
    return f"<small>Rafraichi ! {n} elements recuperes.</small>"
