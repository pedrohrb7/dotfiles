# agent-audit: dc, GNU sed e and awk system() execute commands without classification

- **Status:** Open
- **Reported:** 2026-11-14
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: feature audit-shell-lexer, security-reviewer
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Evidence

- `dc` runs `!cmd` read from stdin.
- GNU sed `e` and `s///e`, and awk `system()`, in arguments or in stdin scripts, are not classified.
- `sed -nf/dev/stdin <<< ...` misses the data-reader check because of the `-nf` cluster.

## Steps to reproduce

1. Classify `dc` with a here-string `!<cmd>` holding a blocked command.
2. Classify sed `e`, `s///e`, awk `system()` and `sed -nf/dev/stdin <<< ...` (synthetic JSON only).

## Expected behavior

These interpreters' code is classified, or the call is level B.

## Actual behavior

Allowed; the here-string is treated as data for the `-nf` form.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
