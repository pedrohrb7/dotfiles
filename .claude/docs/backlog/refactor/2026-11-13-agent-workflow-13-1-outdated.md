# agent-workflow.md 13.1 says the hook is a no-op without an active run

- **Status:** Proposed
- **Opened:** 2026-11-13
- **Scope:** `.claude/agent-workflow.md` (section 13.1) - docs
- **Source:** specker, feature audit-md-outside-docs, 2026-11-13

## Motivation

The documentation misdescribes the hook, which misleads anyone reasoning about what is audited outside a run.

## Current state

13.1 says the hook does nothing without an active run. That is outdated: `md_outside_docs`, `backlog_write_by_other`, the `DESIGN_SYSTEM.md` flags and the Bash categories apply without a run.

## Proposed change

Rewrite 13.1 to list what applies with and without a run. Docs-only; can go through `docs-writer`.

## Risks

None known.

## Out of scope

Other updates to 13.3, 13.5 and 13.7 (already listed as needs_docs in the audit-md-outside-docs spec).
