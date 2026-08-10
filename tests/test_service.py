from __future__ import annotations

from slack_linear_ai_bot.linear import LinearWriteResult
from slack_linear_ai_bot.schemas import AIResponse, LinearIssue
from slack_linear_ai_bot.service import BotService


class FakeAI:
    def __init__(self, response: AIResponse) -> None:
        self.response = response
        self.prompt = ""

    def generate(self, user_prompt: str, image_data_urls=None) -> AIResponse:
        self.prompt = user_prompt
        return self.response


class FakeWriter:
    def __init__(self) -> None:
        self.issues: list[LinearIssue] = []

    def create_or_reuse(self, issue: LinearIssue) -> LinearWriteResult:
        self.issues.append(issue)
        return LinearWriteResult(issue.title, "https://linear.app/team/issue/BE-1", "i1", False)


def issue_response() -> AIResponse:
    return AIResponse(
        reply="Prepared",
        linear_issues=[
            LinearIssue(
                title="[API] Fix onboarding state",
                description_md="## Context\nWrong state\n\n## Acceptance Criteria\n- [ ] State is correct\n\n## Links",
                priority=2,
            )
        ],
    )


def test_confirmed_linear_write_is_truthful_and_has_slack_link(settings) -> None:
    writer = FakeWriter()
    service = BotService(settings, FakeAI(issue_response()), writer)
    result = service.handle(
        "Create a Linear issue for the API bug",
        thread_context="API returns wrong onboarding state",
        slack_thread_url="https://workspace.slack.com/archives/C1/p1",
    )

    assert "Created" in result.reply
    assert result.external_links == ["https://linear.app/team/issue/BE-1"]
    assert writer.issues[0].team_key == "Backend"
    assert "https://workspace.slack.com/archives/C1/p1" in writer.issues[0].description_md


def test_dry_run_prepares_form_without_writing(settings) -> None:
    writer = FakeWriter()
    result = BotService(settings, FakeAI(issue_response()), writer).handle("Create task /dry-run")
    assert "not created" in result.reply
    assert not writer.issues
    assert result.drafts


def test_explicit_approval_is_enforced_when_configured(settings) -> None:
    settings.writes.allow_without_approval = False
    writer = FakeWriter()
    result = BotService(settings, FakeAI(issue_response()), writer).handle("Create task")
    assert settings.writes.approval_token in result.reply
    assert not writer.issues


def test_plain_answer_does_not_touch_linear(settings) -> None:
    writer = FakeWriter()
    response = AIResponse(reply="The current status is green.")
    result = BotService(settings, FakeAI(response), writer).handle("What is the status?")
    assert result.reply == "The current status is green."
    assert not writer.issues
