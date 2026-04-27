# Activity Log

## 2026-04-27 10:36 UTC — Resolve gateway/run.py merge conflict after `hermes update`

### Context
`hermes update` pulled 210 new commits from `origin/main` and replayed the
local Telegram Cockpit autostash. The autostash applied successfully for every
file except `gateway/run.py`, which produced a `<<<<<<< Updated upstream / >>>>>>>
Stashed changes` block inside `_handle_status_command`. The wrapper reset the
working tree to a clean state and preserved the stash at
`stash@{0}: hermes-update-autostash-20260427-103602`.

### Conflict
The upstream branch still rendered `/status` as a markdown bullet list
(`📊 **Hermes Gateway Status**` etc.), while the local Cockpit refactor
replaces the same handler with a `StatusCard`/`render_status_card` flow that
depends on `is_running`, `active_agent`, and `agent_state`. The two halves of
the handler were incompatible: the upstream `lines = [...]` block became dead
code under the new `return render_status_card(...)` exit.

### Resolution
Kept the local Cockpit-card branch — defined `is_running`, `active_agent`, and
`agent_state` exactly once and removed the upstream markdown rendering — so
the rest of the function (`model` resolution, `fields` dict, `StatusCard`
return) compiles against a consistent variable set.

### Verification
- `grep -n '^<<<<<<<\|^=======\|^>>>>>>>' gateway/run.py` → no markers remain.
- `python -m py_compile gateway/run.py` → OK.
- Staged the rest of the autostash (`gateway/cockpit/*`, telegram cockpit
  callbacks, status/jobs/projects helpers, supporting tests, and updated
  docs/notes) so the Cockpit feature ships together with the conflict fix.

## 2026-04-21 11:35 UTC — Gateway restart recovery + health verification

### Context
`hermes gateway restart` exited with code 1. The graceful drain path reported
`✓ Stopped gateway for this profile` but PID 43912 (`python -m hermes_cli.main
gateway run --replace`) remained alive alongside two session daemons
(`session-watcher.py` PID 775, `hermes-session-notify` PID 761). Discord
rate-limited the parallel registration attempt (HTTP 429, retry 22.90s),
confirming a duplicate live gateway.

This reproduces issue #12438 — `SIGUSR1`-based drain does not complete when
the old gateway is unresponsive, leaving a stale process and no CLI recovery
path short of manual force-kill.

### Action taken
1. `kill 43912 775 761` — `SIGTERM` cleared the session daemons; the gateway
   PID stayed up.
2. `kill -9 43912` — `SIGKILL` terminated the stale gateway.
3. Verified fresh process tree (new PIDs 44661 / 44662 / 44691) from the
   restart command's spawn phase.
4. `hermes gateway status` → `✓ Gateway is running (PID: 44691)`.

### Health verification
Ran `scripts/run_tests.sh tests/gateway/` (hermetic, 4 xdist workers,
credential env vars stripped, `TZ=UTC`, `LANG=C.UTF-8`).

- **Result:** 3501 passed · 1 skipped · 2 failed · 147 warnings · 54.00s
- **Failures (both environmental, not gateway defects):**
  - `test_matrix.py::TestMatrixUploadAndSend::test_upload_encrypted_room_uses_file_payload`
    — `No module named 'mautrix'`. Matrix E2EE is an optional extra not
    installed in the active venv.
  - `test_agent_cache.py::TestAgentCacheIdleResume::test_close_vs_release_full_teardown_difference`
    — asserts `"hard-session" in vm_calls`, but the hermetic wrapper
    strips `OPENROUTER_API_KEY`, so the auxiliary LLM path that emits
    `"hard-session"` never runs.

All API server, webhook-integration, session, shutdown/restart, and
platform-adapter tests pass. Running gateway (PID 44691 at verification
time; subsequently respawned to PID 54508 by the restart machinery) is
healthy. `hermes gateway status` reports `✓ Gateway is running`.

### Follow-up
- Issue #12438 could not be closed from this workstation: `gh` is
  authenticated as `syx-labs`, which lacks `CloseIssue` permission on
  `NousResearch/hermes-agent`. Close manually via the web UI (or re-auth
  `gh` with a maintainer token).
- The underlying `SIGUSR1`-only restart fragility remains and is tracked
  under related issues #11932, #7061, #11258, #12875 — this entry records
  the recovery, not a code-level fix.
