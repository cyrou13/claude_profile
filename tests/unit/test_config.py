"""Tests for config loading and saving."""

from __future__ import annotations

from pathlib import Path

from claude_profile.config import load_config, save_config
from claude_profile.models import AppConfig, ProfileConfig


def test_load_config_defaults_when_missing(tmp_path: Path) -> None:
    """Loading from a non-existent file returns defaults."""
    config = load_config(tmp_path / "nonexistent.toml")
    assert isinstance(config, AppConfig)
    assert config.dashboard.port == 8741
    assert len(config.profiles) == 0


def test_load_config_from_toml(tmp_path: Path) -> None:
    """Load a valid TOML config file."""
    toml_content = """
[general]
claude_home = "/tmp/test-claude"
sync_repo = "/tmp/test-sync"

[sync]
include = ["CLAUDE.md", "skills/"]
exclude = ["cache/"]
scan_dirs = ["~/dev"]

[veille]
check_interval_hours = 12
github_repos = ["anthropics/claude-code"]
rss_feeds = []

[dashboard]
port = 9000
host = "0.0.0.0"

[[profiles]]
name = "test"
description = "Test profile"
projects = ["project-a", "project-b"]
claude_md_overlay = "## Test overlay"
"""
    config_file = tmp_path / "config.toml"
    config_file.write_text(toml_content)

    config = load_config(config_file)
    assert config.claude_home == Path("/tmp/test-claude")
    assert config.sync_repo == Path("/tmp/test-sync")
    assert config.dashboard.port == 9000
    assert config.veille.check_interval_hours == 12
    assert len(config.profiles) == 1
    assert config.profiles[0].name == "test"
    assert config.profiles[0].projects == ["project-a", "project-b"]


def test_save_and_reload_config(tmp_path: Path) -> None:
    """Saving and reloading a config round-trips correctly."""
    config = AppConfig(
        claude_home=Path("/tmp/claude"),
        sync_repo=Path("/tmp/sync"),
        profiles=[
            ProfileConfig(
                name="pro",
                description="Professional",
                projects=["cortex", "aria"],
            ),
        ],
    )
    config_file = tmp_path / "config.toml"
    save_config(config, config_file)

    reloaded = load_config(config_file)
    assert reloaded.claude_home == config.claude_home
    assert reloaded.sync_repo == config.sync_repo
    assert len(reloaded.profiles) == 1
    assert reloaded.profiles[0].name == "pro"
    assert reloaded.profiles[0].projects == ["cortex", "aria"]
