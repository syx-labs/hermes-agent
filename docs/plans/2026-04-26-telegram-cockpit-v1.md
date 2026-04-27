# Telegram Cockpit v1 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make Hermes on Telegram feel like an interactive visual cockpit with guided commands, inline actions, rich artifacts, and proactive operational status.

**Architecture:** Build on the existing Telegram adapter instead of replacing it. Reuse the central slash command registry, current inline keyboard support, media delivery pipeline, session isolation, and gateway command dispatch; add a generic action router and lightweight state layer so buttons can safely trigger workflows.

**Tech Stack:** Python, python-telegram-bot, Hermes gateway adapters, existing slash command registry, pytest.

---

## Audit: current Telegram gateway capabilities

Source files inspected:

- `gateway/platforms/telegram.py`
- `gateway/platforms/base.py`
- `hermes_cli/commands.py`
- `website/docs/user-guide/messaging/telegram.md`

### Already supported

- Telegram long polling and webhook mode.
- Bot command menu registration via `telegram_menu_commands(max_commands=100)`.
- Text, command, location, venue, photo, video, audio, voice, document, and sticker input handlers.
- MarkdownV2 formatting with fallback to plain text.
- Message splitting around Telegram's 4096 UTF-16 message limit.
- Markdown table wrapping into fenced code blocks.
- Native media output for images, documents, videos, GIF animations, audio, and voice bubbles.
- `MEDIA:/path` extraction through the base platform adapter.
- Markdown image extraction and local file auto-detection for native attachment delivery.
- Incoming voice/audio caching for STT.
- Auto-TTS response for voice-originated messages when voice mode is enabled.
- Incoming photo caching for vision tools.
- Photo burst/media group batching to avoid self-interruption.
- Incoming `.md`/`.txt` document content injection when under 100 KB.
- Supported document downloads up to 20 MB.
- Static sticker analysis through vision plus sticker description cache.
- Telegram DM topics and group forum topic session isolation.
- Skill binding per configured DM/group topic.
- Group mention gating, ignored threads, free-response chats, and wake-word regexes.
- Interactive model picker with provider/model pagination using inline keyboards.
- Interactive dangerous command approval buttons.
- Interactive update prompt buttons.
- Authorized callback gating based on `TELEGRAM_ALLOWED_USERS`.
- Runtime status machinery in `gateway/status.py`.

### Current gaps for Cockpit UX

- Inline keyboards are implemented only for model picker, command approval, and update prompts; there is no generic button/action framework.
- Callback data handling is hardcoded in `TelegramAdapter._handle_callback_query()`.
- No generic action state store for multi-step workflows like `/newtask`, `/projects`, `/jobs`, or `/briefing`.
- No generic card/template renderer for consistent Telegram responses.
- No visual card renderer to PNG/SVG.
- No artifact manager/index that groups generated files by session/project.
- No project registry for recurring project aliases, paths, skills, and actions.
- Existing `/status` is session-oriented, not a full Telegram cockpit dashboard.
- `/jobs` and `/projects` do not exist as gateway commands.
- `/diagram`, `/briefing`, `/research`, and `/review` do not exist as first-class cockpit commands.
- Button-triggered workflows cannot currently call tools/workflows generically.
- Safety classification is command-approval-focused, not generalized for arbitrary actions.
- Existing link and screenshot handling relies mainly on agent behavior; no Telegram-specific action suggestions are attached to the event.

---

## MVP acceptance criteria

Telegram Cockpit v1 is done when:

1. `/status` returns a cockpit-style dashboard with profile, model, gateway connectivity, active sessions/tasks, and useful next-action buttons.
2. `/jobs` lists cron jobs and exposes safe buttons for run/pause/resume/edit intents.
3. `/projects` lists configured projects and exposes actions like continue, inspect, plan, review, diagram, and handoff.
4. `/newtask` provides a guided task wizard with type, mode, agent, and deliverable choices.
5. Generic callback routing exists for cockpit actions without hardcoding every flow inside `TelegramAdapter._handle_callback_query()`.
6. Callback actions enforce authorization and safety levels.
7. Textual cards are consistent and snapshot-testable.
8. Generated artifacts can be saved under a predictable path and sent back through Telegram.
9. Tests cover callback routing, state expiry, command rendering, and at least one full flow.

