# Align project-docs and implement skills with configurable docs root

- **Status:** Proposed
- **Opened:** 2026-11-11
- **Scope:** .claude/skills/project-docs, .claude/skills/implement
- **Source:** feature design-director (stage H), /implement run 2026-11-11, main session

## Motivation

The hook supports `docs_roots`, but the skills resolve the docs tree only at `docs/` in the repo root; in this repo the feature path must be passed explicitly.

## Current state

Skills hardcode `docs/`.

## Proposed change

Align the skills with a configurable docs root.

## Risks

Not recorded.

## Out of scope

Not recorded.
