"""Guided /newtask wizard helpers for the Telegram Cockpit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from gateway.cockpit.actions import CockpitActionStore, SafetyLevel
from gateway.cockpit.keyboards import ButtonSpec, CockpitKeyboardSpec, build_cockpit_keyboard_spec
from gateway.cockpit.next_actions import NextAction, NextActionKind, render_next_actions
from gateway.cockpit.state import InteractionState, InteractionStateStore


FLOW_NAME = "newtask"


@dataclass(frozen=True)
class NewTaskOption:
    value: str
    label: str
    description: str


@dataclass(frozen=True)
class NewTaskStep:
    key: str
    label: str
    options: tuple[NewTaskOption, ...]

    def option(self, value: str) -> NewTaskOption | None:
        target = str(value).strip().lower()
        return next((option for option in self.options if option.value == target), None)


class NewTaskSteps:
    def __init__(self, steps: Sequence[NewTaskStep]) -> None:
        self._steps = tuple(steps)
        self._by_key = {step.key: step for step in self._steps}

    def get(self, key: str) -> NewTaskStep | None:
        return self._by_key.get(key)

    def next_step(self, key: str) -> str:
        keys = [step.key for step in self._steps]
        try:
            index = keys.index(key)
        except ValueError:
            return "type"
        if index >= len(keys) - 1:
            return "confirm"
        return keys[index + 1]

    def index(self, key: str) -> int:
        keys = [step.key for step in self._steps]
        return keys.index(key) + 1 if key in keys else len(keys) + 1


NEWTASK_STEPS = NewTaskSteps(
    (
        NewTaskStep(
            "type",
            "Type",
            (
                NewTaskOption("code", "Code", "Implementar ou corrigir código"),
                NewTaskOption("research", "Research", "Pesquisar e sintetizar informação"),
                NewTaskOption("document", "Document", "Criar documento, plano ou resumo"),
                NewTaskOption("infra", "Infra", "Operar infraestrutura ou deploy"),
                NewTaskOption("design", "Design", "Criar diagrama ou artefato visual"),
                NewTaskOption("automation", "Automation", "Criar rotina, job ou automação"),
            ),
        ),
        NewTaskStep(
            "mode",
            "Mode",
            (
                NewTaskOption("plan", "Plan", "Planejar antes de executar"),
                NewTaskOption("execute", "Execute", "Executar diretamente após confirmação"),
                NewTaskOption("delegate", "Delegate", "Delegar a agente especializado"),
                NewTaskOption("review", "Review only", "Revisar sem modificar"),
            ),
        ),
        NewTaskStep(
            "agent",
            "Agent",
            (
                NewTaskOption("hermes", "Hermes", "Usar o agente atual"),
                NewTaskOption("claude", "Claude Code", "Delegar para Claude Code"),
                NewTaskOption("codex", "Codex", "Delegar para Codex"),
                NewTaskOption("supervisor", "Supervisor", "Orquestrar via supervisor"),
            ),
        ),
        NewTaskStep(
            "deliverable",
            "Deliverable",
            (
                NewTaskOption("chat", "Chat", "Resposta nesta conversa"),
                NewTaskOption("markdown", "Markdown", "Arquivo Markdown"),
                NewTaskOption("pdf", "PDF", "Documento PDF"),
                NewTaskOption("diagram", "Diagram", "Diagrama Mermaid/SVG/PNG"),
                NewTaskOption("pr", "PR", "Pull request ou patch revisável"),
            ),
        ),
    )
)


def start_newtask_flow(store: InteractionStateStore, *, chat_id: str, user_id: str) -> InteractionState:
    return store.create(flow=FLOW_NAME, chat_id=chat_id, user_id=user_id, step="type")


def option_label(step_key: str, value: object) -> str:
    step = NEWTASK_STEPS.get(step_key)
    if not step:
        return str(value)
    option = step.option(str(value))
    return option.label if option else str(value)


def build_newtask_prompt(answers: Mapping[str, object]) -> str:
    lines = [
        "New task request:",
        f"Task type: {option_label('type', answers.get('type', 'not selected'))}",
        f"Mode: {option_label('mode', answers.get('mode', 'not selected'))}",
        f"Agent: {option_label('agent', answers.get('agent', 'not selected'))}",
        f"Deliverable: {option_label('deliverable', answers.get('deliverable', 'not selected'))}",
    ]
    return "\n".join(lines)


def render_newtask_wizard(state: InteractionState) -> str:
    step = NEWTASK_STEPS.get(state.step)
    is_confirm = state.step == "confirm"
    status = "ready for confirmation" if is_confirm else f"choosing {state.step}"
    step_label = "Confirm" if is_confirm else (step.label if step else state.step.title())
    step_index = 5 if is_confirm else NEWTASK_STEPS.index(state.step)

    lines = [
        "## New Task Cockpit",
        f"Status: {status}",
        "Guided task creation flow.",
        "",
        f"Step: {step_index}/5 · {step_label}",
        f"Flow: {state.flow_id}",
        f"Selected: {_render_selected(state.answers)}",
    ]

    if is_confirm:
        lines.extend(
            [
                "",
                build_newtask_prompt(state.answers),
                "",
                "Safety: Execution/delegation requires explicit confirmation.",
                "Confirm with: /newtask confirm",
            ]
        )
    elif step:
        lines.append("")
        lines.append("Options:")
        for option in step.options:
            lines.append(f"- {option.label} — {option.description} (`/newtask {step.key} {option.value}`)")

    next_actions = (
        NextAction(NextActionKind.CONTINUE, "Escolher próxima opção"),
        NextAction(NextActionKind.DETAIL, "Ver opções e seleção atual"),
        NextAction(NextActionKind.EXECUTE, "Confirmar somente no passo final"),
    )
    lines.extend(["", render_next_actions(next_actions)])
    return "\n".join(line for line in lines if line is not None)


def build_newtask_keyboard_spec(
    state: InteractionState,
    *,
    store: CockpitActionStore,
    chat_id: str | None = None,
    user_id: str | None = None,
) -> CockpitKeyboardSpec:
    if state.step == "confirm":
        rows = ((ButtonSpec("Confirm", "newtask.confirm", {"flow_id": state.flow_id}, SafetyLevel.CONFIRM),),)
    else:
        step = NEWTASK_STEPS.get(state.step)
        if not step:
            return CockpitKeyboardSpec(rows=())
        buttons = [
            ButtonSpec(
                option.label,
                "newtask.select",
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
    for key in ("type", "mode", "agent", "deliverable"):
        if key in answers:
            parts.append(f"{key}={option_label(key, answers[key])}")
    return "; ".join(parts) if parts else "none"
