from gateway.cockpit.actions import CockpitActionStore, SafetyLevel
from gateway.cockpit.jobs import JobSummary, build_job_keyboard_spec, render_jobs_dashboard, summarize_job


def test_summarize_job_normalizes_cron_fields_and_actions():
    summary = summarize_job(
        {
            "id": "job-1234567890",
            "name": "AI coding digest",
            "state": "scheduled",
            "enabled": True,
            "schedule_display": "every 60m",
            "deliver": "telegram",
            "last_run_at": "2026-04-26T20:00:00",
            "last_status": "ok",
            "next_run_at": "2026-04-26T21:00:00",
            "repeat": {"completed": 2, "times": None},
        }
    )

    assert summary == JobSummary(
        job_id="job-1234567890",
        name="AI coding digest",
        status="scheduled",
        schedule="every 60m",
        delivery="telegram",
        last_run="2026-04-26 20:00 · ok",
        next_run="2026-04-26 21:00",
        runs="2/∞",
        actions=(
            "/jobs run job-1234567890",
            "/jobs pause job-1234567890",
            "/jobs edit job-1234567890",
        ),
    )


def test_summarize_job_paused_job_offers_resume_action():
    summary = summarize_job(
        {
            "id": "paused-1",
            "name": "Paused watcher",
            "state": "paused",
            "enabled": False,
            "schedule": {"display": "0 9 * * *"},
            "deliver": "origin",
            "paused_reason": "manual",
            "repeat": {"completed": 1, "times": 3},
        }
    )

    assert summary.status == "paused · manual"
    assert summary.schedule == "0 9 * * *"
    assert summary.delivery == "origin"
    assert summary.last_run == "never"
    assert summary.next_run == "not scheduled"
    assert summary.runs == "1/3"
    assert summary.actions == (
        "/jobs run paused-1",
        "/jobs resume paused-1",
        "/jobs edit paused-1",
    )


def test_render_jobs_dashboard_is_compact_and_deterministic():
    result = render_jobs_dashboard(
        [
            JobSummary(
                job_id="job-1",
                name="Daily briefing",
                status="scheduled",
                schedule="0 9 * * *",
                delivery="origin",
                last_run="never",
                next_run="2026-04-27 09:00",
                runs="0/∞",
                actions=("/jobs run job-1", "/jobs pause job-1", "/jobs edit job-1"),
            ),
            JobSummary(
                job_id="job-2",
                name="Release watcher",
                status="paused",
                schedule="every 120m",
                delivery="telegram",
                last_run="2026-04-26 18:00 · error",
                next_run="not scheduled",
                runs="4/∞",
                actions=("/jobs run job-2", "/jobs resume job-2", "/jobs edit job-2"),
            ),
        ]
    )

    assert result == """## Cron Jobs Cockpit
Status: 2 jobs
Scheduled automation overview.

1. Daily briefing · scheduled
   ID: job-1
   Schedule: 0 9 * * *
   Delivery: origin
   Last run: never
   Next run: 2026-04-27 09:00
   Runs: 0/∞
   Actions: /jobs run job-1 | /jobs pause job-1 | /jobs edit job-1

2. Release watcher · paused
   ID: job-2
   Schedule: every 120m
   Delivery: telegram
   Last run: 2026-04-26 18:00 · error
   Next run: not scheduled
   Runs: 4/∞
   Actions: /jobs run job-2 | /jobs resume job-2 | /jobs edit job-2

Next actions:
1. Continue — Atualizar lista de jobs
2. Detail — Ver detalhes de um job
3. Execute — Criar novo cronjob"""


def test_render_jobs_dashboard_handles_empty_state():
    result = render_jobs_dashboard([])

    assert "## Cron Jobs Cockpit" in result
    assert "Status: empty" in result
    assert "No scheduled jobs found." in result
    assert "Execute — Criar primeiro cronjob" in result


def test_build_job_keyboard_spec_registers_confirmed_cron_actions():
    store = CockpitActionStore()

    keyboard = build_job_keyboard_spec(
        summarize_job({"id": "job-1", "name": "Daily", "state": "scheduled", "enabled": True}),
        store=store,
        chat_id="c1",
        user_id="u1",
    )

    assert [[button.label for button in row] for row in keyboard.rows] == [
        ["Run now", "Pause"],
        ["Edit"],
    ]
    actions = [store.get(button.callback_data.removeprefix("cx:")) for row in keyboard.rows for button in row]
    assert [action.kind for action in actions if action] == ["cron.run", "cron.pause", "cron.edit"]
    assert [action.payload for action in actions if action] == [
        {"job_id": "job-1"},
        {"job_id": "job-1"},
        {"job_id": "job-1"},
    ]
    assert [action.safety_level for action in actions if action] == [
        SafetyLevel.CONFIRM,
        SafetyLevel.CONFIRM,
        SafetyLevel.SAFE,
    ]
