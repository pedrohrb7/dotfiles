# agent-audit: plain pipe readers other than a shell are not flagged as piped_shell

- **Status:** Open
- **Reported:** 2026-11-16
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix of audit-pipe-into-group-not-flagged, reviewers
- **Related:** [pipe-into-group entry](2026-11-14-audit-pipe-into-group-not-flagged.md)

## Evidence

- `echo x | eval bash`, `| busybox sh`, `| python3 -`, `| perl`, `| node -` are not flagged `piped_shell`.
- Pre-existing, also outside groups.

## Steps to reproduce

1. Classify each command above (synthetic input).

## Expected behavior

A command that executes its stdin as code is flagged like `| bash`.

## Actual behavior

Not flagged.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.

## Seen again (2026-11-18)

Source: reviewers of fix bug-audit-pipe-procsub-stdin-family (low, possibly the same root cause). `echo 'git push' | awk '{system($0)}'`, `| sed e` and `| python3 -c "import os; os.system(input())"` pass (`analyze_command`, synthetic strings, flags `[]`).
