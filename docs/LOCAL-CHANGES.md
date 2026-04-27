# Local Gabriel Hermes Changes

This checkout carries Gabriel-private Hermes changes that are not intended for upstream `NousResearch/hermes-agent`.

## Telegram Cockpit v1

Local commit:

```text
eb173ce42 fix(gateway): resolve run.py merge conflict in /status handler
```

Local references:

```text
gabriel/telegram-cockpit-v1
gabriel/hermes-cockpit-v1
```

Patch backup:

```text
/tmp/hermes-cockpit-eb173ce42.patch
```

Validation performed before preserving locally:

```text
python -m pytest tests/gateway/test_cockpit_actions.py tests/gateway/test_cockpit_cards.py tests/gateway/test_cockpit_jobs.py tests/gateway/test_cockpit_jobs_command.py tests/gateway/test_cockpit_keyboards.py tests/gateway/test_cockpit_newtask.py tests/gateway/test_cockpit_next_actions.py tests/gateway/test_cockpit_projects.py tests/gateway/test_cockpit_projects_command.py tests/gateway/test_cockpit_research.py tests/gateway/test_cockpit_review.py tests/gateway/test_cockpit_state.py tests/gateway/test_cockpit_status_dashboard.py tests/gateway/test_status.py tests/gateway/test_telegram_cockpit_callbacks.py tests/hermes_cli/test_gateway_service.py tests/tools/test_tool_backend_helpers.py -q -o 'addopts='
# 256 passed

git diff --check origin/main
python -m compileall gateway/cockpit gateway/run.py gateway/status.py hermes_cli/commands.py hermes_cli/gateway.py tools/tool_backend_helpers.py -q
```

Notes:

- Do not push this change to upstream NousResearch unless Gabriel explicitly changes direction.
- If rebasing against upstream, preserve/reapply branch `gabriel/telegram-cockpit-v1`.
