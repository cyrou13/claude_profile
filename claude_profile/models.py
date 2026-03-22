"""Pydantic models for claude-profile."""

from __future__ import annotations

import tomllib
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


# --- Sync Models ---


class FileEntry(BaseModel):
    """A tracked file in the sync manifest."""

    sha256: str
    modified: datetime
    size: int


class SyncManifest(BaseModel):
    """Tracks the state of synced files per machine."""

    version: int = 1
    last_sync: datetime
    machine_id: str
    files: dict[str, FileEntry] = Field(default_factory=dict)


# --- Profile Models ---


class ProfileConfig(BaseModel):
    """A named profile grouping projects with optional CLAUDE.md overlay."""

    name: str
    description: str = ""
    projects: list[str] = Field(default_factory=list)
    claude_md_overlay: str = ""
    settings_overrides: dict[str, object] | None = None


# --- Veille Models ---


class VeilleConfig(BaseModel):
    """Configuration for the watch/veille system."""

    check_interval_hours: int = 24
    github_repos: list[str] = Field(
        default_factory=lambda: [
            "anthropics/claude-code",
            "modelcontextprotocol/servers",
            "anthropics/courses",
        ]
    )
    rss_feeds: list[str] = Field(
        default_factory=lambda: [
            "https://www.anthropic.com/blog/rss",
        ]
    )


class ReleaseInfo(BaseModel):
    """A GitHub release."""

    repo: str
    tag: str
    name: str
    published_at: datetime
    body: str = ""
    url: str = ""


class FeedEntry(BaseModel):
    """An RSS feed entry."""

    title: str
    link: str
    published: datetime | None = None
    summary: str = ""


class CommunityRepo(BaseModel):
    """A community repository found via GitHub search."""

    name: str
    full_name: str
    description: str = ""
    stars: int = 0
    url: str = ""
    updated_at: datetime | None = None


class VeilleReport(BaseModel):
    """Aggregated veille results."""

    fetched_at: datetime
    releases: list[ReleaseInfo] = Field(default_factory=list)
    feed_entries: list[FeedEntry] = Field(default_factory=list)
    community_repos: list[CommunityRepo] = Field(default_factory=list)


# --- Dashboard / Usage Models ---


class DailyActivity(BaseModel):
    """Daily usage activity."""

    date: str
    message_count: int = 0
    session_count: int = 0
    tool_call_count: int = 0


class ModelUsage(BaseModel):
    """Token usage for a specific model."""

    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


class SessionSummary(BaseModel):
    """Summary of a Claude Code session."""

    session_id: str
    project_name: str = ""
    start_time: datetime | None = None
    duration_minutes: float = 0
    user_messages: int = 0
    assistant_messages: int = 0
    tool_counts: dict[str, int] = Field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    files_modified: int = 0
    languages: dict[str, int] = Field(default_factory=dict)
    git_commits: int = 0
    first_prompt: str = ""
    tool_errors: int = 0
    uses_task_agent: bool = False
    uses_mcp: bool = False
    # From facets
    goal: str = ""
    outcome: str = ""
    summary: str = ""
    session_type: str = ""
    helpfulness: str = ""
    friction_counts: dict[str, int] = Field(default_factory=dict)
    friction_detail: str = ""
    goal_categories: dict[str, int] = Field(default_factory=dict)


class Recommendation(BaseModel):
    """An optimization recommendation."""

    category: str  # "model", "context", "veille", "feature"
    title: str
    description: str
    priority: str = "medium"  # "high", "medium", "low"


# --- App Config ---


class DashboardConfig(BaseModel):
    """Dashboard server configuration."""

    port: int = 8741
    host: str = "127.0.0.1"
    hidden_projects: list[str] = Field(default_factory=list)


class SyncConfig(BaseModel):
    """Sync configuration."""

    include: list[str] = Field(
        default_factory=lambda: [
            "CLAUDE.md",
            "settings.json",
            "skills/",
            "agents/",
            "commands/",
        ]
    )
    exclude: list[str] = Field(
        default_factory=lambda: [
            "settings.local.json",
            "sessions/",
            "history.jsonl",
            "cache/",
            "debug/",
            "telemetry/",
            "tasks/",
            "todos/",
            "paste-cache/",
            "shell-snapshots/",
            "file-history/",
            "session-env/",
            "stats-cache.json",
            "usage-data/",
            "plans/",
            "backups/",
            "downloads/",
            "ide/",
            "statsig/",
            "policy-limits.json",
        ]
    )
    scan_dirs: list[str] = Field(default_factory=lambda: ["~/Documents/dev"])


class AppConfig(BaseModel):
    """Root application configuration."""

    claude_home: Path = Field(default_factory=lambda: Path.home() / ".claude")
    sync_repo: Path = Field(default_factory=lambda: Path.home() / "Documents/dev/claude-profile-sync")
    sync: SyncConfig = Field(default_factory=SyncConfig)
    profiles: list[ProfileConfig] = Field(default_factory=list)
    active_profile: str | None = None
    veille: VeilleConfig = Field(default_factory=VeilleConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    github_token_env: str = "GITHUB_TOKEN"


class AppState(BaseModel):
    """Runtime state persisted between runs."""

    active_profile: str | None = None
    last_sync: datetime | None = None
    last_veille_check: datetime | None = None
    hidden_projects: list[str] = Field(default_factory=list)
