# agent-audit: nvim vim.cmd / nvim_command executing ex commands with a bang are not modeled

- **Status:** Proposed
- **Opened:** 2026-11-14
- **Scope:** `.claude/hooks/agent_audit_classify.py` (X6 list)
- **Source:** agent run: feature audit-shell-lexer; [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Motivation

`vim.cmd("!cmd")`, `vim.api.nvim_command("!cmd")` and `:execute` with a variable run shell commands but are not in the X6 list.

## Current state

Noted in Task 4 as out of scope. The other nvim forms are classified.

## Proposed change

Add them to the X6 list; `:execute` with a variable is level B.

## Risks

Not recorded.

## Out of scope

Not recorded.
