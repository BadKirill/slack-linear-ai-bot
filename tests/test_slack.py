from __future__ import annotations

import asyncio
from typing import Any

from slack_linear_ai_bot.schemas import BotResult
from slack_linear_ai_bot.slack import append_missing_links, friendly_error, process_and_reply, reply_thread_ts


class FakeSlackClient:
    def __init__(self) -> None:
        self.posted: list[dict[str, Any]] = []

    async def chat_postMessage(self, **kwargs: Any) -> dict[str, Any]:
        self.posted.append(kwargs)
        return {"ok": True}

    async def chat_getPermalink(self, **kwargs: Any) -> dict[str, Any]:
        return {"ok": True, "permalink": "https://workspace.slack.com/archives/C1/p1"}


class FakeService:
    def handle(self, user_text: str, **kwargs: Any) -> BotResult:
        assert user_text == "create task"
        assert kwargs["slack_thread_url"].startswith("https://workspace.slack.com")
        return BotResult(reply="Created", external_links=["https://linear.app/issue/BE-1"])


def test_channel_mention_replies_under_trigger_message(settings) -> None:
    client = FakeSlackClient()
    asyncio.run(
        process_and_reply(
            client,
            channel="C1",
            thread_ts=None,
            message_ts="171.999",
            user_text="create task",
            event_files=[],
            bot_token="xoxb-test",
            settings=settings,
            get_service=FakeService,
        )
    )
    assert len(client.posted) == 2
    assert client.posted[0]["thread_ts"] == "171.999"
    assert client.posted[1]["thread_ts"] == "171.999"
    assert client.posted[1]["text"].count("https://linear.app/issue/BE-1") == 1


def test_link_append_is_deduplicated() -> None:
    result = BotResult(
        reply="Done https://linear.app/issue/BE-1",
        external_links=["https://linear.app/issue/BE-1", "https://linear.app/issue/BE-1"],
    )
    assert append_missing_links(result).count("https://linear.app/issue/BE-1") == 1


def test_thread_target_and_localized_error() -> None:
    assert reply_thread_ts("thread", "message") == "thread"
    assert reply_thread_ts(None, "message") == "message"
    assert "Не удалось" in friendly_error("создай задачу")
