# agent-audit: nvim -l ... --busted (lazy.nvim minit) not recognized as a Lua test runner

- **Status:** Proposed
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py`
- **Source:** agent run: feature lua-agent, code-reviewer and security-reviewer (2026-11-13)

## Motivation

A suite run through the lazy.nvim minit escapes runner classification.

## Current state

`nvim -l ... --busted` is not recognized.

## Proposed change

Recognize it as a Lua test runner.

## Risks

Not recorded.

## Out of scope

Not recorded.
