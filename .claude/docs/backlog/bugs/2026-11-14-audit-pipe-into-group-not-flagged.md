# agent-audit: a group or subshell reading a pipe is not flagged

- **Status:** Open
- **Reported:** 2026-11-14
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: feature audit-shell-lexer, security-reviewer
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Evidence

- `echo 'git push' | { bash; }` gives only the canary (level A), no `git push` ask.

## Steps to reproduce

1. Classify `echo 'git push' | { bash; }` through `analyze_command` or the hook with synthetic JSON (no real execution).
2. Repeat with a subshell receiver.

## Expected behavior

A shell reading code from a pipe inside a group or subshell is treated like `... | bash`: the piped text is classified (`git push`).

## Actual behavior

Only the canary is recorded; the command is allowed.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
