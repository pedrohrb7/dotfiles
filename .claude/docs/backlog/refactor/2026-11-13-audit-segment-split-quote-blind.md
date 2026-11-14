# agent-audit: quote-blind SEGMENT_SPLIT splits inside quoted arguments

- **Status:** Done (via [audit-shell-lexer](2026-11-13-audit-shell-lexer.md), uncommitted)
- **Spec:** [audit-shell-lexer](../../features/audit-shell-lexer/spec.md)
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py` (`SEGMENT_SPLIT`); affects every stack
- **Source:** agent run: feature lua-agent, code-reviewer and security-reviewer (2026-11-13)

## Motivation

A command is split at `;` or `|` inside quoted arguments, so the parts are classified as separate commands (for example nvim `-c 'lua x; !cmd'`).

## Current state

`SEGMENT_SPLIT` does not track quotes.

## Proposed change

Make the split quote-aware; add tests to the hook suite.

## Risks

Not recorded.

## Out of scope

Not recorded.

## Result (2026-11-14)
Covered entirely: the lexer tracks quotes and compounds, so segments no longer come from `SEGMENT_SPLIT`. See the [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md) and [log](../../features/audit-shell-lexer/log.md). Related residual: [canary spans in backtick text](../bugs/2026-11-14-audit-canary-span-backtick-escapes.md).
