# md_outside_docs false positive on main-session root .md files

- **Status:** Done
- **Implementation:** implemented by the spec [audit-md-outside-docs](../../features/audit-md-outside-docs/spec.md); change is uncommitted, no PR yet.
- **Opened:** 2026-11-11
- **Scope:** .claude/hooks/agent-audit.py
- **Source:** feature design-director (stage H), /implement run 2026-11-11, specker, code-reviewer
- **Spec:** [audit-md-outside-docs](../../features/audit-md-outside-docs/spec.md)

## Motivation

False positives when the main session creates root `.md` files (new-project copying DESIGN_SYSTEM.md/PRD.md, token extraction).

## Current state

Every actor, including `main`, gets `md_outside_docs` on any Write of a `.md` outside the docs root, overwrites included. Deferred earlier as spec S5.

## Proposed change

Handled by the spec above (rules M1-M8, plus the 2026-11-13 addendum):

- M1: `main` never gets `md_outside_docs` (its other flags stay).
- M2: other actors get it only for a `.md` inside a git root, outside the docs root, that the write creates (case-insensitive extension).
- M3: "creates" means `tool_response.type == "create"`, or a `Write` to a missing target when there is no response; errors count as creation.
- M4: exempt doc names by exact basename, any case: `README.md`, `CHANGELOG.md`, `DEPLOY.md`, `CLAUDE.md`.
- M5: `design-director` stays exempt on `DESIGN_SYSTEM.md`.
- M6: fixed-scope actors with an active run are exempt for `.md` patterns declared in the running tasks' `allowed_paths` or approved `approved_scope`.
- M7: `docs_write_by_implementer` matches `DOC_FILES` by exact basename, any case.
- M8: outside any git root, and for all other flags and categories, nothing changes.
- User decision (addendum): `docs-writer` is exempt for any `.md` (rule M9).

## Risks

Promotion of `md_outside_docs` to block is not part of this change; it needs real-use metrics and the docs-root declaration issue resolved first. A `main` session creating stray `.md` files is no longer flagged (still logged with actor, rel, area and tool).

## Out of scope

- Promotion of the flag to block.
- The unprotected docs-root declaration ([entry](2026-11-13-audit-docs-root-declaration-unprotected.md)); it is the next spec.
- The actor set of `docs_write_by_implementer` ([entry](2026-11-12-audit-docs-write-flag-implementers-only.md)); own spec.
