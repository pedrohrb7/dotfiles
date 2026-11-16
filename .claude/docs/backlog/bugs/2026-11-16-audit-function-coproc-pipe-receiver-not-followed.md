# agent-audit: a function or coproc used as a pipe receiver is not followed

- **Status:** Open
- **Reported:** 2026-11-16
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix of audit-pipe-into-group-not-flagged, reviewers
- **Related:** [pipe-into-group entry](2026-11-14-audit-pipe-into-group-not-flagged.md)

## Evidence

- `f() { bash; }; echo 'git push' | f` gives only `deny_token_unmatched`.
- `coproc { bash; }` fed via `>&${COPROC[1]}` is the same.

## Steps to reproduce

1. Classify `f() { bash; }; echo 'git push' | f`.
2. Classify a `coproc { bash; }` fed through `>&${COPROC[1]}`.

## Expected behavior

The function or coproc body is a shell reading the pipe, classified like `| bash`.

## Actual behavior

Only `deny_token_unmatched`; piped text is not classified.

## Root cause

Function and coproc bodies deliberately do not inherit the pipe (fix of the pipe-into-group entry), and the call to the function is not resolved as a pipe receiver.

## Fix

Not fixed yet.
