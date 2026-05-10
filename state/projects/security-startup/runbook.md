# Runbook

## Verification commands used

```bash
cd /Users/shadow/Projects/github/syx-labs/security-startup
bun test apps/api/src/features/health/routes.test.ts packages/domain/src/quote/rule-versions.test.ts
bun run --filter @aps/api typecheck
bun run --filter @aps/domain typecheck
git diff --check
```

## Independent review command pattern

```bash
python3 - <<'PY' | HOME=/Users/shadow XDG_CONFIG_HOME=/Users/shadow/.config shadow -p '<read-only review prompt>' --model sonnet --max-turns 30 --allowedTools Read,Bash
# print review packet
PY
```
