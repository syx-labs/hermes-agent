"""Text card templates for the Telegram Cockpit.

These renderers are intentionally platform-neutral: they return standard
Markdown-ish text that the Telegram adapter can later convert to MarkdownV2.
Keep them deterministic so tests can snapshot exact output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from gateway.cockpit.next_actions import NextAction, render_next_actions


@dataclass(frozen=True)
class StatusCard:
    title: str
    status: str
    summary: str = ""
    fields: Mapping[str, str] = field(default_factory=dict)
    next_actions: Sequence[str | NextAction] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProjectCard:
    name: str
    status: str
    path: str = ""
    aliases: Sequence[str] = field(default_factory=tuple)
    skills: Sequence[str] = field(default_factory=tuple)
    last_session: str = ""
    actions: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class JobCard:
    name: str
    status: str
    schedule: str = ""
    delivery: str = ""
    last_run: str = ""
    next_run: str = ""
    actions: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class PlanCard:
    title: str
    goal: str = ""
    steps: Sequence[str] = field(default_factory=tuple)
    risks: Sequence[str] = field(default_factory=tuple)
    next_actions: Sequence[str | NextAction] = field(default_factory=tuple)


@dataclass(frozen=True)
class DecisionCard:
    title: str
    question: str = ""
    options: Sequence[Mapping[str, str]] = field(default_factory=tuple)
    recommended: str = ""
    next_actions: Sequence[str | NextAction] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResearchCard:
    title: str
    summary: str = ""
    findings: Sequence[str] = field(default_factory=tuple)
    sources: Sequence[str] = field(default_factory=tuple)
    recommendation: str = ""


@dataclass(frozen=True)
class HandoffCard:
    title: str
    context: str = ""
    deliverables: Sequence[str] = field(default_factory=tuple)
    next_steps: Sequence[str] = field(default_factory=tuple)
    owner: str = ""


def _append_blank_if_needed(lines: list[str]) -> None:
    if lines and lines[-1] != "":
        lines.append("")


def _append_numbered_section(lines: list[str], title: str, items: Sequence[str]) -> None:
    clean_items = [str(item).strip() for item in items if str(item).strip()]
    if not clean_items:
        return
    _append_blank_if_needed(lines)
    lines.append(f"{title}:")
    for index, item in enumerate(clean_items, start=1):
        lines.append(f"{index}. {item}")


def _append_next_actions_section(
    lines: list[str], actions: Sequence[str | NextAction]
) -> None:
    if actions and all(isinstance(action, NextAction) for action in actions):
        rendered = render_next_actions(actions)
        if rendered:
            _append_blank_if_needed(lines)
            lines.extend(rendered.splitlines())
        return

    _append_numbered_section(lines, "Next actions", actions)  # type: ignore[arg-type]


def _join(lines: list[str]) -> str:
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def render_status_card(card: StatusCard) -> str:
    lines = [f"## {card.title}", f"Status: {card.status}"]
    if card.summary:
        lines.append(card.summary)
    if card.fields:
        _append_blank_if_needed(lines)
        for key, value in card.fields.items():
            if str(value).strip():
                lines.append(f"{key}: {value}")
    _append_next_actions_section(lines, card.next_actions)
    return _join(lines)


def render_project_card(card: ProjectCard) -> str:
    lines = [f"## Project: {card.name}", f"Status: {card.status}"]
    if card.path:
        lines.append(f"Path: {card.path}")
    if card.aliases:
        lines.append(f"Aliases: {', '.join(card.aliases)}")
    if card.skills:
        lines.append(f"Skills: {', '.join(card.skills)}")
    if card.last_session:
        lines.append(f"Last session: {card.last_session}")
    _append_numbered_section(lines, "Actions", card.actions)
    return _join(lines)


def render_job_card(card: JobCard) -> str:
    lines = [f"## Job: {card.name}", f"Status: {card.status}"]
    if card.schedule:
        lines.append(f"Schedule: {card.schedule}")
    if card.delivery:
        lines.append(f"Delivery: {card.delivery}")
    if card.last_run:
        lines.append(f"Last run: {card.last_run}")
    if card.next_run:
        lines.append(f"Next run: {card.next_run}")
    _append_numbered_section(lines, "Actions", card.actions)
    return _join(lines)


def render_plan_card(card: PlanCard) -> str:
    lines = [f"## Plan: {card.title}"]
    if card.goal:
        lines.append(f"Goal: {card.goal}")
    _append_numbered_section(lines, "Steps", card.steps)
    _append_numbered_section(lines, "Risks", card.risks)
    _append_next_actions_section(lines, card.next_actions)
    return _join(lines)


def render_decision_card(card: DecisionCard) -> str:
    lines = [f"## Decision: {card.title}"]
    if card.question:
        lines.append(f"Question: {card.question}")
    if card.options:
        _append_blank_if_needed(lines)
        lines.append("Options:")
        for index, option in enumerate(card.options, start=1):
            label = str(option.get("label", "")).strip()
            tradeoff = str(option.get("tradeoff", "")).strip()
            if not label:
                continue
            suffix = f" — {tradeoff}" if tradeoff else ""
            recommended = " (recommended)" if label == card.recommended else ""
            lines.append(f"{index}. {label}{suffix}{recommended}")
    _append_next_actions_section(lines, card.next_actions)
    return _join(lines)


def render_research_card(card: ResearchCard) -> str:
    lines = [f"## Research: {card.title}"]
    if card.summary:
        lines.append(f"Summary: {card.summary}")
    _append_numbered_section(lines, "Findings", card.findings)
    _append_numbered_section(lines, "Sources", card.sources)
    if card.recommendation:
        _append_blank_if_needed(lines)
        lines.append(f"Recommendation: {card.recommendation}")
    return _join(lines)


def render_handoff_card(card: HandoffCard) -> str:
    lines = [f"## Handoff: {card.title}"]
    if card.owner:
        lines.append(f"Owner: {card.owner}")
    if card.context:
        lines.append(f"Context: {card.context}")
    _append_numbered_section(lines, "Deliverables", card.deliverables)
    _append_numbered_section(lines, "Next steps", card.next_steps)
    return _join(lines)