---

## Implementation tasks

### Task 1: Add cockpit command definitions

**Objective:** Register the new Telegram Cockpit slash commands in the central command registry.

**Files:**
- Modify: `hermes_cli/commands.py`
- Test: `tests/hermes_cli/test_commands.py` or nearest existing command registry test

**Steps:**
1. Add `CommandDef` entries for `jobs`, `projects`, `newtask`, `research`, `review`, `diagram`, and `briefing`.
2. Mark them gateway-capable, not CLI-only.
3. Keep descriptions short enough for Telegram menu constraints.
4. Run targeted command registry tests.

**Verification:**
- `telegram_menu_commands()` includes the new commands unless hidden by the 100-command limit.
- `/commands` help output includes them.

---

### Task 2: Create a generic cockpit callback namespace

**Objective:** Reserve a compact callback data format for cockpit actions.

**Files:**
- Create: `gateway/cockpit/actions.py`
- Modify: `gateway/platforms/telegram.py`
- Test: `tests/gateway/test_telegram_cockpit_callbacks.py`

**Design:**

Use compact callback prefixes to respect Telegram's 64-byte callback data limit:

```text
cx:<action_id>
```

`action_id` maps to a server-side state record; do not encode full payloads in callback data.

**Steps:**
1. Create `CockpitAction` dataclass with `id`, `kind`, `payload`, `chat_id`, `user_id`, `created_at`, `expires_at`, and `safety_level`.
2. Create in-memory `CockpitActionStore` with TTL cleanup.
3. Add unit tests for create/get/consume/expire.
4. In `TelegramAdapter._handle_callback_query()`, route `cx:` callbacks to a new cockpit handler before falling through.

**Verification:**
- Unknown/expired `cx:` callbacks answer with a friendly expired message.
- Unauthorized users cannot invoke actions.

**Implemented:**
- `gateway/cockpit/actions.py`
- `tests/gateway/test_cockpit_actions.py`
- `tests/gateway/test_telegram_cockpit_callbacks.py`
- `TelegramAdapter._handle_cockpit_callback()` plus `cx:` routing before legacy callback namespaces.

---

### Task 3: Extract generic Telegram keyboard sending helper

**Objective:** Avoid each cockpit feature hand-building Telegram inline keyboards.

**Files:**
- Modify: `gateway/platforms/telegram.py`
- Create: `gateway/cockpit/keyboards.py`
- Test: `tests/gateway/test_telegram_cockpit_keyboards.py`

**Steps:**
1. Define a platform-neutral `ButtonSpec(label, action_kind, payload, safety_level)`.
2. Add helper to create action records and return compact `cx:` callback rows.
3. Keep labels short and callback data compact.
4. Ensure existing model picker and approval flows remain untouched.

**Verification:**
- Rendering two rows of buttons produces callback specs with `cx:` callback data.
- Existing approval/model picker callback tests still pass.

**Implemented:**
- `gateway/cockpit/keyboards.py`
- `tests/gateway/test_cockpit_keyboards.py`
- Keyboard specs allocate server-side `CockpitAction` records instead of encoding payloads in Telegram callback data.

---

### Task 4: Add textual card templates

**Objective:** Standardize cockpit-style responses before building visual PNG cards.

**Files:**
- Create: `gateway/cockpit/cards.py`
- Test: `tests/gateway/test_cockpit_cards.py`

**Cards:**
- `StatusCard`
- `ProjectCard`
- `JobCard`
- `PlanCard`
- `DecisionCard`
- `ResearchCard`
- `HandoffCard`

**Steps:**
1. Implement pure functions that return Markdown-safe plain text.
2. Keep output concise for Telegram.
3. Add snapshot-like tests using exact string comparisons.

**Verification:**
- Cards render stable text without platform-specific imports.

