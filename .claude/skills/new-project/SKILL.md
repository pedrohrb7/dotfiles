---
name: new-project
description: Scaffold a new monorepo project from the templates - root docs, docs/ tree, services/ per stack, root docker-compose, and per-service GitHub Actions. Accepts a one-line profile (services, stacks, infra, CI level, docs language) or asks for what is missing. Use when user says "new project", "scaffold a project", or "set up a new repo".
argument-hint: <name> backend=<stack> frontend=<stack> [mobile=react-native] [infra=postgres,redis|none] [ci=full|check|none] [docs=pt|en]
---

# New Project

Builds the monorepo described in `~/.claude/templates/project-root/STRUCTURE.md`. Read that file first; it is the source of truth for the layout and the Dockerfile contract.

Arguments: `$ARGUMENTS`

## 1. Resolve the profile

Parse the arguments into the profile below. For each field that is missing, ask in **one** `AskUserQuestion` call (up to 4 questions; group the rest in a second call only if needed). Never guess a stack.

| Field | Values | Default |
|---|---|---|
| name | kebab-case project name | ask |
| services | one or more `<folder>=<stack>`. The usual folders are `backend`, `frontend` and `mobile`; others are allowed (`worker=go`, `admin=react`). | ask |
| stacks | `nestjs`, `express-prisma`, `express-typeorm`, `spring` (+ `maven`/`gradle`), `go`, `python`, `rust`, `react` (+ `vite`/`next`), `react-native` (+ `expo`/`bare`) | ask |
| infra | any of `postgres`, `mysql`, `redis`, or `none` | ask |
| ci | `full` (quality + build + image + publish to GHCR on main), `check` (quality + build), `none` | `full` |
| package manager | Node only: `npm`, `pnpm`, `yarn` | `npm` |
| docs | `pt` or `en`: prose only; code, identifiers, comments and commits are always English | ask |

Stack to template: `nestjs` -> `node-nestjs-api`, `express-prisma` -> `node-express-prisma-api`, `express-typeorm` -> `node-express-typeorm-api`, `spring` -> `spring-boot-api`, `react` -> `node-ts-react`, `react-native` -> `react-native`, and `go`/`python`/`rust` -> the template of the same name.

## 2. Preflight

1. If the target is inside an existing git repo, check the branch and its status against the remote, and ask the user to confirm it is the right, up-to-date branch. Skip this step if there is no repo yet.
2. If the target directory is not empty, list what is there and ask before writing. Never overwrite an existing file. Skip it and report it.
3. Show the final tree (root files, `docs/`, `services/<folder>/` per service, and `.github/workflows/` per service) plus the profile, as a short table. Wait for confirmation.

## 3. Root

From `~/.claude/templates/project-root/`:

1. **Root docs.** Copy `CLAUDE.md`, `PRD.md`, `CONSTRAINTS.md`, `OPEN_QUESTIONS.md`, `DEPLOY.md` and `DESIGN_SYSTEM.md` as-is. They are filled-in skeletons, not stubs to rewrite.
   - Record the docs language in `CLAUDE.md`'s "Documentation language" section, and write all prose in it.
   - Fill the `CLAUDE.md` Services table. Keep `- docs layout: features` in its `Workflow` section.
   - Fill `CLAUDE.md`'s `Local runtime` and `Test suites` sections after the services exist (step 5), as described in step 7.
   - Fill `PRD.md` and `CONSTRAINTS.md` from what the user described. `OPEN_QUESTIONS.md` gets only project-level open decisions (architecture, product direction); feature questions wait for that feature's plan.
   - In `DEPLOY.md`, fill the CI table and one subsection per service; keep only the rows for the CI level chosen.
   - Leave the `DESIGN_SYSTEM.md` tables blank for the `design-system` skill. Drop it if there is no UI service.
