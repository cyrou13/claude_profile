"""Tests for stats parser."""

from __future__ import annotations

import json
from pathlib import Path

from claude_profile.dashboard.services.stats_parser import (
    filter_sessions_by_profile,
    parse_sessions,
    parse_stats_cache,
)
from claude_profile.models import SessionSummary


def test_parse_stats_cache_missing(tmp_path: Path) -> None:
    """Returns empty data when stats file doesn't exist."""
    result = parse_stats_cache(tmp_path)
    assert result["daily_activity"] == []
    assert result["totals"] == {}


def test_parse_stats_cache(tmp_path: Path) -> None:
    """Parses real stats-cache.json format."""
    stats = {
        "version": 2,
        "dailyActivity": [
            {"date": "2026-03-01", "messageCount": 100, "sessionCount": 2, "toolCallCount": 50},
            {"date": "2026-03-02", "messageCount": 200, "sessionCount": 3, "toolCallCount": 80},
        ],
        "dailyModelTokens": [
            {"date": "2026-03-01", "tokensByModel": {"claude-opus-4-6": 5000}},
            {"date": "2026-03-02", "tokensByModel": {"claude-opus-4-6": 3000, "claude-sonnet-4-6": 1000}},
        ],
    }
    (tmp_path / "stats-cache.json").write_text(json.dumps(stats))

    result = parse_stats_cache(tmp_path)
    assert len(result["daily_activity"]) == 2
    assert result["totals"]["messages"] == 300
    assert result["totals"]["sessions"] == 5
    assert len(result["model_usage"]) == 2


def test_parse_sessions(tmp_path: Path) -> None:
    """Parses session-meta and facets files."""
    meta_dir = tmp_path / "usage-data" / "session-meta"
    facets_dir = tmp_path / "usage-data" / "facets"
    meta_dir.mkdir(parents=True)
    facets_dir.mkdir(parents=True)

    session_id = "abc-123"
    meta = {
        "session_id": session_id,
        "project_path": "/home/user/dev/jarvis",
        "start_time": "2026-03-01T10:00:00Z",
        "duration_minutes": 45,
        "user_message_count": 5,
        "assistant_message_count": 20,
        "tool_counts": {"Read": 3, "Edit": 2},
        "input_tokens": 100,
        "output_tokens": 500,
        "lines_added": 50,
        "lines_removed": 10,
        "files_modified": 3,
    }
    (meta_dir / f"{session_id}.json").write_text(json.dumps(meta))

    facet = {
        "session_id": session_id,
        "underlying_goal": "Implement feature X",
        "outcome": "fully_achieved",
        "brief_summary": "Implemented feature X across 3 files.",
    }
    (facets_dir / f"{session_id}.json").write_text(json.dumps(facet))

    sessions = parse_sessions(tmp_path)
    assert len(sessions) == 1
    s = sessions[0]
    assert s.project_name == "jarvis"
    assert s.duration_minutes == 45
    assert s.goal == "Implement feature X"
    assert s.outcome == "fully_achieved"


def test_filter_sessions_by_profile() -> None:
    """Filters sessions by profile project list."""
    sessions = [
        SessionSummary(session_id="1", project_name="jarvis"),
        SessionSummary(session_id="2", project_name="cortex"),
        SessionSummary(session_id="3", project_name="jarvis"),
    ]
    filtered = filter_sessions_by_profile(sessions, ["jarvis"])
    assert len(filtered) == 2
    assert all(s.project_name == "jarvis" for s in filtered)
