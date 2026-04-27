from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.cockpit.actions import CockpitActionStore, SafetyLevel
from gateway.cockpit.review import (
    REVIEW_STEPS,
    build_review_keyboard_spec,
    build_review_prompt,
    render_review_wizard,
    start_review_flow,
)
from gateway.cockpit.state import InteractionStateStore
from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platforms.base import MessageEvent
from gateway.session import SessionEntry, SessionSource, build_session_key


def _source() -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        chat_id="c1",
        user_id="u1",
        user_name="tester",
        chat_type="dm",
    )


def _event(text: str = "/review") -> MessageEvent:
    return MessageEvent(text=text, source=_source(), message_id="m1")


def _runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(platforms={Platform.TELEGRAM: PlatformConfig(enabled=True, token="***")})
    runner.adapters = {Platform.TELEGRAM: MagicMock()}
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._background_tasks = set()
    runner._session_model_overrides = {}
    runner._session_reasoning_overrides = {}
    runner._session_db = None
    runner._review_state_store = InteractionStateStore()

    session_key = build_session_key(_source())
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = SessionEntry(
        session_key=session_key,
        session_id="sess-review",
        created_at=datetime(2026, 4, 26, 20, 30),
        updated_at=datetime(2026, 4, 26, 22, 30),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        total_tokens=0,
    )
    runner.hooks = MagicMock()
    runner.hooks.emit_collect = AsyncMock(return_value=[])
    return runner


def test_review_wizard_renders_first_step_and_prompt_preview():
    store = InteractionStateStore()
    state = start_review_flow(store, chat_id="c1", user_id="u1")

    rendered = render_review_wizard(state)

    assert "## Review Cockpit" in rendered
    assert "Status: choosing scope" in rendered
    assert "Step: 1/5 · Scope" in rendered
    assert "Working diff" in rendered and "Pull request" in rendered and "Project path" in rendered
    assert "Selected: none" in rendered
    assert "Next actions" in rendered

    prompt = build_review_prompt(
        {"scope": "diff", "checks": "full", "runner": "codex", "output": "report", "target": "/repo"}
    )
    assert "Review target: /repo" in prompt
    assert "Scope: Working diff" in prompt
    assert "Checks: Full review" in prompt
    assert "Runner: Codex" in prompt
    assert "Output: Report" in prompt


def test_review_keyboard_registers_step_options_as_compact_callbacks():
    flow_store = InteractionStateStore()
    action_store = CockpitActionStore()
    state = start_review_flow(flow_store, chat_id="c1", user_id="u1")

    keyboard = build_review_keyboard_spec(state, store=action_store, chat_id="c1", user_id="u1")

    labels = [button.label for row in keyboard.rows for button in row]
    callbacks = [button.callback_data for row in keyboard.rows for button in row]
    assert labels == ["Working diff", "Pull request", "Project path"]
    assert all(callback.startswith("cx:") for callback in callbacks)

    action_id = callbacks[0].removeprefix("cx:")
    action = action_store.get(action_id)
    assert action is not None
    assert action.kind == "review.select"
    assert action.payload == {"flow_id": state.flow_id, "step": "scope", "value": "diff"}
    assert action.safety_level == SafetyLevel.SAFE


def test_review_flow_advances_to_confirmation_with_target():
    store = InteractionStateStore()
    state = start_review_flow(store, chat_id="c1", user_id="u1")

    for key, value in (
        ("scope", "diff"),
        ("checks", "full"),
        ("runner", "codex"),
        ("output", "report"),
        ("target", "/repo"),
    ):
        state = store.answer(state.flow_id, chat_id="c1", user_id="u1", key=key, value=value, next_step=REVIEW_STEPS.next_step(key))
        assert state is not None

    rendered = render_review_wizard(state)

    assert "Status: ready for confirmation" in rendered
    assert "Step: 5/5 · Confirm" in rendered
    assert "Review target: /repo" in rendered
    assert "Scope: Working diff" in rendered
    assert "Checks: Full review" in rendered
    assert "Runner: Codex" in rendered
    assert "Output: Report" in rendered
    assert "Confirm with: /review confirm" in rendered


@pytest.mark.asyncio
async def test_review_command_starts_wizard_and_supports_text_choices():
    runner = _runner()

    start_result = await runner._handle_review_command(_event("/review"))
    scope_result = await runner._handle_review_command(_event("/review scope diff"))
    checks_result = await runner._handle_review_command(_event("/review checks full"))
    runner_result = await runner._handle_review_command(_event("/review runner codex"))
    output_result = await runner._handle_review_command(_event("/review output report"))
    target_result = await runner._handle_review_command(_event("/review target /repo"))
    confirm_result = await runner._handle_review_command(_event("/review confirm"))

    assert "Status: choosing scope" in start_result
    assert "Status: choosing checks" in scope_result
    assert "Status: choosing runner" in checks_result
    assert "Status: choosing output" in runner_result
    assert "Status: collecting target" in output_result
    assert "Status: ready for confirmation" in target_result
    assert "Confirmed review request" in confirm_result
    assert "Review target: /repo" in confirm_result
    assert "Checks: Full review" in confirm_result


@pytest.mark.asyncio
async def test_review_command_dispatches_from_gateway_message(monkeypatch):
    runner = _runner()
    monkeypatch.setattr(runner, "_is_user_authorized", lambda source: True)
    runner._handle_review_command = AsyncMock(return_value="review ok")

    result = await runner._handle_message(_event("/review"))

    assert result == "review ok"
    runner._handle_review_command.assert_awaited_once()


def test_review_command_is_registered_for_gateway_surfaces():
    from hermes_cli.commands import ACTIVE_SESSION_BYPASS_COMMANDS, resolve_command

    command = resolve_command("review")

    assert command is not None
    assert command.name == "review"
    assert command.gateway_only is True
    assert "review" in ACTIVE_SESSION_BYPASS_COMMANDS
