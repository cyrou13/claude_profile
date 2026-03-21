"""Tests for manifest operations."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from claude_profile.models import FileEntry, SyncManifest
from claude_profile.sync.manifest import (
    build_manifest,
    compute_sha256,
    diff_manifests,
    load_manifest,
    save_manifest,
)


def test_compute_sha256(tmp_path: Path) -> None:
    """SHA-256 is computed correctly."""
    f = tmp_path / "test.txt"
    f.write_text("hello world\n")
    sha = compute_sha256(f)
    assert len(sha) == 64
    assert sha.isalnum()


def test_compute_sha256_deterministic(tmp_path: Path) -> None:
    """Same content produces same hash."""
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("same content")
    f2.write_text("same content")
    assert compute_sha256(f1) == compute_sha256(f2)


def test_build_manifest(tmp_path: Path) -> None:
    """Build manifest from files dict."""
    f1 = tmp_path / "a.txt"
    f1.write_text("hello")
    f2 = tmp_path / "b.txt"
    f2.write_text("world")

    files = {"a.txt": f1, "b.txt": f2}
    manifest = build_manifest(files)

    assert len(manifest.files) == 2
    assert "a.txt" in manifest.files
    assert manifest.files["a.txt"].size == 5
    assert manifest.machine_id != ""


def test_save_and_load_manifest(tmp_path: Path) -> None:
    """Manifest round-trips through JSON."""
    manifest = SyncManifest(
        last_sync=datetime(2026, 3, 21, tzinfo=timezone.utc),
        machine_id="test-machine",
        files={
            "test.md": FileEntry(
                sha256="abc123",
                modified=datetime(2026, 3, 21, tzinfo=timezone.utc),
                size=42,
            )
        },
    )
    path = tmp_path / "manifest.json"
    save_manifest(manifest, path)

    loaded = load_manifest(path)
    assert loaded is not None
    assert loaded.machine_id == "test-machine"
    assert "test.md" in loaded.files
    assert loaded.files["test.md"].sha256 == "abc123"


def test_load_manifest_missing(tmp_path: Path) -> None:
    """Loading nonexistent manifest returns None."""
    assert load_manifest(tmp_path / "nope.json") is None


def test_diff_manifests_all_new() -> None:
    """Diff against None (first sync) = all added."""
    local = SyncManifest(
        last_sync=datetime.now(tz=timezone.utc),
        machine_id="m1",
        files={
            "a.md": FileEntry(sha256="aaa", modified=datetime.now(tz=timezone.utc), size=10),
            "b.md": FileEntry(sha256="bbb", modified=datetime.now(tz=timezone.utc), size=20),
        },
    )
    added, modified, deleted = diff_manifests(local, None)
    assert set(added) == {"a.md", "b.md"}
    assert modified == []
    assert deleted == []


def test_diff_manifests_modified() -> None:
    """Files with different hashes show as modified."""
    now = datetime.now(tz=timezone.utc)
    local = SyncManifest(
        last_sync=now,
        machine_id="m1",
        files={"a.md": FileEntry(sha256="new-hash", modified=now, size=10)},
    )
    remote = SyncManifest(
        last_sync=now,
        machine_id="m1",
        files={"a.md": FileEntry(sha256="old-hash", modified=now, size=10)},
    )
    added, modified, deleted = diff_manifests(local, remote)
    assert added == []
    assert modified == ["a.md"]
    assert deleted == []


def test_diff_manifests_deleted() -> None:
    """Files in remote but not local show as deleted."""
    now = datetime.now(tz=timezone.utc)
    local = SyncManifest(last_sync=now, machine_id="m1", files={})
    remote = SyncManifest(
        last_sync=now,
        machine_id="m1",
        files={"gone.md": FileEntry(sha256="x", modified=now, size=5)},
    )
    added, modified, deleted = diff_manifests(local, remote)
    assert added == []
    assert modified == []
    assert deleted == ["gone.md"]
