from __future__ import annotations

from typing import Any

from slack_linear_ai_bot.linear import LinearClient, LinearService
from slack_linear_ai_bot.schemas import LinearIssue


def test_client_builds_linear_form_and_reports_missing_labels() -> None:
    client = LinearClient("https://api.linear.test/graphql", "lin_test")
    requests: list[tuple[str, dict[str, Any]]] = []

    def graphql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        requests.append((query, variables or {}))
        if "TeamLabels" in query:
            return {"team": {"labels": {"nodes": [{"id": "label-1", "name": "bug"}]}}}
        return {"issueCreate": {"success": True, "issue": {"id": "i1", "url": "https://linear/i1", "title": "T"}}}

    client.graphql = graphql  # type: ignore[method-assign]
    result = client.create_issue(
        team_id="team-1",
        title="T",
        description_md="D",
        labels=["bug", "missing"],
        priority=2,
        state_id="state-1",
        project_id="project-1",
    )

    issue_input = requests[-1][1]["input"]
    assert issue_input["labelIds"] == ["label-1"]
    assert "Labels requested but not found: missing" in issue_input["description"]
    assert result["url"] == "https://linear/i1"


class FakeLinearClient:
    def __init__(self, existing: bool) -> None:
        self.existing = existing
        self.created = 0

    def resolve_team_id(self, key: str) -> str:
        assert key == "Backend"
        return "team-backend"

    def list_teams(self) -> list[dict[str, str]]:
        return [{"id": "team-first"}]

    def search_issues_by_title(self, team_id: str, title: str) -> list[dict[str, str]]:
        assert team_id == "team-backend"
        return [{"id": "old", "url": "https://linear/old", "title": title}] if self.existing else []

    def create_issue(self, **kwargs: Any) -> dict[str, str]:
        self.created += 1
        return {"id": "new", "url": "https://linear/new", "title": kwargs["title"]}


def test_service_reuses_exact_title(settings, monkeypatch) -> None:
    monkeypatch.setenv("LINEAR_TOKEN", "lin_test")
    fake = FakeLinearClient(existing=True)
    service = LinearService(settings.linear, client_factory=lambda _url, _token: fake)
    result = service.create_or_reuse(LinearIssue(title="[API] Fix state", team_key="Backend"))

    assert result.reused is True
    assert result.url == "https://linear/old"
    assert fake.created == 0
