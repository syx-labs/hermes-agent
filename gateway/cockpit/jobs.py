"""Cron job dashboard helpers for the Telegram Cockpit."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

from gateway.cockpit.actions import CockpitActionStore, SafetyLevel
from gateway.cockpit.keyboards import ButtonSpec, CockpitKeyboardSpec, build_cockpit_keyboard_spec
from gateway.cockpit.next_actions import NextAction, NextActionKind, render_next_actions


@dataclass(frozen=True)
class JobSummary:
    job_id: str
    name: str
    status: str
    schedule: str = ""
    delivery: str = ""
    last_run: str = "never"
    next_run: str = "not scheduled"
    runs: str = "0/∞"
    actions: Sequence[str] = field(default_factory=tuple)


def _clean(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _format_datetime(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return text


def _schedule_display(job: Mapping[str, Any]) -> str:
    display = _clean(job.get("schedule_display"))
    if display:
        return display
    schedule = job.get("schedule")
    if isinstance(schedule, Mapping):
        return _clean(schedule.get("display") or schedule.get("expr") or schedule.get("kind"), "unscheduled")
    return _clean(schedule, "unscheduled")


def _status_display(job: Mapping[str, Any]) -> str:
    state = _clean(job.get("state"), "scheduled")
    enabled = bool(job.get("enabled", True))
    if not enabled and state != "paused":
        state = "disabled"
    if state == "paused":
        reason = _clean(job.get("paused_reason"))
        return f"paused · {reason}" if reason else "paused"
    if job.get("last_status") == "error":
        return f"{state} · last error"
    delivery_error = _clean(job.get("last_delivery_error"))
    if delivery_error:
        return f"{state} · delivery error"
    return state


def _runs_display(job: Mapping[str, Any]) -> str:
    repeat = job.get("repeat") if isinstance(job.get("repeat"), Mapping) else {}
    completed = repeat.get("completed", 0) if repeat else 0
    times = repeat.get("times") if repeat else None
    total = "∞" if times in (None, "", 0) else str(times)
    return f"{completed}/{total}"


def summarize_job(job: Mapping[str, Any]) -> JobSummary:
    job_id = _clean(job.get("id"), "unknown")
    name = _clean(job.get("name") or job.get("prompt"), job_id)
    status = _status_display(job)
    schedule = _schedule_display(job)
    delivery = _clean(job.get("deliver"), "local")

    last_run = _format_datetime(job.get("last_run_at"))
    if last_run:
        last_status = _clean(job.get("last_status"))
        if last_status:
            last_run = f"{last_run} · {last_status}"
    else:
        last_run = "never"

    next_run = _format_datetime(job.get("next_run_at")) or "not scheduled"
    action_toggle = "resume" if status.startswith("paused") else "pause"

    return JobSummary(
        job_id=job_id,
        name=name,
        status=status,
        schedule=schedule,
        delivery=delivery,
        last_run=last_run,
        next_run=next_run,
        runs=_runs_display(job),
        actions=(
            f"/jobs run {job_id}",
            f"/jobs {action_toggle} {job_id}",
            f"/jobs edit {job_id}",
        ),
    )


def summarize_jobs(jobs: Sequence[Mapping[str, Any]], *, limit: int = 12) -> list[JobSummary]:
    summaries = [summarize_job(job) for job in jobs]
    summaries.sort(key=lambda item: (item.next_run == "not scheduled", item.next_run, item.name.lower()))
    return summaries[:limit]


def build_job_keyboard_spec(
    job: JobSummary,
    *,
    store: CockpitActionStore,
    chat_id: str | None = None,
    user_id: str | None = None,
) -> CockpitKeyboardSpec:
    """Register compact callback actions for one job's common operations."""
    toggle_label = "Resume" if job.status.startswith("paused") else "Pause"
    toggle_kind = "cron.resume" if job.status.startswith("paused") else "cron.pause"
    payload = {"job_id": job.job_id}
    return build_cockpit_keyboard_spec(
        rows=(
            (
                ButtonSpec("Run now", "cron.run", payload, SafetyLevel.CONFIRM),
                ButtonSpec(toggle_label, toggle_kind, payload, SafetyLevel.CONFIRM),
            ),
            (ButtonSpec("Edit", "cron.edit", payload, SafetyLevel.SAFE),),
        ),
        store=store,
        chat_id=chat_id,
        user_id=user_id,
    )


def build_jobs_dashboard_keyboard_spec(
    jobs: Sequence[JobSummary],
    *,
    store: CockpitActionStore,
    chat_id: str | None = None,
    user_id: str | None = None,
    limit: int = 5,
) -> CockpitKeyboardSpec:
    """Register compact callback actions for the top jobs or empty-state actions."""
    rows: list[tuple[ButtonSpec, ...]] = []
    if not jobs:
        rows.extend(
            [
                (ButtonSpec("Create first cronjob", "cron.create", {}, SafetyLevel.SAFE),),
                (ButtonSpec("Cron docs", "cron.docs", {}, SafetyLevel.SAFE),),
            ]
        )
    for job in jobs[:limit]:
        toggle_label = "Resume" if job.status.startswith("paused") else "Pause"
        toggle_kind = "cron.resume" if job.status.startswith("paused") else "cron.pause"
        payload = {"job_id": job.job_id}
        rows.append(
            (
                ButtonSpec(f"Run {job.job_id}", "cron.run", payload, SafetyLevel.CONFIRM),
                ButtonSpec(f"{toggle_label} {job.job_id}", toggle_kind, payload, SafetyLevel.CONFIRM),
            )
        )
        rows.append((ButtonSpec(f"Edit {job.job_id}", "cron.edit", payload, SafetyLevel.SAFE),))
    return build_cockpit_keyboard_spec(rows=tuple(rows), store=store, chat_id=chat_id, user_id=user_id)


def render_jobs_dashboard(jobs: Sequence[JobSummary]) -> str:
    count = len(jobs)
    status = "empty" if count == 0 else f"{count} job" if count == 1 else f"{count} jobs"
    lines = [
        "## Cron Jobs Cockpit",
        f"Status: {status}",
        "Scheduled automation overview." if count else "No scheduled jobs found.",
    ]

    if count:
        lines.append("")
        for index, job in enumerate(jobs, start=1):
            if index > 1:
                lines.append("")
            lines.extend(
                [
                    f"{index}. {job.name} · {job.status}",
                    f"   ID: {job.job_id}",
                    f"   Schedule: {job.schedule}",
                    f"   Delivery: {job.delivery}",
                    f"   Last run: {job.last_run}",
                    f"   Next run: {job.next_run}",
                    f"   Runs: {job.runs}",
                    f"   Actions: {' | '.join(job.actions)}",
                ]
            )

    next_actions: tuple[NextAction, ...]
    if count:
        next_actions = (
            NextAction(NextActionKind.CONTINUE, "Atualizar lista de jobs"),
            NextAction(NextActionKind.EXECUTE, "Criar novo cronjob"),
            NextAction(NextActionKind.DETAIL, "Ver detalhes de um job"),
        )
    else:
        next_actions = (
            NextAction(NextActionKind.EXECUTE, "Criar primeiro cronjob"),
            NextAction(NextActionKind.DETAIL, "Ver documentação de cronjobs"),
        )

    rendered_actions = render_next_actions(next_actions)
    if rendered_actions:
        lines.extend(["", rendered_actions])
    return "\n".join(lines)
