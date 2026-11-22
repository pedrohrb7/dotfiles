# agent-audit: BASH_ENV is not modeled (a stdin or process-substitution file is sourced by bash)

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-stdin-other-sources-family, out_of_scope_collected (pre-existing)
- **Related:** none

## Evidence

- `echo x | BASH_ENV=/dev/stdin bash -c true`, `env BASH_ENV=/dev/stdin bash -c true` and `BASH_ENV=<(x) bash -c true` pass.

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

A non-interactive bash with BASH_ENV pointing at stdin or a procsub is flagged like a sourced file.

## Actual behavior

Not flagged.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
