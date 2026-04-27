from gateway.cockpit.next_actions import (
    NextAction,
    NextActionKind,
    default_next_actions,
    render_next_actions,
)


def test_render_next_actions_uses_standard_order_and_labels():
    actions = [
        NextAction(NextActionKind.SAVE_SKILL, "Save workflow as reusable skill"),
        NextAction(NextActionKind.CONTINUE, "Continue implementation"),
        NextAction(NextActionKind.GENERATE_FILE, "Export Markdown handoff"),
        NextAction(NextActionKind.DETAIL, "Show technical diff"),
        NextAction(NextActionKind.SCHEDULE, "Create daily digest"),
        NextAction(NextActionKind.EXECUTE, "Run tests"),
    ]

    assert render_next_actions(actions) == """Next actions:
1. Continue — Continue implementation
2. Detail — Show technical diff
3. Execute — Run tests
4. Generate file — Export Markdown handoff
5. Schedule — Create daily digest
6. Save skill — Save workflow as reusable skill"""


def test_render_next_actions_skips_empty_labels_and_deduplicates_by_kind():
    actions = [
        NextAction(NextActionKind.CONTINUE, "  "),
        NextAction(NextActionKind.CONTINUE, "Continue with next TODO"),
        NextAction(NextActionKind.CONTINUE, "Duplicate should be skipped"),
        NextAction(NextActionKind.EXECUTE, "Run verification"),
    ]

    assert render_next_actions(actions) == """Next actions:
1. Continue — Continue with next TODO
2. Execute — Run verification"""


def test_render_next_actions_accepts_custom_title():
    actions = [NextAction(NextActionKind.DETAIL, "Explain the architecture choices")]

    assert render_next_actions(actions, title="Available actions") == """Available actions:
1. Detail — Explain the architecture choices"""


def test_default_next_actions_are_safe_and_predictable():
    assert default_next_actions() == (
        NextAction(NextActionKind.CONTINUE, "Continuar com o próximo passo"),
        NextAction(NextActionKind.DETAIL, "Detalhar a resposta"),
        NextAction(NextActionKind.EXECUTE, "Executar a ação proposta"),
        NextAction(NextActionKind.GENERATE_FILE, "Gerar arquivo com o resultado"),
        NextAction(NextActionKind.SCHEDULE, "Agendar acompanhamento"),
        NextAction(NextActionKind.SAVE_SKILL, "Salvar como skill reutilizável"),
    )


def test_render_next_actions_returns_empty_string_when_no_actions_remain():
    assert render_next_actions([NextAction(NextActionKind.CONTINUE, "")]) == ""
