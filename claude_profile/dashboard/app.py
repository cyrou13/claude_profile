"""FastAPI dashboard application."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from claude_profile.models import AppConfig

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = TEMPLATES_DIR / "static"


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI dashboard application."""
    from claude_profile.config import load_config

    if config is None:
        config = load_config()

    app = FastAPI(title="Claude Profile Dashboard", version="0.1.0")

    # Store config in app state
    app.state.config = config

    # Templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates

    # Static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Import and include routers
    from claude_profile.dashboard.routers import config, profiles, recommendations, usage, veille

    app.include_router(usage.router, prefix="/api/usage", tags=["usage"])
    app.include_router(veille.router, prefix="/api/veille", tags=["veille"])
    app.include_router(recommendations.router, prefix="/api/recommendations", tags=["recommendations"])
    app.include_router(profiles.router, prefix="/api/profiles", tags=["profiles"])
    app.include_router(config.router, prefix="/api/config", tags=["config"])

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"config": config},
        )

    return app