2. **`docker-compose.yml`.**
   - Replace `__PROJECT__`.
   - Keep one block per containerized service (named after its folder, with that stack's dev port and command) and only the infra chosen.
   - Bind mounts and the anonymous `node_modules` volume apply to Node services only.
   - `depends_on` uses `condition: service_healthy` for infra.
   - Mobile apps are not in compose.
3. **`.env.example`.** Keep only the variables the chosen services and infra use, and add every variable the services read. Use safe local values only.
4. **`.gitignore`.** Copy from `gitignore.template`, keeping the shared section plus the sections for the stacks in use.

## 4. Docs

Run the **project-docs** skill in scaffold mode at `docs/`. Copy `requests/` only if a backend exposes an API.

## 5. Services

For each service, read `~/.claude/templates/<stack>/STRUCTURE.md` and create it under `services/<folder>/`.

- **Docs.** Where the stack template has `README.md`/`CLAUDE.md` skeletons, copy them and fill in the stack, prerequisites and env var sections. Otherwise, draft them in the same shape:
  - `README.md`: stack, prerequisites, setup, run, test, build, env vars;
  - `CLAUDE.md`: conventions, testing, gotchas, reference.

  Write the prose in the docs language.
- **Minimal real files.** Create the manifest, config, entry point, one health or example endpoint/screen, and one passing example test. Never empty placeholders: everything created must build, lint, typecheck and pass its tests.
- **CI entrypoints.** Provide what `~/.claude/templates/ci/README.md` ("What each service must provide") requires for the stack:
  - Node: `.nvmrc`, plus `lint`, `typecheck`, `test` and `build` scripts.
  - Spring: wrapper and `.java-version`.
  - Go: `.golangci.yml` and Makefile targets.
  - Python: `.python-version`, plus ruff, mypy and pytest config.
  - Rust: `Cargo.lock`.
- **Dockerfile** for every service except mobile, following the contract in `STRUCTURE.md`:
  - multi-stage, with a `dev` target for compose and the production runtime as the final stage;
  - non-root user, `EXPOSE`, and a `HEALTHCHECK` where possible;
  - plus a `.dockerignore`.
- Code is always English.

## 6. CI (skip if `ci=none`)

From `~/.claude/templates/ci/` (read its `README.md` first):

1. **One workflow per service.** Copy the stack's workflow to `.github/workflows/<folder>.yml` and replace every `__SERVICE__` with the folder name:
   - `node.yml` for NestJS, Express and React;
   - `react-native.yml` for React Native;
   - `spring-maven.yml` or `spring-gradle.yml` for Spring;
   - `go.yml`, `python.yml` or `rust.yml`.
2. **Package manager.** If it is pnpm or yarn, apply the variant from the CI README.
3. **Test database.** If a backend has `postgres` infra and integration tests, uncomment its `infra:postgres` block and match the env var name.
4. **`ci=full`.** Copy `_docker-image.yml` as-is.
5. **`ci=check`.** Delete the `image` job from every workflow, and don't copy `_docker-image.yml`.
6. **Dependabot.** Copy `dependabot.yml` and add one block per service (ecosystem plus `/services/<folder>`). Add a `docker` block per containerized service. Delete the commented examples.
7. **Pins.** Never change a pinned SHA to a tag. If you add an action, pin it by SHA as the CI README explains.

## 7. Agent contract sections

Fill the two sections of the root `CLAUDE.md` that agents read, from what steps 3 and 5 actually created:

- **`Local runtime`**: `mode: compose`. One line per containerized service: its health path (the health endpoint created in step 5) and `reload: auto` only when its compose block bind-mounts the source and runs a watch/hot-reload command (the Node services); every other service gets `reload: manual`, because the running container does not see code changes. Add the `auth` line only if a service has authentication with a seed user; never put a real credential there. Mobile apps are not listed.
- **`Test suites`**: one row per suite that really exists after step 5 (the lint/typecheck command as type `static` and the example test as `unit`, both with gate `task`; e2e or load suites only if they were created, with gate `full` or `on-demand`). Use the exact commands the CI workflows run.

## 8. Finish

- Do not run `git init`, install dependencies, generate lockfiles or commit. List those as next steps, in order:
  1. `git init`;
  2. install per service (this generates the lockfiles CI needs: `package-lock.json`, `uv.lock`, `Cargo.lock`, `go.sum`, the Maven/Gradle wrappers);
  3. `cp .env.example .env`;
  4. `docker compose up --build`;
  5. first commit, and push to GitHub;
  6. in the repo settings, allow Actions to create packages if the org restricts it.
- Report:
  - the profile used;
  - the tree created;
  - files skipped because they already existed;
  - anything from the templates that didn't apply.
