"""Include/exclude filter logic for sync."""

from __future__ import annotations

from pathlib import Path

from claude_profile.models import SyncConfig

# Hard deny-list: these are NEVER synced regardless of config
HARD_EXCLUDE = frozenset({
    "settings.local.json",
    "history.jsonl",
    "policy-limits.json",
    "stats-cache.json",
})

HARD_EXCLUDE_DIRS = frozenset({
    "sessions",
    "cache",
    "debug",
    "telemetry",
    "tasks",
    "todos",
    "paste-cache",
    "shell-snapshots",
    "file-history",
    "session-env",
    "usage-data",
    "plans",
    "backups",
    "downloads",
    "ide",
    "statsig",
    "projects",
    "plugins",
})


def should_sync(relative_path: str, config: SyncConfig) -> bool:
    """Determine if a file/directory should be synced.

    Args:
        relative_path: Path relative to ~/.claude/ (e.g., "skills/debug/SKILL.md")
        config: Sync configuration with include/exclude lists
    """
    parts = Path(relative_path).parts

    # Check hard excludes first
    if parts[0] in HARD_EXCLUDE or parts[0] in HARD_EXCLUDE_DIRS:
        return False

    # Check config exclude list
    for pattern in config.exclude:
        pattern_clean = pattern.rstrip("/")
        if parts[0] == pattern_clean or relative_path == pattern_clean:
            return False

    # Check config include list
    for pattern in config.include:
        pattern_clean = pattern.rstrip("/")
        # Exact file match
        if relative_path == pattern_clean:
            return True
        # Directory prefix match (e.g., "skills/" matches "skills/debug/SKILL.md")
        if pattern.endswith("/") and parts[0] == pattern_clean:
            return True

    return False


def collect_syncable_files(claude_home: Path, config: SyncConfig) -> dict[str, Path]:
    """Walk ~/.claude/ and return all files that should be synced.

    Returns:
        Dict of {relative_path: absolute_path}
    """
    result: dict[str, Path] = {}

    for item in sorted(claude_home.iterdir()):
        rel = item.name

        if item.is_file():
            if should_sync(rel, config):
                result[rel] = item
        elif item.is_dir():
            # Check if this directory prefix is included
            if should_sync(rel + "/dummy", config):
                for file_path in sorted(item.rglob("*")):
                    if file_path.is_file():
                        file_rel = str(file_path.relative_to(claude_home))
                        result[file_rel] = file_path

    return result
