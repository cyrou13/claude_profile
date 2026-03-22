"""Cross-platform path resolution for Claude Code directories."""

from __future__ import annotations

from pathlib import Path


def claude_home() -> Path:
    """Return the Claude Code home directory."""
    return Path.home() / ".claude"


def projects_dir(home: Path | None = None) -> Path:
    """Return the projects directory."""
    return (home or claude_home()) / "projects"


def normalize_project_name(encoded_dir_name: str) -> str:
    """Extract the project name from an encoded project directory name.

    Claude Code stores project dirs as path-encoded names:
      macOS:  -Users-cyril-Documents-dev-jarvis
      Linux:  -home-cyril-dev-jarvis

    The last path component is the project name, but project names
    can themselves contain hyphens (e.g. cortex-clinical-affairs).

    Strategy: strip the known path prefix up to the dev/projects dir,
    then everything remaining is the project name.
    """
    # Known path prefixes that precede the actual project name.
    # We try to match the longest prefix first.
    # Pattern: -Users-<user>-Documents-dev- or -home-<user>-dev- etc.
    import re

    # Match common path patterns: everything up to a known dev directory
    # macOS: -Users-<user>-Documents-dev-<project>
    # Linux: -home-<user>-dev-<project> or -home-<user>-projects-<project>
    match = re.match(
        r"^-(?:Users|home)-[^-]+-(?:Documents-)?(?:dev|projects|code|src|repos|workspace)-",
        encoded_dir_name,
    )
    if match:
        project_part = encoded_dir_name[match.end():]
        if project_part:
            return project_part

    # Fallback for paths like -Users-cyril (no project component)
    parts = [p for p in encoded_dir_name.split("-") if p]
    if not parts:
        return encoded_dir_name
    return parts[-1]


def project_memory_dir(project_name: str, home: Path | None = None) -> Path | None:
    """Find the memory directory for a project by normalized name.

    Searches all project dirs for one whose normalized name matches.
    Returns None if not found.
    """
    pdir = projects_dir(home)
    if not pdir.exists():
        return None
    for entry in pdir.iterdir():
        if entry.is_dir() and normalize_project_name(entry.name) == project_name:
            memory = entry / "memory"
            if memory.exists():
                return memory
    return None


def find_project_dir(project_name: str, home: Path | None = None) -> Path | None:
    """Find a project directory by normalized name."""
    pdir = projects_dir(home)
    if not pdir.exists():
        return None
    for entry in pdir.iterdir():
        if entry.is_dir() and normalize_project_name(entry.name) == project_name:
            return entry
    return None


def list_projects(home: Path | None = None) -> dict[str, Path]:
    """List all projects as {normalized_name: directory_path}."""
    pdir = projects_dir(home)
    if not pdir.exists():
        return {}
    result: dict[str, Path] = {}
    for entry in sorted(pdir.iterdir()):
        if entry.is_dir():
            name = normalize_project_name(entry.name)
            result[name] = entry
    return result


def find_project_claude_md(project_name: str, scan_dirs: list[str]) -> Path | None:
    """Find a project-level CLAUDE.md by scanning development directories.

    Looks for ~/Documents/dev/<project_name>/CLAUDE.md etc.
    """
    for scan_dir in scan_dirs:
        base = Path(scan_dir).expanduser()
        candidate = base / project_name / "CLAUDE.md"
        if candidate.exists():
            return candidate
    return None
