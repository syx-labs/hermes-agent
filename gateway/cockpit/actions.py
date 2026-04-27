"""Server-side action records for Telegram Cockpit callbacks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Callable, Mapping
from uuid import uuid4


CALLBACK_PREFIX = "cx:"
DEFAULT_ACTION_TTL = timedelta(minutes=15)


class SafetyLevel(StrEnum):
    """Safety policy for interactive cockpit actions."""

    SAFE = "safe"
    CONFIRM = "confirm"
    SENSITIVE = "sensitive"


@dataclass(frozen=True)
class CockpitAction:
    """A compact callback target stored server-side."""

    id: str
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    chat_id: str | None = None
    user_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + DEFAULT_ACTION_TTL)
    safety_level: SafetyLevel = SafetyLevel.SAFE


class CockpitActionStore:
    """In-memory TTL store for compact Telegram callback actions."""

    def __init__(self, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._actions: dict[str, CockpitAction] = {}

    def create(
        self,
        *,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        chat_id: str | None = None,
        user_id: str | None = None,
        ttl: timedelta = DEFAULT_ACTION_TTL,
        safety_level: SafetyLevel = SafetyLevel.SAFE,
    ) -> CockpitAction:
        self.prune_expired()
        created_at = self._now()
        action = CockpitAction(
            id=self._new_id(),
            kind=kind,
            payload=dict(payload or {}),
            chat_id=str(chat_id) if chat_id is not None else None,
            user_id=str(user_id) if user_id is not None else None,
            created_at=created_at,
            expires_at=created_at + ttl,
            safety_level=safety_level,
        )
        self._actions[action.id] = action
        return action

    def get(self, action_id: str) -> CockpitAction | None:
        action = self._actions.get(action_id)
        if not action:
            return None
        if self._is_expired(action):
            self._actions.pop(action_id, None)
            return None
        return action

    def consume(self, action_id: str) -> CockpitAction | None:
        action = self.get(action_id)
        if action:
            self._actions.pop(action_id, None)
        return action

    def prune_expired(self) -> None:
        expired_ids = [
            action_id
            for action_id, action in self._actions.items()
            if self._is_expired(action)
        ]
        for action_id in expired_ids:
            self._actions.pop(action_id, None)

    def _is_expired(self, action: CockpitAction) -> bool:
        return action.expires_at <= self._now()

    @staticmethod
    def _new_id() -> str:
        # 16 hex chars keeps callback_data at 19 bytes with the cx: prefix.
        return uuid4().hex[:16]


def callback_data_for(action_id: str) -> str:
    """Return compact Telegram callback data for a cockpit action id."""

    return f"{CALLBACK_PREFIX}{action_id}"


def is_cockpit_callback(data: str | None) -> bool:
    return bool(data and data.startswith(CALLBACK_PREFIX))


def parse_cockpit_callback(data: str | None) -> str | None:
    if not is_cockpit_callback(data):
        return None
    action_id = str(data)[len(CALLBACK_PREFIX) :].strip()
    return action_id or None
