from pathlib import Path

from gateway.cockpit.actions import CockpitActionStore, SafetyLevel
from gateway.cockpit.projects import (
    ProjectEntry,
    build_project_keyboard_spec,
    load_project_registry,
    render_projects_dashboard,
)


def test_project_registry_loads_from_yaml_and_marks_missing_paths(tmp_path):
    existing = tmp_path / "adaptive-context-harness"
    existing.mkdir()
    registry_path = tmp_path / "projects.yaml"
    registry_path.write_text(
        f"""
projects:
  - name: adaptive-context-harness
    aliases: [ach, harness]
    path: {existing}
    context: Adaptive context harness repo
    skills: [adaptive-context-harness]
    commands:
      test: bun run test
      review: custom workflow
    last_session: sess-123
  - name: missing-client
    aliases: [mc]
    path: {tmp_path / 'missing'}
    skills: [client-work]
""".strip(),
        encoding="utf-8",
    )

    projects = load_project_registry(registry_path)

    assert projects == [
        ProjectEntry(
            name="adaptive-context-harness",
            status="available",
            path=str(existing),
            aliases=("ach", "harness"),
            context="Adaptive context harness repo",
            skills=("adaptive-context-harness",),
            commands={"test": "bun run test", "review": "custom workflow"},
            last_session="sess-123",
        ),
        ProjectEntry(
            name="missing-client",
            status="missing path",
            path=str(tmp_path / "missing"),
            aliases=("mc",),
            context="",
            skills=("client-work",),
            commands={},
            last_session="",
        ),
    ]


def test_project_registry_loads_from_config_mapping(tmp_path):
    project_path = tmp_path / "repo"
    project_path.mkdir()

    projects = load_project_registry(
        {
            "cockpit": {
                "projects": [
                    {
                        "name": "repo",
                        "aliases": "r",
                        "path": str(project_path),
                        "skills": "test-driven-development",
                    }
                ]
            }
        }
    )

    assert projects[0].aliases == ("r",)
    assert projects[0].skills == ("test-driven-development",)
    assert projects[0].status == "available"


def test_render_projects_dashboard_is_compact_and_actionable(tmp_path):
    result = render_projects_dashboard(
        [
            ProjectEntry(
                name="adaptive-context-harness",
                status="available",
                path="/Users/shadow/projects/adaptive-context-harness",
                aliases=("ach", "harness"),
                context="Session-adaptive repository harness",
                skills=("adaptive-context-harness",),
                commands={"test": "bun run test", "review": "custom workflow"},
                last_session="sess-123",
            ),
            ProjectEntry(
                name="missing-client",
                status="missing path",
                path="/tmp/missing-client",
                aliases=("mc",),
                skills=("client-work",),
            ),
        ]
    )

    assert result == """## Projects Cockpit
Status: 2 projects
Recurring project registry.

1. adaptive-context-harness · available
   Path: /Users/shadow/projects/adaptive-context-harness
   Aliases: ach, harness
   Context: Session-adaptive repository harness
   Skills: adaptive-context-harness
   Commands: test, review
   Last session: sess-123
   Actions: /projects continue adaptive-context-harness | /projects inspect adaptive-context-harness | /projects review adaptive-context-harness | /projects diagram adaptive-context-harness

2. missing-client · missing path
   Path: /tmp/missing-client
   Aliases: mc
   Skills: client-work
   Actions: /projects continue missing-client | /projects inspect missing-client | /projects review missing-client | /projects diagram missing-client

Next actions:
1. Continue — Continuar um projeto
2. Detail — Inspecionar contexto de um projeto
3. Execute — Registrar novo projeto"""


def test_render_projects_dashboard_handles_empty_state():
    result = render_projects_dashboard([])

    assert "## Projects Cockpit" in result
    assert "Status: empty" in result
    assert "No projects registered yet." in result
    assert "Execute — Registrar primeiro projeto" in result


def test_build_project_keyboard_spec_registers_project_actions():
    store = CockpitActionStore()
    project = ProjectEntry(name="adaptive-context-harness", status="available")

    keyboard = build_project_keyboard_spec(project, store=store, chat_id="c1", user_id="u1")

    assert [[button.label for button in row] for row in keyboard.rows] == [
        ["Continue", "Inspect"],
        ["Review", "Diagram"],
        ["Handoff"],
    ]
    actions = [store.get(button.callback_data.removeprefix("cx:")) for row in keyboard.rows for button in row]
    assert [action.kind for action in actions if action] == [
        "project.continue",
        "project.inspect",
        "project.review",
        "project.diagram",
        "project.handoff",
    ]
    assert all(action.payload == {"project": "adaptive-context-harness"} for action in actions if action)
    assert all(action.safety_level == SafetyLevel.SAFE for action in actions if action)
