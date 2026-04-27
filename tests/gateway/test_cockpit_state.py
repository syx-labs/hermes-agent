from datetime import datetime, timedelta, timezone

from gateway.cockpit.state import InteractionStateStore


def _clock(start: datetime):
    current = {"now": start}

    def now() -> datetime:
        return current["now"]

    def advance(delta: timedelta) -> None:
        current["now"] = current["now"] + delta

    return now, advance


def test_interaction_state_store_creates_and_advances_flow():
    now, _advance = _clock(datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc))
    store = InteractionStateStore(now=now)

    state = store.create(flow="newtask", chat_id="chat-1", user_id="user-1", step="type")

    assert state.flow == "newtask"
    assert state.chat_id == "chat-1"
    assert state.user_id == "user-1"
    assert state.step == "type"
    assert state.answers == {}
    assert state.expires_at == now() + timedelta(minutes=30)

    updated = store.answer(
        state.flow_id,
        chat_id="chat-1",
        user_id="user-1",
        key="type",
        value="code",
        next_step="mode",
    )

    assert updated is not None
    assert updated.flow_id == state.flow_id
    assert updated.step == "mode"
    assert updated.answers == {"type": "code"}


def test_interaction_state_store_enforces_user_chat_and_expiry():
    now, advance = _clock(datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc))
    store = InteractionStateStore(now=now)
    state = store.create(flow="newtask", chat_id="chat-1", user_id="user-1", step="type")

    assert store.get(state.flow_id, chat_id="chat-2", user_id="user-1") is None
    assert store.get(state.flow_id, chat_id="chat-1", user_id="user-2") is None
    assert store.get(state.flow_id, chat_id="chat-1", user_id="user-1") == state

    advance(timedelta(minutes=31))

    assert store.get(state.flow_id, chat_id="chat-1", user_id="user-1") is None


def test_interaction_state_store_can_complete_flow_once():
    now, _advance = _clock(datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc))
    store = InteractionStateStore(now=now)
    state = store.create(
        flow="newtask",
        chat_id="chat-1",
        user_id="user-1",
        step="confirm",
        answers={"type": "code", "mode": "execute"},
    )

    completed = store.complete(state.flow_id, chat_id="chat-1", user_id="user-1")

    assert completed is not None
    assert completed.answers == {"type": "code", "mode": "execute"}
    assert store.complete(state.flow_id, chat_id="chat-1", user_id="user-1") is None
