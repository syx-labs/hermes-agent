from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.cockpit.actions import CockpitActionStore, SafetyLevel
from gateway.cockpit.newtask import (
    NEWTASK_STEPS,
    build_newtask_keyboard_spec,
    build_newtask_prompt,
    render_newtask_wizard,
    start_newtask_flow,
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


def _event(text: str = "/newtask") -> MessageEvent:
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
    runner._newtask_state_store = InteractionStateStore()

    session_key = build_session_key(_source())
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = SessionEntry(
        session_key=session_key,
        session_id="sess-newtask",
        created_at=datetime(2026, 4, 26, 20, 30),
        updated_at=datetime(2026, 4, 26, 22, 30),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        total_tokens=0,
    )
    runner.hooks = MagicMock()
    runner.hooks.emit_collect = AsyncMock(return_value=[])
    return runner


def test_newtask_wizard_renders_first_step_and_prompt_preview():
    store = InteractionStateStore()
    state = start_newtask_flow(store, chat_id="c1", user_id="u1")

    rendered = render_newtask_wizard(state)

    assert "## New Task Cockpit" in rendered
    assert "Status: choosing type" in rendered
    assert "Step: 1/5 · Type" in rendered
    assert "Code" in rendered and "Research" in rendered and "Automation" in rendered
    assert "Selected: none" in rendered
    assert "Next actions" in rendered

    prompt = build_newtask_prompt(
        {"type": "code", "mode": "execute", "agent": "codex", "deliverable": "pr"}
    )
    assert "Task type: Code" in prompt
    assert "Mode: Execute" in prompt
    assert "Agent: Codex" in prompt
    assert "Deliverable: PR" in prompt


def test_newtask_keyboard_registers_step_options_as_compact_callbacks():
    flow_store = InteractionStateStore()
    action_store = CockpitActionStore()
    state = start_newtask_flow(flow_store, chat_id="c1", user_id="u1")

    keyboard = build_newtask_keyboard_spec(state, store=action_store, chat_id="c1", user_id="u1")

    labels = [button.label for row in keyboard.rows for button in row]
    callbacks = [button.callback_data for row in keyboard.rows for button in row]
    assert labels[:3] == ["Code", "Research", "Document"]
    assert all(callback.startswith("cx:") for callback in callbacks)

    action_id = callbacks[0].removeprefix("cx:")
    action = action_store.get(action_id)
    assert action is not None
    assert action.kind == "newtask.select"
    assert action.payload == {"flow_id": state.flow_id, "step": "type", "value": "code"}
    assert action.safety_level == SafetyLevel.SAFE


def test_newtask_flow_advances_through_confirm_and_builds_prompt():
    store = InteractionStateStore()
    state = start_newtask_flow(store, chat_id="c1", user_id="u1")

    for key, value in (
        ("type", "code"),
        ("mode", "execute"),
        ("agent", "codex"),
        ("deliverable", "pr"),
    ):
        state = store.answer(state.flow_id, chat_id="c1", user_id="u1", key=key, value=value, next_step=NEWTASK_STEPS.next_step(key))
        assert state is not None

    rendered = render_newtask_wizard(state)

    assert "Status: ready for confirmation" in rendered
    assert "Step: 5/5 · Confirm" in rendered
    assert "Task type: Code" in rendered
    assert "Mode: Execute" in rendered
    assert "Agent: Codex" in rendered
    assert "Deliverable: PR" in rendered
    assert "Execution/delegation requires explicit confirmation" in rendered


@pytest.mark.asyncio
async def test_newtask_command_starts_wizard_and_supports_text_choices():
    runner = _runner()

    start_result = await runner._handle_newtask_command(_event("/newtask"))
    type_result = await runner._handle_newtask_command(_event("/newtask type code"))
    mode_result = await runner._handle_newtask_command(_event("/newtask mode execute"))
    agent_result = await runner._handle_newtask_command(_event("/newtask agent codex"))
    deliverable_result = await runner._handle_newtask_command(_event("/newtask deliverable pr"))
    confirm_result = await runner._handle_newtask_command(_event("/newtask confirm"))

    assert "## New Task Cockpit" in start_result
    assert "Status: choosing type" in start_result
    assert "Status: choosing mode" in type_result
    assert "Status: choosing agent" in mode_result
    assert "Status: choosing deliverable" in agent_result
    assert "Status: ready for confirmation" in deliverable_result
    assert "Confirmed new task" in confirm_result
    assert "Task type: Code" in confirm_result
    assert "Mode: Execute" in confirm_result
    assert "Agent: Codex" in confirm_result
    assert "Deliverable: PR" in confirm_result


@pytest.mark.asyncio
async def test_newtask_command_dispatches_from_gateway_message(monkeypatch):
    runner = _runner()
    monkeypatch.setattr(runner, "_is_user_authorized", lambda source: True)
    runner._handle_newtask_command = AsyncMock(return_value="newtask ok")

    result = await runner._handle_message(_event("/newtask"))

    assert result == "newtask ok"
    runner._handle_newtask_command.assert_awaited_once()


def test_newtask_command_is_registered_for_gateway_surfaces():
    from hermes_cli.commands import ACTIVE_SESSION_BYPASS_COMMANDS, resolve_command

    command = resolve_command("newtask")

    assert command is not None
    assert command.name == "newtask"
    assert command.gateway_only is True
    assert "newtask" in ACTIVE_SESSION_BYPASS_COMMANDS
