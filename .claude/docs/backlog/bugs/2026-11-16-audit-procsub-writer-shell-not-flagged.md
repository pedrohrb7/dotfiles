# agent-audit: a shell reading stdin from a process-substitution writer is not flagged

- **Status:** Open
- **Reported:** 2026-11-16
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix of audit-pipe-into-group-not-flagged, reviewers
- **Related:** [pipe-into-group entry](2026-11-14-audit-pipe-into-group-not-flagged.md)

## Evidence

- `echo 'git push' > >(bash)` gives `['other']`, no flags.

## Steps to reproduce

1. Classify `echo 'git push' > >(bash)` through `analyze_command` (synthetic input, no real execution).

## Expected behavior

The shell inside `>(...)` reads the writer's output, so the text is classified like `| bash` (`git push`).

## Actual behavior

Flags are `['other']`; the command is allowed.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
