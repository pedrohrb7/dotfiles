# Project Root - Monorepo Structure

Every new project gets this monorepo wrapper, regardless of size. A single-API project still gets `services/backend/` rather than putting the API at the repo root. This keeps the shape stable as a project grows from one service to several: adding a service is adding a sibling folder (plus its workflow), never a restructure.

The stack-specific templates (`node-nestjs-api`, `node-express-typeorm-api`, `node-express-prisma-api`, `spring-boot-api`, `node-ts-react`, `react-native`, `go`, `python`, `rust`) each describe the contents of **one folder under `services/`**, not a repo root by themselves. Their own `README.md`/`CLAUDE.md`/`Dockerfile` stay scoped to that one service. CI workflows come from `../ci/`.

```
project-name/
  CLAUDE.md                  # project-wide agent instructions: conventions shared by every service. Points to each service's own CLAUDE.md for stack-specific detail, doesn't repeat it (filled-in skeleton in this folder)
  PRD.md                     # product requirements: problem, target user, scope, success criteria - the why behind the project (filled-in skeleton)
  CONSTRAINTS.md             # hard constraints (business, technical, compliance) that bound the solution space (filled-in skeleton)
  OPEN_QUESTIONS.md          # unresolved project-level decisions (architecture, product direction) - one entry per question, with owner and status; feature questions live in the feature's plan/spec (filled-in skeleton)
  DEPLOY.md                  # how the project is built, published and deployed, per environment (filled-in skeleton)
  DESIGN_SYSTEM.md           # design tokens and component conventions shared by every UI service (filled-in skeleton)
  docker-compose.yml         # local dev: every service (dev target, hot reload) + infra (db, cache) with healthchecks (template in this folder)
  .env.example               # every variable docker-compose and the services read locally, with safe local values (template in this folder)
  .gitignore                 # shared section + one section per stack in use (from gitignore.template in this folder)
  .github/
    workflows/
      _docker-image.yml      # reusable: build the image, publish to GHCR on main (from ../ci/)
      backend.yml            # one workflow per service, path-filtered to services/<service>/** (from ../ci/<stack>.yml)
      frontend.yml
    dependabot.yml           # updates SHA-pinned actions, dependencies and base images (from ../ci/)
  docs/                      # the project-docs tree (from ../docs-structure/, scaffolded by the project-docs skill)
    features/
      README.md              # Index: every feature with its plan and spec status
      _template/             # plan.md, spec.md, log.md skeletons
      <slug>/                # one folder per feature: plan.md (product, business rules), spec.md (technical, structured tasks), log.md (implementation log, written by /implement)
    backlog/
      bugs/
      refactor/
    quality/                 # dated quality snapshots
    concepts/
    requests/                # API projects only: request collections
  services/
    backend/                 # one of the API stack templates - see its own STRUCTURE.md
      Dockerfile             # multi-stage: `dev` target for compose, final stage = production runtime built by CI
      .dockerignore
      README.md              # how to run/test just this service
      CLAUDE.md              # service-specific agent instructions (stack conventions, gotchas)
      ...
    frontend/                # node-ts-react structure - see its own STRUCTURE.md
      Dockerfile
      .dockerignore
      README.md
      CLAUDE.md
      ...
    mobile/                  # optional: react-native structure - no Dockerfile, CI runs only lint/typecheck/tests
```

## Dockerfiles

Every containerized service follows the same contract, so `docker-compose.yml` and `_docker-image.yml` work for any stack:

- **Multi-stage.** A `dev` stage with dev dependencies and the stack's watch/hot-reload command. Compose targets it and bind-mounts the source. A final, unnamed-by-compose production stage is what CI builds and publishes: minimal base image, production dependencies only, non-root user, `EXPOSE` of the service port, and a `HEALTHCHECK` when the image has a way to run one.
- **Build context is the service folder.** Nothing outside `services/<service>/` is copied, so a service builds the same in compose, in CI and on its own.
- **`.dockerignore` per service** excludes dependencies, build output, `.env*` and tests that aren't needed in the image.

## Why this shape

- **Root `.md` files are project-wide and living, not duplicated per service.** `OPEN_QUESTIONS.md`/`CONSTRAINTS.md` describe the project as a whole and change independently of any one service's code, so they don't belong inside a service.
- **Each service still keeps its own `README.md` and `CLAUDE.md`.** The root docs answer "what is this project and why"; a service's docs answer "how do I run and work on just this piece". A contributor working only on the frontend shouldn't need to read the whole project's docs to get started.
- **`docs/` is the project-docs tree, not a free-form folder.** Each feature has one folder with its plan (what and the business rules), spec (how, with structured tasks) and implementation log, each with a status, so everything about a feature is found in one place. That is what `planner` (plan) and `specker` (spec) write and `/implement` executes; out-of-scope bugs and refactors the agents report are logged once into `docs/backlog/` by `backlog-keeper`, its single writer. `PRD.md` stays the single product-level document; plans are per feature and link back to it. There is no `TASKS.md`: work in progress is the features Index, and what comes next is the backlog.
- **The root `CLAUDE.md` is also a contract with the agents.** Its `Local runtime` section tells them how to validate against the instance you run (they never start or restart it), `Test suites` tells `test-runner` which suites gate a task, a run, or only run on demand, and `Workflow` declares the docs layout.
- **No `docs/sql/`.** The source of truth for schema is each service's migrations. Seeds and reference queries live next to them, inside the service that owns the database.
- **`docker-compose.yml` at the root.** `docker compose up` from the repo root is the one command to run everything locally, and it is the first thing a new contributor looks for. It is for local development only; production images come from CI.
- **One workflow per service, path-filtered.** A change in `services/frontend/` never runs the backend pipeline, and the reverse. A failing service doesn't block the others, CI time stays proportional to what changed, and adding a service is adding one workflow file. The shared image job is a reusable workflow, so there is one place to change how images are built and published.
- **Actions pinned by commit SHA, updated by Dependabot.** A tag can be moved to malicious code; a SHA cannot. Dependabot keeps the pins current, so the safety doesn't cost staleness.
- **`DESIGN_SYSTEM.md` lives at the root, not inside `services/frontend/`.** Tokens and component conventions are shared across every UI-facing service (web and mobile); putting it under one service would make the others silently drift. The `design-system` skill reads and updates this file directly.
