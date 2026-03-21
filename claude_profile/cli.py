"""CLI entry point using Typer."""

from __future__ import annotations

from pathlib import Path

import typer

from claude_profile.config import load_config, load_state, save_state
from claude_profile.models import AppConfig

app = typer.Typer(
    name="claude-profile",
    help="Sync, profile isolation, and monitoring dashboard for Claude Code.",
    no_args_is_help=True,
)
sync_app = typer.Typer(help="Sync Claude Code config across machines.")
profile_app = typer.Typer(help="Manage personal/professional profiles.")
app.add_typer(sync_app, name="sync")
app.add_typer(profile_app, name="profile")


def _load_cfg() -> AppConfig:
    return load_config()


# --- Sync commands ---


@sync_app.command("init")
def sync_init() -> None:
    """Initialize the sync repository from current ~/.claude/ state."""
    from claude_profile.sync.engine import init_sync_repo

    config = _load_cfg()
    typer.echo(f"Initializing sync repo at {config.sync_repo} ...")
    init_sync_repo(config)
    typer.echo("Done. Sync repo initialized with current config.")


@sync_app.command("status")
def sync_status() -> None:
    """Show diff between local ~/.claude/ and sync repo."""
    from claude_profile.sync.engine import get_sync_status

    config = _load_cfg()
    status = get_sync_status(config)
    typer.echo("Sync status:")
    typer.echo(status.summary())


@sync_app.command("push")
def sync_push() -> None:
    """Push local changes to sync repo (git commit + push)."""
    from claude_profile.sync.engine import push_to_repo

    config = _load_cfg()
    typer.echo("Pushing local changes to sync repo...")
    status = push_to_repo(config)
    if status.has_changes:
        typer.echo(f"Pushed: {len(status.added)} added, {len(status.modified)} modified, {len(status.deleted)} deleted")
    else:
        typer.echo("No changes to push.")


@sync_app.command("pull")
def sync_pull() -> None:
    """Pull sync repo changes to local ~/.claude/."""
    from claude_profile.sync.engine import pull_from_repo

    config = _load_cfg()
    typer.echo("Pulling changes from sync repo...")
    status = pull_from_repo(config)
    if status.has_changes:
        typer.echo(f"Pulled: {len(status.added)} added, {len(status.modified)} modified")
    else:
        typer.echo("Already up to date.")


# --- Profile commands ---


@profile_app.command("list")
def profile_list() -> None:
    """List all configured profiles."""
    config = _load_cfg()
    state = load_state()

    if not config.profiles:
        typer.echo("No profiles configured. Add profiles to ~/.config/claude-profile/config.toml")
        return

    for p in config.profiles:
        active = " (active)" if p.name == state.active_profile else ""
        typer.echo(f"  {p.name}{active} - {p.description} [{len(p.projects)} projects]")


@profile_app.command("show")
def profile_show() -> None:
    """Show the currently active profile and its projects."""
    config = _load_cfg()
    state = load_state()

    if not state.active_profile:
        typer.echo("No active profile. Use 'claude-profile profile activate <name>'")
        return

    profile = next((p for p in config.profiles if p.name == state.active_profile), None)
    if not profile:
        typer.echo(f"Active profile '{state.active_profile}' not found in config.")
        return

    typer.echo(f"Active profile: {profile.name}")
    typer.echo(f"Description: {profile.description}")
    typer.echo(f"Projects ({len(profile.projects)}):")
    for proj in profile.projects:
        typer.echo(f"  - {proj}")


@profile_app.command("activate")
def profile_activate(name: str) -> None:
    """Activate a profile (applies CLAUDE.md overlay)."""
    from claude_profile.profiles.manager import activate_profile

    config = _load_cfg()
    profile = next((p for p in config.profiles if p.name == name), None)
    if not profile:
        typer.echo(f"Profile '{name}' not found. Available: {', '.join(p.name for p in config.profiles)}")
        raise typer.Exit(1)

    activate_profile(config, name)
    state = load_state()
    state.active_profile = name
    save_state(state)
    typer.echo(f"Profile '{name}' activated. CLAUDE.md updated with overlay.")


@profile_app.command("create")
def profile_create(
    name: str,
    projects: str = typer.Option(..., help="Comma-separated project names"),
    description: str = typer.Option("", help="Profile description"),
) -> None:
    """Create a new profile."""
    from claude_profile.config import save_config
    from claude_profile.models import ProfileConfig

    config = _load_cfg()
    if any(p.name == name for p in config.profiles):
        typer.echo(f"Profile '{name}' already exists.")
        raise typer.Exit(1)

    project_list = [p.strip() for p in projects.split(",") if p.strip()]
    new_profile = ProfileConfig(name=name, description=description, projects=project_list)
    config.profiles.append(new_profile)
    save_config(config)
    typer.echo(f"Profile '{name}' created with {len(project_list)} projects.")


# --- Dashboard command ---


@app.command("dashboard")
def dashboard(
    port: int = typer.Option(8741, help="Dashboard port"),
    host: str = typer.Option("127.0.0.1", help="Dashboard host"),
) -> None:
    """Start the monitoring dashboard."""
    import uvicorn

    from claude_profile.dashboard.app import create_app

    config = _load_cfg()
    _app = create_app(config)
    typer.echo(f"Starting dashboard at http://{host}:{port}")
    uvicorn.run(_app, host=host, port=port)


# --- Veille command ---


@app.command("veille")
def veille_check() -> None:
    """Check for latest Claude Code updates, MCP servers, and best practices."""
    import asyncio

    from claude_profile.dashboard.services.veille_fetcher import VeilleFetcher

    config = _load_cfg()
    fetcher = VeilleFetcher(config.veille)
    report = asyncio.run(fetcher.fetch_all())

    typer.echo("\n=== Claude Code Veille ===\n")

    if report.releases:
        typer.echo("Latest Releases:")
        for r in report.releases[:5]:
            typer.echo(f"  {r.repo} {r.tag} ({r.published_at.strftime('%Y-%m-%d')})")
            if r.body:
                first_line = r.body.strip().split("\n")[0][:100]
                typer.echo(f"    {first_line}")

    if report.feed_entries:
        typer.echo("\nBlog / RSS:")
        for e in report.feed_entries[:5]:
            typer.echo(f"  {e.title}")
            typer.echo(f"    {e.link}")

    if report.community_repos:
        typer.echo("\nCommunity:")
        for c in report.community_repos[:5]:
            typer.echo(f"  {c.full_name} ({c.stars} stars)")
            if c.description:
                typer.echo(f"    {c.description[:80]}")

    typer.echo(f"\nFetched at {report.fetched_at.strftime('%Y-%m-%d %H:%M')}")
