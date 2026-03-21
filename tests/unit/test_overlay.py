"""Tests for CLAUDE.md overlay composition."""

from __future__ import annotations

from claude_profile.profiles.overlay import (
    compose_claude_md,
    has_overlay,
    strip_overlay,
)


def test_compose_adds_overlay() -> None:
    base = "# Base\n\nSome instructions.\n"
    overlay = "## Profile: Test\n- Rule 1\n"
    result = compose_claude_md(base, overlay)
    assert "# Base" in result
    assert "## Profile: Test" in result
    assert "overlay-start" in result
    assert "overlay-end" in result


def test_compose_empty_overlay_returns_base() -> None:
    base = "# Base content\n"
    result = compose_claude_md(base, "")
    assert result == base


def test_compose_replaces_existing_overlay() -> None:
    base = "# Base\n"
    first = compose_claude_md(base, "## First overlay")
    second = compose_claude_md(first, "## Second overlay")
    assert "First overlay" not in second
    assert "Second overlay" in second
    assert second.count("overlay-start") == 1


def test_strip_overlay() -> None:
    base = "# Base\n"
    composed = compose_claude_md(base, "## Overlay content")
    stripped = strip_overlay(composed)
    assert "Overlay content" not in stripped
    assert "# Base" in stripped


def test_strip_no_overlay() -> None:
    content = "# Just base content\n"
    assert strip_overlay(content) == content


def test_has_overlay() -> None:
    base = "# Base\n"
    assert not has_overlay(base)
    composed = compose_claude_md(base, "## Test")
    assert has_overlay(composed)
