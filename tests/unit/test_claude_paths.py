"""Tests for cross-platform path utilities."""

from __future__ import annotations

from pathlib import Path

from claude_profile.utils.claude_paths import (
    find_project_dir,
    list_projects,
    normalize_project_name,
    project_memory_dir,
)


class TestNormalizeProjectName:
    def test_macos_path(self) -> None:
        assert normalize_project_name("-Users-cyril-Documents-dev-jarvis") == "jarvis"

    def test_linux_path(self) -> None:
        assert normalize_project_name("-home-cyril-dev-jarvis") == "jarvis"

    def test_nested_project(self) -> None:
        assert normalize_project_name("-Users-cyril-Documents-dev-cortex") == "cortex"

    def test_empty_string(self) -> None:
        assert normalize_project_name("") == ""

    def test_single_component(self) -> None:
        assert normalize_project_name("-simple") == "simple"

    def test_hyphenated_project_name(self) -> None:
        result = normalize_project_name("-Users-cyril-Documents-dev-cortex-clinical-affairs")
        assert result == "cortex-clinical-affairs"

    def test_hyphenated_project_with_docker(self) -> None:
        result = normalize_project_name("-Users-cyril-Documents-dev-cortex-clinical-affairs-docker")
        assert result == "cortex-clinical-affairs-docker"

    def test_linux_hyphenated_project(self) -> None:
        result = normalize_project_name("-home-ubuntu-dev-my-cool-app")
        assert result == "my-cool-app"

    def test_underscore_project(self) -> None:
        result = normalize_project_name("-Users-cyril-Documents-dev-claude_profile")
        assert result == "claude_profile"


class TestListProjects:
    def test_list_projects(self, tmp_claude_home: Path) -> None:
        projects = list_projects(tmp_claude_home)
        assert "jarvis" in projects
        assert "cortex" in projects

    def test_empty_when_no_projects_dir(self, tmp_path: Path) -> None:
        projects = list_projects(tmp_path / "nonexistent")
        assert projects == {}


class TestFindProjectDir:
    def test_find_existing(self, tmp_claude_home: Path) -> None:
        result = find_project_dir("jarvis", tmp_claude_home)
        assert result is not None
        assert result.name.endswith("jarvis")

    def test_find_nonexistent(self, tmp_claude_home: Path) -> None:
        result = find_project_dir("nonexistent", tmp_claude_home)
        assert result is None


class TestProjectMemoryDir:
    def test_find_memory(self, tmp_claude_home: Path) -> None:
        result = project_memory_dir("jarvis", tmp_claude_home)
        assert result is not None
        assert result.name == "memory"

    def test_no_memory_dir(self, tmp_claude_home: Path) -> None:
        result = project_memory_dir("cortex", tmp_claude_home)
        assert result is None
