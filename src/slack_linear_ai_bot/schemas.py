"""Validated AI and Linear payload contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LinearIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=140)
    description_md: str = ""
    labels: list[str] = Field(default_factory=list)
    priority: int = Field(default=0, ge=0, le=4)
    project_id: str = ""
    team_id: str = ""
    team_key: str = ""

    @field_validator("title", "description_md", "project_id", "team_id", "team_key")
    @classmethod
    def strip_strings(cls, value: str) -> str:
        return value.strip()

    @field_validator("labels")
    @classmethod
    def normalize_labels(cls, labels: list[str]) -> list[str]:
        return list(dict.fromkeys(label.strip() for label in labels if label.strip()))


class AIResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str = ""
    linear_issues: list[LinearIssue] = Field(default_factory=list)


class BotResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str
    external_links: list[str] = Field(default_factory=list)
    drafts: list[LinearIssue] = Field(default_factory=list)


AI_RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reply", "linear_issues"],
    "properties": {
        "reply": {"type": "string"},
        "linear_issues": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "title",
                    "description_md",
                    "labels",
                    "priority",
                    "project_id",
                    "team_id",
                    "team_key",
                ],
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": 140},
                    "description_md": {"type": "string"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "priority": {"type": "integer", "minimum": 0, "maximum": 4},
                    "project_id": {"type": "string"},
                    "team_id": {"type": "string"},
                    "team_key": {"type": "string"},
                },
            },
        },
    },
}
