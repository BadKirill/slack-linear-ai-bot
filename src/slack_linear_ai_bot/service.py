"""Transport-independent AI generation and confirmed Linear write flow."""

from __future__ import annotations

import logging
from typing import Protocol

from slack_linear_ai_bot.config import Settings
from slack_linear_ai_bot.linear import LinearWriteResult
from slack_linear_ai_bot.messages import infer_team_hint
from slack_linear_ai_bot.prompts import build_user_prompt
from slack_linear_ai_bot.schemas import AIResponse, BotResult, LinearIssue

logger = logging.getLogger(__name__)


class AIService(Protocol):
    def generate(self, user_prompt: str, image_data_urls: list[str] | None = None) -> AIResponse: ...


class IssueWriter(Protocol):
    def create_or_reuse(self, issue: LinearIssue) -> LinearWriteResult: ...


class BotService:
    def __init__(self, settings: Settings, ai: AIService, linear: IssueWriter) -> None:
        self.settings = settings
        self.ai = ai
        self.linear = linear

    def handle(
        self,
        user_text: str,
        *,
        thread_context: str = "",
        slack_thread_url: str = "",
        image_data_urls: list[str] | None = None,
    ) -> BotResult:
        routing_hint = infer_team_hint(thread_context + "\n" + user_text, self.settings.routing.teams)
        prompt = build_user_prompt(
            user_text,
            thread_context=thread_context,
            slack_thread_url=slack_thread_url,
            routing_hint=routing_hint,
        )
        generated = self.ai.generate(prompt, image_data_urls)
        issues = [self._complete_issue(issue, slack_thread_url, routing_hint) for issue in generated.linear_issues]
        if not issues:
            return BotResult(reply=generated.reply or "No reply generated.")
        write_blocker = self._write_blocker(user_text)
        if write_blocker:
            return BotResult(reply=self._draft_reply(user_text, issues, write_blocker), drafts=issues)

        results: list[LinearWriteResult] = []
        failures: list[str] = []
        for issue in issues:
            try:
                results.append(self.linear.create_or_reuse(issue))
            except Exception as exc:
                logger.exception("Linear write failed for %s: %s", issue.title, exc)
                failures.append(issue.title)
        reply = self._confirmed_reply(user_text, results, failures)
        links = list(dict.fromkeys(result.url for result in results if result.url))
        return BotResult(reply=reply, external_links=links, drafts=issues)

    def _complete_issue(self, issue: LinearIssue, slack_thread_url: str, routing_hint: str | None) -> LinearIssue:
        payload = issue.model_copy(deep=True)
        if not payload.team_key and not payload.team_id and routing_hint:
            payload.team_key = routing_hint
        if not payload.labels and self.settings.linear.default_labels:
            payload.labels = list(self.settings.linear.default_labels)
        if slack_thread_url and slack_thread_url not in payload.description_md:
            suffix = f"- [Slack thread]({slack_thread_url})"
            if "## Links" in payload.description_md:
                payload.description_md = payload.description_md.rstrip() + "\n" + suffix
            else:
                payload.description_md = payload.description_md.rstrip() + "\n\n## Links\n" + suffix
        return payload

    def _write_blocker(self, user_text: str) -> str:
        if "/dry-run" in user_text.lower():
            return "dry_run"
        if not self.settings.writes.enabled or not self.settings.linear.allow_create:
            return "disabled"
        approval = self.settings.writes.approval_token
        if not self.settings.writes.allow_without_approval and approval not in user_text:
            return "approval"
        return ""

    def _draft_reply(self, user_text: str, issues: list[LinearIssue], reason: str) -> str:
        titles = "\n".join(f"- {issue.title}" for issue in issues)
        if _is_russian(user_text):
            notices = {
                "dry_run": "Dry-run: задачи подготовлены, но не созданы.",
                "disabled": "Задачи подготовлены, но запись в Linear отключена.",
                "approval": f"Задачи подготовлены. Добавьте `{self.settings.writes.approval_token}` для создания.",
            }
        else:
            notices = {
                "dry_run": "Dry run: issues were prepared but not created.",
                "disabled": "Issues were prepared, but Linear writes are disabled.",
                "approval": f"Issues were prepared. Add `{self.settings.writes.approval_token}` to create them.",
            }
        return notices[reason] + "\n" + titles

    def _confirmed_reply(
        self,
        user_text: str,
        results: list[LinearWriteResult],
        failures: list[str],
    ) -> str:
        russian = _is_russian(user_text)
        lines: list[str] = []
        for result in results:
            action = (
                ("Найдена существующая" if result.reused else "Создана")
                if russian
                else ("Reused existing" if result.reused else "Created")
            )
            target = f"<{result.url}|{result.title}>" if result.url else result.title
            lines.append(f"- {action}: {target}")
        for title in failures:
            lines.append(f"- Не удалось создать: {title}" if russian else f"- Could not create: {title}")
        heading = "Результат Linear:" if russian else "Linear result:"
        return heading + "\n" + "\n".join(lines)


def _is_russian(text: str) -> bool:
    return any(("а" <= char.lower() <= "я") or char.lower() == "ё" for char in text)
