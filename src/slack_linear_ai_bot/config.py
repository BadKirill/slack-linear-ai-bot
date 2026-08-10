"""Typed settings and packaged resource loading."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

PACKAGE_ROOT = Path(__file__).resolve().parent


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AppSettings(StrictModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"


class AISettings(StrictModel):
    api_key_env: str = "OPENAI_API_KEY"
    model: str = "gpt-5.4"
    reasoning: str = "medium"
    max_output_tokens: int = Field(default=10000, ge=256, le=100000)
    request_timeout_seconds: float = Field(default=300, gt=0)


class SlackSettings(StrictModel):
    enabled: bool = True
    bot_token_env: str = "SLACK_BOT_TOKEN"
    signing_secret_env: str = "SLACK_SIGNING_SECRET"
    request_timeout_seconds: float = Field(default=600, gt=0)
    http_timeout_seconds: float = Field(default=30, gt=0)
    max_thread_images: int = Field(default=12, ge=1, le=24)
    max_image_bytes: int = Field(default=3_000_000, ge=1, le=20_000_000)
    max_context_chars: int = Field(default=60_000, ge=1000, le=500_000)
    thread_message_cap: int = Field(default=28, ge=1, le=100)
    max_reply_chars: int = Field(default=3900, ge=500, le=4000)


class LinearSettings(StrictModel):
    token_env: str = "LINEAR_TOKEN"
    api_url: str = "https://api.linear.app/graphql"
    team_id: str = ""
    project_id: str = ""
    default_state_id: str = ""
    default_labels: list[str] = Field(default_factory=list)
    allow_create: bool = True
    duplicate_title_check: bool = True


class WriteSettings(StrictModel):
    enabled: bool = True
    allow_without_approval: bool = True
    approval_token: str = "/approve-writes"


class RuleSettings(StrictModel):
    ai_system: str = "rules/ai_system.md"
    slack: str = "rules/slack_rules.md"
    linear: str = "rules/linear_rules.md"
    linear_style: str = "rules/linear_style_guide.md"
    linear_profile: str = "rules/linear_style_profile.json"
    linear_schema: str = "config/linear_issue.schema.json"


class RoutingSettings(StrictModel):
    teams: dict[str, list[str]] = Field(default_factory=dict)


class Settings(StrictModel):
    app: AppSettings = Field(default_factory=AppSettings)
    ai: AISettings = Field(default_factory=AISettings)
    slack: SlackSettings = Field(default_factory=SlackSettings)
    linear: LinearSettings = Field(default_factory=LinearSettings)
    writes: WriteSettings = Field(default_factory=WriteSettings)
    rules: RuleSettings = Field(default_factory=RuleSettings)
    routing: RoutingSettings = Field(default_factory=RoutingSettings)


def load_settings(path: str | Path | None = None) -> Settings:
    load_dotenv(Path.cwd() / ".env", override=False)
    configured_path = path or os.getenv("SLACK_LINEAR_BOT_SETTINGS")
    settings_path = Path(configured_path).expanduser() if configured_path else PACKAGE_ROOT / "config" / "settings.yaml"
    with settings_path.open(encoding="utf-8") as stream:
        payload = yaml.safe_load(stream) or {}
    return Settings.model_validate(payload)


def resource_path(path: str) -> Path:
    candidate = Path(path).expanduser()
    return candidate if candidate.is_absolute() else PACKAGE_ROOT / candidate


def read_resource(path: str) -> str:
    return resource_path(path).read_text(encoding="utf-8").strip()


def required_secret(env_name: str) -> str:
    value = (os.getenv(env_name) or "").strip()
    if not value:
        raise ValueError(f"Required environment variable {env_name} is not set")
    return value
