"""Linear GraphQL client and exact-title idempotent issue creation."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from slack_linear_ai_bot.config import LinearSettings, required_secret
from slack_linear_ai_bot.schemas import LinearIssue

logger = logging.getLogger(__name__)


def _should_retry(exc: BaseException) -> bool:
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return bool(status_code == 429 or status_code and 500 <= status_code < 600)


class LinearClient:
    def __init__(self, api_url: str, token: str) -> None:
        self.api_url = api_url
        cleaned = token.strip()
        self.token = cleaned[7:] if cleaned.startswith("Bearer ") else cleaned
        if not self.token:
            raise ValueError("LINEAR_TOKEN must not be empty")

    @retry(
        retry=retry_if_exception(_should_retry),
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=1, max=20),
        reraise=True,
    )
    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        response = requests.post(
            self.api_url,
            json={"query": query, "variables": variables or {}},
            headers={"Authorization": self.token, "Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("errors"):
            messages = "; ".join(str(error.get("message", error)) for error in body["errors"])
            raise RuntimeError(f"Linear GraphQL errors: {messages}")
        return body.get("data", {})

    def create_issue(
        self,
        *,
        team_id: str,
        title: str,
        description_md: str,
        labels: list[str],
        priority: int,
        state_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        label_ids, missing_labels = self.resolve_label_ids(team_id, labels)
        description = description_md
        if missing_labels:
            description = description.rstrip() + "\n\nLabels requested but not found: " + ", ".join(missing_labels)
        issue_input: dict[str, Any] = {"teamId": team_id, "title": title, "description": description or None}
        if priority > 0:
            issue_input["priority"] = priority
        if state_id:
            issue_input["stateId"] = state_id
        if project_id:
            issue_input["projectId"] = project_id
        if label_ids:
            issue_input["labelIds"] = label_ids
        mutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
            issueCreate(input: $input) { success issue { id url title } }
        }
        """
        data = self.graphql(mutation, {"input": issue_input})
        result = data.get("issueCreate") or {}
        if not result.get("success"):
            raise RuntimeError("Linear issueCreate returned success=false")
        issue = result.get("issue") or {}
        return {"id": issue.get("id"), "url": issue.get("url"), "title": issue.get("title")}

    def resolve_label_ids(self, team_id: str, names: list[str]) -> tuple[list[str], list[str]]:
        if not names:
            return [], []
        query = """
        query TeamLabels($teamId: String!) {
            team(id: $teamId) { labels { nodes { id name } } }
        }
        """
        data = self.graphql(query, {"teamId": team_id})
        nodes = ((data.get("team") or {}).get("labels") or {}).get("nodes") or []
        available = {str(node.get("name", "")).lower(): str(node.get("id", "")) for node in nodes}
        ids = [available[name.lower()] for name in names if available.get(name.lower())]
        missing = [name for name in names if not available.get(name.lower())]
        return ids, missing

    def search_issues_by_title(self, team_id: str, title: str) -> list[dict[str, Any]]:
        query = """
        query Issues($filter: IssueFilter, $first: Int) {
            issues(filter: $filter, first: $first) { nodes { id url title } }
        }
        """
        filters = {"team": {"id": {"eq": team_id}}, "title": {"containsIgnoreCase": title}}
        data = self.graphql(query, {"filter": filters, "first": 5})
        return list((data.get("issues") or {}).get("nodes") or [])

    def list_teams(self) -> list[dict[str, Any]]:
        query = "query Teams($first: Int) { teams(first: $first) { nodes { id name key } } }"
        data = self.graphql(query, {"first": 100})
        return list((data.get("teams") or {}).get("nodes") or [])

    def resolve_team_id(self, key_or_name: str) -> str | None:
        value = key_or_name.strip()
        if not value:
            return None
        teams = self.list_teams()
        for team in teams:
            if (
                value.upper() == str(team.get("key") or "").upper()
                or value.lower() == str(team.get("name") or "").lower()
            ):
                return str(team.get("id") or "") or None
        if len(value) > 3:
            for team in teams:
                if value.lower() in str(team.get("name") or "").lower():
                    return str(team.get("id") or "") or None
        return None


@dataclass(frozen=True)
class LinearWriteResult:
    title: str
    url: str
    issue_id: str
    reused: bool


class LinearService:
    def __init__(
        self,
        settings: LinearSettings,
        client_factory: Callable[[str, str], LinearClient] = LinearClient,
    ) -> None:
        self.settings = settings
        self.client_factory = client_factory
        self._client_instance: LinearClient | None = None

    def create_or_reuse(self, issue: LinearIssue) -> LinearWriteResult:
        client = self._client()
        team_id = issue.team_id or self.settings.team_id
        if not team_id and issue.team_key:
            team_id = client.resolve_team_id(issue.team_key) or ""
        if not team_id:
            teams = client.list_teams()
            if not teams:
                raise ValueError("No Linear teams are available")
            team_id = str(teams[0].get("id") or "")
        if self.settings.duplicate_title_check:
            for existing in client.search_issues_by_title(team_id, issue.title):
                if str(existing.get("title") or "").strip() == issue.title:
                    return LinearWriteResult(
                        title=issue.title,
                        url=str(existing.get("url") or ""),
                        issue_id=str(existing.get("id") or ""),
                        reused=True,
                    )
        created = client.create_issue(
            team_id=team_id,
            title=issue.title,
            description_md=issue.description_md,
            labels=issue.labels or self.settings.default_labels,
            priority=issue.priority,
            state_id=self.settings.default_state_id,
            project_id=issue.project_id or self.settings.project_id,
        )
        return LinearWriteResult(
            title=str(created.get("title") or issue.title),
            url=str(created.get("url") or ""),
            issue_id=str(created.get("id") or ""),
            reused=False,
        )

    def _client(self) -> LinearClient:
        if self._client_instance is None:
            self._client_instance = self.client_factory(
                self.settings.api_url,
                required_secret(self.settings.token_env),
            )
        return self._client_instance
