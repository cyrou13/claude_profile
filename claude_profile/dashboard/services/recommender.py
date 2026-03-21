"""Usage-based recommendation engine."""

from __future__ import annotations

from claude_profile.models import DailyActivity, ModelUsage, Recommendation, SessionSummary


def generate_recommendations(
    totals: dict[str, int],
    model_usage: list[dict[str, object]],
    sessions: list[SessionSummary],
) -> list[Recommendation]:
    """Analyze usage patterns and generate actionable recommendations."""
    recs: list[Recommendation] = []

    # Model usage optimization
    _analyze_model_usage(model_usage, recs)

    # Session patterns
    _analyze_sessions(sessions, recs)

    # Context management
    _analyze_context_usage(sessions, recs)

    # General tips
    _add_general_tips(totals, recs)

    return sorted(recs, key=lambda r: {"high": 0, "medium": 1, "low": 2}[r.priority])


def _analyze_model_usage(
    model_usage: list[dict[str, object]], recs: list[Recommendation]
) -> None:
    """Check if the user could benefit from model switching."""
    if not model_usage:
        return

    total_tokens = sum(int(m.get("output_tokens", 0)) for m in model_usage)
    if total_tokens == 0:
        return

    opus_tokens = sum(
        int(m.get("output_tokens", 0))
        for m in model_usage
        if "opus" in str(m.get("model_id", "")).lower()
    )

    opus_ratio = opus_tokens / total_tokens if total_tokens > 0 else 0

    if opus_ratio > 0.9:
        recs.append(
            Recommendation(
                category="model",
                title="Utilisation quasi-exclusive d'Opus",
                description=(
                    f"Tu utilises Opus pour {opus_ratio:.0%} de tes tokens. "
                    "Pour les taches d'implementation simples, switcher a Sonnet "
                    "peut reduire les couts de ~40% sans perte de qualite. "
                    "Reserve Opus pour la planification et l'architecture."
                ),
                priority="high",
            )
        )


def _analyze_sessions(
    sessions: list[SessionSummary], recs: list[Recommendation]
) -> None:
    """Analyze session patterns."""
    if not sessions:
        return

    durations = [s.duration_minutes for s in sessions if s.duration_minutes > 0]

    if durations:
        avg_duration = sum(durations) / len(durations)

        if avg_duration > 60:
            recs.append(
                Recommendation(
                    category="context",
                    title="Sessions longues detectees",
                    description=(
                        f"Duree moyenne de session : {avg_duration:.0f} min. "
                        "Les sessions longues remplissent le contexte et degradent la qualite. "
                        "Utilise /clear regulierement et decoupe les taches en sessions plus courtes."
                    ),
                    priority="high",
                )
            )

    # Check for failed outcomes
    failed = [s for s in sessions if s.outcome in ("not_achieved", "partially_achieved")]
    if len(failed) > len(sessions) * 0.3:
        recs.append(
            Recommendation(
                category="context",
                title="Taux d'echec eleve",
                description=(
                    f"{len(failed)}/{len(sessions)} sessions n'ont pas atteint leur objectif. "
                    "Essaie d'utiliser /plan avant les taches complexes et d'etre plus "
                    "specifique dans tes instructions."
                ),
                priority="high",
            )
        )


def _analyze_context_usage(
    sessions: list[SessionSummary], recs: list[Recommendation]
) -> None:
    """Analyze context window efficiency."""
    if not sessions:
        return

    # Sessions with many tool calls but few user messages = good automation
    high_tool_sessions = [
        s for s in sessions
        if sum(s.tool_counts.values()) > 20 and s.user_messages <= 3
    ]
    if high_tool_sessions:
        recs.append(
            Recommendation(
                category="feature",
                title="Bon usage de l'autonomie",
                description=(
                    f"{len(high_tool_sessions)} sessions avec forte autonomie agent. "
                    "Continue a donner des instructions claires et laisser Claude travailler."
                ),
                priority="low",
            )
        )

    # Check if MCP/web tools are underused
    uses_mcp = any(
        "mcp" in str(s.tool_counts).lower() for s in sessions
    )
    if not uses_mcp:
        recs.append(
            Recommendation(
                category="feature",
                title="MCP servers sous-utilises",
                description=(
                    "Aucune session ne semble utiliser les MCP servers. "
                    "Ils peuvent fournir un contexte supplementaire (GitHub, DB, filesystem)."
                ),
                priority="medium",
            )
        )


def _add_general_tips(
    totals: dict[str, int], recs: list[Recommendation]
) -> None:
    """Add general tips based on overall usage."""
    days = totals.get("days_active", 0)
    if days > 0:
        avg_messages_per_day = totals.get("messages", 0) / days
        if avg_messages_per_day > 3000:
            recs.append(
                Recommendation(
                    category="context",
                    title="Volume de messages tres eleve",
                    description=(
                        f"~{avg_messages_per_day:.0f} messages/jour actif. "
                        "Assure-toi d'utiliser les fichiers CLAUDE.md de projet "
                        "pour eviter de repeter les memes instructions."
                    ),
                    priority="medium",
                )
            )
