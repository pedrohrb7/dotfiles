# agent-audit: `$_` is read as an environment name although the same text sets it

- **Status:** Open
- **Reported:** 2026-11-19
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-regex-and-tables-46ae3a7, out_of_scope_collected (pre-existing)
- **Related:** none

## Evidence

- `: docker; $_ restart x`, `: /usr/bin/docker; "$_" restart x` are level A only (pre-existing).

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

`$_` after a command is the last argument of the previous command, so the head is dynamic (level B or program unknown).

## Actual behavior

Treated as an environment name; no fail-closed level.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
