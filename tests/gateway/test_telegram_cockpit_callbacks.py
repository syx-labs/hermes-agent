"""Tests for Telegram Cockpit callback routing."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_repo = str(Path(__file__).resolve().parents[2])
if _repo not in sys.path:
    sys.path.insert(0, _repo)

from tests.gateway.test_telegram_approval_buttons import _ensure_telegram_mock

_ensure_telegram_mock()

from gateway.config import PlatformConfig
from gateway.cockpit.actions import CockpitActionStore, SafetyLevel
from gateway.cockpit.keyboards import ButtonSpec, build_cockpit_keyboard_spec
import gateway.platforms.telegram as telegram_mod
from gateway.platforms.telegram import TelegramAdapter


class _FakeInlineKeyboardButton:
    def __init__(self, text, callback_data=None):
        self.text = text
        self.callback_data = callback_data


class _FakeInlineKeyboardMarkup:
    def __init__(self, inline_keyboard):
        self.inline_keyboard = inline_keyboard


telegram_mod.InlineKeyboardButton = _FakeInlineKeyboardButton
telegram_mod.InlineKeyboardMarkup = _FakeInlineKeyboardMarkup


def _make_adapter(extra=None):
    config = PlatformConfig(enabled=True, token="test-token", extra=extra or {})
    adapter = TelegramAdapter(config)
    adapter._bot = AsyncMock()
    adapter._app = MagicMock()
    return adapter


def _query(data="cx:missing", *, chat_id=12345, user_id=111):
    query = AsyncMock()
    query.data = data
    query.message = MagicMock()
    query.message.chat_id = chat_id
    query.from_user = MagicMock()
    query.from_user.id = user_id
    query.from_user.first_name = "Gabriel"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    return query


@pytest.mark.asyncio
async def test_cockpit_callback_routes_before_legacy_callbacks(monkeypatch):
    adapter = _make_adapter()
    adapter._message_handler = AsyncMock(return_value=None)
    adapter.handle_message = AsyncMock()
    action = adapter._cockpit_action_store.create(
        kind="research.select",
        payload={"flow_id": "f1", "step": "depth", "value": "deep"},
        chat_id="12345",
        user_id="111",
        safety_level=SafetyLevel.SAFE,
    )
    query = _query(data=f"cx:{action.id}")
    update = MagicMock(callback_query=query)

    await adapter._handle_callback_query(update, MagicMock())

    query.answer.assert_called_once_with(text="Action received")
    query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)
    adapter.handle_message.assert_awaited_once()
    dispatched_event = adapter.handle_message.call_args.args[0]
    assert dispatched_event.text == "/research depth deep"
    assert adapter._cockpit_action_store.get(action.id) is None


@pytest.mark.asyncio
async def test_cockpit_callback_rejects_wrong_user():
    adapter = _make_adapter()
    action = adapter._cockpit_action_store.create(
        kind="execute",
        chat_id="12345",
        user_id="111",
        safety_level=SafetyLevel.SAFE,
    )
    query = _query(data=f"cx:{action.id}", user_id=222)
    update = MagicMock(callback_query=query)

    await adapter._handle_callback_query(update, MagicMock())

    query.answer.assert_called_once()
    assert "not authorized" in query.answer.call_args[1]["text"].lower()
    assert adapter._cockpit_action_store.get(action.id) == action


def test_telegram_send_attaches_cockpit_keyboard_metadata():
    adapter = _make_adapter()
    action_store = CockpitActionStore()
    keyboard = build_cockpit_keyboard_spec(
        rows=((ButtonSpec("Deep research", "research.select", {"step": "depth", "value": "deep"}),),),
        store=action_store,
        chat_id="12345",
        user_id="111",
    )

    reply_markup = adapter._metadata_reply_markup({"cockpit_keyboard": keyboard})

    assert reply_markup is not None
    assert reply_markup.inline_keyboard[0][0].text == "Deep research"
    assert reply_markup.inline_keyboard[0][0].callback_data.startswith("cx:")


@pytest.mark.asyncio
async def test_telegram_send_passes_cockpit_keyboard_to_send_message():
    adapter = _make_adapter()
    mock_msg = MagicMock()
    mock_msg.message_id = 42
    adapter._bot.send_message = AsyncMock(return_value=mock_msg)
    keyboard = build_cockpit_keyboard_spec(
        rows=((ButtonSpec("Confirm", "research.confirm", {"flow_id": "f1"}),),),
        store=adapter._cockpit_action_store,
        chat_id="12345",
        user_id="111",
    )

    result = await adapter.send("12345", "Research Cockpit", metadata={"cockpit_keyboard": keyboard})

    assert result.success is True
    kwargs = adapter._bot.send_message.call_args.kwargs
    assert kwargs["reply_markup"] is not None
    assert kwargs["reply_markup"].inline_keyboard[0][0].text == "Confirm"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "payload", "expected"),
    [
        ("cron.run", {"job_id": "job-1"}, "/jobs run job-1"),
        ("cron.pause", {"job_id": "job-1"}, "/jobs pause job-1"),
        ("cron.resume", {"job_id": "job-1"}, "/jobs resume job-1"),
        ("cron.create", {}, "/jobs create"),
        ("cron.docs", {}, "/jobs docs"),
        ("project.continue", {"project": "repo"}, "/projects continue repo"),
        ("project.inspect", {"project": "repo"}, "/projects inspect repo"),
        ("project.review", {"project": "repo"}, "/projects review repo"),
        ("project.diagram", {"project": "repo"}, "/projects diagram repo"),
    ],
)
async def test_cockpit_callback_maps_jobs_and_projects_to_commands(kind, payload, expected):
    adapter = _make_adapter()
    adapter._message_handler = AsyncMock(return_value=None)
    adapter.handle_message = AsyncMock()
    action = adapter._cockpit_action_store.create(
        kind=kind,
        payload=payload,
        chat_id="12345",
        user_id="111",
        safety_level=SafetyLevel.SAFE,
    )
    query = _query(data=f"cx:{action.id}")
    update = MagicMock(callback_query=query)

    await adapter._handle_callback_query(update, MagicMock())

    query.answer.assert_called_once_with(text="Action received")
    query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)
    dispatched_event = adapter.handle_message.call_args.args[0]
    assert dispatched_event.text == expected


@pytest.mark.asyncio
async def test_cockpit_callback_requires_confirmation_for_confirm_actions():
    adapter = _make_adapter()
    adapter._message_handler = AsyncMock(return_value=None)
    adapter.handle_message = AsyncMock()
    action = adapter._cockpit_action_store.create(
        kind="cron.run",
        payload={"job_id": "job-1"},
        chat_id="12345",
        user_id="111",
        safety_level=SafetyLevel.CONFIRM,
    )
    query = _query(data=f"cx:{action.id}")
    update = MagicMock(callback_query=query)

    await adapter._handle_callback_query(update, MagicMock())

    query.answer.assert_called_once_with(text="Please confirm this action.")
    adapter.handle_message.assert_not_awaited()
    markup = query.edit_message_reply_markup.await_args.kwargs["reply_markup"]
    assert [button.text for button in markup.inline_keyboard[0]] == ["Confirm", "Cancel"]
    assert adapter._cockpit_action_store.get(action.id) == action


@pytest.mark.asyncio
async def test_cockpit_callback_does_not_double_confirm_flow_confirm_buttons():
    adapter = _make_adapter()
    adapter._message_handler = AsyncMock(return_value=None)
    adapter.handle_message = AsyncMock()
    action = adapter._cockpit_action_store.create(
        kind="research.confirm",
        payload={"flow_id": "f1"},
        chat_id="12345",
        user_id="111",
        safety_level=SafetyLevel.CONFIRM,
    )
    query = _query(data=f"cx:{action.id}")
    update = MagicMock(callback_query=query)

    await adapter._handle_callback_query(update, MagicMock())

    query.answer.assert_called_once_with(text="Action received")
    query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)
    dispatched_event = adapter.handle_message.call_args.args[0]
    assert dispatched_event.text == "/research confirm"


@pytest.mark.asyncio
async def test_cockpit_callback_confirm_button_executes_original_action():
    adapter = _make_adapter()
    adapter._message_handler = AsyncMock(return_value=None)
    adapter.handle_message = AsyncMock()
    original = adapter._cockpit_action_store.create(
        kind="cron.pause",
        payload={"job_id": "job-1"},
        chat_id="12345",
        user_id="111",
        safety_level=SafetyLevel.CONFIRM,
    )
    confirm = adapter._cockpit_action_store.create(
        kind="cockpit.confirm",
        payload={"action_id": original.id},
        chat_id="12345",
        user_id="111",
    )
    query = _query(data=f"cx:{confirm.id}")
    update = MagicMock(callback_query=query)

    await adapter._handle_callback_query(update, MagicMock())

    query.answer.assert_called_once_with(text="Action received")
    query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)
    dispatched_event = adapter.handle_message.call_args.args[0]
    assert dispatched_event.text == "/jobs pause job-1"
    assert adapter._cockpit_action_store.get(original.id) is None
    assert adapter._cockpit_action_store.get(confirm.id) is None


@pytest.mark.asyncio
async def test_cockpit_callback_cancel_consumes_original_action():
    adapter = _make_adapter()
    original = adapter._cockpit_action_store.create(
        kind="cron.run",
        payload={"job_id": "job-1"},
        chat_id="12345",
        user_id="111",
        safety_level=SafetyLevel.CONFIRM,
    )
    cancel = adapter._cockpit_action_store.create(
        kind="cockpit.cancel",
        payload={"action_id": original.id},
        chat_id="12345",
        user_id="111",
    )
    query = _query(data=f"cx:{cancel.id}")
    update = MagicMock(callback_query=query)

    await adapter._handle_callback_query(update, MagicMock())

    query.answer.assert_called_once_with(text="Action cancelled")
    query.edit_message_reply_markup.assert_awaited_once_with(reply_markup=None)
    assert adapter._cockpit_action_store.get(original.id) is None
    assert adapter._cockpit_action_store.get(cancel.id) is None


@pytest.mark.asyncio
async def test_cockpit_callback_reports_expired_or_missing_action():
    adapter = _make_adapter()
    query = _query(data="cx:does-not-exist")
    update = MagicMock(callback_query=query)

    await adapter._handle_callback_query(update, MagicMock())

    query.answer.assert_called_once()
    assert "expired" in query.answer.call_args[1]["text"].lower()