**Implemented:**
- `gateway/cockpit/cards.py`
- `tests/gateway/test_cockpit_cards.py`

---

### Task 4b: Standardize next-action blocks

**Objective:** Give important Telegram responses a predictable action vocabulary that can later map directly to inline buttons.

**Files:**
- Create: `gateway/cockpit/next_actions.py`
- Test: `tests/gateway/test_cockpit_next_actions.py`
- Modify: `gateway/cockpit/cards.py`
- Modify: `tests/gateway/test_cockpit_cards.py`

**Canonical action types:**
- Continue
- Detail
- Execute
- Generate file
- Schedule
- Save skill

**Verification:**
- Next-action blocks render in canonical order.
- Empty labels are omitted.
- Duplicate action kinds keep the first useful item.
- Cards can render structured next actions while preserving legacy string actions.

**Implemented:**
- `gateway/cockpit/next_actions.py`
- `tests/gateway/test_cockpit_next_actions.py`
- Structured `NextAction` support in card renderers.

---

### Task 5: Implement `/status` cockpit dashboard

**Objective:** Upgrade `/status` from session info to a useful Telegram operational dashboard while preserving existing behavior for other platforms.

**Files:**
- Modify: `gateway/run.py` or the current gateway command dispatch location
- Modify/Create: `gateway/cockpit/status.py`
- Test: `tests/gateway/test_cockpit_status.py`

**Dashboard should include:**
- Active profile/home path.
- Current provider/model where available.
- Platform connectivity summary.
- Active session/task count.
- Streaming/background state if available.
- Suggested actions: jobs, projects, new task, voice status, help.

**Verification:**
- `/status` works while another task is running because it is already a bypass command.
- Dashboard renders profile, model, tools, jobs, processes, recent sessions, connectivity, session metadata, and standardized next actions.

**Implemented:**
- `gateway/run.py` `/status` now renders `StatusCard` from the Cockpit template layer.
- `tests/gateway/test_cockpit_status_dashboard.py`

---

### Task 6: Implement `/jobs` listing and actions

**Objective:** Show cron jobs in Telegram and expose buttons for common operations.

**Files:**
- Create: `gateway/cockpit/jobs.py`
- Modify: gateway command dispatcher
- Test: `tests/gateway/test_cockpit_jobs.py`

**Actions:**
- Run now.
- Pause.
- Resume.
- Edit intent message.

**Safety:**
- Run/pause/resume: confirmation optional for owner-only DM; confirmation required in groups.
- Remove/delete: not in v1 buttons.

**Verification:**
- Job list renders even when there are zero jobs.
- Buttons generate `cx:` action records.

**Implemented:**
- `gateway/cockpit/jobs.py` adds `JobSummary`, cron-job normalization, deterministic `/jobs` dashboard rendering, and per-job keyboard specs that register compact `cx:` actions for `cron.run`, `cron.pause`/`cron.resume`, and `cron.edit`.
- `gateway/run.py` adds `_handle_jobs_command` and dispatches `/jobs`, including active-session bypass behavior.
- `hermes_cli/commands.py` registers `/jobs` as a gateway command.
- `/jobs` supports:
  - `/jobs` or `/jobs list` for the dashboard;
  - `/jobs run <job_id>` to trigger a job on the next scheduler tick;
  - `/jobs pause <job_id>`;
  - `/jobs resume <job_id>`;
  - `/jobs edit <job_id>` as an edit-intent message pointing to `cronjob(action='update', ...)`.
- Tests:
  - `tests/gateway/test_cockpit_jobs.py`;
  - `tests/gateway/test_cockpit_jobs_command.py`.
- Verified with the Cockpit/Gateway suite: `135 passed`.

---

### Task 7: Implement Project Registry

**Objective:** Provide a durable registry of recurring projects and actions.

**Files:**
- Create: `gateway/cockpit/projects.py`
- Create: `tests/gateway/test_project_registry.py`
- Optional config path: `<HERMES_HOME>/projects.yaml` or `config.yaml` under `cockpit.projects`

