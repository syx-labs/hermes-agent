from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.cockpit.actions import CockpitActionStore, SafetyLevel
from gateway.cockpit.research import (
    RESEARCH_STEPS,
    build_research_keyboard_spec,
    build_research_prompt,
    render_research_wizard,
    start_research_flow,
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


def _event(text: str = "/research") -> MessageEvent:
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
    runner._research_state_store = InteractionStateStore()

    session_key = build_session_key(_source())
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = SessionEntry(
        session_key=session_key,
        session_id="sess-research",
        created_at=datetime(2026, 4, 26, 20, 30),
        updated_at=datetime(2026, 4, 26, 22, 30),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        total_tokens=0,
    )
    runner.hooks = MagicMock()
    runner.hooks.emit_collect = AsyncMock(return_value=[])
    return runner


def test_research_wizard_renders_first_step_and_prompt_preview():
    store = InteractionStateStore()
    state = start_research_flow(store, chat_id="c1", user_id="u1")

    rendered = render_research_wizard(state)

    assert "## Research Cockpit" in rendered
    assert "Status: choosing depth" in rendered
    assert "Step: 1/4 · Depth" in rendered
    assert "Short summary" in rendered and "Deep research" in rendered and "Comparative" in rendered
    assert "Selected: none" in rendered
    assert "Next actions" in rendered

    prompt = build_research_prompt(
        {"depth": "deep", "output": "obsidian", "artifact": "diagram", "topic": "AI coding agents"}
    )
    assert "Research topic: AI coding agents" in prompt
    assert "Depth: Deep research" in prompt
    assert "Output: Obsidian note" in prompt
    assert "Artifact: Diagram" in prompt


def test_research_keyboard_registers_step_options_as_compact_callbacks():
    flow_store = InteractionStateStore()
    action_store = CockpitActionStore()
    state = start_research_flow(flow_store, chat_id="c1", user_id="u1")

    keyboard = build_research_keyboard_spec(state, store=action_store, chat_id="c1", user_id="u1")

    labels = [button.label for row in keyboard.rows for button in row]
    callbacks = [button.callback_data for row in keyboard.rows for button in row]
    assert labels == ["Short summary", "Deep research", "Comparative"]
    assert all(callback.startswith("cx:") for callback in callbacks)

    action_id = callbacks[1].removeprefix("cx:")
    action = action_store.get(action_id)
    assert action is not None
    assert action.kind == "research.select"
    assert action.payload == {"flow_id": state.flow_id, "step": "depth", "value": "deep"}
    assert action.safety_level == SafetyLevel.SAFE


def test_research_flow_advances_to_confirmation_with_topic():
    store = InteractionStateStore()
    state = start_research_flow(store, chat_id="c1", user_id="u1")

    for key, value in (
        ("depth", "deep"),
        ("output", "obsidian"),
        ("artifact", "diagram"),
        ("topic", "AI coding agents"),
    ):
        state = store.answer(state.flow_id, chat_id="c1", user_id="u1", key=key, value=value, next_step=RESEARCH_STEPS.next_step(key))
        assert state is not None

    rendered = render_research_wizard(state)

    assert "Status: ready for confirmation" in rendered
    assert "Step: 4/4 · Confirm" in rendered
    assert "Research topic: AI coding agents" in rendered
    assert "Depth: Deep research" in rendered
    assert "Output: Obsidian note" in rendered
    assert "Artifact: Diagram" in rendered
    assert "Confirm with: /research confirm" in rendered


@pytest.mark.asyncio
async def test_research_command_starts_wizard_and_supports_text_choices():
    runner = _runner()

    start_result = await runner._handle_research_command(_event("/research"))
    depth_result = await runner._handle_research_command(_event("/research depth deep"))
    output_result = await runner._handle_research_command(_event("/research output obsidian"))
    artifact_result = await runner._handle_research_command(_event("/research artifact diagram"))
    topic_result = await runner._handle_research_command(_event("/research topic AI coding agents"))
    confirm_result = await runner._handle_research_command(_event("/research confirm"))

    assert "Status: choosing depth" in start_result
    assert "Status: choosing output" in depth_result
    assert "Status: choosing artifact" in output_result
    assert "Status: collecting topic" in artifact_result
    assert "Status: ready for confirmation" in topic_result
    assert "Confirmed research request" in confirm_result
    assert "Research topic: AI coding agents" in confirm_result
    assert "Depth: Deep research" in confirm_result
    assert "Output: Obsidian note" in confirm_result
    assert "Artifact: Diagram" in confirm_result


@pytest.mark.asyncio
async def test_research_command_sends_inline_keyboard_on_telegram():
    runner = _runner()
    adapter = MagicMock()
    adapter._cockpit_action_store = CockpitActionStore()
    adapter.send = AsyncMock()
    runner.adapters[Platform.TELEGRAM] = adapter

    result = await runner._handle_research_command(_event("/research"))

    assert result is None
    adapter.send.assert_awaited_once()
    args, kwargs = adapter.send.call_args
    assert args[0] == "c1"
    assert "Status: choosing depth" in args[1]
    keyboard = kwargs["metadata"]["cockpit_keyboard"]
    assert [button.label for row in keyboard.rows for button in row] == [
        "Short summary",
        "Deep research",
        "Comparative",
    ]


@pytest.mark.asyncio
async def test_research_command_dispatches_from_gateway_message(monkeypatch):
    runner = _runner()
    monkeypatch.setattr(runner, "_is_user_authorized", lambda source: True)
    runner._handle_research_command = AsyncMock(return_value="research ok")

    result = await runner._handle_message(_event("/research"))

    assert result == "research ok"
    runner._handle_research_command.assert_awaited_once()


def test_research_command_is_registered_for_gateway_surfaces():
    from hermes_cli.commands import ACTIVE_SESSION_BYPASS_COMMANDS, resolve_command

    command = resolve_command("research")

    assert command is not None
    assert command.name == "research"
    assert command.gateway_only is True
    assert "research" in ACTIVE_SESSION_BYPASS_COMMANDS
