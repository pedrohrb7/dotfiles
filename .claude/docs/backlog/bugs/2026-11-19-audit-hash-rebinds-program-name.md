# agent-audit: `hash` rebinding a program name is not modeled

- **Status:** Open
- **Reported:** 2026-11-19
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-regex-and-tables-46ae3a7, out_of_scope_collected (pre-existing)
- **Related:** none

## Evidence

- `hash -p /bin/sh gzip; gzip -c 'git push'` passes.
- `hash gzip=/bin/sh` passes (pre-existing).

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

A `hash -p PATH NAME` or `hash NAME=PATH` in the text makes NAME resolve to PATH, so later uses are classified as that program (a shell here).

## Actual behavior

No flag.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
