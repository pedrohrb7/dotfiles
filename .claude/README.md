# Claude Code global config

## skills/

Personal, explicit-invocation-only skills (`disable-model-invocation: true` - call with `/name`, never auto-triggered). Compose with each other the way `review` calls `codebase-standards`, or `tdd` calls `grill-me` and `scaffold`.

| skill                | purpose                                                                                 |
| -------------------- | --------------------------------------------------------------------------------------- |
| `scaffold`           | Placeholder files with correct types/exports/TODOs                                      |
| `code-simplify`      | Remove unnecessary complexity/duplication, preserve behavior                            |
| `codebase-standards` | Compare recent changes against the codebase's own conventions                           |
| `grill-me`           | Interview the user until a plan/design is fully resolved                                |
| `review`             | Two-phase review: feature correctness, then standards                                   |
| `tdd`                | grill-me -> scaffold -> failing tests, then hand off to implement                       |
| `bug-repro`          | Reproduce a bug end-to-end before attempting a fix                                      |
| `docs`               | Check/create/update documentation for the current change                                |
| `pr-description`     | Draft a PR description and changelog entry from a diff                                  |
| `dep-audit`          | Audit dependencies for outdated/vulnerable packages                                     |
| `design-system`      | Apply design tokens, hierarchy, and accessibility when building a layout                |
| `new-project`        | Scaffold a new project's structure from `templates/`                                    |
| `onboard`            | Document folder structure, patterns, and conventions of an existing project per service |
| `implement`          | Execute an approved spec task by task by orchestrating the agents in `agents/`          |

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

`frontend-design` is not in this folder - it's the official `frontend-design:frontend-design` plugin (auto-invocation follows the plugin's own frontmatter, not the explicit-only convention above). `design-system` calls it for aesthetic direction (palette, type, layout concept) on greenfield UI, then keeps what it produces consistent (tokens, hierarchy, accessibility) afterward.

## agents/

Global subagents, symlinked as `~/.claude/agents -> ~/dotfiles/.claude/agents` (create the link by hand on each machine, like `skills/`). Claude delegates to them automatically when the description matches ("Use proactively when..."), or call one with `@name`.

Each agent pins its own `model` and `effort` to balance quality and token cost:

- `opus` only where a mistake is expensive and runs are rare (reviews, planning).
- `sonnet` for implementation and fixing, the long tool-call loops where most tokens go.
- `haiku` for mechanical work whose value is a short summary, so raw logs never reach the main context.

| agent                 | model  | effort | tools                  | preloaded skills                               | auto-invoked                              |
| --------------------- | ------ | ------ | ---------------------- | ---------------------------------------------- | ----------------------------------------- |
| `code-reviewer`       | opus   | medium | read-only              | -                                              | after significant changes                 |
| `security-reviewer`   | opus   | medium | read-only              | -                                              | only auth, API, input, secrets, deps      |
| `planner`             | opus   | high   | read + write `docs/`   | `project-docs`                                 | no, manual only                           |
| `frontend-react`      | sonnet | medium | all                    | `react-best-practices`, `composition-patterns` | yes                                       |
| `mobile-react-native` | sonnet | medium | all                    | `react-native-skills`, `react-native-core`     | yes                                       |
| `backend-node`        | sonnet | medium | all                    | -                                              | yes                                       |
| `backend-spring`      | sonnet | medium | all                    | -                                              | yes                                       |
| `backend-go`          | sonnet | medium | all                    | -                                              | yes                                       |
| `backend-rust`        | sonnet | medium | all                    | -                                              | yes                                       |
| `backend-python`      | sonnet | medium | all                    | -                                              | yes                                       |
| `test-writer`         | sonnet | medium | all                    | -                                              | when code lands without tests             |
| `quality-fixer`       | sonnet | medium | all                    | `bug-repro`                                    | after `test-runner` reports failures      |
| `test-runner`         | haiku  | low    | Bash, Read, Grep, Glob | -                                              | whenever checks need to run               |

Token-economy rules every agent follows - keep them when adding a new one:

- Model aliases (`opus`/`sonnet`/`haiku`), not full IDs, so agents follow new model versions.
- Preload only small, always-relevant skills: preloaded `SKILL.md` content is paid on every run. Larger or situational skills (`react-view-transitions`, `react-native-expo`, `react-native-performance`, `react-native-testing`, ...) are named in the prompt and loaded on demand.
- Minimal `tools` on read-only agents; no MCP servers unless needed.
- The prompt ends with a fixed, short report format. That report is all that returns to the main context.
- Expensive (`opus`) agents get narrow auto-invocation triggers or are manual only.
- Shell commands go through `rtk` when available.

