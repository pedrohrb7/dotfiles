---
name: project-docs
description: Scaffold the docs/ tree (concepts, plans, specs, backlog/bugs, backlog/refactor, requests) for a new project, and incrementally add new bug/refactor/plan/spec/concept entries from templates as the project evolves. Use when the user says "set up project docs", "log a bug", "add a refactor ticket", "write a plan for X", or "write a spec for X".
disable-model-invocation: true
---

# Project Docs

Maintains the `docs/` tree defined in `~/.claude/templates/docs-structure/`:

```
docs/
├── backlog/
│   ├── bugs/       (README.md, TEMPLATE.md, dated entries)
│   └── refactor/   (README.md, TEMPLATE.md, dated entries)
├── concepts/       (freeform, one file per concept, no template)
├── plans/          (README.md, TEMPLATE.md, dated entries)
├── specs/          (README.md, TEMPLATE.md, dated entries)
└── requests/       (API projects only - README.md, API request collections)
```

`PRD.md` and `CONSTRAINTS.md` are NOT part of this tree - they live at the repo root and are owned by the `new-project` skill (`~/.claude/templates/project-root/`). Never create `docs/PRD.md` or `docs/CONSTRAINTS.md`; if you need product requirements or constraints context, read them from the root instead.

Two modes: **scaffold** (build the tree once) and **add entry** (incremental, ongoing).

## Scaffold mode

Use when `docs/` is missing this structure - typically right after a new project/repo is created.

1. Confirm the docs root: `docs/` at the repo root, unless the user is working in a monorepo with per-service docs, in which case ask which root to scaffold under.
2. Check the root `CLAUDE.md` for a "Documentation language" setting. If there isn't one, ask - English or Portuguese - before writing prose. Section headers copied from the templates stay as-is; only the prose you fill in follows the answer.
3. Copy `~/.claude/templates/docs-structure/` into the docs root as-is - every README.md and TEMPLATE.md is a filled-in skeleton, not a stub to rewrite. Skip any file that already exists; report it instead of overwriting.
4. `requests/` only applies to API projects (a service that exposes HTTP/REST/GraphQL/gRPC endpoints for other clients to call). If it's not already obvious from the project description, ask. Copy `requests/` only when the answer is yes; skip it entirely otherwise - don't create an empty collections folder for a project with no API to call.
5. Leave `backlog/`, `plans/`, `specs/`, and `concepts/` with just their README/TEMPLATE skeletons - don't create dated entries speculatively. Those get added one at a time via add-entry mode as real bugs, refactors, plans, and specs come up.

## Add entry mode

Use whenever the user wants to file a bug, open a refactor ticket, write a plan, write a spec, or add a concept doc - at any point in the project's life, not just at creation.

1. Confirm which kind of entry and get a short slug (a few words) describing it from the user if not already obvious from the request.
2. Check the target subfolder's `TEMPLATE.md` exists; if the docs tree hasn't been scaffolded yet, offer to run scaffold mode first.
3. Build the file name and confirm it with the user before creating (dates and file names here are effectively permanent):
   - Bug: `docs/backlog/bugs/YYYY-MM-DD-<slug>.md` (today's date)
   - Refactor: `docs/backlog/refactor/YYYY-MM-DD-<slug>.md` (today's date)
   - Plan: `docs/plans/YYYY-MM-DD-<slug>-plan.md` (today's date)
   - Spec: `docs/specs/YYYY-MM-DD-<slug>-design.md` (today's date)
   - Concept: `docs/concepts/<slug>.md` (no date - concepts are evergreen and edited in place)
   - Request: add to or create a collection file under `docs/requests/`, and update its `README.md` if it's a new collection. If `docs/requests/` doesn't exist yet, that's expected for a non-API project - confirm the project now exposes an API before creating it (copy it from `~/.claude/templates/docs-structure/requests/`).
4. Copy the matching `TEMPLATE.md` (skip for concepts and requests - they have none) to the new path and fill in every section from what's actually known. For a bug, this means reproducing it first (per the repro-before-reporting rule in `backlog/bugs/README.md`) - don't write speculative steps.
5. Write prose in whatever language the rest of `docs/` already uses (check an existing entry, or the "Documentation language" note in `CLAUDE.md`); ask if neither is present.
