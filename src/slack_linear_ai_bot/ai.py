"""OpenAI Responses API adapter with strict structured output."""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from slack_linear_ai_bot.config import Settings, required_secret
from slack_linear_ai_bot.prompts import build_system_instructions
from slack_linear_ai_bot.schemas import AI_RESPONSE_JSON_SCHEMA, AIResponse


class OpenAIService:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self._client = client

    def generate(self, user_prompt: str, image_data_urls: list[str] | None = None) -> AIResponse:
        client = self._client or self._build_client()
        content: list[dict[str, str]] = [{"type": "input_text", "text": user_prompt}]
        content.extend({"type": "input_image", "image_url": image_url} for image_url in image_data_urls or [])
        request: dict[str, Any] = {
            "model": self.settings.ai.model,
            "instructions": build_system_instructions(self.settings),
            "input": [{"role": "user", "content": content}],
            "max_output_tokens": self.settings.ai.max_output_tokens,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "slack_linear_response",
                    "strict": True,
                    "schema": AI_RESPONSE_JSON_SCHEMA,
                }
            },
        }
        if self.settings.ai.reasoning and _supports_reasoning(self.settings.ai.model):
            request["reasoning"] = {"effort": self.settings.ai.reasoning}
        response = client.responses.create(**request)
        output_text = (getattr(response, "output_text", "") or "").strip()
        if not output_text:
            raise ValueError("OpenAI returned no structured response")
        return AIResponse.model_validate_json(output_text)

    def _build_client(self) -> OpenAI:
        return OpenAI(
            api_key=required_secret(self.settings.ai.api_key_env),
            timeout=self.settings.ai.request_timeout_seconds,
        )


def _supports_reasoning(model: str) -> bool:
    return model.startswith(("gpt-5", "o1", "o3", "o4"))
