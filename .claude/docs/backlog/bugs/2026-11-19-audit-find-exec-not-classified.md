# agent-audit: the program of `find -exec` / `-execdir` / `-ok` is not classified

- **Status:** Open
- **Reported:** 2026-11-19
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-regex-and-tables-46ae3a7, out_of_scope_collected (pre-existing)
- **Related:** none

## Evidence

- `find . -exec git push \;` passes at top level (pre-existing).

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

The command after -exec is classified like a command position (git_push flagged, shells and readers read as code).

## Actual behavior

No flag.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
