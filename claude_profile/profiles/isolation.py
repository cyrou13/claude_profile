"""Project-to-profile mapping and filtering."""

from __future__ import annotations

from pathlib import Path

from claude_profile.models import AppConfig, ProfileConfig
from claude_profile.utils.claude_paths import list_projects


def get_profile_by_name(config: AppConfig, name: str) -> ProfileConfig | None:
    """Find a profile by name."""
    return next((p for p in config.profiles if p.name == name), None)


def get_profile_for_project(config: AppConfig, project_name: str) -> ProfileConfig | None:
    """Find which profile a project belongs to."""
    for profile in config.profiles:
        if project_name in profile.projects:
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
    assigned = set()
    for profile in config.profiles:
        assigned.update(profile.projects)

    return {
        name: path
        for name, path in all_projects.items()
        if name not in assigned
    }
