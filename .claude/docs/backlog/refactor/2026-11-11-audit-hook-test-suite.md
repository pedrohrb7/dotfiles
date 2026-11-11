# Versioned pytest suite for agent-audit hook

- **Status:** Proposed
- **Opened:** 2026-11-11
- **Scope:** .claude/hooks/
- **Source:** feature design-director (stage H), /implement run 2026-11-11, specker

## Motivation

Hook behavior is unprotected by versioned tests.

## Current state

The H1-H28, G1-G11, C (37), D1-D10 and M1-M5 cases live in an ad-hoc stdin harness in a session scratchpad.

## Proposed change

Add a pytest suite under `.claude/hooks/` and a Test suites table for the repo.

## Risks

Not recorded.

## Out of scope

Not recorded.
