"""CLAUDE.md composition: base + profile overlay."""

from __future__ import annotations

from pathlib import Path

OVERLAY_MARKER = "\n\n---\n\n<!-- claude-profile:overlay-start -->\n"
OVERLAY_END_MARKER = "\n<!-- claude-profile:overlay-end -->\n"


def compose_claude_md(base_content: str, overlay_content: str) -> str:
    """Compose final CLAUDE.md by appending profile overlay to base.

    If the base already contains a previous overlay (between markers),
    it is replaced. Otherwise, the overlay is appended.
    """
    # Strip any existing overlay
    clean_base = strip_overlay(base_content)

    if not overlay_content.strip():
        return clean_base

    return clean_base + OVERLAY_MARKER + overlay_content.strip() + OVERLAY_END_MARKER


def strip_overlay(content: str) -> str:
    """Remove any existing profile overlay from CLAUDE.md content."""
    start_idx = content.find(OVERLAY_MARKER)
    if start_idx == -1:
        return content

    end_idx = content.find(OVERLAY_END_MARKER, start_idx)
    if end_idx == -1:
        # Malformed: just cut from start marker
        return content[:start_idx]

    return content[:start_idx] + content[end_idx + len(OVERLAY_END_MARKER):]


def has_overlay(content: str) -> bool:
    """Check if content contains a profile overlay."""
    return OVERLAY_MARKER in content


def read_base_claude_md(claude_home: Path) -> str:
    """Read the current CLAUDE.md, stripping any existing overlay."""
    claude_md = claude_home / "CLAUDE.md"
    if not claude_md.exists():
        return ""
    return strip_overlay(claude_md.read_text())


def write_claude_md(claude_home: Path, content: str) -> None:
    """Write composed CLAUDE.md to disk."""
    claude_md = claude_home / "CLAUDE.md"
    claude_md.write_text(content)
