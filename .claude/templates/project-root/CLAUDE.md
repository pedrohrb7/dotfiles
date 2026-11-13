# CLAUDE.md - <project name>

<!-- Project-wide agent instructions: conventions shared by every service. Service-specific conventions (stack idioms, gotchas) belong in that service's own services/<name>/CLAUDE.md instead - don't duplicate them here, and don't repeat anything already covered by the global ~/.claude/CLAUDE.md. The `Local runtime`, `Test suites` and `Workflow` sections are read by agents: keep their shape. -->

## Overview

<!-- One or two sentences on what this project is. Full detail lives in PRD.md - link it, don't restate it. -->

See `PRD.md` for the full product context.

## Services

| Service | Stack | Path | Conventions |
|---|---|---|---|
| | | `services/<name>/` | `services/<name>/CLAUDE.md` |

## Local runtime

To run everything, from the repo root:

```
cp .env.example .env
docker compose up --build
```

<!-- Add anything beyond that: seed data, first-run migrations. Each service can also run on its own - see its README.md. -->

<!-- Agents read the list below to validate changes against the instance you run. They never start, stop, restart or build anything here: they send one request and read that request's log lines. In `compose` mode, service names, state and ports come from `docker compose ps`, so list only what cannot be inferred.
  - mode: `compose` (default), `docker` (containers started with docker run: list each container name) or `cli` (processes in a terminal: give url, health and an optional log file per service).
  - reload: `auto` only when the running service picks up code changes by itself (bind mount + watch/hot reload). Without it, agents treat the instance as stale and ask you to restart it.
  - auth: how to get a dev token with a seed user. Never a real credential. -->

- mode: compose
- <service>: health `<path>` | reload: <auto | manual>
- auth: <e.g. POST /auth/login with seed user `dev@local` (password in `.env` -> DEV_PASSWORD)>

## Test suites

<!-- Read by test-runner, the only agent that runs whole suites. Gate: `task` = runs in the gate of every task that touches the service; `full` = runs once, in the final gate of a run; `on-demand` = only when asked, or when a spec's Verification names it (load, long e2e). Type: unit, integration, e2e, contract, load, static (lint/typecheck). -->

| Suite | Service | Type | Command | Gate |
|---|---|---|---|---|
| | | | | |

## CI

One GitHub Actions workflow per service in `.github/workflows/<service>.yml`, triggered only by changes under `services/<service>/`. Each runs lint, typecheck and tests, the production build, and the Docker image build. Pushes to `main` also publish the image to GHCR. Actions are pinned by commit SHA and updated by Dependabot; never replace a SHA with a tag. See `DEPLOY.md`.

## Workflow

- docs layout: features
<!-- Add "- docs root: <path>/" only when the docs tree is not at docs/ (project-docs, Layouts and path resolution). -->

`docs/` follows the project-docs structure. Each feature has a folder `docs/features/<slug>/` with `plan.md` (product side, business rules), `spec.md` (technical side, structured tasks) and `log.md` (implementation log, written by `/implement`). Plans are written by `planner`, specs by `specker`, and both are executed with `/implement`. Bugs and refactors go to `docs/backlog/`, written only by `backlog-keeper`.

## Documentation language

<!-- Applies to prose in this file and every other project doc (PRD.md, OPEN_QUESTIONS.md, CONSTRAINTS.md, DEPLOY.md, DESIGN_SYSTEM.md, docs/, and each service's own README.md/CLAUDE.md). Code - identifiers, comments, commit messages - is always English regardless of this setting. -->

- Docs: <English | Portuguese>

## Cross-service conventions

<!-- Only things that apply to every service - commit/branch naming, PR expectations, shared lint/format tooling, how services talk to each other (REST/gRPC/events). Stack-specific conventions go in the service's own CLAUDE.md. -->

-

## Reference

`PRD.md` - what and why · `CONSTRAINTS.md` - hard limits · `DESIGN_SYSTEM.md` - UI tokens/conventions · `OPEN_QUESTIONS.md` - unresolved project-level decisions · `DEPLOY.md` - how this ships · `docs/features/README.md` - features and their status
