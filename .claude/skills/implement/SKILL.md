---
name: implement
description: Implement an approved spec task by task by orchestrating the stack agents, test-runner, quality-fixer, the reviewers and backlog-keeper, with a resumable run state. Use when the user says "/implement <feature>", "podemos seguir com a implementação", "pode implementar", "vamos implementar", "segue com a implementação", "implement this spec", "start development of the plan", or "go" right after approving a spec. Verifies first that the plan and spec are approved, and never guesses which spec when several qualify.
argument-hint: <docs/features/<slug>/ or docs/specs/file.md> [tasks 2-4] [--step]
---

# Implement a spec

You coordinate. Delegate the work to subagents and keep this conversation lean.

- Do not write feature code yourself. Delegate it to the stack agents.
- Pass file paths to subagents, not file contents. They read the spec and the log themselves.
- Never commit or push. Never use the em dash; use "-".

Arguments: `$ARGUMENTS`

## 1. Resolve the target

1. **Layout and paths.** Resolve them with the `project-docs` skill (**Layouts and path resolution**): the docs layout, and the feature's plan, spec and implementation log paths. Never hard-code `docs/plans`, `docs/specs` or `docs/features`. In a `legacy` project with no layout declared, make the one-time migration offer that section describes before anything else.
2. **Which spec**, in this order, and look only inside the current project (the git root, or the working directory):
   1. the feature folder or spec path in the arguments;
   2. the feature or spec named in the conversation;
   3. the only spec with status `Approved` (from `docs/features/README.md`, or the specs Index in `legacy`).

   If none of these resolves to exactly one spec, list the candidates (`Draft` or `Approved`) with their status and ask which one. Never pick between several. If the project has no spec, say so in one line and suggest `@specker` (or `@planner` when there is no plan either).
3. **Tasks**: an optional range or list (`tasks 2-4`, `task 3`). The default is every task in **Implementation order** not already done (`Status: done` in a structured task block, or a ` (done)` suffix in an older free-form list).
4. **`--step`**: pause after each task and wait for the user's approval before starting the next one. Without it, run all tasks and pause only on blockers, scope requests and the questions below.

## 2. Preconditions

Check them before touching anything, in one `AskUserQuestion` call when there is more than one thing to ask:

1. **Plan**: it must be `Approved`. A refactor spec without a plan (its **Source** is a backlog entry) skips this check. A `Draft` plan: stop and say it needs approval first (or that asking `@specker` for the spec approves it).
2. **Spec**: `Approved` or `In progress` proceeds. A `Draft` spec:
   - invoked explicitly as `/implement`: that counts as approval;
   - invoked from a phrase ("podemos seguir com a implementação"): ask "the spec is still Draft - approve it and start?". A yes counts as approval.

   Set an approved spec to `Approved` and update the Index.
3. **Open questions**: if the spec or plan has open questions that block a selected task, ask the user before starting.
4. **Working tree**: run `git status`. If there are uncommitted changes unrelated to this spec, ask the user whether to continue. The reviewers diff the whole working tree, so they would mix those changes with this work.
5. **Run state ignored by git**: `git check-ignore -q .claude/runs/<slug>.json`. If it would be tracked, ask the user once whether to add `.claude/runs/` to `.gitignore`; if they decline, keep the run state anyway and mention it in the final report.

## 3. Run state

The run state lives in `.claude/runs/<slug>.json` at the project root (`<slug>` is the feature folder name, or the legacy spec file name without date and suffix). It is how a run resumes, how budgets are enforced and how hooks and an external orchestrator observe the run. Write it after every step that changes it.

```json
{
  "feature": "docs/features/<slug>/",
  "spec": "<spec path>",
  "log": "<log path>",
  "phase": "implement | verify | review | done",
  "started_at": "<ISO timestamp>",
  "updated_at": "<ISO timestamp>",
  "current_task": 3,
  "tasks": { "1": "done", "2": "done", "3": "in_progress", "4": "pending" },
  "allowed_paths": { "3": ["services/api/src/orders/**"] },
  "approved_scope": [
    { "task": 3, "action": "edit", "target": "<path or command>", "reason": "...", "decision": "approved | denied", "at": "<ISO timestamp>" }
  ],
  "budget": { "fix_rounds": { "3": 1 }, "full_gate_runs": 0, "review_rounds": 0 },
  "agent_calls": [{ "agent": "backend-node", "task": 1, "result": "done", "at": "<ISO timestamp>" }]
}
```

- **Start**: if the file exists with `phase` other than `done`, this is a resume: show where the run stopped (phase, done tasks, pending scope decisions) and continue from there, without repeating done tasks. Otherwise create it.
- **Budgets**: at most 2 fix rounds per task, 1 full gate per run (plus one re-run after review fixes), 1 review round (plus 1 only when blockers were fixed). When a budget runs out, stop and ask the user.
- **End**: set `phase: done` when the final report is delivered. Never delete the file.

## 4. Build the task list

