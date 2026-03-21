"""Shared test fixtures for claude-profile."""

from __future__ import annotations

from pathlib import Path

import pytest

from claude_profile.models import AppConfig, ProfileConfig, SyncConfig, VeilleConfig


@pytest.fixture
def tmp_claude_home(tmp_path: Path) -> Path:
    """Create a fake ~/.claude/ structure for testing."""
    home = tmp_path / ".claude"
    home.mkdir()

    # CLAUDE.md
    (home / "CLAUDE.md").write_text("# Global Instructions\n\nTest CLAUDE.md content.\n")

    # settings.json
    (home / "settings.json").write_text('{"model": "Opus", "language": "French"}\n')

    # settings.local.json (should NOT be synced)
    (home / "settings.local.json").write_text('{"env": {"DEBUG": "1"}}\n')

    # skills/
    skills = home / "skills"
    skill1 = skills / "debug"
    skill1.mkdir(parents=True)
    (skill1 / "SKILL.md").write_text("---\nname: debug\n---\n# Debug Skill\n")

    skill2 = skills / "tdd"
    skill2.mkdir()
    (skill2 / "SKILL.md").write_text("---\nname: tdd\n---\n# TDD Skill\n")
    scripts = skill2 / "scripts"
    scripts.mkdir()
    (scripts / "run.py").write_text("print('hello')\n")

    # agents/
    agents = home / "agents"
    agents.mkdir()
    (agents / "python-pro.md").write_text("---\nname: python-pro\n---\n# Python Pro Agent\n")
    (agents / "debugger.md").write_text("---\nname: debugger\n---\n# Debugger Agent\n")

    # commands/
    commands = home / "commands"
    commands.mkdir()
    (commands / "adr.md").write_text("---\ndescription: Create ADR\n---\n# ADR Command\n")

    # plugins/
    plugins = home / "plugins"
    plugins.mkdir()
    (plugins / "installed_plugins.json").write_text(
        '{"version": 2, "plugins": {"context7@official": [{"version": "abc123"}]}}\n'
    )

    # projects/
    projects = home / "projects"

    # macOS-style project
    proj_mac = projects / "-Users-cyril-Documents-dev-jarvis"
    proj_mac.mkdir(parents=True)
    memory = proj_mac / "memory"
    memory.mkdir()
    (memory / "MEMORY.md").write_text("# Jarvis memory\n")

    # Linux-style project
    proj_linux = projects / "-home-cyril-dev-cortex"
    proj_linux.mkdir()

    # Excluded dirs
    for excluded in ["sessions", "cache", "debug", "telemetry", "tasks"]:
        (home / excluded).mkdir()
        (home / excluded / "dummy.txt").write_text("excluded\n")

    (home / "history.jsonl").write_text("{}\n")

    return home


@pytest.fixture
def tmp_sync_repo(tmp_path: Path) -> Path:
    """Create a temporary sync repository directory."""
    repo = tmp_path / "sync-repo"
    repo.mkdir()
    return repo


@pytest.fixture
def sample_config(tmp_claude_home: Path, tmp_sync_repo: Path) -> AppConfig:
    """Create a sample AppConfig for testing."""
    return AppConfig(
        claude_home=tmp_claude_home,
        sync_repo=tmp_sync_repo,
        sync=SyncConfig(scan_dirs=[str(tmp_claude_home.parent / "dev")]),
        profiles=[
            ProfileConfig(
                name="avicenna",
                description="Professional",
                projects=["cortex", "aria", "reportia"],
                claude_md_overlay="## Context: Avicenna\n- Medical device focus\n",
            ),
            ProfileConfig(
                name="personal",
                description="Personal projects",
                projects=["jarvis", "botflow", "12weeks"],
                claude_md_overlay="## Context: Personal\n- Side projects\n",
            ),
        ],
        veille=VeilleConfig(),
    )
