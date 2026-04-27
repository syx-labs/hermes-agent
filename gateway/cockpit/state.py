"""Lightweight interaction state for Telegram Cockpit flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping
from uuid import uuid4


DEFAULT_FLOW_TTL = timedelta(minutes=30)


@dataclass(frozen=True)
class InteractionState:
    """A short-lived multi-step Cockpit flow owned by one chat/user."""

    flow_id: str
    flow: str
    chat_id: str
    user_id: str
    step: str
    answers: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + DEFAULT_FLOW_TTL)


class InteractionStateStore:
    """In-memory TTL store for guided Telegram Cockpit flows."""

    def __init__(self, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._states: dict[str, InteractionState] = {}
        self._latest_by_owner_flow: dict[tuple[str, str, str], str] = {}

    def create(
        self,
        *,
        flow: str,
        chat_id: str,
        user_id: str,
        step: str,
        answers: Mapping[str, Any] | None = None,
        ttl: timedelta = DEFAULT_FLOW_TTL,
    ) -> InteractionState:
        self.prune_expired()
        created_at = self._now()
        state = InteractionState(
            flow_id=self._new_id(),
            flow=flow,
            chat_id=str(chat_id),
            user_id=str(user_id),
            step=step,
            answers=dict(answers or {}),
            created_at=created_at,
            updated_at=created_at,
            expires_at=created_at + ttl,
        )
        self._states[state.flow_id] = state
        self._latest_by_owner_flow[self._owner_key(state.flow, state.chat_id, state.user_id)] = state.flow_id
        return state

    def latest(self, *, flow: str, chat_id: str, user_id: str) -> InteractionState | None:
        self.prune_expired()
        flow_id = self._latest_by_owner_flow.get(self._owner_key(flow, chat_id, user_id))
        if not flow_id:
            return None
        return self.get(flow_id, chat_id=chat_id, user_id=user_id)

    def get(self, flow_id: str, *, chat_id: str | None = None, user_id: str | None = None) -> InteractionState | None:
        state = self._states.get(flow_id)
        if not state:
            return None
        if self._is_expired(state):
            self._remove(state)
            return None
        if chat_id is not None and state.chat_id != str(chat_id):
            return None
        if user_id is not None and state.user_id != str(user_id):
            return None
        return state

    def answer(
        self,
        flow_id: str,
        *,
        chat_id: str,
        user_id: str,
        key: str,
        value: Any,
        next_step: str | None,
        ttl: timedelta = DEFAULT_FLOW_TTL,
    ) -> InteractionState | None:
        state = self.get(flow_id, chat_id=chat_id, user_id=user_id)
        if not state:
            return None
        now = self._now()
        answers = dict(state.answers)
        answers[str(key)] = value
        updated = InteractionState(
            flow_id=state.flow_id,
            flow=state.flow,
            chat_id=state.chat_id,
            user_id=state.user_id,
            step=next_step or state.step,
            answers=answers,
            created_at=state.created_at,
            updated_at=now,
            expires_at=now + ttl,
        )
        self._states[updated.flow_id] = updated
        self._latest_by_owner_flow[self._owner_key(updated.flow, updated.chat_id, updated.user_id)] = updated.flow_id
        return updated

    def complete(self, flow_id: str, *, chat_id: str, user_id: str) -> InteractionState | None:
        state = self.get(flow_id, chat_id=chat_id, user_id=user_id)
        if not state:
            return None
        self._remove(state)
        return state

    def prune_expired(self) -> None:
        expired = [state for state in self._states.values() if self._is_expired(state)]
        for state in expired:
            self._remove(state)

    def _remove(self, state: InteractionState) -> None:
        self._states.pop(state.flow_id, None)
        owner_key = self._owner_key(state.flow, state.chat_id, state.user_id)
        if self._latest_by_owner_flow.get(owner_key) == state.flow_id:
            self._latest_by_owner_flow.pop(owner_key, None)

    def _is_expired(self, state: InteractionState) -> bool:
        return state.expires_at <= self._now()

    @staticmethod
    def _owner_key(flow: str, chat_id: str, user_id: str) -> tuple[str, str, str]:
        return (str(flow), str(chat_id), str(user_id))

    @staticmethod
    def _new_id() -> str:
        return uuid4().hex[:16]
