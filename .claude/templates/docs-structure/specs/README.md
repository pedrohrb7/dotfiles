# Specs

Specs written before implementing a non-trivial feature or change, one file per spec. A spec describes **how** it will be built - the technical implementation of a plan.

- File name: `YYYY-MM-DD-topic-design.md` (date written, topic being designed).
- Start every new entry from `TEMPLATE.md`.
- A spec covers the concrete technical design (data model, API contracts, components, file-by-file changes), the alternatives considered and their trade-offs, the tests to write, the implementation order and how to verify it. The **what and the business rules** live in the matching file under `../plans/`, linked in **Related plan**.
- Keep specs as the historical record of a decision - if the design changes later, add a dated addendum or a new spec rather than rewriting the original.
- Keep **Status** up to date: `Draft` -> `Approved` -> `Implemented`, or `Superseded` (link what replaced it).
- Keep the index below in sync whenever an entry is created or its status changes.

## Index

| Spec | Status |
| --- | --- |
