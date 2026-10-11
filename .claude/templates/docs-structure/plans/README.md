# Plans

Plans written before starting non-trivial work, one file per plan. A plan describes **what** will be built and the **business rules** it must follow - the product side of the work.

- File name: `YYYY-MM-DD-topic-plan.md` (date written, topic describing the work).
- Start every new entry from `TEMPLATE.md`.
- A plan covers goal, context, scope, business rules, edge cases and the product-level approach (screens, flows, expected API behavior). The **technical implementation** - data model, contracts, components, tests, implementation order - goes in a matching file under `../specs/`, linked in **Related spec**.
- Plans are a record of intent at the time, not living documents - if the approach changes significantly mid-work, note the change in the plan rather than silently rewriting history.
- Keep **Status** up to date: `Draft` -> `Approved` -> `Implemented`, or `Superseded` (link what replaced it). Partial states are fine when true (e.g. "Implemented in the API only").
- Keep the index below in sync whenever an entry is created or its status changes.

## Index

| Plan | Status |
| --- | --- |
