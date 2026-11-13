# Align project-docs and implement skills with configurable docs root

- **Status:** Done (implemented by the spec, 2026-11-13; uncommitted, no PR yet)
- **Opened:** 2026-11-11
- **Scope:** the hook (`agent-audit.py`, `agent-audit.json`, `agent-metrics.py`), the root `CLAUDE.md`, the skills (`project-docs`, `implement`, `fix-bug`, `onboard`, `implementer-contract`, `docs`), the global `.claude/CLAUDE.md`, 12 agents and 2 templates
- **Source:** feature design-director (stage H), /implement run 2026-11-11, main session
- **Spec:** [spec.md](../../features/skills-docs-root/spec.md)

## Motivation

The hook supports `docs_roots`, but the skills resolve the docs tree only at `docs/` in the repo root; in this repo the feature path must be passed explicitly.

## Current state

Skills hardcode `docs/`.

## Proposed change

Summary of rules R1-R4 from the spec:

- Each project declares its docs root once, as `- docs root: <path>/` in the git-root `CLAUDE.md` `## Workflow`. It defaults to `docs/`.
- The hook reads the declaration per git root.
- `docs_roots` leaves the global `agent-audit.json`.
- The skills use the `<docs>/` placeholder, resolved by `project-docs`.

## Risks

Projects with docs under `.claude/docs/` and no declaration start getting `md_outside_docs` warnings.

## Out of scope

Several docs roots per project.
