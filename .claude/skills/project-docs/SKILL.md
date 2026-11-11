---
name: project-docs
description: Single source of truth for a project's docs/ tree - scaffold it (features, backlog/bugs, backlog/refactor, concepts, quality, requests), resolve where a feature's plan, spec and implementation log live in either layout (features/<slug>/ or the legacy plans/ + specs/), add bug/refactor/plan/spec/log/concept/quality-snapshot entries from templates, and migrate a legacy docs/ to features/. Use when the user says "set up project docs", "log a bug", "add a refactor ticket", "write a plan for X", "write a spec for X", "record a quality snapshot" or "migrate the docs", and whenever an agent or skill needs a feature's doc paths.
---

# Project Docs

Maintains the `docs/` tree defined in `~/.claude/templates/docs-structure/`:

```
docs/
├── features/
│   ├── README.md       (Index: feature, plan status, spec status, updated)
│   ├── _template/      (plan.md, spec.md, log.md)
│   └── <slug>/         (plan.md, spec.md, log.md - one folder per feature)
├── backlog/
│   ├── bugs/           (README.md, TEMPLATE.md, dated entries)
│   └── refactor/       (README.md, TEMPLATE.md, dated entries)
├── concepts/           (freeform, one file per concept, no template)
├── quality/            (README.md, TEMPLATE.md, dated snapshots)
└── requests/           (API projects only - README.md, .http files or collections)
```

**Plan, spec and log**: a feature keeps its three documents together in `features/<slug>/`.
- `plan.md` is the product side - *what* is being built and the **business rules** it must follow (goal, context, scope, business rules, edge cases, product-level approach).
- `spec.md` is the technical side - *how* it is built (design, data model, API contracts, components, alternatives, trade-offs, tests, verification) and the **Implementation order** as structured task blocks (Stack, Files, Depends on, Done when, Status) that `/implement` reads without interpreting prose.
- `log.md` is the implementation log, written only by `/implement`, append-only: per task, the files, decisions, assumptions and approved scope. Agents read it before coding.
- A pure technical change (e.g. a large refactor) has only `spec.md` and `log.md`; its spec points to the backlog entry it came from (**Source**).

**Indexes**: `features/README.md` keeps one row per feature with the plan and spec status. `backlog/bugs` and `backlog/refactor` keep an **Index** of their entries with their **Status**. All are updated whenever an entry is created or changes status. `quality/` keeps a **History** table instead (one row per snapshot with its headline numbers), because snapshots have no status - they are never edited after being written.

**Quality snapshots**: a snapshot records the project's quality numbers (tests, coverage, mutation score, front-end audits such as Lighthouse) at a delivery - a plan marked as implemented, a release, or each deploy once a pipeline exists. It is written only after the project's quality gate passed, with numbers copied from the generated reports and the commit of each service measured. When the project generates a machine-readable summary, the snapshot is a pair with the same name - a generated `.json` (never hand-edited, the source for any quality dashboard) and the `.md` written from it.

