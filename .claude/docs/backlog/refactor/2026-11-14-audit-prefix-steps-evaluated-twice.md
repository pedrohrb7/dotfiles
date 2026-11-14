# agent-audit: _prefix_steps evaluated twice per site

- **Status:** Proposed
- **Opened:** 2026-11-14
- **Scope:** `.claude/hooks/agent_audit_classify.py` (`_command_starts`, `_code_args`)
- **Source:** agent run: feature audit-shell-lexer; [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Motivation

Wasted work per command; no failure.

## Current state

Task 3/4 note: `_prefix_steps` runs once in `_command_starts` and again in `_code_args`. Latency is small (median about 0.3 ms).

## Proposed change

Compute once per site and share.

## Risks

Not recorded.

## Out of scope

Not recorded.
