# agent-audit: a mapfile/readarray -C callback runs with mapfile's stdin, not followed

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-pipe-procsub-stdin-family, reviewers (see Evidence)
- **Related:** [pipe-readers entry](2026-11-16-audit-pipe-readers-not-piped-shell.md)

## Evidence

Security re-review of the fix. `f() { bash; }; printf 'x\ngit push\n' | mapfile -C f -c 1` (and `readarray`) passes: the callback runs in the current shell with mapfile's stdin.

All via `analyze_command` on synthetic strings (nothing executed), flags `[]` for the passing forms.

## Steps to reproduce

1. Classify the command above, with `mapfile` and `readarray`.

## Expected behavior

The callback is treated as a code reader of the piped stdin.

## Actual behavior

Not flagged.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
