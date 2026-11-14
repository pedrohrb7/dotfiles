# agent-audit: exotic forms not modeled (trap DEBUG, zparseopts -A, same-text aliases)

- **Status:** Proposed
- **Opened:** 2026-11-14
- **Scope:** `.claude/hooks/agent_audit_classify.py`
- **Source:** agent run: feature audit-shell-lexer; [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Motivation

Forms that run or rename commands outside the model.

## Current state

- `trap '...' DEBUG` runs code on every command.
- zsh `zparseopts -A` can change a known name.
- Same-text aliases (`alias g=git`, then `g push`): unverified whether Claude Code's zsh eval expands them.

## Proposed change

Verify the alias behavior first; the rest is low value unless metrics show them.

## Risks

Not recorded.

## Out of scope

Not recorded.