Scope rule every agent that edits code follows - keep it when adding a new one: fix only the lint, typecheck, test and visual (UI) problems the current change caused, or that the task names. Pre-existing problems found along the way are not fixed; they are logged with the `project-docs` skill (add-entry mode) - failing/flaky tests, type/build errors and visual defects as bugs in `docs/backlog/bugs/`, lint violations and code smells as refactors in `docs/backlog/refactor/`, one entry per root cause, deduplicated against the folder's Index. If the project has no `docs/backlog/`, the agent lists them in its report instead of scaffolding it.

`planner` writes one document per run: plan mode (a feature request -> `docs/plans/`, product side only) or spec mode (a plan path -> `docs/specs/`, technical side, with an **Implementation order** whose tasks name their stack, files, dependencies and done criteria so `/implement` can execute them). Asking for the spec of a `Draft` plan marks the plan `Approved`.

### Feature workflow

1. `@planner write the plan for <feature>` - review `docs/plans/...`, answer its open questions, ask for changes.
2. `@planner write the spec for docs/plans/<file>.md` - review `docs/specs/...`.
3. `/implement docs/specs/<file>.md [tasks 2-4] [--step]` - the main session orchestrates: per task, stack agent -> `test-runner` -> `quality-fixer` (max 2 rounds) -> `test-writer` if tests are missing, marking the task `(done)` in the spec so a run can resume; then one review pass (`code-reviewer`, plus `security-reviewer` for auth/API/input/secrets/deps), fixes, spec **Verification**, and spec status `Implemented`. `--step` pauses after each task.
4. Documentation pass - check `docs/` and READMEs against what shipped, update the plan status, review new `docs/backlog/` entries. Lighter than before, since the agents already update docs per change.

Subagents cannot spawn subagents, so chains like `test-runner` -> `quality-fixer` -> `code-reviewer` are orchestrated by the main session (that is what `/implement` encodes). `planner`'s "only write inside `docs/`" is enforced by its prompt, not by `tools`.

## templates/

Reference docs for how a new project should be structured, one per stack, each a `STRUCTURE.md` with the folder tree plus a "why this shape" section explaining the reasoning (so it can be adapted, not followed blindly). Used by the `new-project` skill; also readable directly.

`project-root` is the monorepo wrapper every new project gets: root-level `CLAUDE.md`/`PRD.md`/`TASKS.md`/`OPEN_QUESTIONS.md`/`CONSTRAINTS.md`/`DEPLOY.md`/`DESIGN_SYSTEM.md`, a root `docker-compose.yml` (services on their `dev` Dockerfile target + infra with healthchecks) with `.env.example` and `gitignore.template`, a `docs/` folder built from `docs-structure/` (plans, specs, backlog - what `@planner`, `/implement` and the agents expect), a `services/` folder with one subfolder per service, and `.github/` with one workflow per service.

`ci/` holds the GitHub Actions templates: one workflow per stack (`node.yml` for NestJS/Express/React, `react-native.yml`, `spring-maven.yml`/`spring-gradle.yml`, `go.yml`, `python.yml`, `rust.yml`), the reusable `_docker-image.yml`, and `dependabot.yml`. Each service's workflow runs only when `services/<service>/**` changes: `quality` (lint, typecheck, tests) and `build` in parallel, then `image` (Docker build, published to GHCR on pushes to `main`); mobile runs `quality` only. Every action is pinned by commit SHA and kept current by Dependabot. `ci/README.md` documents placeholders, variants (pnpm/yarn, test database) and what each service must provide.

`new-project` accepts a one-line profile, e.g. `/new-project shop backend=nestjs frontend=react infra=postgres,redis ci=full docs=pt` (services, stacks, infra, `ci=full|check|none`, docs language), asks only for what is missing, and shows the tree for confirmation before writing anything.

Each of the other templates describes the contents of one `services/<name>/` folder, not a repo root by itself: `node-nestjs-api`, `node-express-typeorm-api`, `node-express-prisma-api`, `spring-boot-api` (backend), `node-ts-react` (frontend), `react-native` (mobile), plus the generic `go`, `python`, `rust`.

Structures favor feature-first organization (folders per domain, not per technical layer), a thin wiring-only entrypoint, isolated data access, and validated config that fails fast - consistent with the global CLAUDE.md preference for robustness and long-term maintainability over short-term dev cost.

`onboarding/` holds the `BACKEND.md`/`FRONTEND.md`/`MOBILE.md` skeletons the `onboard` skill fills in when reverse-engineering an existing project - documents current reality, not the prescriptive shape the other templates describe.
