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


def _event(text: str = "/jobs") -> MessageEvent:
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
        session_id="sess-jobs",
        created_at=datetime(2026, 4, 26, 20, 30),
        updated_at=datetime(2026, 4, 26, 22, 30),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        total_tokens=0,
    )
    runner.hooks = MagicMock()
    runner.hooks.emit_collect = MagicMock(return_value=[])
    return runner


@pytest.mark.asyncio
async def test_jobs_command_renders_cockpit_dashboard(monkeypatch):
    runner = _runner()

    def fake_list_jobs(include_disabled: bool = True):
        assert include_disabled is True
        return [
            {
                "id": "job-1",
                "name": "Daily briefing",
                "state": "scheduled",
                "enabled": True,
                "schedule_display": "0 9 * * *",
                "deliver": "origin",
                "last_run_at": None,
                "next_run_at": "2026-04-27T09:00:00",
                "repeat": {"completed": 0, "times": None},
            }
        ]

    monkeypatch.setattr("cron.jobs.list_jobs", fake_list_jobs)

    result = await runner._handle_jobs_command(_event())

    assert "## Cron Jobs Cockpit" in result
    assert "Status: 1 job" in result
    assert "1. Daily briefing · scheduled" in result
    assert "Actions: /jobs run job-1 | /jobs pause job-1 | /jobs edit job-1" in result


@pytest.mark.asyncio
async def test_jobs_command_sends_inline_keyboard_on_telegram(monkeypatch):
    runner = _runner()
    adapter = MagicMock()
    adapter._cockpit_action_store = CockpitActionStore()
    adapter.send = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}

    def fake_list_jobs(include_disabled: bool = True):
        assert include_disabled is True
        return [
            {"id": "job-1", "name": "Daily briefing", "state": "scheduled", "enabled": True},
            {"id": "job-2", "name": "Paused briefing", "state": "paused", "enabled": True},
        ]

    monkeypatch.setattr("cron.jobs.list_jobs", fake_list_jobs)

    result = await runner._handle_jobs_command(_event())

    assert result is None
    adapter.send.assert_awaited_once()
    _, content = adapter.send.await_args.args[:2]
    metadata = adapter.send.await_args.kwargs["metadata"]
    keyboard = metadata["cockpit_keyboard"]
    labels = [button.label for row in keyboard.rows for button in row]
    assert "## Cron Jobs Cockpit" in content
    assert "Run job-1" in labels
    assert "Pause job-1" in labels
    assert "Resume job-2" in labels
    assert all(button.callback_data.startswith("cx:") for row in keyboard.rows for button in row)


@pytest.mark.asyncio
async def test_jobs_command_sends_empty_state_inline_keyboard_on_telegram(monkeypatch):
    runner = _runner()
    adapter = MagicMock()
    adapter._cockpit_action_store = CockpitActionStore()
    adapter.send = AsyncMock()
    runner.adapters = {Platform.TELEGRAM: adapter}

    monkeypatch.setattr("cron.jobs.list_jobs", lambda include_disabled=True: [])

    result = await runner._handle_jobs_command(_event())

    assert result is None
    adapter.send.assert_awaited_once()
    _, content = adapter.send.await_args.args[:2]
    metadata = adapter.send.await_args.kwargs["metadata"]
    keyboard = metadata["cockpit_keyboard"]
    labels = [button.label for row in keyboard.rows for button in row]
    assert "Status: empty" in content
    assert labels == ["Create first cronjob", "Cron docs"]
    assert all(button.callback_data.startswith("cx:") for row in keyboard.rows for button in row)


@pytest.mark.asyncio
async def test_jobs_command_can_show_create_and_docs_guidance():
    runner = _runner()

    create_result = await runner._handle_jobs_command(_event("/jobs create"))
    docs_result = await runner._handle_jobs_command(_event("/jobs docs"))

    assert "To create a cronjob" in create_result
    assert "schedule and the task" in create_result
    assert "Cron jobs docs:" in docs_result
    assert "docs/user-guide/features/cron" in docs_result


@pytest.mark.asyncio
async def test_jobs_command_can_trigger_pause_resume_and_explain_edit(monkeypatch):
    runner = _runner()
    calls = []

    def fake_trigger(job_id: str):
        calls.append(("run", job_id))
        return {"id": job_id, "name": "Daily briefing", "next_run_at": "2026-04-26T22:31:00"}

    def fake_pause(job_id: str, reason: str | None = None):
        calls.append(("pause", job_id, reason))
        return {"id": job_id, "name": "Daily briefing", "state": "paused"}

    def fake_resume(job_id: str):
        calls.append(("resume", job_id))
        return {"id": job_id, "name": "Daily briefing", "state": "scheduled"}

    monkeypatch.setattr("cron.jobs.trigger_job", fake_trigger)
    monkeypatch.setattr("cron.jobs.pause_job", fake_pause)
    monkeypatch.setattr("cron.jobs.resume_job", fake_resume)

    assert await runner._handle_jobs_command(_event("/jobs run job-1")) == "Scheduled job `job-1` to run on the next scheduler tick."
    assert await runner._handle_jobs_command(_event("/jobs pause job-1")) == "Paused job `job-1`."
    assert await runner._handle_jobs_command(_event("/jobs resume job-1")) == "Resumed job `job-1`."
    edit_result = await runner._handle_jobs_command(_event("/jobs edit job-1"))

    assert calls == [
        ("run", "job-1"),
        ("pause", "job-1", "manual from /jobs"),
        ("resume", "job-1"),
    ]
    assert "Edit job `job-1` with the cronjob tool" in edit_result
    assert "action='update'" in edit_result


@pytest.mark.asyncio
async def test_jobs_command_reports_missing_job_for_actions(monkeypatch):
    runner = _runner()
    monkeypatch.setattr("cron.jobs.trigger_job", lambda job_id: None)

    result = await runner._handle_jobs_command(_event("/jobs run missing"))

    assert result == "Job `missing` was not found. Run /jobs to see available job IDs."


@pytest.mark.asyncio
async def test_jobs_command_dispatches_from_gateway_message(monkeypatch):
    runner = _runner()
    monkeypatch.setattr(runner, "_is_user_authorized", lambda source: True)
    runner._handle_jobs_command = AsyncMock(return_value="jobs ok")

    result = await runner._handle_message(_event("/jobs"))

    assert result == "jobs ok"
    runner._handle_jobs_command.assert_called_once()


def test_jobs_command_is_registered_for_gateway_surfaces():
    from hermes_cli.commands import ACTIVE_SESSION_BYPASS_COMMANDS, resolve_command

    command = resolve_command("jobs")

    assert command is not None
    assert command.name == "jobs"
    assert command.gateway_only is True
    assert "jobs" in ACTIVE_SESSION_BYPASS_COMMANDS
