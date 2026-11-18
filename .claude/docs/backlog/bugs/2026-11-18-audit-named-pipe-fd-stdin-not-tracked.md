# agent-audit: a shell reading a named pipe or an fd set up elsewhere is not tracked

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-pipe-procsub-stdin-family, reviewers (see Evidence)
- **Related:** [pipe-readers entry](2026-11-16-audit-pipe-readers-not-piped-shell.md)

## Evidence

Diagnosis of the fix. These pass: `mkfifo p; bash < p`, `exec 3< p; bash <&3`.

All via `analyze_command` on synthetic strings (nothing executed), flags `[]` for the passing forms.

## Steps to reproduce

1. Classify each command above.

## Expected behavior

A shell reading a fifo or a dup'd fd is treated as reading code from an unknown source.

## Actual behavior

Not flagged.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
