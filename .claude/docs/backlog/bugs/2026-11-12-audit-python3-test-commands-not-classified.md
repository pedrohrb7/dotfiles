# agent-audit: classify_command ignores python3 -m unittest/pytest as test commands

- **Status:** Open
- **Reported:** 2026-11-12
- **Severity:** low
- **Environment:** local
- **Source:** agent run: audit-hook-test-suite, spec writing, specker
- **Related:** [audit-hook-test-suite spec](../../features/audit-hook-test-suite/spec.md); scope `.claude/hooks/agent-audit.py`

## Evidence

`classify_command` recognizes only `python -m pytest`; `python3 -m unittest` and `python3 -m pytest` are not treated as test commands (found by reading `.claude/hooks/agent-audit.py`). Not run.

## Steps to reproduce

1. As an agent other than test-runner, run `python3 -m unittest` for this repo's hook suite.
2. Check the audit output.

## Expected behavior

The command is classified as a test command and `suite_by_non_runner` is flagged.

## Actual behavior

No flag: `suite_by_non_runner` never fires for this repo's hook suite.

## Root cause

Not diagnosed yet. Suspected: the test-command patterns in `classify_command` match only `python -m pytest`.

## Fix

Not diagnosed yet.
