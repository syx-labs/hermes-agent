from gateway.cockpit.cards import (
    DecisionCard,
    HandoffCard,
    JobCard,
    PlanCard,
    ProjectCard,
    ResearchCard,
    StatusCard,
    render_decision_card,
    render_handoff_card,
    render_job_card,
    render_plan_card,
    render_project_card,
    render_research_card,
    render_status_card,
)
from gateway.cockpit.next_actions import NextAction, NextActionKind


def test_render_status_card_is_compact_and_actionable():
    card = StatusCard(
        title="Hermes Telegram Cockpit",
        status="operational",
        summary="Gateway connected and ready.",
        fields={
            "Profile": "friday",
            "Model": "openai-codex/gpt-5.5",
            "Jobs": "2 active",
        },
        next_actions=["Open jobs", "Create task"],
    )

    assert render_status_card(card) == """## Hermes Telegram Cockpit
Status: operational
Gateway connected and ready.

Profile: friday
Model: openai-codex/gpt-5.5
Jobs: 2 active

Next actions:
1. Open jobs
2. Create task"""


def test_render_project_card_includes_aliases_path_skills_and_actions():
    card = ProjectCard(
        name="adaptive-context-harness",
        status="active",
        path="/Users/shadow/projects/adaptive-context-harness",
        aliases=["ach", "harness"],
        skills=["adaptive-context-harness", "requesting-code-review"],
        last_session="2026-04-26",
        actions=["Inspect repo", "Run review"],
    )

    assert render_project_card(card) == """## Project: adaptive-context-harness
Status: active
Path: /Users/shadow/projects/adaptive-context-harness
Aliases: ach, harness
Skills: adaptive-context-harness, requesting-code-review
Last session: 2026-04-26

Actions:
1. Inspect repo
2. Run review"""


def test_render_job_card_includes_schedule_delivery_and_state():
    card = JobCard(
        name="gpt55-catalog-watch",
        status="active",
        schedule="0 9 * * *",
        delivery="telegram",
        last_run="2026-04-26 09:00",
        next_run="2026-04-27 09:00",
        actions=["Run now", "Pause"],
    )

    assert render_job_card(card) == """## Job: gpt55-catalog-watch
Status: active
Schedule: 0 9 * * *
Delivery: telegram
Last run: 2026-04-26 09:00
Next run: 2026-04-27 09:00

Actions:
1. Run now
2. Pause"""


def test_render_plan_card_keeps_steps_numbered():
    card = PlanCard(
        title="Telegram Cockpit v1",
        goal="Make Telegram interactive and visual.",
        steps=["Add action router", "Add cards", "Implement commands"],
        risks=["Callback state expiry", "Telegram callback data limit"],
        next_actions=["Start implementation"],
    )

    assert render_plan_card(card) == """## Plan: Telegram Cockpit v1
Goal: Make Telegram interactive and visual.

Steps:
1. Add action router
2. Add cards
3. Implement commands

Risks:
1. Callback state expiry
2. Telegram callback data limit

Next actions:
1. Start implementation"""


def test_render_decision_card_marks_recommended_option():
    card = DecisionCard(
        title="Choose MVP scope",
        question="Which scope should ship first?",
        options=[
            {"label": "Text cards", "tradeoff": "Fast, low risk"},
            {"label": "PNG cards", "tradeoff": "More visual, more dependencies"},
        ],
        recommended="Text cards",
        next_actions=["Choose Text cards", "Compare again"],
    )

    assert render_decision_card(card) == """## Decision: Choose MVP scope
Question: Which scope should ship first?

Options:
1. Text cards — Fast, low risk (recommended)
2. PNG cards — More visual, more dependencies

Next actions:
1. Choose Text cards
2. Compare again"""


def test_render_research_card_includes_sources_and_recommendation():
    card = ResearchCard(
        title="Telegram Bot API",
        summary="Inline keyboards are the fastest UX win.",
        findings=["Callback data is limited", "Buttons need server-side state"],
        sources=["gateway/platforms/telegram.py", "telegram.md"],
        recommendation="Build a generic cx: action namespace.",
    )

    assert render_research_card(card) == """## Research: Telegram Bot API
Summary: Inline keyboards are the fastest UX win.

Findings:
1. Callback data is limited
2. Buttons need server-side state

Sources:
1. gateway/platforms/telegram.py
2. telegram.md

Recommendation: Build a generic cx: action namespace."""


def test_render_handoff_card_includes_context_deliverables_and_next_steps():
    card = HandoffCard(
        title="Telegram Cockpit v1",
        context="Audit and MVP scope are done.",
        deliverables=["docs/plans/2026-04-26-telegram-cockpit-v1.md"],
        next_steps=["Implement cards", "Implement action router"],
        owner="Hermes friday",
    )

    assert render_handoff_card(card) == """## Handoff: Telegram Cockpit v1
Owner: Hermes friday
Context: Audit and MVP scope are done.

Deliverables:
1. docs/plans/2026-04-26-telegram-cockpit-v1.md

Next steps:
1. Implement cards
2. Implement action router"""


def test_cards_render_structured_next_actions_with_standard_labels():
    card = StatusCard(
        title="Hermes Telegram Cockpit",
        status="operational",
        next_actions=[
            NextAction(NextActionKind.EXECUTE, "Run verification"),
            NextAction(NextActionKind.CONTINUE, "Continue implementation"),
        ],
    )

    assert render_status_card(card) == """## Hermes Telegram Cockpit
Status: operational

Next actions:
1. Continue — Continue implementation
2. Execute — Run verification"""


def test_empty_optional_sections_are_omitted():
    card = StatusCard(title="Minimal", status="ok")

    assert render_status_card(card) == """## Minimal
Status: ok"""
