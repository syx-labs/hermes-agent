from datetime import datetime, timezone

from gateway.cockpit.actions import CockpitActionStore, SafetyLevel
from gateway.cockpit.keyboards import ButtonSpec, build_cockpit_keyboard_spec


def test_build_cockpit_keyboard_spec_creates_action_records_and_rows():
    store = CockpitActionStore(now=lambda: datetime(2026, 4, 26, 12, 0, tzinfo=timezone.utc))

    keyboard = build_cockpit_keyboard_spec(
        rows=[
            [
                ButtonSpec("Continue", "continue", {"todo": "ux-06"}),
                ButtonSpec("Detail", "detail"),
            ],
            [ButtonSpec("Run tests", "execute", safety_level=SafetyLevel.CONFIRM)],
        ],
        store=store,
        chat_id="123",
        user_id="456",
    )

    assert [[button.label for button in row] for row in keyboard.rows] == [
        ["Continue", "Detail"],
        ["Run tests"],
    ]
    assert all(button.callback_data.startswith("cx:") for row in keyboard.rows for button in row)
    assert all(len(button.callback_data) <= 64 for row in keyboard.rows for button in row)

    first_id = keyboard.rows[0][0].callback_data.removeprefix("cx:")
    first_action = store.get(first_id)
    assert first_action is not None
    assert first_action.kind == "continue"
    assert first_action.payload == {"todo": "ux-06"}
    assert first_action.chat_id == "123"
    assert first_action.user_id == "456"

    run_id = keyboard.rows[1][0].callback_data.removeprefix("cx:")
    assert store.get(run_id).safety_level is SafetyLevel.CONFIRM


def test_build_cockpit_keyboard_spec_skips_blank_labels():
    store = CockpitActionStore()

    keyboard = build_cockpit_keyboard_spec(
        rows=[[ButtonSpec(" ", "continue"), ButtonSpec("Detail", "detail")]],
        store=store,
    )

    assert [[button.label for button in row] for row in keyboard.rows] == [["Detail"]]