**Initial fields:**

```yaml
name: adaptive-context-harness
aliases: [ach, harness]
path: /Users/shadow/projects/...
skills: [adaptive-context-harness]
commands:
  test: bun run test
  review: custom workflow
last_session: optional
```

**Verification:**
- Registry loads from config.
- Missing paths are reported but do not crash `/projects`.

**Implemented:**
- `gateway/cockpit/projects.py` adds `ProjectEntry`, YAML/config loading, alias lookup, deterministic dashboard rendering, and safe `cx:` keyboard specs for project actions.
- Registry source order:
  - `HERMES_COCKPIT_PROJECTS_FILE` when set;
  - `<HERMES_HOME>/projects.yaml` by default;
  - direct config mapping support for `cockpit.projects`.
- Missing paths are rendered as `missing path`; existing paths as `available`.
- Tests: `tests/gateway/test_cockpit_projects.py`.

---

### Task 8: Implement `/projects`

**Objective:** Let Telegram list recurring projects and expose action buttons.

**Files:**
- Create: `gateway/cockpit/projects_command.py`
- Modify: gateway command dispatcher
- Test: `tests/gateway/test_cockpit_projects_command.py`

**Actions:**
- Continue.
- Inspect repo.
- Create plan.
- Code review.
- Generate diagram.
- Handoff.

**Verification:**
- `/projects` renders project cards and buttons.

**Implemented:**
- `gateway/run.py` adds `_handle_projects_command` and dispatches `/projects`, including active-session bypass behavior.
- `hermes_cli/commands.py` registers `/projects` as a gateway command.
- `/projects` supports:
  - `/projects` or `/projects list` for the dashboard;
  - `/projects continue <name-or-alias>`;
  - `/projects inspect <name-or-alias>`;
  - `/projects review <name-or-alias>`;
  - `/projects diagram <name-or-alias>`;
  - `/projects handoff <name-or-alias>`.
- Tests: `tests/gateway/test_cockpit_projects_command.py`.

---

### Task 9: Implement lightweight interaction state for `/newtask`

**Objective:** Support guided multi-step Telegram flows.

**Files:**
- Create: `gateway/cockpit/state.py`
- Test: `tests/gateway/test_cockpit_state.py`

**State:**
- `flow_id`
- `chat_id`
- `user_id`
- `step`
- `answers`
- `expires_at`

**Verification:**
- State expires automatically.
- Only the initiating user can continue a flow in a group.

**Implemented:**
- `gateway/cockpit/state.py` defines `InteractionState` and `InteractionStateStore` for short-lived guided flows.
- Flow state is keyed by `flow_id`, `chat_id`, `user_id`, `step`, `answers`, `created_at`, `updated_at`, and `expires_at`.
- The store supports create, latest lookup by owner/flow, guarded get, answer/advance, single completion, and TTL pruning.
- Guarded lookup enforces chat/user ownership, so another user in the same group cannot continue the initiating user's flow.
- Tests: `tests/gateway/test_cockpit_state.py`.

---

### Task 10: Implement `/newtask` wizard

**Objective:** Guide task creation through buttons.

**Files:**
- Create: `gateway/cockpit/newtask.py`
- Modify: gateway command dispatcher
- Test: `tests/gateway/test_cockpit_newtask.py`

**Flow:**
1. Type: Code, Research, Document, Infra, Design, Automation.
2. Mode: Plan, Execute, Delegate, Review only.
3. Agent: Hermes, Claude Code, Codex, Supervisor.
4. Deliverable: Chat, Markdown, PDF, Diagram, PR.
5. Final confirmation: enqueue as a normal user prompt or background task.

**Safety:**
- Execution/delegation requires explicit final confirmation.

**Implemented:**
- `gateway/cockpit/newtask.py` defines the `/newtask` wizard steps, option labels/descriptions, prompt preview builder, deterministic text renderer, and keyboard specs.
- `/newtask` starts a guided flow and renders the first step.
- Text fallback commands are supported for every step:
  - `/newtask type <code|research|document|infra|design|automation>`
  - `/newtask mode <plan|execute|delegate|review>`
  - `/newtask agent <hermes|claude|codex|supervisor>`
  - `/newtask deliverable <chat|markdown|pdf|diagram|pr>`
  - `/newtask confirm`