**Evolving the structure**: when a project needs a new folder, section or convention in `docs/`, change this skill and `~/.claude/templates/docs-structure/` first (with the user's approval - it affects every project), then apply it to the project. Don't let a single project drift from the templates on its own.

`PRD.md`, `CONSTRAINTS.md` and `OPEN_QUESTIONS.md` are NOT part of this tree - they live at the repo root and are owned by the `new-project` skill (`~/.claude/templates/project-root/`). Never create them under `docs/`. `OPEN_QUESTIONS.md` holds only project-level questions; a feature's questions go in its plan or spec.

## Layouts and path resolution

This section is the only place that knows where a feature's documents live. `/implement`, `@planner` and every other agent or skill that needs a plan, spec or log path resolves it here.

**Two layouts:**
- `features` - the default, and the only one new projects get.
- `legacy` - `docs/plans/` + `docs/specs/`, kept working for existing projects that have not migrated.

**Detection, in this order:**
1. The root `CLAUDE.md` declares it in its `## Workflow` section: `- docs layout: features` or `- docs layout: legacy`.
2. `docs/features/` exists: `features`.
3. `docs/plans/` or `docs/specs/` exists: `legacy`.
4. None of these: `features`.

**One-time migration offer.** When `/implement` or `@planner` starts work in a `legacy` project with **no** declaration, it asks once: "migrate `docs/` to `docs/features/` now?". Yes: run migrate mode (below), which records `docs layout: features`. No: record `- docs layout: legacy` in the root `CLAUDE.md` `## Workflow` section (create the section if missing) and never ask again. The user can still ask for a migration later.

**Path map:**

| Document | `features` | `legacy` |
|---|---|---|
| plan | `docs/features/<slug>/plan.md` | `docs/plans/YYYY-MM-DD-<slug>-plan.md` |
| spec | `docs/features/<slug>/spec.md` | `docs/specs/YYYY-MM-DD-<slug>-design.md` |
| implementation log | `docs/features/<slug>/log.md` | `docs/specs/YYYY-MM-DD-<slug>-design.log.md` (next to the spec) |
| Index | `docs/features/README.md` | `docs/plans/README.md` and `docs/specs/README.md` |
| templates | the project's `docs/features/_template/` (fallback: `~/.claude/templates/docs-structure/features/_template/`) | the project's `docs/plans/TEMPLATE.md` and `docs/specs/TEMPLATE.md` |
| what an agent receives | `feature: docs/features/<slug>/` | `spec: docs/specs/<file>.md` |

**Rules for both layouts:**
- The implementation log is always a separate file, never a section inside the spec. A legacy spec that already has a `## Implementation log` section keeps it; new runs append to the separate file.
- New specs always use the structured task blocks of `features/_template/spec.md` in **Implementation order**, even in a legacy project. Older specs with a free-form list keep working: `/implement` reads them as before and never rewrites them.

## Modes

Four modes: **scaffold** (build the tree once), **add entry** (incremental, ongoing), **resolve** (answer where a feature's documents live) and **migrate** (legacy to features, on request).

## Scaffold mode

Use when `docs/` is missing this structure - typically right after a new project/repo is created.

1. Confirm the docs root: `docs/` at the repo root, unless the user is working in a monorepo with per-service docs, in which case ask which root to scaffold under.
2. Check the root `CLAUDE.md` for a "Documentation language" setting. If there isn't one, ask - English or Portuguese - before writing prose. Section headers copied from the templates stay as-is; only the prose you fill in follows the answer.
3. Copy `~/.claude/templates/docs-structure/` into the docs root as-is - every README.md, TEMPLATE.md and `features/_template/` file is a filled-in skeleton, not a stub to rewrite. Skip any file that already exists; report it instead of overwriting. Never create `plans/` or `specs/`.
4. `requests/` only applies to API projects (a service that exposes HTTP/REST/GraphQL/gRPC endpoints for other clients to call). If it's not already obvious from the project description, ask. Copy `requests/` only when the answer is yes; skip it entirely otherwise.
5. Leave `features/`, `backlog/`, `quality/` and `concepts/` with just their README/template skeletons - don't create entries speculatively. Those get added one at a time via add-entry mode.
6. Make sure the root `CLAUDE.md` `## Workflow` section says `- docs layout: features`.

## Resolve mode

Given a feature (slug, title or path), return the paths of its plan, spec and log and the layout in use, following **Layouts and path resolution**. If several features match, list them with their status and ask which one; never guess between them.

## Add entry mode

Use whenever the user, an agent or a skill needs a new bug, refactor, plan, spec, log, concept, quality snapshot or request.

1. Confirm which kind of entry and get a short slug (a few words, kebab-case) describing it from the user if not already obvious from the request.
2. Resolve the layout. Check the matching template exists; if the docs tree hasn't been scaffolded yet, offer to run scaffold mode first.
3. Build the path and confirm it with the user before creating (folder names, dates and file names are effectively permanent):
   - Bug: `docs/backlog/bugs/YYYY-MM-DD-<slug>.md` (today's date)
   - Refactor: `docs/backlog/refactor/YYYY-MM-DD-<slug>.md` (today's date)
   - Plan, spec, log: the path map above. In `features`, a new feature also gets its folder; reuse an existing folder when the feature already has one.
   - Quality snapshot: `docs/quality/YYYY-MM-DD-<slug>.md` (date measured; slug names the delivery it closes). Run the project's quality gate first and fill every number from the reports it generated - never from memory or an older snapshot. If the project has a snapshot command (check `docs/quality/README.md`), run it first to generate the `.json` with the same name, and fill the `.md` from that `.json`
   - Concept: `docs/concepts/<slug>.md` (no date - concepts are evergreen and edited in place)
   - Request: add to or create a file under `docs/requests/` (prefer `.http`), and update its `README.md` if it's a new file. If `docs/requests/` doesn't exist yet, that's expected for a non-API project - confirm the project now exposes an API before creating it (copy it from `~/.claude/templates/docs-structure/requests/`).
4. Copy the matching template (concepts and requests have none) and fill in every section from what's actually known. A section with nothing known says so explicitly ("not recorded", "none open") instead of being invented or left as the placeholder.
   - Bug: reproduce it first (per the repro-before-reporting rule in `backlog/bugs/README.md`) - backend through a request to the local instance plus its log lines, UI through the steps the user confirms. Fill **Source** and **Evidence**; don't write speculative steps.
   - Plan: business rules go in **Business rules**, not in Approach.
   - Spec: tests in **Testing**, structured task blocks in **Implementation order**, checks in **Verification**. Link plan and spec to each other (in `features`, the template links `plan.md` and `spec.md` already; in `legacy`, fill **Related plan/spec** in both).
   - Log: only `/implement` creates and appends to it.
5. Update the Index: a new feature row (or a status change) in `features/README.md`, or the folder README's Index for backlog entries (legacy: the plans or specs README). For a quality snapshot, add its row to the **History** table instead.
6. Write prose in whatever language the rest of `docs/` already uses (check an existing entry, or the "Documentation language" note in `CLAUDE.md`); ask if neither is present.

## Migrate mode

Moves a `legacy` docs tree to `features`. Runs only when the user asks or accepts the one-time offer. Never commits or stages anything.

1. Check `git status` for `docs/`. If it has uncommitted changes, ask before continuing.
2. **Pair the documents.** Match each plan with its spec through the **Related plan/spec** fields, then by slug. A plan without a spec, or a spec without a plan, becomes a feature folder on its own.
3. **Propose the slugs.** For each pair, the slug is the file name without the date prefix and the `-plan`/`-design` suffix. Show the full table (old paths -> new folder) and wait for the user to confirm or rename.
4. **Move**, with `mv` (git detects the renames on commit): plan -> `features/<slug>/plan.md`, spec -> `features/<slug>/spec.md`, an existing `<spec>.log.md` -> `features/<slug>/log.md`. Without a log file, create `log.md` from the template with one "Migrated" run that lists the tasks already marked `(done)` and the spec's `## Implementation log` section, if it had one.
5. **Fix links.** Replace **Related plan/spec** with `Plan: [plan.md](plan.md)` / `Spec: [spec.md](spec.md)`, and update every reference to the old paths in `docs/`, `PRD.md`, backlog entries and READMEs (grep for `docs/plans/` and `docs/specs/`).
6. **Indexes and templates.** Build `features/README.md` from the plans and specs Indexes (one row per feature, both statuses). Copy `features/_template/` from `~/.claude/templates/docs-structure/`. Remove the old `plans/` and `specs/` README and TEMPLATE files only after every entry has moved, then the empty folders.
7. Record `- docs layout: features` in the root `CLAUDE.md` `## Workflow` section.
8. Report: the table of moves, the links fixed, and anything that could not be paired or moved.
