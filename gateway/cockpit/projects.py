"""Project registry and dashboard helpers for the Telegram Cockpit."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from gateway.cockpit.actions import CockpitActionStore, SafetyLevel
from gateway.cockpit.keyboards import ButtonSpec, CockpitKeyboardSpec, build_cockpit_keyboard_spec
from gateway.cockpit.next_actions import NextAction, NextActionKind, render_next_actions


@dataclass(frozen=True)
class ProjectEntry:
    name: str
    status: str
    path: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    context: str = ""
    skills: tuple[str, ...] = field(default_factory=tuple)
    commands: Mapping[str, str] = field(default_factory=dict)
    last_session: str = ""


def _clean(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        raw = [value]
    else:
        raw = list(value) if isinstance(value, Sequence) else [value]
    return tuple(str(item).strip() for item in raw if str(item).strip())


def _project_status(path: str, explicit: str = "") -> str:
    if explicit:
        return explicit
    if not path:
        return "configured"
    return "available" if Path(path).expanduser().exists() else "missing path"


def _normalize_project(raw: Mapping[str, Any]) -> ProjectEntry | None:
    name = _clean(raw.get("name"))
    if not name:
        return None
    path = _clean(raw.get("path"))
    commands = raw.get("commands") if isinstance(raw.get("commands"), Mapping) else {}
    return ProjectEntry(
        name=name,
        status=_project_status(path, _clean(raw.get("status"))),
        path=path,
        aliases=_string_tuple(raw.get("aliases")),
        context=_clean(raw.get("context") or raw.get("description")),
        skills=_string_tuple(raw.get("skills") or raw.get("skill")),
        commands={str(key): str(value) for key, value in commands.items()},
        last_session=_clean(raw.get("last_session")),
    )


def _extract_project_items(source: Any) -> list[Mapping[str, Any]]:
    if isinstance(source, Mapping):
        if isinstance(source.get("projects"), list):
            return [item for item in source["projects"] if isinstance(item, Mapping)]
        cockpit = source.get("cockpit")
        if isinstance(cockpit, Mapping) and isinstance(cockpit.get("projects"), list):
            return [item for item in cockpit["projects"] if isinstance(item, Mapping)]
    return []


def _default_registry_path() -> Path:
    env_path = os.getenv("HERMES_COCKPIT_PROJECTS_FILE")
    if env_path:
        return Path(env_path).expanduser()
    try:
        from hermes_constants import get_hermes_home

        return get_hermes_home() / "projects.yaml"
    except Exception:
        return Path.home() / ".hermes" / "projects.yaml"


def load_project_registry(source: str | Path | Mapping[str, Any] | None = None) -> list[ProjectEntry]:
    """Load project registry entries from YAML file or config mapping."""
    data: Any
    if source is None:
        source = _default_registry_path()
    if isinstance(source, Mapping):
        data = source
    else:
        path = Path(source).expanduser()
        if not path.exists():
            return []
        import yaml

        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

    projects = [_normalize_project(item) for item in _extract_project_items(data)]
    return [project for project in projects if project is not None]


def find_project(projects: Sequence[ProjectEntry], query: str) -> ProjectEntry | None:
    target = query.strip().lower()
    if not target:
        return None
    for project in projects:
        names = (project.name, *project.aliases)
        if any(name.lower() == target for name in names):
            return project
    return None


def render_projects_dashboard(projects: Sequence[ProjectEntry]) -> str:
    count = len(projects)
    status = "empty" if count == 0 else f"{count} project" if count == 1 else f"{count} projects"
    lines = [
        "## Projects Cockpit",
        f"Status: {status}",
        "Recurring project registry." if count else "No projects registered yet.",
    ]
    if count:
        lines.append("")
        for index, project in enumerate(projects, start=1):
            if index > 1:
                lines.append("")
            lines.append(f"{index}. {project.name} · {project.status}")
            if project.path:
                lines.append(f"   Path: {project.path}")
            if project.aliases:
                lines.append(f"   Aliases: {', '.join(project.aliases)}")
            if project.context:
                lines.append(f"   Context: {project.context}")
            if project.skills:
                lines.append(f"   Skills: {', '.join(project.skills)}")
            if project.commands:
                lines.append(f"   Commands: {', '.join(project.commands.keys())}")
            if project.last_session:
                lines.append(f"   Last session: {project.last_session}")
            lines.append(
                "   Actions: "
                f"/projects continue {project.name} | "
                f"/projects inspect {project.name} | "
                f"/projects review {project.name} | "
                f"/projects diagram {project.name}"
            )

    if count:
        next_actions = (
            NextAction(NextActionKind.CONTINUE, "Continuar um projeto"),
            NextAction(NextActionKind.DETAIL, "Inspecionar contexto de um projeto"),
            NextAction(NextActionKind.EXECUTE, "Registrar novo projeto"),
        )
    else:
        next_actions = (
            NextAction(NextActionKind.EXECUTE, "Registrar primeiro projeto"),
            NextAction(NextActionKind.DETAIL, "Ver formato de projects.yaml"),
        )
    rendered_actions = render_next_actions(next_actions)
    if rendered_actions:
        lines.extend(["", rendered_actions])
    return "\n".join(lines)


def build_project_keyboard_spec(
    project: ProjectEntry,
    *,
    store: CockpitActionStore,
    chat_id: str | None = None,
    user_id: str | None = None,
) -> CockpitKeyboardSpec:
    payload = {"project": project.name}
    return build_cockpit_keyboard_spec(
        rows=(
            (
                ButtonSpec("Continue", "project.continue", payload, SafetyLevel.SAFE),
                ButtonSpec("Inspect", "project.inspect", payload, SafetyLevel.SAFE),
            ),
            (
                ButtonSpec("Review", "project.review", payload, SafetyLevel.SAFE),
                ButtonSpec("Diagram", "project.diagram", payload, SafetyLevel.SAFE),
            ),
            (ButtonSpec("Handoff", "project.handoff", payload, SafetyLevel.SAFE),),
        ),
        store=store,
        chat_id=chat_id,
        user_id=user_id,
    )


def build_projects_dashboard_keyboard_spec(
    projects: Sequence[ProjectEntry],
    *,
    store: CockpitActionStore,
    chat_id: str | None = None,
    user_id: str | None = None,
    limit: int = 5,
) -> CockpitKeyboardSpec:
    """Register compact callback actions for the top projects in a dashboard."""
    rows: list[tuple[ButtonSpec, ...]] = []
    for project in projects[:limit]:
        payload = {"project": project.name}
        rows.append(
            (
                ButtonSpec(f"Continue {project.name}", "project.continue", payload, SafetyLevel.SAFE),
                ButtonSpec(f"Inspect {project.name}", "project.inspect", payload, SafetyLevel.SAFE),
            )
        )
        rows.append(
            (
                ButtonSpec(f"Review {project.name}", "project.review", payload, SafetyLevel.SAFE),
                ButtonSpec(f"Diagram {project.name}", "project.diagram", payload, SafetyLevel.SAFE),
            )
        )
    return build_cockpit_keyboard_spec(rows=tuple(rows), store=store, chat_id=chat_id, user_id=user_id)
