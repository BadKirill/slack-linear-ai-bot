from slack_linear_ai_bot.messages import (
    extract_message_text,
    infer_team_hint,
    is_direct_message_event,
    redact_slack_secrets,
    strip_mentions,
)


def test_message_parsing_and_secret_redaction() -> None:
    assert strip_mentions("<@U123> create task") == "create task"
    assert "[REDACTED_SLACK_TOKEN]" in redact_slack_secrets("token xoxb-123456789012-abcdef")
    blocks = [{"type": "rich_text", "elements": [{"type": "text", "text": "from blocks"}]}]
    assert extract_message_text({"text": "", "blocks": blocks}) == "from blocks"


def test_backend_hint_has_priority_over_web(settings) -> None:
    text = "The web form shows the wrong response from api.example.com"
    assert infer_team_hint(text, settings.routing.teams) == "Backend"


def test_direct_message_filters_bot_events() -> None:
    user_event = {"type": "message", "channel_type": "im", "user": "U1", "text": "hello"}
    bot_event = {**user_event, "bot_id": "B1"}
    assert is_direct_message_event(user_event, "U-BOT") is True
    assert is_direct_message_event(bot_event, "U-BOT") is False
