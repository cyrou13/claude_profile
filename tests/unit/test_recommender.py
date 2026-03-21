"""Tests for recommendation engine."""

from __future__ import annotations

from claude_profile.dashboard.services.recommender import generate_recommendations
from claude_profile.models import SessionSummary


def test_recommends_model_switching() -> None:
    """Recommends model switching when Opus usage > 90%."""
    model_usage = [
        {"model_id": "claude-opus-4-6", "output_tokens": 9500},
        {"model_id": "claude-sonnet-4-6", "output_tokens": 500},
    ]
    recs = generate_recommendations(
        totals={"messages": 1000, "sessions": 10, "days_active": 5},
        model_usage=model_usage,
        sessions=[],
    )
    model_recs = [r for r in recs if r.category == "model"]
    assert len(model_recs) == 1
    assert "Opus" in model_recs[0].title


def test_no_model_rec_when_balanced() -> None:
    """No model recommendation when usage is balanced."""
    model_usage = [
        {"model_id": "claude-opus-4-6", "output_tokens": 5000},
        {"model_id": "claude-sonnet-4-6", "output_tokens": 5000},
    ]
    recs = generate_recommendations(
        totals={"messages": 1000, "sessions": 10, "days_active": 5},
        model_usage=model_usage,
        sessions=[],
    )
    model_recs = [r for r in recs if r.category == "model"]
    assert len(model_recs) == 0


def test_recommends_shorter_sessions() -> None:
    """Recommends shorter sessions when average > 60min."""
    sessions = [
        SessionSummary(session_id="1", duration_minutes=90),
        SessionSummary(session_id="2", duration_minutes=120),
        SessionSummary(session_id="3", duration_minutes=75),
    ]
    recs = generate_recommendations(
        totals={"messages": 1000, "sessions": 3, "days_active": 3},
        model_usage=[],
        sessions=sessions,
    )
    context_recs = [r for r in recs if "longues" in r.title.lower()]
    assert len(context_recs) == 1


def test_recommends_on_high_failure_rate() -> None:
    """Recommends improvements when failure rate > 30%."""
    sessions = [
        SessionSummary(session_id="1", outcome="fully_achieved"),
        SessionSummary(session_id="2", outcome="not_achieved"),
        SessionSummary(session_id="3", outcome="not_achieved"),
    ]
    recs = generate_recommendations(
        totals={"messages": 500, "sessions": 3, "days_active": 3},
        model_usage=[],
        sessions=sessions,
    )
    failure_recs = [r for r in recs if "echec" in r.title.lower()]
    assert len(failure_recs) == 1
