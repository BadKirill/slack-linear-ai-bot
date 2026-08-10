"""Slack Bolt events, thread context, image input, and threaded replies."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.client import WebClient as SyncWebClient

from slack_linear_ai_bot.config import Settings, required_secret
from slack_linear_ai_bot.files import (
    build_thread_images_block,
    collect_image_file_urls,
    download_slack_file_as_data_url,
)
from slack_linear_ai_bot.messages import (
    extract_message_text,
    is_direct_message_event,
    redact_slack_secrets,
    strip_mentions,
)
from slack_linear_ai_bot.schemas import BotResult
from slack_linear_ai_bot.service import BotService

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task[Any]] = set()


def reply_thread_ts(thread_ts: str | None, message_ts: str | None) -> str | None:
    return thread_ts or message_ts or None


def spawn_background_task(coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)

    def done(completed: asyncio.Task[Any]) -> None:
        _background_tasks.discard(completed)
        if completed.cancelled():
            return
        error = completed.exception()
        if error is not None:
            logger.error("Slack background task failed", exc_info=(type(error), error, error.__traceback__))

    task.add_done_callback(done)
    return task


async def slack_permalink(client: AsyncWebClient, channel: str, message_ts: str) -> str:
    if not channel or not message_ts:
        return ""
    try:
        response = await client.chat_getPermalink(channel=channel, message_ts=message_ts)
        return str(response.get("permalink") or "").strip() if response.get("ok") else ""
    except Exception as exc:
        logger.warning("Slack permalink lookup failed: %s", exc)
        return ""


async def fetch_thread_context(
    client: AsyncWebClient,
    channel: str,
    thread_ts: str,
    settings: Settings,
) -> tuple[str, list[str]]:
    try:
        response = await client.conversations_replies(channel=channel, ts=thread_ts, limit=100)
        messages = list(response.get("messages") or []) if response.get("ok") else []
    except Exception as exc:
        logger.warning("Slack thread fetch failed: %s", exc)
        return "", []
    images_block, image_urls = build_thread_images_block(messages, settings.slack.max_thread_images)
    omitted = max(0, len(messages) - settings.slack.thread_message_cap)
    selected = messages[-settings.slack.thread_message_cap :]
    lines: list[str] = []
    for message in selected:
        text = redact_slack_secrets(strip_mentions(extract_message_text(message)))
        if text:
            author = message.get("user") or message.get("bot_id") or "unknown"
            lines.append(f"**{author}:** {text}")
    prefix = f"[…{omitted} older thread messages omitted]\n\n" if omitted else ""
    context = (images_block + "\n\n" + prefix + "\n\n".join(lines)).strip()
    if len(context) > settings.slack.max_context_chars:
        context = "[…older context truncated]\n" + context[-settings.slack.max_context_chars :]
    return context, image_urls


async def build_slack_request(
    client: AsyncWebClient,
    *,
    channel: str,
    thread_ts: str | None,
    message_ts: str | None,
    user_text: str,
    event_files: list[dict[str, Any]],
    bot_token: str,
    settings: Settings,
) -> tuple[str, str, str, list[str]]:
    permalink_ts = thread_ts or message_ts or ""
    thread_url = await slack_permalink(client, channel, permalink_ts)
    event_block, event_urls = build_thread_images_block([{"files": event_files}], settings.slack.max_thread_images)
    thread_context = event_block
    image_urls = event_urls or collect_image_file_urls(
        [{"files": event_files}],
        settings.slack.max_thread_images,
    )
    if thread_ts:
        thread_context, thread_urls = await fetch_thread_context(client, channel, thread_ts, settings)
        image_urls.extend(thread_urls)
    attachments: list[str] = []
    for url in list(dict.fromkeys(image_urls))[: settings.slack.max_thread_images]:
        data_url = await download_slack_file_as_data_url(
            url,
            bot_token,
            max_bytes=settings.slack.max_image_bytes,
            timeout_seconds=settings.slack.http_timeout_seconds,
        )
        if data_url:
            attachments.append(data_url)
    return redact_slack_secrets(user_text), thread_context, thread_url, attachments


async def post_message(
    client: AsyncWebClient,
    *,
    channel: str,
    text: str,
    thread_ts: str | None,
) -> None:
    payload: dict[str, Any] = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    await client.chat_postMessage(**payload)


async def process_and_reply(
    client: AsyncWebClient,
    *,
    channel: str,
    thread_ts: str | None,
    message_ts: str | None,
    user_text: str,
    event_files: list[dict[str, Any]],
    bot_token: str,
    settings: Settings,
    get_service: Callable[[], BotService],
) -> None:
    target_thread = reply_thread_ts(thread_ts, message_ts)
    try:
        await post_message(client, channel=channel, text="Working on it…", thread_ts=target_thread)
    except Exception as exc:
        logger.warning("Slack acknowledgement failed: %s", exc)
    try:
        clean_text, thread_context, thread_url, attachments = await build_slack_request(
            client,
            channel=channel,
            thread_ts=thread_ts,
            message_ts=message_ts,
            user_text=user_text,
            event_files=event_files,
            bot_token=bot_token,
            settings=settings,
        )
        result = await asyncio.wait_for(
            asyncio.to_thread(
                get_service().handle,
                clean_text,
                thread_context=thread_context,
                slack_thread_url=thread_url,
                image_data_urls=attachments,
            ),
            timeout=settings.slack.request_timeout_seconds,
        )
        reply = append_missing_links(result)
        if len(reply) > settings.slack.max_reply_chars:
            reply = reply[: settings.slack.max_reply_chars - 3] + "..."
        await post_message(client, channel=channel, text=reply, thread_ts=target_thread)
    except TimeoutError:
        await post_message(
            client,
            channel=channel,
            text=f"The request timed out after {int(settings.slack.request_timeout_seconds)} seconds. Please retry.",
            thread_ts=target_thread,
        )
    except Exception as exc:
        logger.exception("Slack request failed: %s", exc)
        await post_message(
            client,
            channel=channel,
            text=friendly_error(user_text),
            thread_ts=target_thread,
        )


def append_missing_links(result: BotResult) -> str:
    reply = result.reply
    missing = [link for link in result.external_links if link and link not in reply]
    return reply.rstrip() + ("\n\n" + "\n".join(dict.fromkeys(missing)) if missing else "")


def friendly_error(user_text: str) -> str:
    russian = any(("а" <= char.lower() <= "я") or char.lower() == "ё" for char in user_text)
    if russian:
        return "Не удалось обработать запрос. Попробуйте ещё раз; подробности сохранены в логах бота."
    return "I could not process this request. Please retry; details were saved in the bot logs."


def create_slack_app(
    settings: Settings,
    get_service: Callable[[], BotService],
) -> tuple[AsyncApp, AsyncSlackRequestHandler]:
    token = required_secret(settings.slack.bot_token_env)
    signing_secret = required_secret(settings.slack.signing_secret_env)
    client = AsyncWebClient(token=token, timeout=settings.slack.http_timeout_seconds)
    slack_app = AsyncApp(token=token, signing_secret=signing_secret, client=client)
    try:
        auth = SyncWebClient(token=token, timeout=int(settings.slack.http_timeout_seconds)).auth_test()
        bot_user_id = str(auth.get("user_id") or "")
    except Exception as exc:
        logger.warning("Slack auth_test failed: %s", exc)
        bot_user_id = ""

    def dispatch(event: dict[str, Any], event_client: AsyncWebClient, user_text: str) -> None:
        spawn_background_task(
            process_and_reply(
                event_client,
                channel=str(event.get("channel") or ""),
                thread_ts=str(event.get("thread_ts") or "") or None,
                message_ts=str(event.get("ts") or "") or None,
                user_text=user_text,
                event_files=list(event.get("files") or []),
                bot_token=token,
                settings=settings,
                get_service=get_service,
            )
        )

    @slack_app.event("app_mention")
    async def handle_app_mention(event: dict[str, Any], client: AsyncWebClient) -> None:
        request = strip_mentions(str(event.get("text") or ""))
        dispatch(event, client, request or "Summarize this thread and create a Linear task for it.")

    @slack_app.event({"type": "message", "subtype": "thread_broadcast"})
    async def handle_thread_broadcast(event: dict[str, Any], client: AsyncWebClient) -> None:
        text = str(event.get("text") or "")
        if bot_user_id and f"<@{bot_user_id}>" in text:
            request = strip_mentions(text) or "Summarize this thread and create a Linear task for it."
            dispatch(event, client, request)

    @slack_app.event("message")
    async def handle_direct_message(event: dict[str, Any], client: AsyncWebClient) -> None:
        if is_direct_message_event(event, bot_user_id):
            dispatch(event, client, str(event.get("text") or "").strip())

    return slack_app, AsyncSlackRequestHandler(slack_app)
