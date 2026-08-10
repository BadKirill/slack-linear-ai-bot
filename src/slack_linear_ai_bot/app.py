"""FastAPI application exposing Slack Events API and health status."""

from __future__ import annotations

import os
from collections.abc import Callable

from fastapi import FastAPI, Request

from slack_linear_ai_bot.ai import OpenAIService
from slack_linear_ai_bot.config import Settings, load_settings
from slack_linear_ai_bot.linear import LinearService
from slack_linear_ai_bot.service import BotService
from slack_linear_ai_bot.slack import create_slack_app


def create_app(
    settings: Settings | None = None,
    service_factory: Callable[[], BotService] | None = None,
) -> FastAPI:
    active_settings = settings or load_settings()
    api = FastAPI(title="Slack Linear AI Bot", version="0.1.0")
    service: BotService | None = None

    def get_service() -> BotService:
        nonlocal service
        if service_factory:
            return service_factory()
        if service is None:
            service = BotService(
                active_settings,
                OpenAIService(active_settings),
                LinearService(active_settings.linear),
            )
        return service

    slack_credentials = all(
        (os.getenv(env_name) or "").strip()
        for env_name in (active_settings.slack.bot_token_env, active_settings.slack.signing_secret_env)
    )
    api.state.slack_events_mounted = False
    api.state.slack_skip_reason = ""
    if active_settings.slack.enabled and slack_credentials:
        _, handler = create_slack_app(active_settings, get_service)

        @api.post("/slack/events")
        async def slack_events(request: Request):
            return await handler.handle(request)

        api.state.slack_events_mounted = True
    elif not active_settings.slack.enabled:
        api.state.slack_skip_reason = "slack.enabled is false"
    else:
        api.state.slack_skip_reason = "Slack credentials are not configured"

    @api.get("/healthz")
    async def health() -> dict[str, object]:
        secret_status = {
            active_settings.ai.api_key_env: bool((os.getenv(active_settings.ai.api_key_env) or "").strip()),
            active_settings.linear.token_env: bool((os.getenv(active_settings.linear.token_env) or "").strip()),
            active_settings.slack.bot_token_env: bool((os.getenv(active_settings.slack.bot_token_env) or "").strip()),
            active_settings.slack.signing_secret_env: bool(
                (os.getenv(active_settings.slack.signing_secret_env) or "").strip()
            ),
        }
        ready = all(secret_status.values()) and api.state.slack_events_mounted
        return {
            "status": "ok" if ready else "configuration_required",
            "ready": ready,
            "slack_events_mounted": api.state.slack_events_mounted,
            "slack_skip_reason": api.state.slack_skip_reason,
            "configured": secret_status,
        }

    return api


app = create_app()
