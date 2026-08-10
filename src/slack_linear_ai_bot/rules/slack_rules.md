# Slack Context and Issue Rules

- Use the full supplied thread as context for the latest user request.
- Preserve the exact Slack thread URL under `## Links` in every created issue description.
- When `[Thread images]` lists screenshot permalinks, copy those links under `## Evidence`, one screenshot per bullet.
- Describe what each screenshot shows only when visible content or thread text supports the description.
- Include product area and page or flow names from the thread.
- Describe Actual versus Expected behavior when the request is a bug.
- Include three to seven reproducible steps when the thread provides enough evidence.
- Include verifiable acceptance criteria as Markdown checkboxes (`- [ ]`).
- Do not create a Video link unless the thread contains an actual video file or video URL.
- Do not label a generic product URL as video reproduction.
- Do not guess links or repurpose a Slack URL as a Figma, specification, or product link.
- When Where, Steps, Actual, or Expected cannot be filled confidently, write exactly `Clarify with person who has found` in that section.
- Follow the supplied routing hint when it matches the evidence, but leave `team_key` empty when the target team remains uncertain.
