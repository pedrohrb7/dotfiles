# Claude Code global config

The design behind the agents and skills (phases, single owner per action, agent contracts, runtime validation, the decisions taken and the rollout stages) is in [`agent-workflow.md`](agent-workflow.md). It lives only in this repo and is not symlinked into `~/.claude`. The same goes for `.claude/docs/`, where the plans, specs and logs of this config's own features live (for example `.claude/docs/features/design-director/`). In agent and skill instructions `<docs>` stands for the project's docs root (see the hooks section); `project-docs` resolves it. The run states in `.claude/runs/` are git-ignored.

## Setup: symlinks

Create these links by hand on each machine, each pointing to the same name in this repo:

```sh
ln -s ~/dotfiles/.claude/CLAUDE.md   ~/.claude/CLAUDE.md
ln -s ~/dotfiles/.claude/settings.json ~/.claude/settings.json
ln -s ~/dotfiles/.claude/agents      ~/.claude/agents
ln -s ~/dotfiles/.claude/skills      ~/.claude/skills
ln -s ~/dotfiles/.claude/hooks       ~/.claude/hooks
ln -s ~/dotfiles/.claude/templates   ~/.claude/templates
```

`agent-workflow.md` and this `README.md` are not linked. Do not skip `hooks`: `settings.json` wires `python3 "$HOME/.claude/hooks/agent-audit.py"` on `PreToolUse`, and the hook fails when the file is absent, which breaks every Bash, Write and Edit call.

## skills/

Personal skills. Each one owns a phase of the workflow or a piece of know-how, and the global `CLAUDE.md` **Workflow** table routes phrases to them ("tenho uma ideia" -> `grill-me`, "cria a identidade visual" -> `design-director`, "podemos seguir com a implementação" -> `implement`, "corrige o bug X" -> `fix-bug`, "escreve o PR" -> `pr-description`). The skill holds the know-how, the agent executes: several are preloaded by agents through their `skills:` frontmatter. No skill is disabled in `settings.json` (`skillOverrides`).

| skill                  | purpose                                                                                 | preloaded by |
| ---------------------- | --------------------------------------------------------------------------------------- | ------------ |
| `grill-me`             | Discover: interview the user one question at a time until the decisions are clear, then hand off to `planner` | - |
| `implement`            | Execute an approved spec task by task through the agents, with preconditions, a resumable run state in `.claude/runs/` and an optional `--tdd` mode | - |
| `fix-bug`              | Fix a registered bug: reproduce, diagnose (read-only), regression test red by assertion, fix without touching it, gate, review, docs, close the entry | - |
| `tdd`                  | TDD where the user implements: settle the behavior, scaffold stubs that compile, tests red by assertion, hand off | - |
| `bug-repro`            | Reproduce a bug end to end as the user sees it: request + logs, failing command, or UI steps the user confirms | `quality-fixer` |
| `project-docs`         | The `<docs>/` tree: docs root, layouts and path resolution (features or legacy), scaffold, add entry, migrate | `planner`, `specker`, `backlog-keeper`, `docs-writer` |
| `docs`                 | Know-how of the documentation pass                                                      | `docs-writer` |
| `design-system`        | Maintenance of design tokens, hierarchy and accessibility, with `DESIGN_SYSTEM.md` as the single source; creating the direction belongs to `design-director` | `frontend-react`, `mobile-react-native`, `design-director` |
| `dep-audit`            | Audit dependencies by real risk; never auto-upgrade                                      | `security-reviewer` |
| `pr-description`       | Deliver: draft the PR description and changelog entry from the diff and the feature's documents (text only) | - |
| `archify`              | Architecture, flow, sequence and state diagrams as standalone HTML                       | - |
| `new-project`          | Scaffold a new project's structure from `templates/`                                    | - |
| `onboard`              | Document an existing project per service, plus the root `CLAUDE.md` agent sections      | - |