- `build_newtask_keyboard_spec` registers compact `cx:` callbacks with server-side payloads for `newtask.select` and final `newtask.confirm`.
- `gateway/run.py` initializes `_newtask_state_store`, registers `_handle_newtask_command`, and dispatches `/newtask` through the same command bypass paths as `/status`, `/jobs`, and `/projects`.
- `hermes_cli/commands.py` registers `/newtask` as `gateway_only=True` and includes it in `ACTIVE_SESSION_BYPASS_COMMANDS`.
- Tests: `tests/gateway/test_cockpit_newtask.py`.

---

### Task 11: Implement `/research` guided flow

**Objective:** Guide research request creation through Telegram Cockpit options.

**Files:**
- Create: `gateway/cockpit/research.py`
- Modify: gateway command dispatcher
- Test: `tests/gateway/test_cockpit_research.py`

**Flow:**
1. Depth: Short summary, Deep research, Comparative.
2. Output: Chat summary, Obsidian note, Markdown file, PDF.
3. Artifact: No extra artifact, Sources table, Diagram, Comparison matrix.
4. Topic: free-text question/topic.
5. Final confirmation.

**Implemented:**
- `gateway/cockpit/research.py` defines the `/research` guided wizard, option labels/descriptions, prompt preview builder, deterministic text renderer, and keyboard specs.
- Text fallback commands are supported:
  - `/research depth <short|deep|comparative>`
  - `/research output <chat|obsidian|markdown|pdf>`
  - `/research artifact <none|sources|diagram|comparison>`
  - `/research topic <question or topic>`
  - `/research confirm`
- `build_research_keyboard_spec` registers compact `cx:` callbacks for `research.select` and final `research.confirm`.
- `gateway/run.py` initializes `_research_state_store`, registers `_handle_research_command`, and dispatches `/research` through command bypass paths.
- `hermes_cli/commands.py` registers `/research` as `gateway_only=True` and includes it in `ACTIVE_SESSION_BYPASS_COMMANDS`.
- Tests: `tests/gateway/test_cockpit_research.py`.

---

### Task 12: Implement `/review` guided flow

**Objective:** Guide code review request creation through Telegram Cockpit options.

**Files:**
- Create: `gateway/cockpit/review.py`
- Modify: gateway command dispatcher
- Test: `tests/gateway/test_cockpit_review.py`

**Flow:**
1. Scope: Working diff, Pull request, Project path.
2. Checks: Quick review, Full review, Security focus, Tests focus.
3. Runner: Hermes, Codex, Claude Code, Supervisor.
4. Output: Chat, Report, PR comment, Patch plan.
5. Target: path, PR URL, branch, or current project.
6. Final confirmation.

**Implemented:**
- `gateway/cockpit/review.py` defines the `/review` guided wizard, option labels/descriptions, prompt preview builder, deterministic text renderer, and keyboard specs.
- Text fallback commands are supported:
  - `/review scope <diff|pr|path>`
  - `/review checks <quick|full|security|tests>`
  - `/review runner <hermes|codex|claude|supervisor>`
  - `/review output <chat|report|pr|patch>`
  - `/review target <path, PR URL, branch, or current>`
  - `/review confirm`
- `build_review_keyboard_spec` registers compact `cx:` callbacks for `review.select` and final `review.confirm`.
- `gateway/run.py` initializes `_review_state_store`, registers `_handle_review_command`, and dispatches `/review` through command bypass paths.
- `hermes_cli/commands.py` registers `/review` as `gateway_only=True` and includes it in `ACTIVE_SESSION_BYPASS_COMMANDS`.
- Tests: `tests/gateway/test_cockpit_review.py`.

---

### Task 13: Implement `/briefing`

**Objective:** Generate concise executive summaries and optionally attach files/audio later.

