"""Tests for profile management."""

from __future__ import annotations

from pathlib import Path

from claude_profile.models import AppConfig
from claude_profile.profiles.isolation import (
    get_profile_by_name,
    get_profile_for_project,
    list_profile_projects,
    list_unassigned_projects,
)
from claude_profile.profiles.manager import activate_profile, deactivate_profile


class TestIsolation:
    def test_get_profile_by_name(self, sample_config: AppConfig) -> None:
        profile = get_profile_by_name(sample_config, "avicenna")
        assert profile is not None
        assert profile.name == "avicenna"

    def test_get_profile_by_name_missing(self, sample_config: AppConfig) -> None:
        assert get_profile_by_name(sample_config, "nope") is None

    def test_get_profile_for_project(self, sample_config: AppConfig) -> None:
        profile = get_profile_for_project(sample_config, "cortex")
        assert profile is not None
        assert profile.name == "avicenna"

    def test_get_profile_for_project_personal(self, sample_config: AppConfig) -> None:
        profile = get_profile_for_project(sample_config, "jarvis")
        assert profile is not None
        assert profile.name == "personal"

    def test_get_profile_for_unassigned(self, sample_config: AppConfig) -> None:
        assert get_profile_for_project(sample_config, "random-project") is None

    def test_list_profile_projects(self, sample_config: AppConfig) -> None:
        projects = list_profile_projects(sample_config, "personal")
        assert "jarvis" in projects

    def test_list_unassigned_projects(self, sample_config: AppConfig) -> None:
        unassigned = list_unassigned_projects(sample_config)
        # jarvis and cortex are assigned; any other project dirs are unassigned
        assert "jarvis" not in unassigned
        assert "cortex" not in unassigned


class TestActivateProfile:
    def test_activate_writes_overlay(self, sample_config: AppConfig) -> None:
        activate_profile(sample_config, "avicenna")
        claude_md = sample_config.claude_home / "CLAUDE.md"
        content = claude_md.read_text()
        assert "Avicenna" in content
        assert "Medical device focus" in content
        # Base content preserved
        assert "Global Instructions" in content

    def test_activate_replaces_previous_overlay(self, sample_config: AppConfig) -> None:
        activate_profile(sample_config, "avicenna")
        activate_profile(sample_config, "personal")
        claude_md = sample_config.claude_home / "CLAUDE.md"
        content = claude_md.read_text()
        assert "Side projects" in content
        assert "Avicenna" not in content
        # Only one overlay marker pair
        assert content.count("overlay-start") == 1

    def test_deactivate_removes_overlay(self, sample_config: AppConfig) -> None:
        activate_profile(sample_config, "avicenna")
        deactivate_profile(sample_config)
        claude_md = sample_config.claude_home / "CLAUDE.md"
        content = claude_md.read_text()
        assert "Avicenna" not in content
        assert "overlay-start" not in content
        assert "Global Instructions" in content

    def test_activate_nonexistent_profile_raises(self, sample_config: AppConfig) -> None:
        import pytest
        with pytest.raises(ValueError, match="not found"):
            activate_profile(sample_config, "nonexistent")
