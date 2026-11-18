# agent-audit: `export "$(cat f)"` (dynamic export) passes

- **Status:** Open
- **Reported:** 2026-11-19
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-regex-and-tables-46ae3a7, out_of_scope_collected (pre-existing)
- **Related:** none

## Evidence

- `export "$(cat f)"; git status` passes (pre-existing); the export can set GIT_CONFIG_PARAMETERS and similar.

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

A dynamic export operand fails closed (dynamic environment for later commands).

## Actual behavior

No flag.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
