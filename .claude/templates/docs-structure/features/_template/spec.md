# <Spec title>

- **Date:** <YYYY-MM-DD>
- **Status:** Draft
- **Plan:** [plan.md](plan.md) <!-- for a refactor without a plan, replace with: **Source:** docs/backlog/refactor/<entry>.md -->
- **Implementation log:** [log.md](log.md)

## Summary

<What is being implemented, in a few sentences - which services/layers change>

## Background

<The plan and decisions this implements; anything technical the reader needs first>

## Design

<The technical implementation - be concrete: data model and migrations, API contracts, modules and components, file-by-file changes>

## Alternatives considered

<What else was considered and why it was rejected>

## Trade-offs

<What this design gives up in exchange for what it gains>

## Testing

<Tests to write per file or module, with the cases each covers. Every business rule of the plan maps to at least one test. Name suites as they appear in the root CLAUDE.md `Test suites` table>

## Implementation order

<!-- One block per task, in exactly this shape: /implement reads it without interpreting prose. Each task is small enough for one PR. Backend and data tasks come before the clients that consume them. `Files` lists every path (globs allowed) the task may write: it becomes the agent's allowed_paths, so a list that is too narrow turns into scope requests. /implement only changes `Status`. -->

### Task 1 - <title>

- **Stack:** <backend-node | backend-spring | backend-go | backend-rust | backend-python | frontend-react | mobile-react-native>
- **Files:** `<path or glob>`, `<path or glob>`
- **Depends on:** <- | Task N>
- **Done when:** <observable criteria>
- **Status:** pending

## Verification

<Suites from the `Test suites` table to run at the end, naming any on-demand suite explicitly (load, long e2e), and the manual checks the user does on the local run>

## Open questions

...
