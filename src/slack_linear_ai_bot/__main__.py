"""Console entry point."""

from __future__ import annotations

import logging
import os

import uvicorn

from slack_linear_ai_bot.config import load_settings


def main() -> None:
    settings = load_settings()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", settings.app.log_level).upper())
    uvicorn.run(
        "slack_linear_ai_bot.app:app",
        host=os.getenv("HOST", settings.app.host),
        port=int(os.getenv("PORT", str(settings.app.port))),
    )


if __name__ == "__main__":
    main()