A structured task block gives every field directly (**Stack**, **Files**, **Depends on**, **Done when**, **Status**). For an older free-form list, derive them from the task text. Each task has:
- its number and title;
- its stack (from **Stack**, or inferred from its files: `package.json` with Nest/Express means `backend-node`, `pom.xml`/`build.gradle` means `backend-spring`, `go.mod` means `backend-go`, `Cargo.toml` means `backend-rust`, `pyproject.toml` means `backend-python`, React web means `frontend-react`, React Native/Expo means `mobile-react-native`);
- its `allowed_paths` (from **Files**, or the files the task text names, plus scope approved earlier in `approved_scope`);
- its dependencies and its done criteria.

Show the list to the user in a short table, set the spec to `In progress` when the first task starts, then go.

## 5. Per task

1. **Implement.** Delegate to the stack agent with this prompt shape:

   > phase: implement. Implement task N of `<spec path>` (plan: `<plan path>`, implementation log: `<log path>`). Only this task: `<task title>`. Done criteria: `<criteria>`. allowed_paths: `<list>`. Read the implementation log first: it holds the files, decisions and assumptions of earlier tasks. Follow the spec's Design and Testing sections for this task.

   Independent tasks that touch different services may run in parallel, as separate agents in the same message. Run tasks that share files or depend on each other in order.

2. **Scope requests.** If a report ends with `result: blocked` and `scope_requests`, collect the requests of every agent that stopped (parallel ones included) and ask the user once, one `AskUserQuestion` call, each request with its reason. Record each decision in `approved_scope`. Then resume the same agent with `SendMessage`, keeping its context: approved targets join that task's `allowed_paths`; denied ones are stated, so the agent finishes without them (`partial`) or declares a blocker.

3. **Check.** Delegate to `test-runner` with scope `task`, limited to the packages or services the task touched.

4. **Fix.** If `test-runner` reports failures, delegate to `quality-fixer` with the failure list, then run `test-runner` again. After 2 rounds still failing, stop and ask the user.

5. **Tests.** If the stack agent's report says the changed behavior has no tests, delegate to `test-writer` for that task's files.

6. **Mark done.** Set the task's `Status: done` (or append ` (done)` to the line of an older free-form list), and `tasks[N] = "done"` in the run state. These and the spec status are the only edits you make to the spec.

7. **Collect and log.** The agents end with a YAML report. Keep `decisions`, `assumptions`, `migrations`, `env_vars`, `needs_docs`, `manual_checks`, `local_checks` and `out_of_scope_issues` for the final report, and append the task's block to the implementation log (create it from the log template on the first task of the feature; start a new `## Run <date>` section on each run): files, decisions, assumptions, approved scope, migrations/env vars, docs pending. The next task reads it from there.

8. **Pause** here if `--step` was given: show a 3-5 line summary of the task and wait for the user.

## 6. Review (once, after all selected tasks)

1. Set `phase: review`. Delegate to `code-reviewer` (scope: the working tree, and the spec and log paths).
2. If any task touched authentication, authorization, API endpoints, user input, uploads, queries, secrets or dependencies, delegate to `security-reviewer` in parallel with the code reviewer.
3. **Fix the findings.**
   - Send blocker and major bugs, and critical, high or medium security findings, to the owning stack agent with the exact findings and the task's `allowed_paths`. Then run `test-runner` (scope `task`) again.
   - Run `code-reviewer` once more, only if blockers were fixed. Never loop more than once.
   - Minor findings and standards notes: fix them in the same round if they are in this change's code. Otherwise add them to the collected `out_of_scope_issues`.
   - The reviewers' `needs_docs` join the collected `needs_docs`.

## 7. Verify and close

1. Set `phase: verify`. Run the final gate once through `test-runner` with scope `full`, plus any suite the spec's **Verification** section names explicitly.
2. **Manual checks** (UI, flows, restarts, requests that could not run): never run them yourself - no browser, dev server, simulator or screenshots, and no starting or restarting services. Consolidate the agents' `manual_checks` and the spec's manual verification steps into one checklist for the user.
3. **Backlog.** Send every collected `out_of_scope_issues` to `backlog-keeper` in a single call, in run-batch mode, each with its source (feature, task, agent). Do not write backlog entries yourself.
4. If every task of the spec is done and verification passes, set the spec to `Implemented` and update the Index. Otherwise leave it `In progress`. Set the run state's `phase: done`.

## 8. Final report to the user

Keep it short:
- tasks completed, and tasks remaining;
- files changed, grouped by service (one line per file);
- migrations and new env vars;
- check results, and review findings fixed and still open;
- `local_checks` results (request, status, pass/fail/skipped);
- scope requests approved or denied;
- assumptions the agents made that the user should confirm;
- backlog entries created or updated (paths, from `backlog-keeper`);
- **Para validar localmente**: the consolidated manual checklist, as `- [ ]` items;
- **Documentation pass**: the consolidated `needs_docs`, plus plan status, README and `docs/` coherence. Run it after the user confirms the manual checks; no agent edited docs during the run.
