# Versioned unittest suite for agent-audit hook

- **Status:** Done (implemented by the spec, uncommitted, no PR yet)
- **Opened:** 2026-11-11
- **Scope:** .claude/hooks/
- **Source:** feature design-director (stage H), /implement run 2026-11-11, specker
- **Related:** spec [audit-hook-test-suite](../../features/audit-hook-test-suite/spec.md) (implemented)

## Motivation

Hook behavior is unprotected by versioned tests.

## Current state

`.claude/hooks/tests/test_agent_audit.py` already has 82 passing stdlib unittest tests covering heredoc handling, parallel-task scope and writes outside the git root. The ad-hoc scratchpad harness (H/M/G/C/D cases) is lost; the spec rebuilds those cases from the design-director spec and log.

## Proposed change

Stay on stdlib unittest, not pytest: pytest is not installed and the project does not add frameworks it does not have. Add a Test suites table in a new root `CLAUDE.md`, written by docs-writer at the end.

## Risks

Not recorded.

## Out of scope

Not recorded.