**Files:**
- Create: `gateway/cockpit/briefing.py`
- Test: `tests/gateway/test_cockpit_briefing.py`

**V1 behavior:**
- Text card only.
- Buttons: Markdown file, PDF later, audio later, expand.

**Verification:**
- Works without image/PDF dependencies.

---

### Task 12: Add Artifact Manager foundation

**Objective:** Store generated artifacts predictably for Telegram delivery.

**Files:**
- Create: `gateway/cockpit/artifacts.py`
- Test: `tests/gateway/test_cockpit_artifacts.py`

**Path pattern:**

```text
<HERMES_HOME>/artifacts/telegram/<session-or-chat>/<YYYY-MM-DD>/<artifact-id>/
```

**Verification:**
- Writes metadata JSON.
- Returns host-visible paths suitable for `MEDIA:/...`.

---

### Task 13: Add visual card renderer later behind optional dependency checks

**Objective:** Generate PNG/SVG cards after textual cockpit is stable.

**Files:**
- Create: `gateway/cockpit/renderers/card_renderer.py`
- Test: `tests/gateway/test_card_renderer.py`

**Approach:**
- Start with SVG string generation using standard library.
- PNG export can be optional and skipped when renderer dependencies are missing.

**Verification:**
- SVG output is deterministic.

---

### Task 14: Add `/diagram` integration

**Objective:** Provide a first-class diagram command.

**Files:**
- Create: `gateway/cockpit/diagram.py`
- Modify: gateway command dispatcher
- Test: `tests/gateway/test_cockpit_diagram.py`

**V1 behavior:**
- Ask the agent to generate Mermaid from provided prompt/context.
- If renderer exists, attach SVG/PNG; otherwise return Mermaid code block.

---

### Task 15: Add `/research` and `/review` guided entrypoints

**Objective:** Make common user workflows one-tap from Telegram.

**Files:**
- Create: `gateway/cockpit/research.py`
- Create: `gateway/cockpit/review.py`
- Test: matching gateway tests

**V1 behavior:**
- These commands build structured prompts and route them through the existing agent loop.
- Actual research/review implementation remains tool/skill-driven.

---

### Task 16: Improve screenshot/link follow-up actions

**Objective:** Attach contextual next-action buttons after image/link inputs.

**Files:**
- Modify: `gateway/platforms/base.py` or Telegram-specific post-processing hook
- Test: `tests/gateway/test_telegram_photo_interrupts.py` plus new tests

**V1 behavior:**
- Do not change vision/link analysis behavior.
- Add optional post-response buttons for image/link events when supported by Telegram.

---

### Task 17: Documentation

**Objective:** Document the feature for users and developers.

**Files:**
- Modify: `website/docs/user-guide/messaging/telegram.md`
- Create: `website/docs/developer-guide/telegram-cockpit.md`

**Include:**
- Commands.
- Button safety model.
- Artifact paths.
- Known Telegram limits.
- How to configure projects.

---

### Task 18: Test matrix and rollout

**Objective:** Ship safely.

**Commands:**

```bash
python -m pytest tests/gateway/test_telegram_approval_buttons.py -q
python -m pytest tests/gateway/test_telegram_format.py -q
python -m pytest tests/gateway/test_telegram_documents.py -q
python -m pytest tests/gateway/test_cockpit_*.py -q
python -m pytest tests/hermes_cli/ -q
```

**Rollout:**
1. Enable behind `cockpit.telegram.enabled: false` default if risk is high.
2. Test locally with Gabriel in Telegram DM.
3. Enable commands one by one: status, jobs, projects, newtask.
4. Add visual renderers only after textual flow is stable.

---

## Recommended implementation order

1. Generic action store/router.
2. Text card templates.
3. `/status` cockpit.
4. `/jobs`.
5. Project Registry + `/projects`.
6. `/newtask` wizard.
7. Artifact Manager.
8. `/briefing` and `/diagram`.
9. `/research` and `/review`.
10. Visual card renderer.
11. Screenshot/link next-action buttons.
12. Docs and full rollout.
