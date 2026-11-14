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

Neste repo (dotfiles), o plan de uma etapa da config vive no `.claude/agent-workflow.md`, e não num `plan.md` dentro da pasta da feature; a spec aponta para a seção certa.

## Index

| Feature | Plan | Spec | Updated |
| --- | --- | --- | --- |
| [design-director](design-director/) | Implemented ([agent-workflow.md, 15.1](../../agent-workflow.md#151-etapa-h---design-director-adendo-2026-11-11)) | Implemented ([spec.md](design-director/spec.md)) | 2026-11-11 |
| [audit-hook-test-suite](audit-hook-test-suite/) | - (refactor, sem plan; [entrada](../backlog/refactor/2026-11-11-audit-hook-test-suite.md)) | Implemented ([spec.md](audit-hook-test-suite/spec.md)) | 2026-11-12 |
| [audit-scratch-exemption](audit-scratch-exemption/) | - (refactor, sem plan; [entrada](../backlog/refactor/2026-11-11-audit-scratch-exemption-too-broad.md)) | Implemented ([spec.md](audit-scratch-exemption/spec.md)) | 2026-11-12 |
| [skills-docs-root](skills-docs-root/) | - (refactor, sem plan; [entrada](../backlog/refactor/2026-11-11-skills-configurable-docs-root.md)) | Implemented ([spec.md](skills-docs-root/spec.md)) | 2026-11-13 |
| [audit-md-outside-docs](audit-md-outside-docs/) | - (refactor, sem plan; [entrada](../backlog/refactor/2026-11-11-audit-md-outside-docs-false-positive.md)) | Implemented ([spec.md](audit-md-outside-docs/spec.md)) | 2026-11-13 |
| [lua-agent](lua-agent/) | Implemented ([agent-workflow.md, 15.2](../../agent-workflow.md#152-etapa-i---agent-lua-adendo-2026-11-12)) | Implemented ([spec.md](lua-agent/spec.md)) | 2026-11-13 |
| [audit-hook-hardening](audit-hook-hardening/) | - (refactor, sem plan; [entrada](../backlog/refactor/2026-11-13-audit-hook-hardening.md)) | Implemented ([spec.md](audit-hook-hardening/spec.md)) | 2026-11-13 |
| [audit-shell-lexer](audit-shell-lexer/) | - (refactor, sem plan; [entrada](../backlog/refactor/2026-11-13-audit-shell-lexer.md)) | Implemented ([spec.md](audit-shell-lexer/spec.md)) | 2026-11-13 |
