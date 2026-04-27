"""Standard next-action templates for Telegram Cockpit responses.

This module stays platform-neutral. It renders deterministic Markdown-ish text
that can later be paired with Telegram inline buttons by the action router.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class NextActionKind(StrEnum):
    """Canonical action types used by cockpit responses."""

    CONTINUE = "continue"
    DETAIL = "detail"
    EXECUTE = "execute"
    GENERATE_FILE = "generate_file"
    SCHEDULE = "schedule"
    SAVE_SKILL = "save_skill"


@dataclass(frozen=True)
class NextAction:
    """A user-facing follow-up action.

    The kind is stable and can later map to a callback intent. The label is the
    concrete task shown to the user for the current response.
    """

    kind: NextActionKind
    label: str


_ACTION_LABELS: dict[NextActionKind, str] = {
    NextActionKind.CONTINUE: "Continue",
    NextActionKind.DETAIL: "Detail",
    NextActionKind.EXECUTE: "Execute",
    NextActionKind.GENERATE_FILE: "Generate file",
    NextActionKind.SCHEDULE: "Schedule",
    NextActionKind.SAVE_SKILL: "Save skill",
}

_ACTION_ORDER: tuple[NextActionKind, ...] = (
    NextActionKind.CONTINUE,
    NextActionKind.DETAIL,
    NextActionKind.EXECUTE,
    NextActionKind.GENERATE_FILE,
    NextActionKind.SCHEDULE,
    NextActionKind.SAVE_SKILL,
)


def default_next_actions() -> tuple[NextAction, ...]:
    """Return the default safe action block for important responses."""

    return (
        NextAction(NextActionKind.CONTINUE, "Continuar com o próximo passo"),
        NextAction(NextActionKind.DETAIL, "Detalhar a resposta"),
        NextAction(NextActionKind.EXECUTE, "Executar a ação proposta"),
        NextAction(NextActionKind.GENERATE_FILE, "Gerar arquivo com o resultado"),
        NextAction(NextActionKind.SCHEDULE, "Agendar acompanhamento"),
        NextAction(NextActionKind.SAVE_SKILL, "Salvar como skill reutilizável"),
    )


def normalize_next_actions(actions: Iterable[NextAction]) -> tuple[NextAction, ...]:
    """Return non-empty actions deduplicated by kind in canonical order."""

    first_by_kind: dict[NextActionKind, NextAction] = {}
    for action in actions:
        label = action.label.strip()
        if not label or action.kind in first_by_kind:
            continue
        first_by_kind[action.kind] = NextAction(action.kind, label)

    return tuple(
        first_by_kind[kind] for kind in _ACTION_ORDER if kind in first_by_kind
    )


def render_next_actions(actions: Iterable[NextAction], title: str = "Next actions") -> str:
    """Render the standard next-action block.

    Empty action sets produce an empty string so callers can omit the section
    without extra whitespace.
    """

    clean_actions = normalize_next_actions(actions)
    if not clean_actions:
        return ""

    lines = [f"{title}:"]
    for index, action in enumerate(clean_actions, start=1):
        kind_label = _ACTION_LABELS[action.kind]
        lines.append(f"{index}. {kind_label} — {action.label}")
    return "\n".join(lines)
