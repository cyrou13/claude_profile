"""Configuration loading and validation."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from claude_profile.models import AppConfig, AppState

CONFIG_DIR = Path.home() / ".config" / "claude-profile"
CONFIG_FILE = CONFIG_DIR / "config.toml"
STATE_FILE = CONFIG_DIR / "state.json"


def ensure_config_dir() -> Path:
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load application config from TOML file.

    Falls back to defaults if file doesn't exist.
    The TOML uses [general] for top-level fields; we flatten before validation.
    """
    path = config_path or CONFIG_FILE
    if path.exists():
        with open(path, "rb") as f:
            data = tomllib.load(f)
        # Flatten [general] section into root
        general = data.pop("general", {})
        data.update(general)
        # Expand ~ in path fields
        for key in ("claude_home", "sync_repo"):
            if key in data and isinstance(data[key], str):
                data[key] = str(Path(data[key]).expanduser())
        config = AppConfig.model_validate(data)
        # Expand ~ in scan_dirs
        if config.sync.scan_dirs:
            config.sync.scan_dirs = [
                str(Path(d).expanduser()) for d in config.sync.scan_dirs
            ]
        return config
    return AppConfig()


def save_config(config: AppConfig, config_path: Path | None = None) -> None:
    """Save application config to TOML file."""
    path = config_path or CONFIG_FILE
    ensure_config_dir()
    # Manual TOML serialization (no tomli-w dependency needed for simple structure)
    lines = _config_to_toml(config)
    path.write_text(lines)


def load_state() -> AppState:
    """Load application state."""
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text())
        return AppState.model_validate(data)
    return AppState()


def save_state(state: AppState) -> None:
    """Save application state."""
    ensure_config_dir()
    STATE_FILE.write_text(state.model_dump_json(indent=2))


def _config_to_toml(config: AppConfig) -> str:
    """Serialize AppConfig to TOML string."""
    lines: list[str] = []

    lines.append("[general]")
    lines.append(f'claude_home = "{config.claude_home}"')
    lines.append(f'sync_repo = "{config.sync_repo}"')
    lines.append(f'github_token_env = "{config.github_token_env}"')
    lines.append("")

    lines.append("[sync]")
    lines.append(f"include = {_toml_list(config.sync.include)}")
    lines.append(f"exclude = {_toml_list(config.sync.exclude)}")
    lines.append(f"scan_dirs = {_toml_list(config.sync.scan_dirs)}")
    lines.append("")

    lines.append("[veille]")
    lines.append(f"check_interval_hours = {config.veille.check_interval_hours}")
    lines.append(f"github_repos = {_toml_list(config.veille.github_repos)}")
    lines.append(f"rss_feeds = {_toml_list(config.veille.rss_feeds)}")
    lines.append("")

    lines.append("[dashboard]")
    lines.append(f"port = {config.dashboard.port}")
    lines.append(f'host = "{config.dashboard.host}"')
    lines.append("")

    for profile in config.profiles:
        lines.append("[[profiles]]")
        lines.append(f'name = "{profile.name}"')
        lines.append(f'description = "{profile.description}"')
        lines.append(f"projects = {_toml_list(profile.projects)}")
        if profile.claude_md_overlay:
            lines.append(f'claude_md_overlay = """{profile.claude_md_overlay}"""')
        lines.append("")

    return "\n".join(lines) + "\n"


def _toml_list(items: list[str]) -> str:
    """Format a list of strings as TOML array."""
    quoted = [f'"{item}"' for item in items]
    if len(quoted) <= 3:
        return f"[{', '.join(quoted)}]"
    inner = ",\n    ".join(quoted)
    return f"[\n    {inner},\n]"
