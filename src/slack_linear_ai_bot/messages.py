"""Slack message parsing, redaction, and Linear team hints."""

from __future__ import annotations

import re
from typing import Any

MENTION_RE = re.compile(r"<@[A-Z0-9]+>\s*")

_REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-_\.]+"), "Bearer [REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9]{10,}\b"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"\bglpat-[A-Za-z0-9]{10,}\b"), "[REDACTED_GITLAB_TOKEN]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"\beyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\b"), "[REDACTED_JWT]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
]


def strip_mentions(text: str) -> str:
    return MENTION_RE.sub("", text).strip()


def extract_text_from_slack_blocks(blocks: Any) -> str:
    if not isinstance(blocks, list):
        return ""
    parts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            node_type = node.get("type")
            if node_type in {"text", "plain_text", "mrkdwn"} and isinstance(node.get("text"), str):
                parts.append(node["text"])
            for key in ("elements", "fields", "accessory", "text"):
                value = node.get(key)
                if isinstance(value, (list, dict)):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(blocks)
    return "\n".join(part.strip() for part in parts if part.strip()).strip()


def extract_message_text(message: dict[str, Any]) -> str:
    text = (message.get("text") or "").strip()
    return text or extract_text_from_slack_blocks(message.get("blocks"))


def is_direct_message_event(event: dict[str, Any], bot_user_id: str) -> bool:
    if event.get("type") != "message" or event.get("channel_type") != "im":
        return False
    if event.get("bot_id") or (event.get("subtype") or "") in {"bot_message", "message_changed", "message_deleted"}:
        return False
    user = (event.get("user") or "").strip()
    return bool(user and user != bot_user_id and (event.get("text") or "").strip())


def redact_slack_secrets(text: str) -> str:
    redacted = text
    for pattern, replacement in _REDACT_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def infer_team_hint(text: str, teams: dict[str, list[str]]) -> str | None:
    normalized = text.lower()
    if not normalized.strip():
        return None
    ranked = list(teams.items())
    backend = next(((name, aliases) for name, aliases in ranked if name.lower() == "backend"), None)
    if backend and _matches_alias(normalized, backend[1]):
        return backend[0]
    for team_name, aliases in ranked:
        if team_name.lower() != "backend" and _matches_alias(normalized, aliases):
            return team_name
    return None


def _matches_alias(normalized_text: str, aliases: list[str]) -> bool:
    for alias in aliases:
        value = alias.lower().strip()
        if value and re.search(rf"(?<!\w){re.escape(value)}(?!\w)", normalized_text):
            return True
    return False
