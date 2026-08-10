from __future__ import annotations

import pytest

from slack_linear_ai_bot.config import Settings, load_settings


@pytest.fixture
def settings() -> Settings:
    return load_settings().model_copy(deep=True)
