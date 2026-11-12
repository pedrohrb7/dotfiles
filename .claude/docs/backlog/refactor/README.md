# Refactor backlog

Planned refactors that aren't urgent bugs but are worth doing deliberately, one file per refactor.

- File name: `YYYY-MM-DD-short-slug.md` (date opened, slug describing the refactor).
- Start every new entry from `TEMPLATE.md`.
- Update `Status` as it moves through `Proposed` -> `In progress` -> `Done` (link the PR) or `Dropped` (say why).
- If a refactor is large enough to need a design decision, write a spec first - a feature folder `../../features/<slug>/` with only `spec.md` (its **Source** points back to this entry) - and link it here instead of duplicating the reasoning. In a project still on the legacy layout, the spec goes in `../../specs/`.
- Keep the index below in sync whenever an entry is created or its status changes.

## Index

| Entry | Status |
| --- | --- |
| [Versioned pytest suite for agent-audit hook](2026-11-11-audit-hook-test-suite.md) | Proposed |
| [md_outside_docs false positive on main-session root .md files](2026-11-11-audit-md-outside-docs-false-positive.md) | Proposed |
| [Align project-docs and implement skills with configurable docs root](2026-11-11-skills-configurable-docs-root.md) | Proposed |
| [agent-audit: nested repo cwd does not consult the parent repo's run](2026-11-11-audit-nested-repo-run-lookup.md) | Proposed |
| [agent-audit: scratch exemption accepts any /tmp/claude-* dir](2026-11-11-audit-scratch-exemption-too-broad.md) | Proposed |
