# NestJS API - Project Structure

This is the contents of `services/backend/` in the [project-root](../project-root/STRUCTURE.md) wrapper - not a repo root by itself.

```
services/backend/
  Dockerfile
  README.md                    # how to run/test just this service
  CLAUDE.md                    # service-specific agent instructions (stack conventions, gotchas)
  src/
    main.ts                     # bootstrap: create the app, apply global pipes/filters, listen
    app.module.ts                # root module: imports ConfigModule + every feature module
    config/
      configuration.ts           # typed config factory (registered via @nestjs/config), validated with a schema (joi/zod) - fail fast on boot
    common/                      # cross-cutting, app-wide - not owned by one feature
      guards/
      interceptors/
      pipes/
      filters/                   # global exception filters (map exceptions -> HTTP responses)
      decorators/
    modules/                     # one folder per domain/feature, not per technical layer
      <feature>/
        <feature>.module.ts       # DI wiring for this module: providers, controllers, imports/exports
        controllers/
          <feature>.controller.ts             # main CRUD-shaped endpoints
          <feature>-management.controller.ts  # split out when one controller would get too large (e.g. admin-only actions)
        dto/
          create-<feature>.dto.ts
          update-<feature>.dto.ts
          <feature>-params.dto.ts   # route/query param shapes, validated separately from the body
          <feature>.dto.ts          # response shape returned to the client
        enums/                     # standalone enums shared across this module
        exceptions/                # domain-specific exceptions, caught by a filter in common/filters or the module
        mappers/                   # entity/model <-> dto translation, kept out of services and controllers
        models/                    # domain interfaces/enums, framework-agnostic - what the service layer actually operates on
        repositories/
          <feature>.repository.ts   # wraps the ORM/DB client, isolates it from services
        services/
          <feature>.service.ts       # orchestrator: composes actions, is what the controller calls
          create/
            create-<feature>.action.ts   # one class, one use case - easy to test and to find
          get/
            find-one-<feature>.action.ts
            find-all-<feature>.action.ts
          update/
            update-<feature>.action.ts
        strategies/                 # interchangeable algorithms behind one interface (e.g. create-<feature>.strategy.ts)
        validators/                 # business-rule validation that doesn't fit a DTO's shape validation
  test/
    modules/                       # mirrors src/modules/ 1:1, folder for folder
      <feature>/
        controllers/
          <feature>.controller.spec.ts
        services/
          create/
            create-<feature>.action.spec.ts
        mappers/
          <feature>.mapper.spec.ts
        repositories/
          <feature>.repository.spec.ts
        validators/
        builders/                   # module-specific test data builders (e.g. <feature>-interface.builder.ts)
    e2e/                            # black-box HTTP tests against a running instance (supertest against the Nest app)
    fixtures/                       # cross-module shared test data
  .env.example
  package.json
  tsconfig.json
  nest-cli.json
  eslint.config.* / .prettierrc
```

## Why this shape

- **`test/` sibling to `src/`, mirroring its structure exactly**: a test's location tells you exactly what it covers without opening it, and moving/renaming a module means a predictable, mechanical move on both sides. Nothing under `test/` is colocated inside `src/modules/`.
- **`services/<feature>.service.ts` orchestrates, `services/<verb>/*.action.ts` execute**: each action is one use case, one class, one reason to change - a controller endpoint maps to exactly one action, so finding "what happens when you create a `<feature>`" means opening one file, not tracing a 300-line service.
- **`mappers/` is its own folder, not inlined in services or controllers**: entity/DTO/domain-model translation is boilerplate-heavy and changes independently of business logic - isolating it keeps `services/` free of shape-conversion noise.
- **`models/` (domain-agnostic) vs `dto/` (HTTP contract) vs `entities` (in the ORM template variant, persistence shape) are three separate concerns**: conflating them means every ORM migration or API contract change ripples into business logic. Here only `mappers/` needs to know about more than one of the three.
- **`repositories/` wraps the ORM/DB client**: services depend on a repository's method signatures, not on TypeORM/Prisma/whatever directly - swapping the data layer touches one file per feature.
- **`strategies/` and `validators/` are separate from `services/`**: an interchangeable algorithm (strategy) or a business rule (validator) is not a use case (action) - keeping them apart avoids one folder becoming a dumping ground for anything vaguely "logic".
- **`common/` holds only what's genuinely app-wide**: a guard/interceptor/pipe/filter used by one module only belongs inside that module, not in `common/` - promote it only when a second module needs it too.
