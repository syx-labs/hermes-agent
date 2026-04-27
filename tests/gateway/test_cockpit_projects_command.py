from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.cockpit.actions import CockpitActionStore
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


def _event(text: str = "/projects") -> MessageEvent:
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

    session_key = build_session_key(_source())
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = SessionEntry(
        session_key=session_key,
        session_id="sess-projects",
        created_at=datetime(2026, 4, 26, 20, 30),
        updated_at=datetime(2026, 4, 26, 22, 30),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        total_tokens=0,
    )
    runner.hooks = MagicMock()
    runner.hooks.emit_collect = AsyncMock(return_value=[])
    return runner


@pytest.mark.asyncio
async def test_projects_command_renders_cockpit_dashboard(monkeypatch, tmp_path):
    runner = _runner()
    project_path = tmp_path / "repo"
    project_path.mkdir()
    registry_path = tmp_path / "projects.yaml"
    registry_path.write_text(
        f"""
projects:
  - name: repo
    aliases: [r]
    path: {project_path}
    skills: [test-driven-development]
    last_session: sess-repo
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_COCKPIT_PROJECTS_FILE", str(registry_path))

    result = await runner._handle_projects_command(_event())

    assert "## Projects Cockpit" in result
    assert "Status: 1 project" in result
    assert "1. repo · available" in result
    assert "Path:" in result
    assert "Skills: test-driven-development" in result
    assert "Actions: /projects continue repo | /projects inspect repo | /projects review repo | /projects diagram repo" in result


@pytest.mark.asyncio
async def test_projects_command_sends_inline_keyboard_on_telegram(monkeypatch, tmp_path):
    runner = _runner()
    adapter = MagicMock()
    adapter._cockpit_action_store = CockpitActionStore()
    adapter.send = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}

    project_path = tmp_path / "repo"
    project_path.mkdir()
    registry_path = tmp_path / "projects.yaml"
    registry_path.write_text(
        f"""
projects:
  - name: repo
    aliases: [r]
    path: {project_path}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_COCKPIT_PROJECTS_FILE", str(registry_path))

    result = await runner._handle_projects_command(_event())

    assert result is None
    adapter.send.assert_awaited_once()
    _, content = adapter.send.await_args.args[:2]
    metadata = adapter.send.await_args.kwargs["metadata"]
    keyboard = metadata["cockpit_keyboard"]
    labels = [button.label for row in keyboard.rows for button in row]
    assert "## Projects Cockpit" in content
    assert "Continue repo" in labels
    assert "Inspect repo" in labels
    assert "Review repo" in labels
    assert "Diagram repo" in labels
    assert all(button.callback_data.startswith("cx:") for row in keyboard.rows for button in row)


@pytest.mark.asyncio
async def test_projects_command_supports_project_action_intents(monkeypatch, tmp_path):
    runner = _runner()
    project_path = tmp_path / "repo"
    project_path.mkdir()
    registry_path = tmp_path / "projects.yaml"
    registry_path.write_text(
        f"""
projects:
  - name: repo
    aliases: [r]
    path: {project_path}
    context: Demo project
    skills: [test-driven-development]
    commands:
      test: bun run test
    last_session: sess-repo
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_COCKPIT_PROJECTS_FILE", str(registry_path))

    continue_result = await runner._handle_projects_command(_event("/projects continue r"))
    inspect_result = await runner._handle_projects_command(_event("/projects inspect repo"))
    review_result = await runner._handle_projects_command(_event("/projects review repo"))
    diagram_result = await runner._handle_projects_command(_event("/projects diagram repo"))
    handoff_result = await runner._handle_projects_command(_event("/projects handoff repo"))

    assert "Resume project `repo` from session `sess-repo`" in continue_result
    assert "Path:" in inspect_result and "Commands: test" in inspect_result
    assert "Code review intent for `repo`" in review_result
    assert "Diagram intent for `repo`" in diagram_result
    assert "Handoff intent for `repo`" in handoff_result


@pytest.mark.asyncio
async def test_projects_command_reports_unknown_project(monkeypatch, tmp_path):
    runner = _runner()
    registry_path = tmp_path / "projects.yaml"
    registry_path.write_text("projects: []\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_COCKPIT_PROJECTS_FILE", str(registry_path))

    result = await runner._handle_projects_command(_event("/projects inspect missing"))

    assert result == "Project `missing` was not found. Run /projects to see registered projects."


@pytest.mark.asyncio
async def test_projects_command_dispatches_from_gateway_message(monkeypatch):
    runner = _runner()
    monkeypatch.setattr(runner, "_is_user_authorized", lambda source: True)
    runner._handle_projects_command = AsyncMock(return_value="projects ok")

    result = await runner._handle_message(_event("/projects"))

    assert result == "projects ok"
    runner._handle_projects_command.assert_awaited_once()


def test_projects_command_is_registered_for_gateway_surfaces():
    from hermes_cli.commands import ACTIVE_SESSION_BYPASS_COMMANDS, resolve_command

    command = resolve_command("projects")

    assert command is not None
    assert command.name == "projects"
    assert command.gateway_only is True
    assert "projects" in ACTIVE_SESSION_BYPASS_COMMANDS
