# agent-audit: quote-blind SEGMENT_SPLIT splits inside quoted arguments

- **Status:** Merged into [audit-shell-lexer](2026-11-13-audit-shell-lexer.md)
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
