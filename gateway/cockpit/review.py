"""Guided /review wizard helpers for the Telegram Cockpit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from gateway.cockpit.actions import CockpitActionStore, SafetyLevel
from gateway.cockpit.keyboards import ButtonSpec, CockpitKeyboardSpec, build_cockpit_keyboard_spec
from gateway.cockpit.next_actions import NextAction, NextActionKind, render_next_actions
from gateway.cockpit.state import InteractionState, InteractionStateStore


FLOW_NAME = "review"


@dataclass(frozen=True)
class ReviewOption:
    value: str
    label: str
    description: str


@dataclass(frozen=True)
class ReviewStep:
    key: str
    label: str
    options: tuple[ReviewOption, ...] = ()

    def option(self, value: str) -> ReviewOption | None:
        target = str(value).strip().lower()
        return next((option for option in self.options if option.value == target), None)


class ReviewSteps:
    def __init__(self, steps: Sequence[ReviewStep]) -> None:
        self._steps = tuple(steps)
        self._by_key = {step.key: step for step in self._steps}

    def get(self, key: str) -> ReviewStep | None:
        return self._by_key.get(key)

    def next_step(self, key: str) -> str:
        keys = [step.key for step in self._steps]
        try:
            index = keys.index(key)
        except ValueError:
            return "scope"
        if index >= len(keys) - 1:
            return "confirm"
        return keys[index + 1]

    def index(self, key: str) -> int:
        keys = [step.key for step in self._steps]
        return keys.index(key) + 1 if key in keys else len(keys) + 1


REVIEW_STEPS = ReviewSteps(
    (
        ReviewStep(
            "scope",
            "Scope",
            (
                ReviewOption("diff", "Working diff", "Revisar mudanças locais"),
                ReviewOption("pr", "Pull request", "Revisar PR ou branch remota"),
                ReviewOption("path", "Project path", "Revisar um caminho/projeto específico"),
            ),
        ),
        ReviewStep(
            "checks",
            "Checks",
            (
                ReviewOption("quick", "Quick review", "Checagem rápida de lógica"),
                ReviewOption("full", "Full review", "Diff, testes, segurança e relatório"),
                ReviewOption("security", "Security focus", "Foco em riscos e credenciais"),
                ReviewOption("tests", "Tests focus", "Foco em testes e regressões"),
            ),
        ),
        ReviewStep(
            "runner",
            "Runner",
            (
                ReviewOption("hermes", "Hermes", "Revisão pelo agente atual"),
                ReviewOption("codex", "Codex", "Delegar revisão para Codex"),
                ReviewOption("claude", "Claude Code", "Delegar revisão para Claude Code"),
                ReviewOption("supervisor", "Supervisor", "Revisão orquestrada"),
            ),
        ),
        ReviewStep(
            "output",
            "Output",
            (
                ReviewOption("chat", "Chat", "Resumo nesta conversa"),
                ReviewOption("report", "Report", "Relatório estruturado"),
                ReviewOption("pr", "PR comment", "Comentário para pull request"),
                ReviewOption("patch", "Patch plan", "Plano de correção"),
            ),
        ),
        ReviewStep("target", "Target"),
    )
)


def start_review_flow(store: InteractionStateStore, *, chat_id: str, user_id: str) -> InteractionState:
    return store.create(flow=FLOW_NAME, chat_id=chat_id, user_id=user_id, step="scope")


def option_label(step_key: str, value: object) -> str:
    step = REVIEW_STEPS.get(step_key)
    if not step:
        return str(value)
    option = step.option(str(value))
    return option.label if option else str(value)


def build_review_prompt(answers: Mapping[str, object]) -> str:
    target = str(answers.get("target") or "current project").strip() or "current project"
    lines = [
        "Review request:",
        f"Review target: {target}",
        f"Scope: {option_label('scope', answers.get('scope', 'not selected'))}",
        f"Checks: {option_label('checks', answers.get('checks', 'not selected'))}",
        f"Runner: {option_label('runner', answers.get('runner', 'not selected'))}",
        f"Output: {option_label('output', answers.get('output', 'not selected'))}",
    ]
    return "\n".join(lines)


def render_review_wizard(state: InteractionState) -> str:
    step = REVIEW_STEPS.get(state.step)
    is_confirm = state.step == "confirm"
    status = "ready for confirmation" if is_confirm else ("collecting target" if state.step == "target" else f"choosing {state.step}")
    step_label = "Confirm" if is_confirm else (step.label if step else state.step.title())
    step_index = 5 if is_confirm else REVIEW_STEPS.index(state.step)

    lines = [
        "## Review Cockpit",
        f"Status: {status}",
        "Guided code review request flow.",
        "",
        f"Step: {step_index}/5 · {step_label}",
        f"Flow: {state.flow_id}",
        f"Selected: {_render_selected(state.answers)}",
    ]

    if is_confirm:
        lines.extend(["", build_review_prompt(state.answers), "", "Confirm with: /review confirm"])
    elif state.step == "target":
        lines.extend(["", "Target:", "- Use `/review target <path, PR URL, branch, or current>` to define review target."])
    elif step:
        lines.append("")
        lines.append("Options:")
        for option in step.options:
            lines.append(f"- {option.label} — {option.description} (`/review {step.key} {option.value}`)")

    next_actions = (
        NextAction(NextActionKind.CONTINUE, "Escolher próxima opção"),
        NextAction(NextActionKind.DETAIL, "Ver escopo e checks selecionados"),
        NextAction(NextActionKind.EXECUTE, "Confirmar revisão no passo final"),
    )
    lines.extend(["", render_next_actions(next_actions)])
    return "\n".join(line for line in lines if line is not None)


def build_review_keyboard_spec(
    state: InteractionState,
    *,
    store: CockpitActionStore,
    chat_id: str | None = None,
    user_id: str | None = None,
) -> CockpitKeyboardSpec:
    if state.step == "confirm":
        rows = ((ButtonSpec("Confirm", "review.confirm", {"flow_id": state.flow_id}, SafetyLevel.CONFIRM),),)
    else:
        step = REVIEW_STEPS.get(state.step)
        if not step or not step.options:
            return CockpitKeyboardSpec(rows=())
        buttons = [
            ButtonSpec(
                option.label,
                "review.select",
                {"flow_id": state.flow_id, "step": step.key, "value": option.value},
                SafetyLevel.SAFE,
            )
            for option in step.options
        ]
        rows = tuple(tuple(buttons[index : index + 3]) for index in range(0, len(buttons), 3))
    return build_cockpit_keyboard_spec(rows=rows, store=store, chat_id=chat_id, user_id=user_id)


def _render_selected(answers: Mapping[str, object]) -> str:
    if not answers:
        return "none"
    parts = []
    for key in ("scope", "checks", "runner", "output"):
        if key in answers:
            parts.append(f"{key}={option_label(key, answers[key])}")
    if answers.get("target"):
        parts.append(f"target={answers['target']}")
    return "; ".join(parts) if parts else "none"
