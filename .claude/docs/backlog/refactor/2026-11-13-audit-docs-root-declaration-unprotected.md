# agent-audit: edits to the root CLAUDE.md docs root declaration are not flagged

- **Status:** Proposed
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py` (`_assess_root`, around lines 595-605)
- **Source:** agent run: skills-docs-root, security-reviewer (low)

## Motivation

The docs root now comes from `- docs root:` in the root `CLAUDE.md`. Editing that file raises no flag: it is exempt from `md_outside_docs` by name and is not in `DOC_FILES`. An actor allowed to edit it (planner, specker, docs-writer, main, or a scoped agent outside a run) can move the root away from the real tree. Edits to existing files there then stop raising `backlog_write_by_other`, `docs_write_by_implementer` and `md_outside_docs`.

## Current state

All these flags are warn, so audit coverage weakens but no capability is granted. Absolute and `..` values are already rejected.

## Proposed change

Either read the declaration from both HEAD and the working tree and protect their union (the working tree can then only add flags), or add a flag for Write/Edit of the root `CLAUDE.md` by actors other than main, onboard, planner and specker. Needs a choice before a spec.

## Seen again (2026-11-13)

- Metrics on 2026-11-12 show `backend-python` editing a project's root `CLAUDE.md` with no flag. Source: specker, feature audit-md-outside-docs, 2026-11-13.
- Severity re-rated MEDIUM by an automated review of commit cc05e36 (previously low).

## Decision (2026-11-13)

The user decided this will be the next spec: read the declaration from HEAD, plus backlog protection in every candidate tree (HEAD, working tree and `docs/`). See open question 2 of [audit-md-outside-docs](../../features/audit-md-outside-docs/spec.md).

## Risks

The HEAD read adds a git call per assessment; the actor-based flag may be noisy for legitimate docs-root offers.

## Out of scope

Hook self-protection in general (see the bugs entry on rewriting the hook).
