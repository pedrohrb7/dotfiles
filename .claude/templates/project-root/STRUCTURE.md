# Project Root - Wrapper Structure

Every new project gets this wrapper, regardless of size - a single-API project still gets `services/backend/` rather than putting the API at the repo root. This keeps the shape stable as a project grows from one service to several: adding a service is adding a sibling folder, never a restructure.

The stack-specific templates (`node-nestjs-api`, `node-express-typeorm-api`, `node-express-prisma-api`, `spring-boot-api`, `node-ts-react`, `react-native`, `go`, `python`, `rust`) each describe the contents of **one folder under `services/`** - not a repo root by themselves. Their own `README.md`/`CLAUDE.md`/`Dockerfile` stay scoped to that one service.

```
project-name/
  CLAUDE.md                  # project-wide agent instructions: conventions shared by every service. Points to each service's own CLAUDE.md for stack-specific detail, doesn't repeat it (filled-in skeleton: see CLAUDE.md in this template folder)
  PRD.md                     # product requirements: problem, target user, scope, success criteria - the why behind the project (filled-in skeleton: see PRD.md in this template folder)
  TASKS.md                   # current/planned work, broken into concrete tasks, checked off as they land (filled-in skeleton: see TASKS.md in this template folder)
  OPEN_QUESTIONS.md          # unresolved decisions blocking work - one entry per question, with owner and status (filled-in skeleton: see OPEN_QUESTIONS.md in this template folder)
  CONSTRAINTS.md             # hard constraints (business, technical, compliance) that bound the solution space (filled-in skeleton: see CONSTRAINTS.md in this template folder)
  DEPLOY.md                  # how the project is deployed/released, per environment (filled-in skeleton: see DEPLOY.md in this template folder)
  DESIGN_SYSTEM.md           # design tokens (spacing/type/color scales, breakpoints) and component conventions shared by every UI service (filled-in skeleton: see DESIGN_SYSTEM.md in this template folder)
  docs/
    modules/
      <module>/
        spec.md               # what this module does and why
        plan.md               # how it's being/was built, in phases
    sql/                      # reference schema, seed scripts, ad-hoc queries - not the source of truth for schema changes
  services/
    docker-compose.yml        # orchestrates every service's container, plus local infra (db, cache, ...), for local dev
    backend/                   # one of the API stack templates - see its own STRUCTURE.md for what's inside
      Dockerfile
      README.md                # how to run/test just this service
      CLAUDE.md                 # service-specific agent instructions (stack conventions, gotchas)
      ...
    frontend/                  # node-ts-react or react-native structure - see its own STRUCTURE.md
      Dockerfile
      README.md
      CLAUDE.md
      ...
```

## Why this shape

- **Root `.md` files are project-wide and living, not duplicated per service**: `TASKS.md`/`OPEN_QUESTIONS.md`/`CONSTRAINTS.md` describe the project as a whole and change independently of any one service's code, so they don't belong inside `services/backend/` or `services/frontend/`.
- **Each service still keeps its own `README.md` and `CLAUDE.md`**: the root docs answer "what is this project and why"; a service's own docs answer "how do I run and work on just this piece" - a contributor working only on the frontend shouldn't need to read the whole project's docs to get started.
- **`PRD.md` is one product-level doc, `docs/modules/<module>/spec.md` is many module-level ones**: the PRD answers what's being built and why at the product scope; a module spec answers how one module implements a slice of that. Neither substitutes for the other - the PRD doesn't grow module-by-module, and module specs don't restate product-level rationale.
- **`docs/modules/<module>/` holds a spec + plan pair per module**: mirrors how the code itself is organized feature-first, and keeps each doc small enough to actually stay current.
- **`docs/sql/` is reference-only**: schema dumps, seed scripts, and ad-hoc queries useful for debugging live here, but the source of truth for schema changes is each service's own migrations (e.g. `services/backend/migrations/`, Flyway's `db/migration/`) - `docs/sql/` never contains versioned migrations.
- **`docker-compose.yml` lives under `services/`, one level below root**: it orchestrates services and infra containers only, not project meta docs, so it sits next to the things it actually starts.
- **`DESIGN_SYSTEM.md` lives at the root, not inside `services/frontend/`**: tokens and component conventions are meant to be shared across every UI-facing service (web frontend, mobile) - putting it under one service would make the other silently drift. The `design-system` skill reads and updates this file directly.
