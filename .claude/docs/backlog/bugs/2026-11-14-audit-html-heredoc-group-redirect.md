# agent-audit: heredoc with HTML body and a group-level redirect, or HEAD() { cat <<EOF }, reads as code (lex_error)

- **Status:** Open
- **Reported:** 2026-11-14
- **Severity:** low
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: feature audit-shell-lexer, Task 2 and A1
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Evidence

- Task 2: `HEAD() { cat <<EOF }` and a group with `cat <<EOF` and `> page.html` after the group have no redirect on the `cat`, so the HTML body stays code and hits `lex_error` (1 command in replay E3).
- Later replays judged E3 results intended (HD3 decision); not re-verified, so this may be closed as intended.

## Steps to reproduce

1. Classify a group `{ cat <<EOF` + an HTML body + `EOF` + `; } > page.html`.

## Expected behavior

The body is data.

## Actual behavior

The body is read as code and fails with `lex_error`.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
