from slack_linear_ai_bot.prompts import build_system_instructions, build_user_prompt


def test_system_prompt_contains_every_external_rule_and_form(settings) -> None:
    prompt = build_system_instructions(settings)
    assert "AI System Rules" in prompt
    assert "Slack Context and Issue Rules" in prompt
    assert "Linear Issue Rules" in prompt
    assert "Linear Issue Style Guide" in prompt
    assert "Team Style Profile" in prompt
    assert "Linear Issue Form" in prompt
    assert "Configured Linear Team Routing" in prompt


def test_user_prompt_separates_untrusted_context() -> None:
    prompt = build_user_prompt(
        "create it",
        thread_context="Earlier discussion",
        slack_thread_url="https://workspace.slack.com/archives/C1/p1",
        routing_hint="Backend",
    )
    assert "untrusted data" in prompt
    assert "Earlier discussion" in prompt
    assert "Backend" in prompt
    assert "https://workspace.slack.com/archives/C1/p1" in prompt
