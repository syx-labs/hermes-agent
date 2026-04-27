from datetime import datetime, timedelta, timezone

from gateway.cockpit.actions import (
    CALLBACK_PREFIX,
    CockpitAction,
    CockpitActionStore,
    SafetyLevel,
    callback_data_for,
    is_cockpit_callback,
    parse_cockpit_callback,
)


def test_callback_data_is_compact_and_prefixed():
    assert callback_data_for("abc123") == "cx:abc123"
    assert len(callback_data_for("abc123")) < 64
    assert is_cockpit_callback("cx:abc123") is True
    assert is_cockpit_callback("ea:once:1") is False
    assert CALLBACK_PREFIX == "cx:"


def test_parse_cockpit_callback_rejects_empty_or_wrong_namespace():
    assert parse_cockpit_callback("cx:abc123") == "abc123"
    assert parse_cockpit_callback("cx:") is None
    assert parse_cockpit_callback("mp:abc123") is None


def test_action_store_create_get_consume_and_expire():
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    store = CockpitActionStore(now=lambda: now)

    action = store.create(
        kind="continue",
        payload={"todo": "ux-06"},
        chat_id="123",
        user_id="456",
        ttl=timedelta(seconds=30),
    )

    assert action.id
    assert action.kind == "continue"
    assert action.payload == {"todo": "ux-06"}
    assert action.chat_id == "123"
    assert action.user_id == "456"
    assert action.safety_level is SafetyLevel.SAFE
    assert action.expires_at == now + timedelta(seconds=30)
    assert store.get(action.id) == action

    consumed = store.consume(action.id)
    assert consumed == action
    assert store.get(action.id) is None

    expiring = store.create(kind="detail", ttl=timedelta(seconds=1))
    store._now = lambda: now + timedelta(seconds=2)
    assert store.get(expiring.id) is None


def test_action_store_prunes_expired_records_before_create():
    now = datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc)
    store = CockpitActionStore(now=lambda: now)
    expired = CockpitAction(
        id="old",
        kind="detail",
        payload={},
        chat_id=None,
        user_id=None,
        created_at=now - timedelta(minutes=10),
        expires_at=now - timedelta(minutes=9),
        safety_level=SafetyLevel.SAFE,
    )
    store._actions[expired.id] = expired

    store.create(kind="execute")

    assert "old" not in store._actions
