# Linear Issue Rules

## Scope and Granularity

- One issue maps to one deliverable.
- Split requests containing independent deliverables into separate issue forms.
- Avoid meta-issues and work larger than one sprint unless the user explicitly asks for an umbrella task.

## Required Content

- `title`: clear and action-oriented, in the form `[Area] Verb + object + optional qualifier`.
- `description_md`: context, problem or expected behavior when applicable, acceptance criteria, evidence, and links.
- `labels`: existing labels only. Do not invent workspace labels.
- `priority`: 0=None, 1=Urgent, 2=High, 3=Medium, 4=Low. Prefer 2 or 3 when the evidence supports no stronger choice.
- `team_key`: infer from the configured routing aliases and leave empty when uncertain.
- `team_id` and `project_id`: use only identifiers explicitly supplied by configuration or context.

## Team Routing

- Use Backend for API behavior, wrong JSON or server state, KYB/KYC or onboarding endpoints, `api.*`, `/v1/`, GraphQL, curl, Bearer tokens, database behavior, or backend environment differences.
- Use Web only for client-only component, routing, browser, CSS, or UI behavior when the API response is known to be correct.
- Prefer Backend when API evidence exists and the boundary is uncertain.

## Description Structure

```markdown
## Context
Why the task exists.

## Problem
Actual behavior and impact.

## Expected
Expected behavior.

## Steps to reproduce
1. First sourced step.

## Acceptance Criteria
- [ ] Verifiable criterion.

## Evidence
- [Screenshot](url)

## Links
- [Slack thread](url)
```

Omit sections that do not apply, except `## Context`, `## Acceptance Criteria`, and `## Links`.

## Traceability

- Include the exact Slack thread URL.
- Include only evidence and links present in the supplied context.
- Never report successful creation before the application confirms the Linear API response.
