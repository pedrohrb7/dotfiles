# Features

One folder per feature or technical change, named `<slug>/` (kebab-case, no date - the date lives in each file and in the Index). Everything about a feature stays together:

| File | Side | Written by | Read by |
| --- | --- | --- | --- |
| `plan.md` | product: goal, scope, **business rules**, edge cases, flows | `planner` | `specker`, `/implement` (precondition) |
| `spec.md` | technical: design, contracts, tests, **structured tasks**, verification | `specker` | `/implement`, the stack agents, reviewers |
| `log.md` | implementation log: per task, files, decisions, assumptions, approved scope | `/implement` only | the stack agents (before coding), reviewers, the documentation pass |

- Start every new file from `_template/`. A refactor without product impact gets a folder with only `spec.md` and `log.md`; its spec points to the backlog entry it came from.
- Plan status: `Draft` -> `Approved` -> `Implemented`, or `Superseded` (link what replaced it).
- Spec status: `Draft` -> `Approved` -> `In progress` -> `Implemented`, or `Superseded`.
- Plans and specs are a record of intent: once `Approved`, change them with a dated addendum, not a silent rewrite. The log is append-only.
- Keep the Index below in sync whenever a feature is created or a status changes.

## Index

| Feature | Plan | Spec | Updated |
| --- | --- | --- | --- |