Removed in stage F (see `agent-workflow.md`): `review` (its intent check moved into `code-reviewer`), `codebase-standards` (already `code-reviewer`'s standards phase), `scaffold` (now step 2 of `tdd` and the `scaffold` phase of the stack agents) and `code-simplify` (replaced by the built-in `/simplify`; its "wait for approval before applying" rule is in the Workflow table).

`implementer-contract` is not called by hand (`user-invocable: false`): it is the shared contract every stack agent preloads through its `skills:` frontmatter - inputs, write scope and scope requests, narrow-checks policy, runtime validation against the user's local instance, UI policy, out-of-scope reporting and the YAML report. Rules common to the stack agents change there, not in the seven agent files.

### Third-party, auto-invoked skills

These are vendored from upstream and keep model invocation on: Claude loads them on its own when the description matches the task. Each must sit directly under `skills/<name>/SKILL.md` - Claude Code does not discover nested folders, so never group them in a subfolder.

| skill                               | source        | triggers on                                                             |
| ----------------------------------- | ------------- | ----------------------------------------------------------------------- |
| `react-best-practices`              | vercel        | Writing/reviewing React or Next.js code, data fetching, bundle size     |
| `composition-patterns`              | vercel        | Component API design, compound components, boolean prop proliferation   |
| `react-view-transitions`            | vercel        | Page/route transitions, shared element and enter/exit animations        |
| `react-native-skills`               | vercel        | General React Native/Expo performance and best practices                |
| `web-design-guidelines`             | vercel        | UI/UX and accessibility audits                                          |
| `writing-guidelines`                | vercel        | Docs/prose style reviews                                                |
| `react-native-core`                 | maikotrindade | Core RN components, layout, styling, lists, platform APIs               |
| `react-native-ecosystem`            | maikotrindade | React Navigation, Zustand, TanStack Query, Reanimated, storage          |
| `react-native-expo`                 | maikotrindade | Expo Router, EAS Build/Update/Deploy, Expo modules, SDK upgrades        |
| `react-native-performance`          | maikotrindade | Profiling and fixing FPS, TTI, memory and bundle size                   |
| `react-native-testing`              | maikotrindade | Jest + React Native Testing Library tests                               |
| `react-native-reusables`            | maikotrindade | shadcn-style RN components with NativeWind                              |
| `upgrading-react-native`            | maikotrindade | Bumping RN versions, native iOS/Android migration                       |
| `react-native-brownfield-migration` | maikotrindade | Adopting RN inside an existing native iOS/Android app                   |
| `github`                            | maikotrindade | gh CLI, PRs, stacked PRs, branching                                     |
| `github-actions`                    | maikotrindade | CI workflows for RN simulator/emulator builds                           |

The maikotrindade descriptions of `react-native-expo`, `react-native-performance` and `react-native-testing` were extended locally with a "Use when..." clause so they trigger reliably; re-apply that if they are updated from upstream.

Visual direction is split in two, with no external plugin. **Creation** belongs to the `design-director` agent: for a project with no defined frontend it runs in rounds (brief if missing, two contrasting directions, the user's choice) and writes only `DESIGN_SYSTEM.md` (palette with light and dark, type, `Layout concept`, principles). It is never automatic: it is called only after the user's yes, from three entry points - the `new-project` question (UI services only), the Workflow phrases ("cria a identidade visual", "define o design do zero", "vamos criar o frontend do zero") and the offer in step 1 of `design-system`. **Maintenance** stays with the `design-system` skill, which keeps the file consistent afterward (tokens, hierarchy, accessibility); after creation only the main session writes the file, and stack agents propose values through `scope_requests`. Tokens already in code without a `DESIGN_SYSTEM.md` are documented by the main session following `design-system` (extraction), not by the agent. Taking the tokens to the code is a normal plan and spec.

### skills/synced/

Auto-generated by Claude Code: the skills enabled on claude.ai (docx, pdf, pptx, xlsx, browser, computer-use...) are downloaded here and rewritten on every sync. Not versioned - it's in the root `.gitignore`. Don't edit files there; changes are overwritten on the next sync.

### skills/.trash/

Also auto-generated by Claude Code: where the claude.ai skill sync moves the old copies of the synced skills (docx, pdf, pptx, xlsx, computer-use...) when it replaces them. Not versioned - it's in the root `.gitignore` (`.claude/skills/.trash/`). Don't edit it.

## agents/

Global subagents, symlinked as `~/.claude/agents -> ~/dotfiles/.claude/agents` (link listed in [Setup: symlinks](#setup-symlinks)). Claude delegates to them automatically when the description matches ("Use proactively when..."), or call one with `@name`.

Each agent pins its own `model` and `effort` to balance quality and token cost:

- `opus` only where a mistake is expensive and runs are rare (reviews, planning).
- `sonnet` for implementation and fixing, the long tool-call loops where most tokens go.
- `haiku` for mechanical work whose value is a short summary, so raw logs never reach the main context.

| agent                 | model  | effort | tools                  | preloaded skills                               | auto-invoked                              |
| --------------------- | ------ | ------ | ---------------------- | ---------------------------------------------- | ----------------------------------------- |
| `code-reviewer`       | opus   | medium | read-only              | -                                              | after significant changes                 |
| `security-reviewer`   | opus   | medium | read-only              | `dep-audit`                                    | only auth, API, input, secrets, deps      |
| `planner`             | opus   | high   | read + write `<docs>/` | `project-docs`                                 | "vamos planejar", "escreve o plano"       |
| `specker`             | opus   | high   | read + write `<docs>/` | `project-docs`                                 | "pode especificar", "escreve a spec"      |
| `docs-writer`         | sonnet | medium | read + write doc files | `docs`, `project-docs`                         | end of `/implement` and bug fixes, "documenta" |
| `ui-verifier`         | sonnet | low    | all, read-only by prompt | -                                            | only on an explicit "tira um print", "pode subir um snapshot" |
| `design-director`     | opus   | high   | `Read`, `Grep`, `Glob`, `Write`, `Edit` (no `Bash`) | `design-system`                | no - only after the user's yes, from `new-project`, the Workflow phrases or `design-system` |
| `backlog-keeper`      | sonnet | low    | read + write `<docs>/backlog/` | `project-docs`                           | "encontrei um bug", "registra um refactor", end of `/implement` |
| `frontend-react`      | sonnet | medium | all                    | `implementer-contract`, `design-system`, `react-best-practices`, `composition-patterns` | yes               |
| `mobile-react-native` | sonnet | medium | all                    | `implementer-contract`, `design-system`, `react-native-skills`, `react-native-core` | yes               |
| `backend-node`        | sonnet | medium | all                    | `implementer-contract`                         | yes                                       |
| `backend-spring`      | sonnet | medium | all                    | `implementer-contract`                         | yes                                       |
| `backend-go`          | sonnet | medium | all                    | `implementer-contract`                         | yes                                       |
| `backend-rust`        | sonnet | medium | all                    | `implementer-contract`                         | yes                                       |
| `backend-python`      | sonnet | medium | all                    | `implementer-contract`                         | yes                                       |
| `test-writer`         | sonnet | medium | all                    | -                                              | requested tests, legacy gaps, a report saying tests are missing; tdd and regression modes for `tdd`, `implement --tdd` and `fix-bug` |
| `quality-fixer`       | sonnet | medium | all                    | `bug-repro`                                    | after `test-runner` reports failures      |
| `test-runner`         | haiku  | low    | Bash, Read, Grep, Glob | -                                              | whenever checks need to run (sole owner of the gate) |

Token-economy rules every agent follows - keep them when adding a new one:

- Model aliases (`opus`/`sonnet`/`haiku`), not full IDs, so agents follow new model versions.
- Preload only small, always-relevant skills: preloaded `SKILL.md` content is paid on every run. Larger or situational skills (`react-view-transitions`, `react-native-expo`, `react-native-performance`, `react-native-testing`, ...) are named in the prompt and loaded on demand.
- Minimal `tools` on read-only agents; no MCP servers unless needed.
- The prompt ends with a fixed YAML report. That report is all that returns to the main context, and it is the interface an external orchestrator parses.
- Expensive (`opus`) agents get narrow auto-invocation triggers or are manual only.
- Narrow checks only: agents run the tests and files they touched. Whole suites run only through `test-runner` (one gate per task, one full gate per run), honoring the project's `## Test suites` table when it has one.
- No visual validation: agents never open a browser, simulator or screenshot unless the user explicitly asks; UI work reports `manual_checks` for the user. Backend runtime validation is one request to the user's running local instance plus a filtered log read, never starting, stopping or restarting services (see `implementer-contract`).

Scope rule every agent that edits code follows - keep it when adding a new one: fix only the lint, typecheck and test problems the current change caused, or that the task names. Pre-existing problems found along the way are not fixed and not written by the agent: they go to `out_of_scope_issues` in its report, and the main session (or `/implement`, at the end of a run) hands them to `backlog-keeper` in one call, which logs them once - failing/flaky tests, type/build errors and visual defects as bugs in `<docs>/backlog/bugs/`, lint violations and code smells as refactors in `<docs>/backlog/refactor/`, one entry per root cause, deduplicated against the folder's Index. A single writer avoids duplicate entries when agents run in parallel. Likewise, agents never edit docs: they list `needs_docs`, and the documentation pass happens once, at the end.

Write-scope rule: an agent writes only inside its task's `allowed_paths`. Anything else it needs is a `scope_requests` entry with the reason; the caller asks the user and resumes the same agent with the answer.

One writer per document: `planner` writes the feature's `plan.md` (product side only), `specker` writes its `spec.md` (technical side, with an **Implementation order** of structured task blocks - Stack, Files, Depends on, Done when, Status - so `/implement` can execute them without interpreting prose; also specs for refactor entries, with no plan), `/implement` writes `log.md`, and `backlog-keeper` writes `<docs>/backlog/`. Asking `specker` for the spec of a `Draft` plan marks the plan `Approved`. Paths come from the `project-docs` skill: `<docs>/features/<slug>/` by default, or `<docs>/plans/` + `<docs>/specs/` in a project still on the legacy layout.

Subagents cannot ask the user. `planner`, `specker` and `backlog-keeper` return `result: needs_input` with the question (a missing decision, the one-time docs migration offer, a bug with no way to reproduce it); stack agents return `result: blocked` with `scope_requests`. The main session asks, then resumes the same agent with `SendMessage`.

The global `CLAUDE.md` has a **Workflow** table that routes phrases to phases ("vamos planejar" -> `planner`, "pode especificar" -> `specker`, "podemos seguir com a implementação" -> `implement`, "encontrei um bug" -> `backlog-keeper`), each with its precondition, so nothing depends on remembering to call an agent by name.

### Feature workflow

1. "vamos planejar <feature>" (or `@planner`) - review `<docs>/features/<slug>/plan.md`, answer its open questions, ask for changes.
2. "pode especificar" (or `@specker`) - review `<docs>/features/<slug>/spec.md`.
3. "podemos seguir com a implementação" (or `/implement <docs>/features/<slug>/ [tasks 2-4] [--step]`) - checks that plan and spec are approved (a Draft spec reached by a phrase needs a yes), keeps a resumable run state in `.claude/runs/<slug>.json` (tasks, budgets, approved scope, agent calls), and orchestrates: per task, stack agent (with the task's **Files** as `allowed_paths`; scope requests go to the user) -> `test-runner` -> `quality-fixer` (max 2 rounds) -> `test-writer` if tests are missing, setting the task's `Status: done` in the spec and appending its block to `log.md`, so a run can resume and the next task inherits the decisions; then one review pass (`code-reviewer`, plus `security-reviewer` for auth/API/input/secrets/deps), fixes, one full gate, `docs-writer` once with the consolidated `needs_docs`, the out-of-scope issues handed to `backlog-keeper` once, and spec and plan status `Implemented`. `--step` pauses after each task. The final report lists the docs updated and ends with the "Para validar localmente" checklist.
4. Validate locally with the checklist. For a visual check, ask for it explicitly ("tira um print de /orders"): `ui-verifier` does it and only text comes back.

### Bug workflow

1. "encontrei um bug ..." - `backlog-keeper` registers it (deduplicated, from the template) and the session asks "quer corrigir agora?" ("só registra" skips the question).
2. "corrige o bug X" (or yes to the question) - `fix-bug` runs: reproduce as the user sees it (request + logs on the local instance, the failing command, or UI steps the user confirms), diagnose with the owning stack agent in read-only `diagnose` phase, `test-writer` writes a regression test that must fail by assertion, the stack agent fixes it in `fix` phase without touching the test, `test-runner` gate, review, the repro repeated, `docs-writer` if needed, and `backlog-keeper` closes the entry with root cause and fix. Resumable through `.claude/runs/bug-<slug>.json`.

Subagents cannot spawn subagents, so chains like `test-runner` -> `quality-fixer` -> `code-reviewer` are orchestrated by the main session (that is what `/implement` encodes). The write scopes of `planner`, `specker` (`<docs>/`) and `backlog-keeper` (`<docs>/backlog/`) are enforced by their prompts, not by `tools`.

### Permissions

`settings.json` allows reading and editing `~/.claude` and `~/dotfiles/.claude` without prompts, except the `settings*.json` files themselves, which always ask (an `ask` rule): otherwise an agent could rewrite its own permissions or hooks without the user seeing it. It also allows the `Read`, `Grep` and `Glob` tools everywhere, and read-only shell and git commands (listing, search and inspection such as `ls`, `cat`, `rg`, `fd`, `jq`, `diff`; `git status|log|diff|show|blame|rev-parse|ls-files`, bare `git branch` and `git remote -v`). `find`, `printenv` and `git branch <args>` are left out on purpose: `find` can run or delete (`-exec`, `-delete`), `printenv` exposes secrets and `git branch <args>` can delete branches (`-D`), and the read-only Docker commands agents use for runtime validation (`docker compose ps|logs|port|config|images`, `docker ps|logs|inspect|port|images`), and denies the lifecycle and exec commands (`up`, `down`, `start`, `stop`, `restart`, `rm`, `kill`, `pull`, `create`, `run`, `exec`, compose or plain). Image builds are in neither list: agents run them only when the task changes a Dockerfile or its build context. Permission rules match by command prefix, so a form like `docker compose -f other.yml up` is not caught by them; the `PreToolUse` enforcement of `hooks/agent-audit.py` normalizes those forms and blocks them.

## hooks/

Symlinked as `~/.claude/hooks -> ~/dotfiles/.claude/hooks` (link listed in [Setup: symlinks](#setup-symlinks); without it every Bash/Write/Edit call fails).

- `agent-audit.py` - audit and enforcement hook. **Recording**: wired on `PostToolUse`/`PostToolUseFailure` (Bash, file writes, MCP tools) and `SubagentStart`/`SubagentStop`, async, it appends one JSON line per event to `~/.claude/metrics/<session_id>.jsonl` (outside the repo). It classifies Bash commands (narrow/package/full/load tests, lint, typecheck, docker read/build/lifecycle, git commit/push, local/external requests), checks file writes against the active run's `allowed_paths` and `approved_scope` (`.claude/runs/<slug>.json` in the project). A scoped actor's write is in scope if it matches the `allowed_paths` or approved `approved_scope` of any task in the run's `running_tasks` (tasks with agents running now, set before a parallel batch) or of `current_task`; a stale `running_tasks` only widens the scope. The record's `task` is those keys joined with `,` (bug runs stay scalar), and flags what the workflow forbids: writes outside scope, `.md` files outside the project's docs root, docs (including READMEs and `.env.example`) or backlog edited by the wrong agent, any write by a read-only agent (`ui-verifier`, `test-runner`, reviewers), browser/screenshot tools used by anyone but `ui-verifier`, suites run by agents other than `test-runner`, docker lifecycle commands, commits and pushes, external requests. Reads and searches are not recorded; neither are file contents or command output. **Enforcement**: wired synchronously on `PreToolUse` (Bash, file writes, and only the browser/screenshot MCP tools, about 50 ms per call), it applies each flagged category's action from `agent-audit.json`: `block` denies the call with the reason and what to do instead (a scope request for subagents, asking the user for the main session, `manual_checks` for docker), `ask` makes Claude Code prompt the user, `warn` lets it through with a reminder in the agent's context, `audit` only records. Blocks and asks are recorded too. It fails open: any error lets the action through. **Heredocs**: a heredoc body is ignored by the classifier only for known data sinks (top-level `cat`/`tee` without pipes or substitutions, `git commit -F -`, `$(cat <<EOF)` as a `git commit -m` or `gh` message value, `gh pr|issue|release ... --body-file -`); any other heredoc body (`bash`, `python3`, `| sh`, ...) is classified as commands, and constructs the scanner does not model (`${`, backticks, process substitution, fd >= 3, ...) disable stripping entirely. A script written to a file and run later is out of its reach (see `agent-workflow.md`, 13.6). Tests: see the `tests/` entry below.
- `agent-audit.json` - the mode (`enforce` now; `audit` = record only, `off`) and the action per category. Current policy: `block` for docker lifecycle commands (also catching `-f` and `rtk` forms the permission rules miss), writes by read-only agents and browser/screenshot tools outside `ui-verifier`; `ask` for `git commit`/`git push`; `warn` for writes outside scope, suites outside `test-runner`, `.md` outside the docs roots, docs or backlog by the wrong agent, `design_system_write_by_other` and external requests; `audit` for docker builds. A `warn` category moves to `block` only after the metrics show no false positives.
  - `design_director_write_outside` (`block`): any write by `design-director` to a file that is not a `DESIGN_SYSTEM.md`, at any path (actor-only flags do not depend on a git root). `design_system_write_by_other` (`warn`): a `DESIGN_SYSTEM.md` written by anyone but `design-director` or the main session; the reminder says to propose the value in `scope_requests`.
  - Write targets outside the repo: the governing root is the git root of the session cwd (where the run lives), falling back to the target's own root. A target inside a nested repo (submodule) of that root is judged by both roots and the flags are unioned (stricter wins). The path has `~` expanded and is resolved; with `..`, the resolved and the lexical form are both judged. A target outside every root is recorded with `area: "outside"` and its absolute path as `rel`. Actor-only flags (`write_by_readonly_agent`, `design_director_write_outside`, `design_system_write_by_other`, the last by raw or resolved name) apply to any path; area flags (`md_outside_docs`, `docs_write_by_implementer`, `backlog_write_by_other`) only inside a repo. Fixed-scope actors (implementers, `quality-fixer`, `test-writer`) in a run get `out_of_scope_write` for an outside target unless an approved `approved_scope` entry is an absolute glob matching it (literally after `~` expansion, symlinks not resolved, so a write through a symlink alias is flagged; relative globs and the always-allowed repo conventions never cover outside paths) or the path is strictly inside the session scratchpad, the `scratchpad_dir` of the hook payload (compared by path component and as given, never resolved; other sessions' scratchpads and other `claude-*` directories are not exempt). Without a usable `scratchpad_dir` there is no scratch exemption. Each outside write record carries `scratch`: `match`, `no-match` or `unavailable` (no scratchpad known). `agent-metrics.py` reports them in one line, `outside the repo during a run: N (session scratchpad: a; approved glob: g; out of scope: o; no scratchpad known: c)`. A path that cannot be resolved fails closed: actor flags, plus `out_of_scope_write` for scoped actors in a run.
  - The `DESIGN_SYSTEM.md` rule is by name, case-insensitive, in any directory (so `apps/web/DESIGN_SYSTEM.md` and `templates/**` are covered). `design-director` is exempt from `md_outside_docs` only for that name. Targets of `approved_scope` matching it are not added to the derived allowed paths, so approving a request never lets the agent write the file.
  - docs root: not a key of `agent-audit.json` (the old `docs_roots` list is gone). Each project declares it once as `- docs root: <path>/` in the `## Workflow` section of the root `CLAUDE.md` (the git root's, never `.claude/CLAUDE.md`), relative to the git root; this repo declares `.claude/docs/`. Without the line the root is `docs/`. The hook reads it per git root (a nested repo uses its own), only from a regular file, and never blocks on it: `.md` files under the root are not `md_outside_docs`, and `<root>backlog/` is written only by `backlog-keeper`. The value is normalized (trimmed, backticks dropped, `\` to `/`, empty and `.` segments dropped, one trailing `/`); an empty, absolute, `..` or control-character value is invalid and the hook falls back to `docs/`, while the skills stop and ask. The match is by prefix: `services/x/docs/` is not a root. `project-docs` (**Docs root**) resolves the same line for skills and agents.
- `agent-metrics.py` - the report: `agent-metrics.py` (last session), `--last N`, `--session <id>`, `--since YYYY-MM-DD [--merge]`, `--run <slug>` (one `/implement` run across sessions). It lists agent calls and durations, actions by category and actor, gates run by `test-runner`, writes checked against scope, the enforcement decisions by category (with the false-positive rule for promoting a category), and every flag with examples. A `## design-director` section appears only when the session has a `design-director` call or event: calls, writes other than to a `DESIGN_SYSTEM.md` (target 0, up to 5 examples) and a reminder to check by hand, in the transcript, calls made without a prior yes from the user (the hook does not see the conversation; target 0).
- `tests/` - the versioned `claude-hooks` suite (stdlib `unittest`, 237 tests, about 4 s; needs Python >= 3.13 and `git`). Run from `~/dotfiles`, always with `-I -B` (isolates from `PYTHON*` and the user site, and creates no `__pycache__`): `python3 -I -B -m unittest discover -s .claude/hooks/tests -t .claude/hooks`. One module: add `-p 'test_<module>.py'`. It is hermetic: `tests/__init__.py` points `AGENT_AUDIT_DIR` at a temp dir (nothing reaches `~/.claude/metrics`) and drops `GIT_*` variables. Mechanism tests use a fixed `TEST_CONFIG`; only `test_config_contract.py` reads the live `agent-audit.json` and `settings.json`, checking floors rather than exact actions, so promoting a `warn` category to `block` does not break it. `tests/_support.py` is the shared toolkit for new tests: `audit` and `metrics` (the loaded hook modules), `TEST_CONFIG` and `config(**overrides)`, `declare_docs_root()` (writes a root `CLAUDE.md` with the `- docs root:` line), `TempRepoCase` (temporary git repo with `write_run()`, `declare()`, `make_scratchpad()`, `eval_at()` and `evaluate()`; `eval_at()` takes `scratchpad=`), `payload()` (hook JSON for `main`, a subagent or a named agent; takes `scratchpad=`), `call_main()` (runs `main()` in process and returns `HookResult(output, records)`), `HookProcess` (runs a copy of the hook as a real process, for the stdin/stdout/exit contract), `read_jsonl()` and the `assert_no_git_root()` environment check. A helper only one module needs stays in that module.


## templates/

Reference docs for how a new project should be structured, one per stack, each a `STRUCTURE.md` with the folder tree plus a "why this shape" section explaining the reasoning (so it can be adapted, not followed blindly). Used by the `new-project` skill; also readable directly.

`project-root` is the monorepo wrapper every new project gets: root-level `CLAUDE.md`/`PRD.md`/`OPEN_QUESTIONS.md`/`CONSTRAINTS.md`/`DEPLOY.md`/`DESIGN_SYSTEM.md`, a root `docker-compose.yml` (services on their `dev` Dockerfile target + infra with healthchecks) with `.env.example` and `gitignore.template`, a `docs/` folder built from `docs-structure/` (`features/<slug>/` with plan, spec and log, plus backlog - what `@planner`, `/implement` and the agents expect), a `services/` folder with one subfolder per service, and `.github/` with one workflow per service.

Templates are a contract between agents and skills: every section has a writer and a reader (the full map is in `agent-workflow.md`, section 11). The root `CLAUDE.md` carries three sections agents read - `Local runtime` (how to validate against the instance the user runs), `Test suites` (which suites `test-runner` runs per task, per run or only on demand) and `Workflow` (the docs layout). There is no `TASKS.md`: work in progress is the features Index and what comes next is the backlog. `OPEN_QUESTIONS.md` holds only project-level decisions.

`ci/` holds the GitHub Actions templates: one workflow per stack (`node.yml` for NestJS/Express/React, `react-native.yml`, `spring-maven.yml`/`spring-gradle.yml`, `go.yml`, `python.yml`, `rust.yml`), the reusable `_docker-image.yml`, and `dependabot.yml`. Each service's workflow runs only when `services/<service>/**` changes: `quality` (lint, typecheck, tests) and `build` in parallel, then `image` (Docker build, published to GHCR on pushes to `main`); mobile runs `quality` only. Every action is pinned by commit SHA and kept current by Dependabot. `ci/README.md` documents placeholders, variants (pnpm/yarn, test database) and what each service must provide.

`new-project` accepts a one-line profile, e.g. `/new-project shop backend=nestjs frontend=react infra=postgres,redis ci=full docs=pt` (services, stacks, infra, `ci=full|check|none`, docs language), asks only for what is missing, and shows the tree for confirmation before writing anything.

Each of the other templates describes the contents of one `services/<name>/` folder, not a repo root by itself: `node-nestjs-api`, `node-express-typeorm-api`, `node-express-prisma-api`, `spring-boot-api` (backend), `node-ts-react` (frontend), `react-native` (mobile), plus the generic `go`, `python`, `rust`.

Structures favor feature-first organization (folders per domain, not per technical layer), a thin wiring-only entrypoint, isolated data access, and validated config that fails fast - consistent with the global CLAUDE.md preference for robustness and long-term maintainability over short-term dev cost.

`onboarding/` holds the `BACKEND.md`/`FRONTEND.md`/`MOBILE.md` skeletons the `onboard` skill fills in when reverse-engineering an existing project - documents current reality, not the prescriptive shape the other templates describe.
