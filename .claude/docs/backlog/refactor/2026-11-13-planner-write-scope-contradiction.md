# planner agent contradicts itself on where it may write

- **Status:** Proposed
- **Opened:** 2026-11-13
- **Scope:** `.claude/agents/planner.md`
- **Source:** specker, feature audit-md-outside-docs, 2026-11-13

## Motivation

The agent definition gives two incompatible instructions, so the hook's `md_outside_docs` flag fires on a legitimate-by-instruction write.

## Current state

Line 14 says `planner` writes only inside `<docs>/` (plus the `CLAUDE.md` docs lines). Line 23 tells it to also write project-level questions to `OPEN_QUESTIONS.md` at the repo root.

## Proposed change

Needs a decision: either allow `OPEN_QUESTIONS.md` explicitly in line 14 (and make the hook exempt it) or route those questions through the main session. Needs a spec.

## Risks

Not recorded.

## Out of scope

The `md_outside_docs` rules themselves (see [audit-md-outside-docs](../../features/audit-md-outside-docs/spec.md)).
