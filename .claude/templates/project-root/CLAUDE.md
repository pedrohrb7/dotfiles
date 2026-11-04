# CLAUDE.md - <project name>

<!-- Project-wide agent instructions: conventions shared by every service. Service-specific conventions (stack idioms, gotchas) belong in that service's own services/<name>/CLAUDE.md instead - don't duplicate them here, and don't repeat anything already covered by the global ~/.claude/CLAUDE.md. -->

## Overview

<!-- One or two sentences on what this project is. Full detail lives in PRD.md - link it, don't restate it. -->

See `PRD.md` for the full product context.

## Services

| Service | Stack | Path | Conventions |
|---|---|---|---|
| | | `services/<name>/` | `services/<name>/CLAUDE.md` |

## Running locally

From the repo root:

```
cp .env.example .env
docker compose up --build
```

<!-- Add anything beyond that: seed data, first-run migrations. Each service can also run on its own - see its README.md. -->

## CI

One GitHub Actions workflow per service in `.github/workflows/<service>.yml`, triggered only by changes under `services/<service>/`. Each runs lint, typecheck and tests, the production build, and the Docker image build. Pushes to `main` also publish the image to GHCR. Actions are pinned by commit SHA and updated by Dependabot; never replace a SHA with a tag. See `DEPLOY.md`.

## Docs

`docs/` follows the project-docs structure: `plans/` (product side, business rules) and `specs/` (technical side, implementation order), written with `@planner` and executed with `/implement`. Bugs and refactors go to `docs/backlog/`.

## Documentation language

<!-- Applies to prose in this file and every other project doc (PRD.md, TASKS.md, OPEN_QUESTIONS.md, CONSTRAINTS.md, DEPLOY.md, DESIGN_SYSTEM.md, docs/, and each service's own README.md/CLAUDE.md). Code - identifiers, comments, commit messages - is always English regardless of this setting. -->

- Docs: <English | Portuguese>

## Cross-service conventions

<!-- Only things that apply to every service - commit/branch naming, PR expectations, shared lint/format tooling, how services talk to each other (REST/gRPC/events). Stack-specific conventions go in the service's own CLAUDE.md. -->

-

## Testing

<!-- How tests are run across the whole project, if there's a project-wide entrypoint (e.g. a root script that runs every service's suite). Per-service test commands live in that service's own README.md. -->

-

## Reference

`PRD.md` - what and why · `CONSTRAINTS.md` - hard limits · `DESIGN_SYSTEM.md` - UI tokens/conventions · `TASKS.md` - current work · `OPEN_QUESTIONS.md` - unresolved decisions · `DEPLOY.md` - how this ships
