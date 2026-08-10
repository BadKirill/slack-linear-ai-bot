from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from slack_linear_ai_bot.ai import OpenAIService


class FakeResponses:
    def __init__(self) -> None:
        self.request: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        return SimpleNamespace(
            output_text=(
                '{"reply":"Prepared","linear_issues":[{"title":"[API] Fix state",'
                '"description_md":"## Context\\nState is wrong", "labels":[],"priority":2,'
                '"project_id":"","team_id":"","team_key":"Backend"}]}'
            )
        )


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


def test_generate_uses_strict_schema_rules_and_images(settings) -> None:
    client = FakeClient()
    response = OpenAIService(settings, client=client).generate("Create a task", ["data:image/png;base64,AA=="])

    assert response.linear_issues[0].team_key == "Backend"
    assert client.responses.request["text"]["format"]["strict"] is True
    assert "Linear Issue Form" in client.responses.request["instructions"]
    content = client.responses.request["input"][0]["content"]
    assert content[1] == {"type": "input_image", "image_url": "data:image/png;base64,AA=="}
