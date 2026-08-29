"""Tests for the mid-run /goal gate and the fork's structured-goal verbs.

While the agent is busy, ``GatewayRunner._busy_goal_command`` only lets
control-plane verbs through (status/pause/wait/gate...). The fork adds
structured-goal verbs (structured/round/evidence/reviewer/decision/report)
that only write to the goal store and never inject a prompt into the running
turn — so they must be reachable mid-run too, which is exactly when a round's
evidence gets recorded. Free-text goals (and ``report <text>`` /
``structured <text>``, which the handler would treat as a new goal) must keep
being rejected.
"""

import asyncio
from types import SimpleNamespace

import pytest

from gateway.run import GatewayRunner


def _runner(calls):
    runner = GatewayRunner.__new__(GatewayRunner)

    async def _handle_goal_command(event):
        calls.append(event.get_command_args())
        return "handled"

    runner._handle_goal_command = _handle_goal_command
    return runner


def _event(args: str):
    return SimpleNamespace(get_command_args=lambda: args)


def _run(runner, args: str) -> str:
    return asyncio.run(runner._busy_goal_command(_event(args), "quick-key", None))


@pytest.mark.parametrize(
    "args",
    [
        "structured",
        "structured status",
        "round Investigate the flaky login test",
        "evidence pytest tests/login -q -> 12 passed",
        "reviewer pass looks good",
        "decision complete",
        "decision blocked --force waiting on infra",
        "report",
        "Report",  # the gate compares lowercased; handler receives the original
    ],
)
def test_structured_verbs_are_control_plane_mid_run(args):
    calls = []
    runner = _runner(calls)
    assert _run(runner, args) == "handled"
    assert calls == [args]


@pytest.mark.parametrize(
    "args",
    [
        "ship the release by friday",
        "report the sprint findings to the team",
        "structured plan for the migration",
    ],
)
def test_free_text_goal_is_still_rejected_mid_run(args):
    calls = []
    runner = _runner(calls)
    reply = _run(runner, args)
    assert "Agent is running" in reply
    assert calls == []


@pytest.mark.parametrize("args", ["", "status", "pause", "wait 4242", "gate add pytest -q"])
def test_upstream_control_verbs_unchanged(args):
    calls = []
    runner = _runner(calls)
    assert _run(runner, args) == "handled"
    assert calls == [args]
