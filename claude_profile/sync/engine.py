"""Core sync engine: push, pull, status."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from claude_profile.models import AppConfig, SyncManifest
from claude_profile.sync.filters import collect_syncable_files
from claude_profile.sync.manifest import (
    build_manifest,
    compute_sha256,
    diff_manifests,
    load_manifest,
    save_manifest,
)
from claude_profile.utils import git_ops
from claude_profile.utils.claude_paths import find_project_claude_md, list_projects


@dataclass
class SyncStatus:
    """Result of comparing local state with sync repo."""

    added: list[str]
    modified: list[str]
    deleted: list[str]

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.modified or self.deleted)

    def summary(self) -> str:
        lines: list[str] = []
        if self.added:
            lines.append(f"  + {len(self.added)} added")
            for f in self.added:
                lines.append(f"    + {f}")
        if self.modified:
            lines.append(f"  ~ {len(self.modified)} modified")
            for f in self.modified:
                lines.append(f"    ~ {f}")
        if self.deleted:
            lines.append(f"  - {len(self.deleted)} deleted")
            for f in self.deleted:
                lines.append(f"    - {f}")
        if not lines:
            lines.append("  Everything is in sync.")
        return "\n".join(lines)


def init_sync_repo(config: AppConfig) -> None:
    """Initialize the sync repository structure."""
    repo = config.sync_repo
    repo.mkdir(parents=True, exist_ok=True)

    if not git_ops.is_repo(repo):
        git_ops.init(repo)

    # Create directory structure
    (repo / "shared").mkdir(exist_ok=True)
    (repo / "project-claude-md").mkdir(exist_ok=True)
    (repo / "profiles").mkdir(exist_ok=True)

    # Write .gitignore
    gitignore = repo / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("# Machine-specific files\n*.local\n.DS_Store\n")

    # Do initial push
    push_to_repo(config)


def get_sync_status(config: AppConfig) -> SyncStatus:
    """Compare local ~/.claude/ state with sync repo."""
    local_files = collect_syncable_files(config.claude_home, config.sync)
    local_manifest = build_manifest(local_files)

    manifest_path = config.sync_repo / "manifest.json"
    remote_manifest = load_manifest(manifest_path)

    added, modified, deleted = diff_manifests(local_manifest, remote_manifest)
    return SyncStatus(added=added, modified=modified, deleted=deleted)


def push_to_repo(config: AppConfig) -> SyncStatus:
    """Push local ~/.claude/ changes to the sync repo."""
    repo = config.sync_repo
    shared = repo / "shared"
    shared.mkdir(parents=True, exist_ok=True)

    # Collect and copy syncable files
    local_files = collect_syncable_files(config.claude_home, config.sync)
    local_manifest = build_manifest(local_files)

    manifest_path = repo / "manifest.json"
    remote_manifest = load_manifest(manifest_path)
    added, modified, deleted = diff_manifests(local_manifest, remote_manifest)

    # Copy added and modified files
    for rel_path in added + modified:
        src = local_files[rel_path]
        dst = shared / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # Remove deleted files from repo
    for rel_path in deleted:
        dst = shared / rel_path
        if dst.exists():
            dst.unlink()
            # Clean up empty parent dirs
            _cleanup_empty_parents(dst.parent, shared)

    # Sync project-level CLAUDE.md files
    _sync_project_claude_mds(config, repo / "project-claude-md")

    # Extract plugin list
    _sync_plugin_list(config.claude_home, repo)

    # Sync app config (config.toml) so profiles are shared across machines
    _sync_app_config_push(repo)

    # Save manifest
    save_manifest(local_manifest, manifest_path)

    # Git operations
    if git_ops.is_repo(repo):
        git_ops.add_all(repo)
        git_ops.commit(repo, f"sync: push from {local_manifest.machine_id}")

    return SyncStatus(added=added, modified=modified, deleted=deleted)


def pull_from_repo(config: AppConfig) -> SyncStatus:
    """Pull sync repo changes to local ~/.claude/."""
    repo = config.sync_repo
    shared = repo / "shared"

    if not shared.exists():
        return SyncStatus(added=[], modified=[], deleted=[])

    # Pull from remote if available
    if git_ops.is_repo(repo) and git_ops.has_remote(repo):
        git_ops.pull(repo)

    # Build manifest of what's in the repo
    repo_files: dict[str, Path] = {}
    for file_path in sorted(shared.rglob("*")):
        if file_path.is_file():
            rel = str(file_path.relative_to(shared))
            repo_files[rel] = file_path

    repo_manifest = build_manifest(repo_files)

    # Build manifest of current local state
    local_files = collect_syncable_files(config.claude_home, config.sync)
    local_manifest = build_manifest(local_files)

    # Find what repo has that local doesn't (or differs)
    added, modified, deleted = diff_manifests(repo_manifest, local_manifest)

    # Copy from repo to local
    for rel_path in added + modified:
        src = repo_files[rel_path]
        dst = config.claude_home / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # Note: we don't delete local files that aren't in repo
    # (they might be new local additions not yet pushed)

    # Sync project-level CLAUDE.md files back
    _pull_project_claude_mds(config, repo / "project-claude-md")

    # Sync app config (config.toml) — profiles, veille, dashboard settings
    _sync_app_config_pull(repo)

    # Report plugin differences
    _report_plugin_diff(config.claude_home, repo)

    return SyncStatus(added=added, modified=modified, deleted=[])


def _sync_project_claude_mds(config: AppConfig, target_dir: Path) -> None:
    """Copy project-level CLAUDE.md files to sync repo."""
    target_dir.mkdir(parents=True, exist_ok=True)
    projects = list_projects(config.claude_home)
    scan_dirs = config.sync.scan_dirs

    for project_name in projects:
        claude_md = find_project_claude_md(project_name, scan_dirs)
        if claude_md:
            shutil.copy2(claude_md, target_dir / f"{project_name}.md")


def _pull_project_claude_mds(config: AppConfig, source_dir: Path) -> None:
    """Copy project-level CLAUDE.md files from sync repo to project dirs."""
    if not source_dir.exists():
        return
    scan_dirs = config.sync.scan_dirs

    for md_file in source_dir.iterdir():
        if md_file.suffix == ".md":
            project_name = md_file.stem
            # Find the actual project directory
            for scan_dir in scan_dirs:
                base = Path(scan_dir).expanduser()
                target = base / project_name / "CLAUDE.md"
                if target.parent.exists():
                    shutil.copy2(md_file, target)
                    break


def _sync_plugin_list(claude_home: Path, repo: Path) -> None:
    """Extract plugin names and versions to plugins-list.json."""
    installed = claude_home / "plugins" / "installed_plugins.json"
    if not installed.exists():
        return

    data = json.loads(installed.read_text())
    plugins = data.get("plugins", {})

    # Extract just names and versions (not local paths)
    plugin_list: dict[str, str] = {}
    for name, entries in plugins.items():
        if entries and isinstance(entries, list):
            plugin_list[name] = entries[0].get("version", "unknown")

    (repo / "plugins-list.json").write_text(json.dumps(plugin_list, indent=2))


def _report_plugin_diff(claude_home: Path, repo: Path) -> list[str]:
    """Compare local plugins with repo plugin list. Returns missing plugin names."""
    repo_plugins_file = repo / "plugins-list.json"
    if not repo_plugins_file.exists():
        return []

    repo_plugins = json.loads(repo_plugins_file.read_text())

    local_installed = claude_home / "plugins" / "installed_plugins.json"
    local_plugins: dict[str, str] = {}
    if local_installed.exists():
        data = json.loads(local_installed.read_text())
        for name, entries in data.get("plugins", {}).items():
            if entries and isinstance(entries, list):
                local_plugins[name] = entries[0].get("version", "unknown")

    missing = [name for name in repo_plugins if name not in local_plugins]
    return missing


def _sync_app_config_push(repo: Path) -> None:
    """Copy config.toml into the sync repo so profiles are shared across machines."""
    from claude_profile.config import CONFIG_FILE

    if CONFIG_FILE.exists():
        shutil.copy2(CONFIG_FILE, repo / "config.toml")


def _sync_app_config_pull(repo: Path) -> None:
    """Restore config.toml from sync repo, preserving machine-specific paths."""
    from claude_profile.config import CONFIG_FILE, ensure_config_dir

    repo_config = repo / "config.toml"
    if not repo_config.exists():
        return

    # If local config already exists, merge: keep local paths, take remote profiles/veille/dashboard
    if CONFIG_FILE.exists():
        import tomllib

        with open(repo_config, "rb") as f:
            remote = tomllib.load(f)
        with open(CONFIG_FILE, "rb") as f:
            local = tomllib.load(f)

        # Keep local machine-specific values
        remote_general = remote.get("general", {})
        local_general = local.get("general", {})
        for key in ("claude_home", "sync_repo"):
            if key in local_general:
                remote_general[key] = local_general[key]
        remote["general"] = remote_general

        # Keep local scan_dirs (paths differ between machines)
        if "sync" in local and "scan_dirs" in local["sync"]:
            remote.setdefault("sync", {})["scan_dirs"] = local["sync"]["scan_dirs"]

        # Write merged config using our serializer
        from claude_profile.config import save_config, load_config

        merged_config = load_config(repo_config)
        # Restore local paths
        if "claude_home" in local_general:
            merged_config.claude_home = Path(local_general["claude_home"]).expanduser()
        if "sync_repo" in local_general:
            merged_config.sync_repo = Path(local_general["sync_repo"]).expanduser()
        if "sync" in local and "scan_dirs" in local["sync"]:
            merged_config.sync.scan_dirs = [
                str(Path(d).expanduser()) for d in local["sync"]["scan_dirs"]
            ]

        save_config(merged_config)
    else:
        # No local config — just copy it
        ensure_config_dir()
        shutil.copy2(repo_config, CONFIG_FILE)


def _cleanup_empty_parents(directory: Path, stop_at: Path) -> None:
    """Remove empty parent directories up to stop_at."""
    current = directory
    while current != stop_at and current.exists():
        if any(current.iterdir()):
            break
        current.rmdir()
        current = current.parent
