# agent-audit: operand-path stdin aliases are matched exactly

- **Status:** Open
- **Reported:** 2026-11-16
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix of audit-pipe-into-group-not-flagged, reviewers
- **Related:** [pipe-into-group entry](2026-11-14-audit-pipe-into-group-not-flagged.md)

## Evidence

- `echo x | bash /dev/./stdin` and `| source /dev/./stdin` are allowed (`_first_operand_code`, `_STDIN_FILES` exact match).
- The same alias family is closed for redirects by the pipe-into-group fix.

## Steps to reproduce

1. Classify `echo x | bash /dev/./stdin`.
2. Classify `echo x | source /dev/./stdin`.

## Expected behavior

Paths that name stdin (`/dev/./stdin`, `/proc/self/fd/0`, ...) are read as stdin.

## Actual behavior

Allowed, nothing flagged.

## Root cause

`_first_operand_code` compares the operand against `_STDIN_FILES` by exact string, without normalizing the path.

## Fix

Not fixed yet.
