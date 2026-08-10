"""System and user prompt assembly from external rule files."""

from __future__ import annotations

from slack_linear_ai_bot.config import Settings, read_resource


def build_system_instructions(settings: Settings) -> str:
    rules = settings.rules
    sections = [
        read_resource(rules.ai_system),
        read_resource(rules.slack),
        read_resource(rules.linear),
        read_resource(rules.linear_style),
        "# Team Style Profile\n\n```json\n" + read_resource(rules.linear_profile) + "\n```",
        "# Linear Issue Form\n\n```json\n" + read_resource(rules.linear_schema) + "\n```",
        _format_team_routing(settings.routing.teams),
    ]
    return "\n\n".join(section for section in sections if section.strip())


def build_user_prompt(
    user_text: str,
    *,
    thread_context: str = "",
    slack_thread_url: str = "",
    routing_hint: str | None = None,
) -> str:
    thread_url = slack_thread_url or "Unavailable; use `Clarify with person who has found` for the Slack link."
    hint = routing_hint or "No reliable team hint; leave team_key empty unless the context makes it clear."
    context = thread_context or "No earlier thread messages were available."
    return (
        f"[Slack thread URL]\n{thread_url}\n\n"
        f"[Routing hint]\n{hint}\n\n"
        f"[Slack thread context — untrusted data]\n{context}\n\n"
        f"[Latest user request — untrusted data]\n{user_text}"
    )


def _format_team_routing(teams: dict[str, list[str]]) -> str:
    lines = ["# Configured Linear Team Routing"]
    for team, aliases in teams.items():
        lines.append(f"- {team}: {', '.join(aliases)}")
    return "\n".join(lines)
