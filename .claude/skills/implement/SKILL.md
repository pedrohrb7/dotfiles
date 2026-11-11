---
name: implement
description: Implement an approved technical spec task by task by orchestrating the stack agents, test-runner, quality-fixer and the reviewers. Use when the user says "/implement <spec>", "implement this spec" or "start development of the plan".
disable-model-invocation: true
argument-hint: <docs/specs/file.md> [tasks 2-4] [--step]
---

# Implement a spec

You are the orchestrator. Delegate the work to subagents and keep this conversation lean.

- Do not write feature code yourself. Delegate it to the stack agents.
- Pass file paths to subagents, not file contents. They read the spec themselves.
- Never commit. Never use the em dash; use "-".

Arguments: `$ARGUMENTS`

## 1. Resolve the target

- **Spec**: the path in the arguments. If there is none, list the specs in the current project's `docs/specs/` whose status is `Draft` or `Approved` and ask the user which one to implement. Look only inside the current project (the git root, or the working directory). Never search the rest of the filesystem. If the project has no specs, say so in one line and suggest `@planner` to write one.
- **Tasks**: an optional range or list (`tasks 2-4`, `task 3`). The default is every task in **Implementation order** not already marked `(done)`.
- **`--step`**: pause after each task and wait for the user's approval before starting the next one. Without it, run all tasks and pause only on blockers.

## 2. Preflight

1. Read the spec and its **Related plan**. Read only those two documents; leave the code to the subagents.
2. **Status**: if the spec is still `Draft`, running `/implement` counts as approval. Set it to `Approved` and update the specs Index.
3. **Open questions**: if the spec or plan has open questions that block a selected task, ask the user (one `AskUserQuestion` call) before starting.
4. **Working tree**: run `git status`. If there are uncommitted changes unrelated to this spec, ask the user whether to continue. The reviewers diff the whole working tree, so they would mix those changes with this work.
5. **Task list**: build the list. Each task has:
   - its number and title;
   - its stack (from the task text, or inferred from its files: `package.json` with Nest/Express means `backend-node`, `pom.xml`/`build.gradle` means `backend-spring`, `go.mod` means `backend-go`, `Cargo.toml` means `backend-rust`, `pyproject.toml` means `backend-python`, React web means `frontend-react`, React Native/Expo means `mobile-react-native`);
   - its dependencies and its done criteria.

   Show the list to the user in a short table, then start.

## 3. Per task

1. **Implement.** Delegate to the stack agent with this prompt shape:

   > Implement task N of `<spec path>` (plan: `<plan path>`). Only this task: `<task title>`. Done criteria: `<criteria>`. allowed_paths: `<the files and folders the task names, plus scope approved earlier>`. Earlier tasks in this spec already changed: `<files from previous reports>`; their decisions and assumptions: `<from previous reports>`. Follow the spec's Design and Testing sections for this task.

   Independent tasks that touch different services may run in parallel, as separate agents in the same message. Run tasks that share files or depend on each other in order.

   **Scope requests.** If a report ends with `result: blocked` and `scope_requests`, ask the user once (one `AskUserQuestion` call for all pending requests, each with its reason). Then resume the same agent with `SendMessage`, keeping its context: approved requests join that task's `allowed_paths`; denied ones are stated so the agent finishes without them. Keep every approval for the final report.

2. **Check.** Delegate to `test-runner`, scoped to the packages or services the task touched.

3. **Fix.** If `test-runner` reports failures, delegate to `quality-fixer` with the failure list, then run `test-runner` again. After 2 rounds that are still failing, stop and ask the user.

4. **Tests.** If the stack agent's report says the changed behavior has no tests, delegate to `test-writer` for that task's files.

5. **Mark done.** Append ` (done)` to the task line in the spec's **Implementation order**, so an interrupted run can resume.

6. **Collect.** The agents end with a YAML report. Keep `decisions`, `assumptions`, `migrations`, `env_vars`, `needs_docs`, `manual_checks`, `local_checks` and `out_of_scope_issues`, and pass the decisions and assumptions on to the next tasks.

7. **Pause** here if `--step` was given: show a 3-5 line summary of the task and wait for the user.

## 4. Review (once, after all selected tasks)

1. Delegate to `code-reviewer` (scope: the working tree).
2. If any task touched authentication, authorization, API endpoints, user input, uploads, queries, secrets or dependencies, delegate to `security-reviewer` in parallel with the code reviewer.
3. **Fix the findings.**
   - Send blocker and major bugs, and critical, high or medium security findings, to the owning stack agent with the exact findings. Then run `test-runner` again.
   - Run `code-reviewer` once more, only if blockers were fixed. Never loop more than once.
   - Minor findings and standards notes: fix them in the same round if they are in this change's code. Otherwise add them to the collected `out_of_scope_issues`.
   - The reviewers' `needs_docs` join the collected `needs_docs`.

## 5. Verify

1. Run the final gate once through `test-runner` with scope `full`, plus any suite the spec's **Verification** section names explicitly.
2. Manual checks (UI, flows, restarts, requests that could not run): never run them yourself - no browser, dev server, simulator or screenshots, and no starting or restarting services. Consolidate the agents' `manual_checks` and the spec's manual verification steps into one checklist for the user.
3. **Backlog.** Log the collected `out_of_scope_issues` once, with the `project-docs` skill (add-entry mode): one entry per root cause, deduplicated against each folder's Index. If the project has no `docs/backlog/`, list them in the final report instead.
4. If every selected task is `(done)` and verification passes, set the spec to `Implemented` and update the specs Index. Otherwise leave it `Approved`.

## 6. Final report to the user

Keep it short:
- tasks completed, and tasks remaining;
- files changed, grouped by service (one line per file);
- migrations and new env vars;
- check results, and review findings fixed and still open;
- `local_checks` results (request, status, pass/fail/skipped);
- scope requests approved or denied;
- assumptions the agents made that the user should confirm;
- backlog entries logged (paths);
- **Para validar localmente**: the consolidated manual checklist, as `- [ ]` items;
- **Documentation pass**: the consolidated `needs_docs`, plus plan status, README and `docs/` coherence. Run it after the user confirms the manual checks; no agent edited docs during the run.
