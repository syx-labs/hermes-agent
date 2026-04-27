"""Platform-neutral keyboard specs for Telegram Cockpit actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Mapping, Sequence

from gateway.cockpit.actions import (
    DEFAULT_ACTION_TTL,
    CockpitActionStore,
    SafetyLevel,
    callback_data_for,
)


@dataclass(frozen=True)
class ButtonSpec:
    """Requested cockpit button before callback data is allocated."""

    label: str
    action_kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    safety_level: SafetyLevel = SafetyLevel.SAFE


@dataclass(frozen=True)
class KeyboardButtonSpec:
    """Rendered platform-neutral button with compact callback data."""

    label: str
    callback_data: str


@dataclass(frozen=True)
class CockpitKeyboardSpec:
    """Rendered platform-neutral inline keyboard rows."""

    rows: tuple[tuple[KeyboardButtonSpec, ...], ...]


def build_cockpit_keyboard_spec(
    *,
    rows: Sequence[Sequence[ButtonSpec]],
    store: CockpitActionStore,
    chat_id: str | None = None,
    user_id: str | None = None,
    ttl: timedelta = DEFAULT_ACTION_TTL,
) -> CockpitKeyboardSpec:
    """Create action records and return compact callback button rows."""

    rendered_rows: list[tuple[KeyboardButtonSpec, ...]] = []
    for row in rows:
        rendered_buttons: list[KeyboardButtonSpec] = []
        for button in row:
            label = button.label.strip()
            if not label:
                continue
            action = store.create(
                kind=button.action_kind,
                payload=button.payload,
                chat_id=chat_id,
                user_id=user_id,
                ttl=ttl,
                safety_level=button.safety_level,
            )
            rendered_buttons.append(
                KeyboardButtonSpec(label=label, callback_data=callback_data_for(action.id))
            )
        if rendered_buttons:
            rendered_rows.append(tuple(rendered_buttons))
    return CockpitKeyboardSpec(rows=tuple(rendered_rows))
