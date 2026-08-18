# Express + TypeORM API (TypeScript) - Project Structure

This is the contents of `services/backend/` in the [project-root](../project-root/STRUCTURE.md) wrapper - not a repo root by itself.

```
services/backend/
  Dockerfile
  README.md                    # how to run/test just this service
  CLAUDE.md                    # service-specific agent instructions (stack conventions, gotchas)
  src/
    index.ts                    # entrypoint: creates the app, starts the HTTP server
    app.ts                      # express app assembly: global middleware, module routers, error handler - exported for tests without a live port
    config/
      env.ts                     # typed, validated environment config - fail fast on missing/invalid vars
      data-source.ts              # TypeORM DataSource: connection options + entity/migration globs
    common/                      # cross-cutting, app-wide - the Express equivalent of Nest's guards/interceptors/filters
      middleware/
        auth.middleware.ts
        error-handler.middleware.ts    # central error -> HTTP response mapping
        logging.middleware.ts
      lib/                        # framework-agnostic utilities shared across modules
    modules/                     # one folder per domain/feature, not per technical layer
      <feature>/
        <feature>.routes.ts       # composition root for this module: builds the repository -> services/actions -> controller chain and wires the router
        controllers/
          <feature>.controller.ts
        dto/
          create-<feature>.dto.ts
          update-<feature>.dto.ts
          <feature>-params.dto.ts
          <feature>.dto.ts         # response shape returned to the client
        entities/
          <feature>.entity.ts       # TypeORM entity - the table shape, not the domain model
        enums/
        exceptions/
        mappers/                    # entity <-> dto/domain-model translation
        models/                     # domain interfaces/enums, framework- and ORM-agnostic
        repositories/
          <feature>.repository.ts    # wraps the TypeORM Repository<Entity>, isolates ORM calls from services
        services/
          <feature>.service.ts        # orchestrator, calls actions
          create/
            create-<feature>.action.ts
          get/
            find-one-<feature>.action.ts
            find-all-<feature>.action.ts
          update/
            update-<feature>.action.ts
        strategies/
        validators/
  test/
    modules/                      # mirrors src/modules/ 1:1, folder for folder
      <feature>/
        controllers/
        services/
          create/
            create-<feature>.action.spec.ts
        mappers/
        repositories/
        validators/
        builders/                  # module-specific test data builders
    e2e/                           # black-box HTTP tests (supertest) against a running instance
    fixtures/                      # cross-module shared test data
  migrations/                      # TypeORM migrations, generated - never hand-edit an already-run one
  .env.example
  package.json
  tsconfig.json
  eslint.config.* / .prettierrc
```

## Why this shape

- **`<feature>.routes.ts` is the manual composition root**: there's no DI container, so each module explicitly builds its own dependency chain (repository -> action -> service -> controller) in one place. That file is the single spot to look at to understand a module's wiring - it should contain construction and route registration only, never logic.
- **`entities/` is separate from `models/`**: the TypeORM entity describes the table; `models/` describes what the service layer actually reasons about. They usually look similar but diverge over time (soft-delete columns, join tables, audit fields belong on the entity, not the domain model) - `mappers/` is what bridges them.
- **Everything else matches the NestJS template's module shape** (`controllers/`, `dto/`, `mappers/`, `services/<verb>/*.action.ts`, `repositories/`, `strategies/`, `validators/`) intentionally: moving a feature between an Express and a Nest service, or between two Express services, should feel mechanical, not like a rewrite.
- **`test/` sibling to `src/`, mirroring its structure exactly**: same reasoning as the NestJS template - a test's location tells you what it covers, and nothing lives colocated inside `src/modules/`.
- **`migrations/` at the repo root, not under `src/`**: migrations are an operational artifact run by the TypeORM CLI outside the app's runtime, and are treated as append-only history once applied.
