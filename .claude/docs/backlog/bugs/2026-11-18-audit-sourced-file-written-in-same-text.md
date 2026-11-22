# agent-audit: a file written earlier in the same text and then sourced is not read

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-pipe-procsub-stdin-family, reviewers (see Evidence)
- **Related:** [pipe-readers entry](2026-11-16-audit-pipe-readers-not-piped-shell.md)

## Evidence

Security re-review of the fix. These pass:
- `echo 'git push' > x.sh; . ./x.sh`
- `echo 'f() { bash; }' > x.sh; . ./x.sh; echo 'git push' | f`

All via `analyze_command` on synthetic strings (nothing executed), flags `[]` for the passing forms.

## Steps to reproduce

1. Classify each command above.

## Expected behavior

The content written to the file is classified when the file is sourced in the same text.

## Actual behavior

Not flagged.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
