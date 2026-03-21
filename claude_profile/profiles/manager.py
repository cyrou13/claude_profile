"""Profile management: activate, deactivate, list."""

from __future__ import annotations

from claude_profile.models import AppConfig
from claude_profile.profiles.isolation import get_profile_by_name
from claude_profile.profiles.overlay import (
    compose_claude_md,
    read_base_claude_md,
    write_claude_md,
)


def activate_profile(config: AppConfig, profile_name: str) -> None:
    """Activate a profile by applying its CLAUDE.md overlay.

    Reads the base CLAUDE.md (stripping any previous overlay),
    composes it with the new profile's overlay, and writes it back.
    """
    profile = get_profile_by_name(config, profile_name)
    if not profile:
        msg = f"Profile '{profile_name}' not found"
        raise ValueError(msg)

    base = read_base_claude_md(config.claude_home)
    composed = compose_claude_md(base, profile.claude_md_overlay)
    write_claude_md(config.claude_home, composed)


def deactivate_profile(config: AppConfig) -> None:
    """Remove any profile overlay from CLAUDE.md."""
    base = read_base_claude_md(config.claude_home)
    write_claude_md(config.claude_home, base)
