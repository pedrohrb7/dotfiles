# md_outside_docs false positive on main-session root .md files

- **Status:** Proposed
- **Opened:** 2026-11-11
- **Scope:** .claude/hooks/agent-audit.py
- **Source:** feature design-director (stage H), /implement run 2026-11-11, specker, code-reviewer

## Motivation

False positives when the main session creates root `.md` files (new-project copying DESIGN_SYSTEM.md/PRD.md, token extraction).

## Current state

Deferred as spec S5.

## Proposed change

Needs a spec; handle in the warn->block promotion analysis.

## Risks

Not recorded.

## Out of scope

Not recorded.
