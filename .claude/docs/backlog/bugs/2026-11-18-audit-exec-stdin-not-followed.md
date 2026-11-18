# agent-audit: stdin set by exec is not followed

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-pipe-procsub-stdin-family, reviewers (see Evidence)
- **Related:** [pipe-readers entry](2026-11-16-audit-pipe-readers-not-piped-shell.md)

## Evidence

Code review of the fix (pre-existing). These pass: `exec < <(x); bash`, `exec 0< <(x); { bash; }`.

All via `analyze_command` on synthetic strings (nothing executed), flags `[]` for the passing forms.

## Steps to reproduce

1. Classify each command above.

## Expected behavior

After `exec` rebinds fd 0 to a process substitution, later shells reading stdin are dynamic_code.

## Actual behavior

Not flagged.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
