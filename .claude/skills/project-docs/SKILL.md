---
name: project-docs
description: Scaffold the docs/ tree (concepts, plans, specs, quality, backlog/bugs, backlog/refactor, requests) for a new project, and incrementally add new bug/refactor/plan/spec/concept/quality-snapshot entries from templates as the project evolves. Plans hold the product side (scope, business rules); specs hold the technical implementation; quality holds dated snapshots of test, coverage, mutation and audit numbers. Use when the user says "set up project docs", "log a bug", "add a refactor ticket", "write a plan for X", "write a spec for X", or "record a quality snapshot".
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
├── quality/        (README.md, TEMPLATE.md, dated snapshots)
└── requests/       (API projects only - README.md, API request collections)
```

**Plans vs specs**: a plan is the product side - *what* is being built and the **business rules** it must follow (goal, context, scope, business rules, edge cases, product-level approach). A spec is the technical side - *how* it is built (design, data model, API contracts, components, alternatives, trade-offs, tests, implementation order, verification). A feature usually has one plan and one spec linked to each other through the **Related plan/spec** fields; a pure technical change (e.g. a large refactor) may have only a spec.

Every folder README with dated entries (`backlog/bugs`, `backlog/refactor`, `plans`, `specs`) keeps an **Index** table of its entries with their **Status**, updated whenever an entry is created or changes status. `quality/` keeps a **History** table instead (one row per snapshot with its headline numbers), because snapshots have no status - they are never edited after being written.

**Quality snapshots**: a snapshot records the project's quality numbers (tests, coverage, mutation score, front-end audits such as Lighthouse) at a delivery - a plan marked as implemented, a release, or each deploy once a pipeline exists. It is written only after the project's quality gate passed, with numbers copied from the generated reports and the commit of each service measured. When the project generates a machine-readable summary, the snapshot is a pair with the same name - a generated `.json` (never hand-edited, the source for any quality dashboard) and the `.md` written from it.

**Evolving the structure**: when a project needs a new folder, section or convention in `docs/`, change this skill and `~/.claude/templates/docs-structure/` first (with the user's approval - it affects every project), then apply it to the project. Don't let a single project drift from the templates on its own.

`PRD.md` and `CONSTRAINTS.md` are NOT part of this tree - they live at the repo root and are owned by the `new-project` skill (`~/.claude/templates/project-root/`). Never create `docs/PRD.md` or `docs/CONSTRAINTS.md`; if you need product requirements or constraints context, read them from the root instead.

Two modes: **scaffold** (build the tree once) and **add entry** (incremental, ongoing).

## Scaffold mode

Use when `docs/` is missing this structure - typically right after a new project/repo is created.

1. Confirm the docs root: `docs/` at the repo root, unless the user is working in a monorepo with per-service docs, in which case ask which root to scaffold under.
2. Check the root `CLAUDE.md` for a "Documentation language" setting. If there isn't one, ask - English or Portuguese - before writing prose. Section headers copied from the templates stay as-is; only the prose you fill in follows the answer.
3. Copy `~/.claude/templates/docs-structure/` into the docs root as-is - every README.md and TEMPLATE.md is a filled-in skeleton, not a stub to rewrite. Skip any file that already exists; report it instead of overwriting.
4. `requests/` only applies to API projects (a service that exposes HTTP/REST/GraphQL/gRPC endpoints for other clients to call). If it's not already obvious from the project description, ask. Copy `requests/` only when the answer is yes; skip it entirely otherwise - don't create an empty collections folder for a project with no API to call.
5. Leave `backlog/`, `plans/`, `specs/`, `quality/` and `concepts/` with just their README/TEMPLATE skeletons - don't create dated entries speculatively. Those get added one at a time via add-entry mode as real bugs, refactors, plans, and specs come up.

## Add entry mode

Use whenever the user wants to file a bug, open a refactor ticket, write a plan, write a spec, or add a concept doc - at any point in the project's life, not just at creation.

1. Confirm which kind of entry and get a short slug (a few words) describing it from the user if not already obvious from the request.
2. Check the target subfolder's `TEMPLATE.md` exists; if the docs tree hasn't been scaffolded yet, offer to run scaffold mode first.
3. Build the file name and confirm it with the user before creating (dates and file names here are effectively permanent):
   - Bug: `docs/backlog/bugs/YYYY-MM-DD-<slug>.md` (today's date)
   - Refactor: `docs/backlog/refactor/YYYY-MM-DD-<slug>.md` (today's date)
   - Plan: `docs/plans/YYYY-MM-DD-<slug>-plan.md` (today's date)
   - Spec: `docs/specs/YYYY-MM-DD-<slug>-design.md` (today's date)
   - Quality snapshot: `docs/quality/YYYY-MM-DD-<slug>.md` (date measured; slug names the delivery it closes). Run the project's quality gate first and fill every number from the reports it generated - never from memory or an older snapshot. If the project has a snapshot command (check `docs/quality/README.md`), run it first to generate the `.json` with the same name, and fill the `.md` from that `.json`
   - Concept: `docs/concepts/<slug>.md` (no date - concepts are evergreen and edited in place)
   - Request: add to or create a collection file under `docs/requests/`, and update its `README.md` if it's a new collection. If `docs/requests/` doesn't exist yet, that's expected for a non-API project - confirm the project now exposes an API before creating it (copy it from `~/.claude/templates/docs-structure/requests/`).
4. Copy the matching `TEMPLATE.md` (skip for concepts and requests - they have none) to the new path and fill in every section from what's actually known. For a bug, this means reproducing it first (per the repro-before-reporting rule in `backlog/bugs/README.md`) - don't write speculative steps. A section with nothing known says so explicitly ("not recorded", "none open") instead of being invented or left as the placeholder. For a plan, put business rules in **Business rules**, not in Approach; for a spec, put tests, order and checks in **Testing**, **Implementation order** and **Verification**. When a plan and a spec belong together, fill **Related plan/spec** in both.
5. Add a row for the new entry to the folder README's **Index** (and update the row whenever the entry's status changes). For a quality snapshot, add its row to the **History** table instead.
6. Write prose in whatever language the rest of `docs/` already uses (check an existing entry, or the "Documentation language" note in `CLAUDE.md`); ask if neither is present.
