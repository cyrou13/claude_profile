"""Project-to-profile mapping and filtering."""

from __future__ import annotations

from pathlib import Path

from claude_profile.models import AppConfig, ProfileConfig
from claude_profile.utils.claude_paths import list_projects


def get_profile_by_name(config: AppConfig, name: str) -> ProfileConfig | None:
    """Find a profile by name."""
    return next((p for p in config.profiles if p.name == name), None)


def _normalize_name(name: str) -> str:
    """Normalize project name: lowercase, unify - and _."""
    return name.lower().replace("_", "-")


def get_profile_for_project(config: AppConfig, project_name: str) -> ProfileConfig | None:
    """Find which profile a project belongs to."""
    norm = _normalize_name(project_name)
    for profile in config.profiles:
        if norm in {_normalize_name(p) for p in profile.projects}:
            return profile
    return None


def list_profile_projects(
    config: AppConfig, profile_name: str
) -> dict[str, Path]:
    """List projects that belong to a specific profile.

    Returns {normalized_name: directory_path} for matching projects.
    """
    profile = get_profile_by_name(config, profile_name)
    if not profile:
        return {}

    all_projects = list_projects(config.claude_home)
    return {
        name: path
        for name, path in all_projects.items()
        if name in profile.projects
    }


def list_unassigned_projects(config: AppConfig) -> dict[str, Path]:
    """List projects not assigned to any profile."""
    all_projects = list_projects(config.claude_home)
    assigned_normalized = set()
    for profile in config.profiles:
        assigned_normalized.update(_normalize_name(p) for p in profile.projects)

    return {
        name: path
        for name, path in all_projects.items()
        if _normalize_name(name) not in assigned_normalized
    }
