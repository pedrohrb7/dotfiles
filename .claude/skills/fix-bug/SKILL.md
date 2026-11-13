---
name: fix-bug
description: Fix a registered bug end to end by orchestrating the agents - reproduce it as the user sees it, diagnose the root cause, write a regression test that fails, fix it without touching that test, gate, review, document and close the backlog entry, with a resumable run state. Use when the user says "corrige o bug X", "vamos resolver esse bug", "fix bug", "/fix-bug <entry>", or answers yes to "quer corrigir agora?" after backlog-keeper registered a bug.
argument-hint: <<docs>/backlog/bugs/<entry>.md or bug title> [--step]
---

# Fix a bug

You coordinate. Delegate the work to subagents and keep this conversation lean. Never commit or push. Never use the em dash; use "-".

Arguments: `$ARGUMENTS`

## 1. The entry

1. Find the bug entry in `<docs>/backlog/bugs/` (`<docs>` is the project docs root, resolved with the project-docs skill, **Docs root**: the `- docs root:` line of the git-root `CLAUDE.md` `## Workflow`, default `docs/`; path in the arguments, or the bug named in the conversation; with several candidates, list them and ask). If it is not registered yet, delegate to `backlog-keeper` (user report mode) first. The entry is the source of truth for the symptom, steps and evidence.
2. Set its status to `In progress` through `backlog-keeper` (update mode).
3. **Run state** in `.claude/runs/bug-<slug>.json` (same rules as `/implement`: ignored by git, resumable, budgets), with `phase` (`reproduce | diagnose | regression | fix | gate | review | verify | document | done`), `current_task` (`regression` or `fix`, which the audit hook uses; bug runs are sequential, so it stays a scalar and there is no `running_tasks`), `allowed_paths` per step, `approved_scope`, budgets and `agent_calls`. If it exists with `phase` other than `done`, resume from there.

## 2. Reproduce (`phase: reproduce`)

Follow the `bug-repro` skill, as the user experiences the bug:
- **Backend**: a request against the user's running local instance with an `X-Request-Id` header, plus that request's filtered log lines (see the project's `## Local runtime`). Never start, restart or rebuild anything; if the service is down or stale, ask the user to start or restart it.
- **Failing command**: run it once and keep 1-10 lines of output.
- **UI**: write the exact steps (screen, viewport or device, theme, state) and ask the user to confirm the symptom on their local run. Only on an explicit request, delegate a visual check to `ui-verifier`.

Not reproduced: stop. Have `backlog-keeper` record the attempt and its evidence in the entry ("could not reproduce"), and report it. Never fix what you could not reproduce.

## 3. Diagnose (`phase: diagnose`)

Delegate to the stack agent that owns the code, with `phase: diagnose`, the entry path and the reproduction evidence. It writes nothing and returns `diagnosis`: root cause at `path:line`, fix plan, `fix_paths` and where the regression test belongs. If the root cause sits in a service other than the one the symptom showed, delegate a second diagnose there before going on.

## 4. Regression test (`phase: regression`)

Set `current_task: regression` and `allowed_paths.regression` to the test location from the diagnosis. Delegate to `test-writer` in **regression mode** with the entry, the evidence and the diagnosis. Then run it through `test-runner` with scope `files`: it must fail with `failure_kind: assertion`, for the reason the bug describes. A test that passes does not reproduce the bug: send it back once, then stop and ask the user.

## 5. Fix (`phase: fix`)

Set `current_task: fix` and `allowed_paths.fix` to `fix_paths`. Delegate to the stack agent with `phase: fix`, the entry, the diagnosis and the regression test path. It fixes the root cause without editing the test. Handle `scope_requests` as `/implement` does: one question to the user for everything pending, then resume the same agent.

## 6. Gate and review (`phase: gate`, then `review`)

1. `test-runner` with scope `task` for the touched services. Failures go to `quality-fixer`, at most 2 rounds, then ask the user.
2. `code-reviewer` on the working tree, with the entry and the diagnosis as the intended behavior; add `security-reviewer` when the fix touches auth, API endpoints, input handling, queries, secrets or dependencies. Blockers and major findings go back to the stack agent (`phase: fix`), then `test-runner` again; one re-review only if blockers were fixed.

## 7. Verify (`phase: verify`)

Repeat the reproduction of step 2. Backend and command: it must now show the expected behavior. UI: add the steps to the checklist for the user. The service does not reload code by itself: ask the user to restart it before repeating.

## 8. Close (`phase: document`, then `done`)

1. **Docs.** If the agents reported `needs_docs`, delegate to `docs-writer` once.
2. **Backlog.** One call to `backlog-keeper`: update the entry (root cause, fix summary and changed files, regression test path, status `Fixed`) and log every collected `out_of_scope_issues` in run-batch mode.
3. Set the run state's `phase: done`.

## 9. Final report

Keep it short: the root cause (one line), the files changed, the regression test, check and review results, the repro before and after (request, status, log line; or the command), docs updated, backlog entries created or updated, and **Para validar localmente** as `- [ ]` items (UI steps, restarts). `--step` pauses after each phase for the user's go.
