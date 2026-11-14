# agent-audit: the git push check matches push as an argument; use the git subcommand

- **Status:** Proposed
- **Opened:** 2026-11-14
- **Scope:** `.claude/hooks/agent_audit_classify.py` (git push regex)
- **Source:** agent run: feature audit-shell-lexer; [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Motivation

`git log --grep push` asks as a push; false ask.

## Current state

The git commit check uses the subcommand after global options (`_git_has_subcommand`, A2); the git push check still uses a regex.

## Proposed change

Reuse the subcommand helper for push, with tests.

## Risks

Not recorded.

## Out of scope

Not recorded.
