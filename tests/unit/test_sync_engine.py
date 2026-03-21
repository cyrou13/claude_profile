"""Tests for sync engine."""

from __future__ import annotations

from pathlib import Path

from claude_profile.models import AppConfig, SyncConfig
from claude_profile.sync.engine import get_sync_status, push_to_repo, pull_from_repo
from claude_profile.sync.manifest import load_manifest


class TestSyncStatus:
    def test_status_shows_all_files_when_no_manifest(
        self, sample_config: AppConfig
    ) -> None:
        """First sync: everything shows as added."""
        status = get_sync_status(sample_config)
        assert status.has_changes
        assert len(status.added) > 0
        assert "CLAUDE.md" in status.added

    def test_status_clean_after_push(self, sample_config: AppConfig) -> None:
        """After pushing, status should show no changes."""
        push_to_repo(sample_config)
        status = get_sync_status(sample_config)
        assert not status.has_changes


class TestPush:
    def test_push_creates_shared_dir(self, sample_config: AppConfig) -> None:
        """Push creates shared/ directory with synced files."""
        push_to_repo(sample_config)
        shared = sample_config.sync_repo / "shared"
        assert shared.exists()
        assert (shared / "CLAUDE.md").exists()
        assert (shared / "settings.json").exists()

    def test_push_copies_skills(self, sample_config: AppConfig) -> None:
        """Push copies skill directories."""
        push_to_repo(sample_config)
        shared = sample_config.sync_repo / "shared"
        assert (shared / "skills" / "debug" / "SKILL.md").exists()
        assert (shared / "skills" / "tdd" / "SKILL.md").exists()
        assert (shared / "skills" / "tdd" / "scripts" / "run.py").exists()

    def test_push_copies_agents(self, sample_config: AppConfig) -> None:
        """Push copies agent files."""
        push_to_repo(sample_config)
        shared = sample_config.sync_repo / "shared"
        assert (shared / "agents" / "python-pro.md").exists()
        assert (shared / "agents" / "debugger.md").exists()

    def test_push_copies_commands(self, sample_config: AppConfig) -> None:
        """Push copies command files."""
        push_to_repo(sample_config)
        shared = sample_config.sync_repo / "shared"
        assert (shared / "commands" / "adr.md").exists()

    def test_push_excludes_settings_local(self, sample_config: AppConfig) -> None:
        """settings.local.json must never be synced."""
        push_to_repo(sample_config)
        shared = sample_config.sync_repo / "shared"
        assert not (shared / "settings.local.json").exists()

    def test_push_excludes_sessions_and_cache(self, sample_config: AppConfig) -> None:
        """Excluded directories are not synced."""
        push_to_repo(sample_config)
        shared = sample_config.sync_repo / "shared"
        assert not (shared / "sessions").exists()
        assert not (shared / "cache").exists()
        assert not (shared / "debug").exists()

    def test_push_creates_manifest(self, sample_config: AppConfig) -> None:
        """Push creates manifest.json."""
        push_to_repo(sample_config)
        manifest_path = sample_config.sync_repo / "manifest.json"
        assert manifest_path.exists()
        manifest = load_manifest(manifest_path)
        assert manifest is not None
        assert "CLAUDE.md" in manifest.files
        assert manifest.machine_id != ""

    def test_push_creates_plugins_list(self, sample_config: AppConfig) -> None:
        """Push extracts plugin list."""
        push_to_repo(sample_config)
        plugins = sample_config.sync_repo / "plugins-list.json"
        assert plugins.exists()
        import json
        data = json.loads(plugins.read_text())
        assert "context7@official" in data

    def test_push_detects_modifications(self, sample_config: AppConfig) -> None:
        """After modifying a file, push detects the change."""
        push_to_repo(sample_config)

        # Modify CLAUDE.md
        claude_md = sample_config.claude_home / "CLAUDE.md"
        claude_md.write_text("# Updated instructions\n")

        status = get_sync_status(sample_config)
        assert "CLAUDE.md" in status.modified

    def test_push_detects_new_agent(self, sample_config: AppConfig) -> None:
        """Adding a new agent shows as added."""
        push_to_repo(sample_config)

        # Add new agent
        new_agent = sample_config.claude_home / "agents" / "new-agent.md"
        new_agent.write_text("---\nname: new-agent\n---\n# New Agent\n")

        status = get_sync_status(sample_config)
        assert "agents/new-agent.md" in status.added


class TestPull:
    def test_pull_applies_remote_changes(self, sample_config: AppConfig) -> None:
        """Pulling applies changes from repo to local."""
        # First push
        push_to_repo(sample_config)

        # Simulate remote change by modifying repo directly
        shared_claude_md = sample_config.sync_repo / "shared" / "CLAUDE.md"
        shared_claude_md.write_text("# Remote update\n")

        # Pull
        pull_from_repo(sample_config)

        local_claude_md = sample_config.claude_home / "CLAUDE.md"
        assert local_claude_md.read_text() == "# Remote update\n"

    def test_pull_adds_new_files(self, sample_config: AppConfig) -> None:
        """Pull adds files that exist in repo but not locally."""
        push_to_repo(sample_config)

        # Add file to repo
        new_cmd = sample_config.sync_repo / "shared" / "commands" / "new-cmd.md"
        new_cmd.write_text("# New command from remote\n")

        # Update manifest
        from claude_profile.sync.manifest import build_manifest, save_manifest
        repo_files: dict[str, Path] = {}
        shared = sample_config.sync_repo / "shared"
        for fp in shared.rglob("*"):
            if fp.is_file():
                repo_files[str(fp.relative_to(shared))] = fp
        manifest = build_manifest(repo_files)
        save_manifest(manifest, sample_config.sync_repo / "manifest.json")

        pull_from_repo(sample_config)

        local_cmd = sample_config.claude_home / "commands" / "new-cmd.md"
        assert local_cmd.exists()
        assert local_cmd.read_text() == "# New command from remote\n"
