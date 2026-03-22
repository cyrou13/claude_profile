"""Integration tests for dashboard API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from claude_profile.dashboard.app import create_app
from claude_profile.models import AppConfig, ProfileConfig, SyncConfig, VeilleConfig


@pytest.fixture
def dashboard_client(tmp_path: Path) -> TestClient:
    """Create a test client with a fake ~/.claude/ structure."""
    claude_home = tmp_path / ".claude"
    claude_home.mkdir()

    # Stats cache
    stats = {
        "version": 2,
        "dailyActivity": [
            {"date": "2026-03-01", "messageCount": 500, "sessionCount": 5, "toolCallCount": 100},
        ],
        "dailyModelTokens": [
            {"date": "2026-03-01", "tokensByModel": {"claude-opus-4-6": 8000}},
        ],
    }
    (claude_home / "stats-cache.json").write_text(json.dumps(stats))

    # Session meta + facets
    meta_dir = claude_home / "usage-data" / "session-meta"
    facets_dir = claude_home / "usage-data" / "facets"
    meta_dir.mkdir(parents=True)
    facets_dir.mkdir(parents=True)

    meta = {
        "session_id": "test-session",
        "project_path": "/dev/jarvis",
        "start_time": "2026-03-01T10:00:00Z",
        "duration_minutes": 30,
        "user_message_count": 3,
        "assistant_message_count": 15,
        "tool_counts": {"Read": 5},
        "input_tokens": 50,
        "output_tokens": 300,
        "lines_added": 20,
        "lines_removed": 5,
        "files_modified": 2,
    }
    (meta_dir / "test-session.json").write_text(json.dumps(meta))

    facet = {
        "session_id": "test-session",
        "underlying_goal": "Test goal",
        "outcome": "fully_achieved",
        "brief_summary": "Test summary",
    }
    (facets_dir / "test-session.json").write_text(json.dumps(facet))

    config = AppConfig(
        claude_home=claude_home,
        sync_repo=tmp_path / "sync",
        profiles=[
            ProfileConfig(name="test", projects=["jarvis"]),
        ],
        veille=VeilleConfig(),
    )

    app = create_app(config)
    return TestClient(app)


def test_index_page(dashboard_client: TestClient) -> None:
    """Dashboard index returns HTML."""
    resp = dashboard_client.get("/")
    assert resp.status_code == 200
    assert "Claude Profile" in resp.text


def test_usage_summary(dashboard_client: TestClient) -> None:
    """Usage summary returns HTML with stats."""
    resp = dashboard_client.get("/api/usage/summary")
    assert resp.status_code == 200
    assert "500" in resp.text  # 500 messages
    assert "Messages" in resp.text


def test_sessions_list(dashboard_client: TestClient) -> None:
    """Sessions returns HTML table with session data."""
    resp = dashboard_client.get("/api/usage/sessions")
    assert resp.status_code == 200
    assert "jarvis" in resp.text
    assert "Reussi" in resp.text


def test_sessions_filter_by_profile(dashboard_client: TestClient) -> None:
    """Sessions can be filtered by profile."""
    resp = dashboard_client.get("/api/usage/sessions?profile=test")
    assert resp.status_code == 200
    assert "jarvis" in resp.text

    resp = dashboard_client.get("/api/usage/sessions?profile=nonexistent")
    assert resp.status_code == 200
    # Unknown profile: no filter applied, returns all
    assert "jarvis" in resp.text


def test_profiles_usage(dashboard_client: TestClient) -> None:
    """Profiles returns HTML cards."""
    resp = dashboard_client.get("/api/usage/profiles")
    assert resp.status_code == 200
    assert "test" in resp.text
    assert "1" in resp.text  # 1 session


def test_recommendations(dashboard_client: TestClient) -> None:
    """Recommendations returns HTML."""
    resp = dashboard_client.get("/api/recommendations/")
    assert resp.status_code == 200
    # Should return HTML (either recommendations or "aucune")
    assert "<" in resp.text


def test_veille_releases(dashboard_client: TestClient) -> None:
    """Veille releases endpoint returns HTML."""
    resp = dashboard_client.get("/api/veille/releases")
    assert resp.status_code == 200
    # Returns either cached data or empty-cache placeholder
    assert "<" in resp.text
