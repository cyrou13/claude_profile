"""Parse Claude Code stats-cache.json and usage-data/ files."""

from __future__ import annotations

import json
from pathlib import Path

from claude_profile.models import DailyActivity, ModelUsage, SessionSummary


def parse_stats_cache(claude_home: Path) -> dict[str, object]:
    """Parse stats-cache.json into a structured summary."""
    stats_file = claude_home / "stats-cache.json"
    if not stats_file.exists():
        return {"daily_activity": [], "model_tokens": [], "totals": {}}

    data = json.loads(stats_file.read_text())

    daily_activity = [
        DailyActivity(
            date=d["date"],
            message_count=d.get("messageCount", 0),
            session_count=d.get("sessionCount", 0),
            tool_call_count=d.get("toolCallCount", 0),
        )
        for d in data.get("dailyActivity", [])
    ]

    # Aggregate model usage across all days
    model_totals: dict[str, int] = {}
    for day in data.get("dailyModelTokens", []):
        for model_id, tokens in day.get("tokensByModel", {}).items():
            model_totals[model_id] = model_totals.get(model_id, 0) + tokens

    model_usage = [
        ModelUsage(model_id=model_id, output_tokens=tokens)
        for model_id, tokens in sorted(model_totals.items(), key=lambda x: -x[1])
    ]

    # Compute totals
    total_messages = sum(d.message_count for d in daily_activity)
    total_sessions = sum(d.session_count for d in daily_activity)
    total_tool_calls = sum(d.tool_call_count for d in daily_activity)
    total_tokens = sum(model_totals.values())

    return {
        "daily_activity": [d.model_dump() for d in daily_activity],
        "model_usage": [m.model_dump() for m in model_usage],
        "totals": {
            "messages": total_messages,
            "sessions": total_sessions,
            "tool_calls": total_tool_calls,
            "tokens": total_tokens,
            "days_active": len(daily_activity),
        },
    }


def parse_sessions(claude_home: Path) -> list[SessionSummary]:
    """Parse all session-meta and facets files."""
    sessions: list[SessionSummary] = []

    meta_dir = claude_home / "usage-data" / "session-meta"
    facets_dir = claude_home / "usage-data" / "facets"

    if not meta_dir.exists():
        return sessions

    for meta_file in sorted(meta_dir.iterdir()):
        if not meta_file.suffix == ".json":
            continue

        meta = json.loads(meta_file.read_text())
        session_id = meta.get("session_id", meta_file.stem)

        # Extract project name from path
        project_path = meta.get("project_path", "")
        project_name = Path(project_path).name if project_path else ""

        # Parse facets if available
        facet_file = facets_dir / meta_file.name
        goal = ""
        outcome = ""
        summary = ""
        session_type = ""
        helpfulness = ""
        friction_counts: dict[str, int] = {}
        friction_detail = ""
        goal_categories: dict[str, int] = {}
        if facet_file.exists():
            facet = json.loads(facet_file.read_text())
            goal = facet.get("underlying_goal", "")
            outcome = facet.get("outcome", "")
            summary = facet.get("brief_summary", "")
            session_type = facet.get("session_type", "")
            helpfulness = facet.get("claude_helpfulness", "")
            friction_counts = facet.get("friction_counts", {})
            friction_detail = facet.get("friction_detail", "")
            goal_categories = facet.get("goal_categories", {})

        sessions.append(
            SessionSummary(
                session_id=session_id,
                project_name=project_name,
                start_time=meta.get("start_time"),
                duration_minutes=meta.get("duration_minutes", 0),
                user_messages=meta.get("user_message_count", 0),
                assistant_messages=meta.get("assistant_message_count", 0),
                tool_counts=meta.get("tool_counts", {}),
                input_tokens=meta.get("input_tokens", 0),
                output_tokens=meta.get("output_tokens", 0),
                lines_added=meta.get("lines_added", 0),
                lines_removed=meta.get("lines_removed", 0),
                files_modified=meta.get("files_modified", 0),
                languages=meta.get("languages", {}),
                git_commits=meta.get("git_commits", 0),
                first_prompt=meta.get("first_prompt", ""),
                tool_errors=meta.get("tool_errors", 0),
                uses_task_agent=meta.get("uses_task_agent", False),
                uses_mcp=meta.get("uses_mcp", False),
                goal=goal,
                outcome=outcome,
                summary=summary,
                session_type=session_type,
                helpfulness=helpfulness,
                friction_counts=friction_counts,
                friction_detail=friction_detail,
                goal_categories=goal_categories,
            )
        )

    return sessions


def _normalize_name(name: str) -> str:
    """Normalize project name for matching: lowercase, replace - and _ with same char."""
    return name.lower().replace("_", "-")


def filter_sessions_by_profile(
    sessions: list[SessionSummary], profile_projects: list[str]
) -> list[SessionSummary]:
    """Filter sessions to only those belonging to profile projects.

    Handles naming mismatches between session paths (ct_perfusion)
    and config names (ct-perfusion) by normalizing both sides.
    """
    normalized_projects = {_normalize_name(p) for p in profile_projects}
    return [s for s in sessions if _normalize_name(s.project_name) in normalized_projects]
