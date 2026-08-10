# Slack Linear AI Bot

Standalone Slack bot extracted from QA AI Engine. It reads channel mentions, threads, direct messages, and screenshot attachments; asks OpenAI for a structured Linear issue form; validates the form; and creates or reuses Linear issues.

The folder has no imports from the parent repository and can be copied into its own Git repository.

## Included behavior

- Slack `app_mention`, thread broadcast, and direct-message handling.
- Immediate threaded acknowledgement so Slack receives a fast event response.
- Full bounded Slack-thread context with secret redaction.
- Private Slack screenshot download with MIME and size validation for OpenAI vision input.
- OpenAI Responses API with strict JSON Schema output.
- Single or multiple Linear issue forms in one request.
- Configurable team routing, model settings, prompts, write approval, timeouts, and limits.
- Exact Slack thread and screenshot links in Linear descriptions.
- Linear team-name/key resolution, label resolution, and exact-title duplicate reuse.
- Honest replies based on confirmed Linear API results.
- `/dry-run` and optional `/approve-writes` protection.

The standalone bot intentionally does not contain the parent project's web UI, RAG/Qdrant index, Notion, TestLodge, GitLab generation, browser automation, memory database, or review-agent council. Those paths were not Slack/Linear-only and would make the extraction dependent on the original engine.

## Project layout

```text
slack_linear_ai_bot/
├── .env.example
├── Dockerfile
├── pyproject.toml
├── scripts/print_slack_event_url.py
├── src/slack_linear_ai_bot/
│   ├── app.py                 # FastAPI endpoint and health status
│   ├── slack.py               # Slack events, threads, files, and replies
│   ├── ai.py                  # OpenAI structured generation
│   ├── service.py             # AI → validation → Linear write flow
│   ├── linear.py              # Linear GraphQL client and duplicate reuse
│   ├── config/settings.yaml   # All runtime and AI settings
│   ├── config/linear_issue.schema.json
│   └── rules/                 # AI, Slack, Linear, and team-style rules
└── tests/
```

## 1. Local installation

Python 3.11 or newer is required.

```bash
cd slack_linear_ai_bot
cp .env.example .env
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

Fill the four required variables in `.env`:

```dotenv
OPENAI_API_KEY=...
LINEAR_TOKEN=...
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
```

Real secret values are not included in this extraction. Never commit `.env`.

## 2. Slack app configuration

Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps) and add these bot token scopes:

- `app_mentions:read`
- `chat:write`
- `channels:history`
- `groups:history`
- `im:history`
- `files:read`

Under Event Subscriptions, subscribe to these bot events:

- `app_mention`
- `message.im`
- `message.channels` if thread-broadcast mentions should be supported in public channels
- `message.groups` if thread-broadcast mentions should be supported in private channels

Install the app to the workspace and put its Bot User OAuth Token and Signing Secret in `.env`.

## 3. Run

```bash
.venv/bin/slack-linear-ai-bot
```

The service listens on `0.0.0.0:8000` by default:

```bash
curl http://127.0.0.1:8000/healthz
```

For local Slack testing, expose the service with ngrok:

```bash
ngrok http 8000
.venv/bin/python scripts/print_slack_event_url.py
```

Use the printed HTTPS URL as Slack's Event Subscriptions Request URL. The endpoint is always `/slack/events`.

Example requests:

```text
@QABot create a Linear bug from this thread
@QABot split this discussion into Backend and Web tasks
@QABot prepare a task but do not create it /dry-run
```

## AI settings, rules, and Linear form

All AI-related settings are in [`src/slack_linear_ai_bot/config/settings.yaml`](src/slack_linear_ai_bot/config/settings.yaml):

- model, reasoning effort, output limit, and OpenAI timeout;
- Slack request, API, context, image, and reply limits;
- Linear endpoint, default team/project/state/labels, write enablement, and duplicate lookup;
- write approval behavior;
- team-routing aliases;
- paths to every rule and schema file.

The model receives these external rule files on every request:

- `rules/ai_system.md`
- `rules/slack_rules.md`
- `rules/linear_rules.md`
- `rules/linear_style_guide.md`
- `rules/linear_style_profile.json`

The Linear creation form is [`config/linear_issue.schema.json`](src/slack_linear_ai_bot/config/linear_issue.schema.json). OpenAI returns zero or more instances of this form, and Pydantic validates them again before any write.

To use another settings file without changing the package:

```bash
export SLACK_LINEAR_BOT_SETTINGS=/absolute/path/to/settings.yaml
```

Rule paths may also be absolute. Relative rule paths resolve inside the installed package.

## Write safety

The extracted configuration preserves the current trusted-workspace behavior:

```yaml
writes:
  enabled: true
  allow_without_approval: true
```

For an untrusted or broad Slack workspace, change `allow_without_approval` to `false`. Users must then include `/approve-writes` in the request. `/dry-run` always prevents a Linear write.

The application, not the model, reports whether an issue was created, reused, blocked, or failed. An exact title match in the resolved Linear team is reused instead of creating another issue.

## Docker

```bash
docker build -t slack-linear-ai-bot .
docker run --rm --env-file .env -p 8000:8000 slack-linear-ai-bot
```

Use a stable HTTPS reverse proxy in production and point Slack to `https://your-host/slack/events`.

## Verification

```bash
.venv/bin/pytest
.venv/bin/ruff check src scripts tests
```

The test suite covers structured OpenAI requests, rule loading, Slack message and image handling, threaded replies, secret redaction, team routing, dry-run and approval gates, Linear payload construction, duplicate reuse, and truthful confirmed replies.
