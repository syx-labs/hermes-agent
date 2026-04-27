from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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


def _event(text: str = "/status") -> MessageEvent:
    return MessageEvent(text=text, source=_source(), message_id="m1")


def _entry(session_id: str, *, minutes_ago: int, tokens: int = 0) -> SessionEntry:
    now = datetime(2026, 4, 26, 22, 30)
    return SessionEntry(
        session_key=f"telegram:c1:{session_id}",
        session_id=session_id,
        created_at=now - timedelta(hours=2),
        updated_at=now - timedelta(minutes=minutes_ago),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        total_tokens=tokens,
    )


def _runner():
    from gateway.run import GatewayRunner

    runner = object.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={
            Platform.TELEGRAM: PlatformConfig(enabled=True, token="***"),
            Platform.DISCORD: PlatformConfig(enabled=True, token="***"),
        }
    )
    runner.adapters = {Platform.TELEGRAM: MagicMock()}
    runner._running_agents = {}
    runner._running_agents_ts = {}
    runner._background_tasks = set()
    runner._session_model_overrides = {}
    runner._session_reasoning_overrides = {}
    runner._session_db = MagicMock()
    runner._session_db.get_session_title.return_value = "Cockpit buildout"

    current_key = build_session_key(_source())
    current = SessionEntry(
        session_key=current_key,
        session_id="sess-current",
        created_at=datetime(2026, 4, 26, 20, 30),
        updated_at=datetime(2026, 4, 26, 22, 30),
        platform=Platform.TELEGRAM,
        chat_type="dm",
        total_tokens=1234,
    )
    older = _entry("sess-older", minutes_ago=30, tokens=456)
    runner.session_store = MagicMock()
    runner.session_store.get_or_create_session.return_value = current
    runner.session_store._entries = {
        current.session_key: current,
        older.session_key: older,
    }
    return runner


@pytest.mark.asyncio
async def test_status_command_renders_cockpit_dashboard(monkeypatch):
    runner = _runner()
    session_key = build_session_key(_source())
    runner._running_agents[session_key] = SimpleNamespace(model="session/model")
    runner._session_model_overrides[session_key] = {
        "provider": "openrouter",
        "model": "anthropic/claude-sonnet-4-5",
    }
    monkeypatch.setenv("HERMES_MODEL", "fallback/model")
    monkeypatch.setenv("HERMES_INFERENCE_PROVIDER", "fallback-provider")
    monkeypatch.setenv("HERMES_ENABLED_TOOLSETS", "terminal,file,web")

    result = await runner._handle_status_command(_event())

    assert "## Hermes Telegram Cockpit" in result
    assert "Status: operational" in result
    assert "Profile:" in result
    assert "Model: openrouter/anthropic/claude-sonnet-4-5" in result
    assert "Tools: terminal, file, web" in result
    assert "Jobs: 0 scheduled" in result
    assert "Processes: 0 running" in result
    assert "Recent sessions: sess-current, sess-older" in result
    assert "Connectivity: telegram connected; discord configured" in result
    assert "Session: sess-current" in result
    assert "Title: Cockpit buildout" in result
    assert "Agent: running" in result
    assert "Next actions:" in result
    assert "Continue — Atualizar status" in result
    assert "Detail — Abrir detalhes de agentes, jobs e processos" in result


@pytest.mark.asyncio
async def test_status_command_handles_minimal_runtime(monkeypatch):
    runner = _runner()
    runner.adapters = {}
    runner.session_store._entries = {}
    runner._session_db.get_session_title.side_effect = RuntimeError("db down")
    monkeypatch.delenv("HERMES_MODEL", raising=False)
    monkeypatch.delenv("HERMES_INFERENCE_PROVIDER", raising=False)
    monkeypatch.delenv("HERMES_ENABLED_TOOLSETS", raising=False)

    result = await runner._handle_status_command(_event())

    assert "Model: auto" in result
    assert "Tools: default" in result
    assert "Connectivity: telegram configured; discord configured" in result
    assert "Agent: idle" in result
