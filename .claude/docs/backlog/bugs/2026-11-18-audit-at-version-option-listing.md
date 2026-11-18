# agent-audit: at -V is treated as listing but still reads the job from stdin

- **Status:** Fixed (2026-11-19, not committed)
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: security review of commit 46ae3a7 (stdin family fix), confirmed with analyze_command on synthetic strings
- **Related:** none

## Evidence

- `echo x | at -V now` gives []; at prints the version and still reads the pipe as a job. `_AT_LISTING` includes `V`.

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

`at -V` with a time reads stdin as a job and is flagged like any at job.

## Actual behavior

No flag: the V option puts the call in the listing set.

## Root cause

`V` was in `_AT_LISTING`.

## Fix

Removed `V` from `_AT_LISTING`. Fix run: .claude/runs/bug-audit-regex-and-tables-46ae3a7.json. Gate: 1145 tests pass. Not committed yet.
