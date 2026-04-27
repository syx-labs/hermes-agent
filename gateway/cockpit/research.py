"""Guided /research wizard helpers for the Telegram Cockpit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from gateway.cockpit.actions import CockpitActionStore, SafetyLevel
from gateway.cockpit.keyboards import ButtonSpec, CockpitKeyboardSpec, build_cockpit_keyboard_spec
from gateway.cockpit.next_actions import NextAction, NextActionKind, render_next_actions
from gateway.cockpit.state import InteractionState, InteractionStateStore


FLOW_NAME = "research"


@dataclass(frozen=True)
class ResearchOption:
    value: str
    label: str
    description: str


@dataclass(frozen=True)
class ResearchStep:
    key: str
    label: str
    options: tuple[ResearchOption, ...] = ()

    def option(self, value: str) -> ResearchOption | None:
        target = str(value).strip().lower()
        return next((option for option in self.options if option.value == target), None)


class ResearchSteps:
    def __init__(self, steps: Sequence[ResearchStep]) -> None:
        self._steps = tuple(steps)
        self._by_key = {step.key: step for step in self._steps}

    def get(self, key: str) -> ResearchStep | None:
        return self._by_key.get(key)

    def next_step(self, key: str) -> str:
        keys = [step.key for step in self._steps]
        try:
            index = keys.index(key)
        except ValueError:
            return "depth"
        if index >= len(keys) - 1:
            return "confirm"
        return keys[index + 1]

    def index(self, key: str) -> int:
        keys = [step.key for step in self._steps]
        return keys.index(key) + 1 if key in keys else len(keys) + 1


RESEARCH_STEPS = ResearchSteps(
    (
        ResearchStep(
            "depth",
            "Depth",
            (
                ResearchOption("short", "Short summary", "Síntese curta e rápida"),
                ResearchOption("deep", "Deep research", "Pesquisa ampla com fontes e síntese"),
                ResearchOption("comparative", "Comparative", "Comparar opções, ferramentas ou abordagens"),
            ),
        ),
        ResearchStep(
            "output",
            "Output",
            (
                ResearchOption("chat", "Chat summary", "Responder nesta conversa"),
                ResearchOption("obsidian", "Obsidian note", "Preparar nota para Obsidian"),
                ResearchOption("markdown", "Markdown file", "Gerar artefato Markdown"),
                ResearchOption("pdf", "PDF", "Preparar saída em PDF"),
            ),
        ),
        ResearchStep(
            "artifact",
            "Artifact",
            (
                ResearchOption("none", "No extra artifact", "Somente texto"),
                ResearchOption("sources", "Sources table", "Tabela de fontes"),
                ResearchOption("diagram", "Diagram", "Diagrama de conceitos ou fluxo"),
                ResearchOption("comparison", "Comparison matrix", "Matriz comparativa"),
            ),
        ),
        ResearchStep("topic", "Topic"),
    )
)


def start_research_flow(store: InteractionStateStore, *, chat_id: str, user_id: str) -> InteractionState:
    return store.create(flow=FLOW_NAME, chat_id=chat_id, user_id=user_id, step="depth")


def option_label(step_key: str, value: object) -> str:
    step = RESEARCH_STEPS.get(step_key)
    if not step:
        return str(value)
    option = step.option(str(value))
    return option.label if option else str(value)


def build_research_prompt(answers: Mapping[str, object]) -> str:
    topic = str(answers.get("topic") or "not provided").strip() or "not provided"
    lines = [
        "Research request:",
        f"Research topic: {topic}",
        f"Depth: {option_label('depth', answers.get('depth', 'not selected'))}",
        f"Output: {option_label('output', answers.get('output', 'not selected'))}",
        f"Artifact: {option_label('artifact', answers.get('artifact', 'not selected'))}",
    ]
    return "\n".join(lines)


def render_research_wizard(state: InteractionState) -> str:
    step = RESEARCH_STEPS.get(state.step)
    is_confirm = state.step == "confirm"
    status = "ready for confirmation" if is_confirm else ("collecting topic" if state.step == "topic" else f"choosing {state.step}")
    step_label = "Confirm" if is_confirm else (step.label if step else state.step.title())
    step_index = 4 if is_confirm else RESEARCH_STEPS.index(state.step)

    lines = [
        "## Research Cockpit",
        f"Status: {status}",
        "Guided research request flow.",
        "",
        f"Step: {step_index}/4 · {step_label}",
        f"Flow: {state.flow_id}",
        f"Selected: {_render_selected(state.answers)}",
    ]

    if is_confirm:
        lines.extend(["", build_research_prompt(state.answers), "", "Confirm with: /research confirm"])
    elif state.step == "topic":
        lines.extend(["", "Topic:", "- Use `/research topic <question or topic>` to describe what to research."])
    elif step:
        lines.append("")
        lines.append("Options:")
        for option in step.options:
            lines.append(f"- {option.label} — {option.description} (`/research {step.key} {option.value}`)")

    next_actions = (
        NextAction(NextActionKind.CONTINUE, "Escolher próxima opção"),
        NextAction(NextActionKind.DETAIL, "Ver opções e seleção atual"),
        NextAction(NextActionKind.EXECUTE, "Confirmar pesquisa no passo final"),
    )
    lines.extend(["", render_next_actions(next_actions)])
    return "\n".join(line for line in lines if line is not None)


def build_research_keyboard_spec(
    state: InteractionState,
    *,
    store: CockpitActionStore,
    chat_id: str | None = None,
    user_id: str | None = None,
) -> CockpitKeyboardSpec:
    if state.step == "confirm":
        rows = ((ButtonSpec("Confirm", "research.confirm", {"flow_id": state.flow_id}, SafetyLevel.CONFIRM),),)
    else:
        step = RESEARCH_STEPS.get(state.step)
        if not step or not step.options:
            return CockpitKeyboardSpec(rows=())
        buttons = [
            ButtonSpec(
                option.label,
                "research.select",
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
    for key in ("depth", "output", "artifact"):
        if key in answers:
            parts.append(f"{key}={option_label(key, answers[key])}")
    if answers.get("topic"):
        parts.append(f"topic={answers['topic']}")
    return "; ".join(parts) if parts else "none"
