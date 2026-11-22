# agent-audit: a backtick in a `<&` target and a dynamic attached `at -f$s` value are not resolved

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** low
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-stdin-other-sources-family, round-2 security review (user decision)
- **Related:** none

## Evidence

- A backtick command substitution in a `<&` target and `at -f$s` (dynamic attached value) pass.

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

Both fail closed (dynamic_code).

## Actual behavior

Not flagged.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
