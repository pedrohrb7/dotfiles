# agent-audit: canary spans inside a backtick with escapes are relative to the unescaped text

- **Status:** Open
- **Reported:** 2026-11-14
- **Severity:** low
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: feature audit-shell-lexer, Task 1
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Evidence

- Task 1 note: spans are exact except inside a backtick whose escapes are removed; the canary then slices the wrong place of the raw text.

## Steps to reproduce

1. Classify a command with a backtick substitution containing backslash escapes and a dynamic word.

## Expected behavior

The canary slices the raw text where the word is.

## Actual behavior

The slice is shifted by the removed escapes.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
