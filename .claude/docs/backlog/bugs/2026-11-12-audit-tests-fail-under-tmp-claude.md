# agent-audit tests: 14 fail when TMPDIR is under /tmp/claude-*

- **Status:** Fixed (uncommitted, no PR yet)
- **Reported:** 2026-11-12
- **Severity:** medium
- **Environment:** local, agent sandboxes (TMPDIR under `/tmp/claude-*`)
- **Source:** agent run: audit-hook-test-suite, spec writing, specker
- **Related:** [audit-hook-test-suite spec](../../features/audit-hook-test-suite/spec.md) (Task 1 fixes it); scope `.claude/hooks/tests/`

## Evidence

14 tests in `.claude/hooks/tests/test_agent_audit.py` fail with `TMPDIR` under `/tmp/claude-*`. Reported by specker; command output not recorded.

## Steps to reproduce

1. Set `TMPDIR=/tmp/claude-<id>/...` (as agent sandboxes do).
2. Run the unittest suite in `.claude/hooks/tests/`.

## Expected behavior

All tests pass regardless of `TMPDIR`.

## Actual behavior

14 tests fail.

## Root cause

The "outside" dirs the tests create land under `/tmp/claude-*`, and `is_scratch()` treats them as scratchpads because `/tmp` is a literal scratch base. The defect is in the tests, not the hook.

## Fix

Fixed in Task 1 of the audit-hook-test-suite spec (2026-11-12): `TempRepoCase` patches `SCRATCH_BASES`. The final gate passed (207 tests), also with `TMPDIR` under a `claude-*` dir. Not committed yet, no PR.
