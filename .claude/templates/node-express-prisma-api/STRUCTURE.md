# Express + Prisma API (TypeScript) - Project Structure

This is the contents of `services/backend/` in the [project-root](../project-root/STRUCTURE.md) wrapper - not a repo root by itself.

```
services/backend/
  Dockerfile
  README.md                    # how to run/test just this service
  CLAUDE.md                    # service-specific agent instructions (stack conventions, gotchas)
  prisma/
    schema.prisma                # single source of truth for the data model - generates the Prisma Client's types
    migrations/                  # Prisma Migrate history - generated, never hand-edit an already-applied one
  src/
    index.ts                    # entrypoint: creates the app, starts the HTTP server
    app.ts                      # express app assembly: global middleware, module routers, error handler - exported for tests without a live port
    config/
      env.ts                     # typed, validated environment config - fail fast on missing/invalid vars
      prisma-client.ts            # single shared PrismaClient instance (never instantiate more than one per process)
    common/                      # cross-cutting, app-wide - the Express equivalent of Nest's guards/interceptors/filters
      middleware/
        auth.middleware.ts
        error-handler.middleware.ts    # central error -> HTTP response mapping (map Prisma errors here too)
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
        enums/
        exceptions/
        mappers/                    # Prisma model <-> dto/domain-model translation
        models/                     # domain interfaces/enums, framework- and ORM-agnostic
        repositories/
          <feature>.repository.ts    # wraps the relevant `prisma.<model>` calls, isolates the generated client from services
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
  .env.example
  package.json
  tsconfig.json
  eslint.config.* / .prettierrc
```

## Why this shape

- **No `entities/` folder**: Prisma generates its model types directly from `schema.prisma`, so there's no hand-written entity class to own. `models/` still exists for the domain shape the service layer reasons about, once it diverges from the generated Prisma type (e.g. combining two models, dropping internal fields).
- **`repositories/<feature>.repository.ts` wraps `prisma.<model>`**: services call the repository, never the Prisma Client directly - swapping an individual feature's persistence, mocking data access in tests, or reacting to a schema change all touch one file.
- **One shared `PrismaClient` in `config/prisma-client.ts`**: Prisma explicitly warns against instantiating multiple clients per process (connection pool exhaustion) - centralizing it makes that impossible to get wrong.
- **`prisma/` lives at the repo root, not under `src/`**: the Prisma CLI expects `schema.prisma` there by default, and migrations are an operational artifact, same reasoning as the TypeORM template's `migrations/`.
- **Everything else matches the NestJS and Express+TypeORM templates' module shape** on purpose: moving a feature between any of these three should feel mechanical.
- **`test/` sibling to `src/`, mirroring its structure exactly**: same reasoning as the other Node templates.
