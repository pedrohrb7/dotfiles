# agent-audit: env -C / --chdir is not counted as a directory change

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-stdin-other-sources-family, out_of_scope_collected (pre-existing)
- **Related:** none

## Evidence

- `echo x | env -C /dev bash stdin` passes (relative stdin alias after the change).

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

env -C / --chdir moves the cwd used to resolve relative stdin aliases.

## Actual behavior

Not flagged.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
