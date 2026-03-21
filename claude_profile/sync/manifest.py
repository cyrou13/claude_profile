"""Manifest tracking for sync state."""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from claude_profile.models import FileEntry, SyncManifest


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_manifest(files: dict[str, Path]) -> SyncManifest:
    """Build a manifest from a dict of {relative_path: absolute_path}."""
    entries: dict[str, FileEntry] = {}
    for rel_path, abs_path in files.items():
        stat = abs_path.stat()
        entries[rel_path] = FileEntry(
            sha256=compute_sha256(abs_path),
            modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            size=stat.st_size,
        )

    return SyncManifest(
        last_sync=datetime.now(tz=timezone.utc),
        machine_id=platform.node(),
        files=entries,
    )


def load_manifest(manifest_path: Path) -> SyncManifest | None:
    """Load manifest from JSON file. Returns None if not found."""
    if not manifest_path.exists():
        return None
    data = json.loads(manifest_path.read_text())
    return SyncManifest.model_validate(data)


def save_manifest(manifest: SyncManifest, manifest_path: Path) -> None:
    """Save manifest to JSON file."""
    manifest_path.write_text(manifest.model_dump_json(indent=2))


def diff_manifests(
    local: SyncManifest,
    remote: SyncManifest | None,
) -> tuple[list[str], list[str], list[str]]:
    """Compare local and remote manifests.

    Returns:
        Tuple of (added, modified, deleted) relative paths.
        - added: files in local but not remote
        - modified: files in both but with different checksums
        - deleted: files in remote but not local
    """
    if remote is None:
        return list(local.files.keys()), [], []

    local_keys = set(local.files.keys())
    remote_keys = set(remote.files.keys())

    added = sorted(local_keys - remote_keys)
    deleted = sorted(remote_keys - local_keys)
    modified = sorted(
        k
        for k in local_keys & remote_keys
        if local.files[k].sha256 != remote.files[k].sha256
    )

    return added, modified, deleted
