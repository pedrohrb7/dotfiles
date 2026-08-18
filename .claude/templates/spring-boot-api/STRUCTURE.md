# Spring Boot API - Project Structure

This is the contents of `services/backend/` in the [project-root](../project-root/STRUCTURE.md) wrapper - not a repo root by itself.

```
services/backend/
  Dockerfile
  README.md                    # how to run/test just this service
  CLAUDE.md                    # service-specific agent instructions (stack conventions, gotchas)
  src/
    main/
      java/com/company/project/
        ProjectApplication.java        # @SpringBootApplication entrypoint - wiring only
        config/
          SecurityConfig.java
          OpenApiConfig.java
          properties/
            AppProperties.java           # @ConfigurationProperties, validated with @Validated - fail fast on boot
        common/                         # cross-cutting, app-wide
          exception/
            GlobalExceptionHandler.java   # @RestControllerAdvice: exception -> HTTP response mapping
            ApiException.java
          validation/                     # custom @Constraint annotations shared across modules
        modules/                        # one package per domain/feature, not per technical layer
          <feature>/
            <Feature>Controller.java
            <Feature>Service.java          # orchestrator: calls the repository, composes use cases
            <Feature>Repository.java        # Spring Data JPA interface - the abstraction services depend on
            dto/
              Create<Feature>Request.java
              Update<Feature>Request.java
              <Feature>Response.java
            entity/
              <Feature>.java                 # @Entity - the table shape, not the domain model
            mapper/
              <Feature>Mapper.java            # entity <-> dto translation (MapStruct or hand-written)
            exception/
              <Feature>NotFoundException.java
            validator/                        # business-rule validation beyond bean-validation annotations
      resources/
        application.yml                  # base config; application-{profile}.yml overrides per environment
        db/migration/                    # Flyway (or Liquibase) migrations - append-only once applied
    test/
      java/com/company/project/
        modules/                         # mirrors src/main/java/.../modules/ 1:1, package for package
          <feature>/
            <Feature>ServiceTest.java
            <Feature>ControllerTest.java   # @WebMvcTest - controller layer in isolation
            mapper/
              <Feature>MapperTest.java
        e2e/                              # @SpringBootTest black-box tests against a running context
      resources/
        application-test.yml
  pom.xml (or build.gradle.kts)
```

## Why this shape

- **`src/main` / `src/test` mirror each other package-for-package**: this is Maven/Gradle's own convention, and it's kept strict here on purpose - a test's package tells you exactly what it covers.
- **Package-by-feature under `modules/`, not package-by-layer** (`controller/`, `service/`, `repository/` at the top level): keeps everything for one feature together, the same reasoning as the Node templates - scaling to more features means adding a package, not touching five existing ones.
- **`entity/` is separate from the DTOs**: the JPA `@Entity` describes the table (relationships, cascade rules, audit columns); the request/response DTOs describe the API contract. `mapper/` is the only place that knows about both, so a schema change doesn't leak into the controller layer.
- **`<Feature>Repository.java` is the abstraction services depend on**: Spring Data JPA generates the implementation, but services never touch `EntityManager`/JPQL directly - custom queries live behind a repository method, keeping the persistence mechanism swappable in principle.
- **`db/migration/` (Flyway/Liquibase), not `ddl-auto: update`**: schema changes are explicit, reviewable, and reproducible across environments - relying on Hibernate to infer schema changes in anything beyond local dev is how drift happens.
- **`GlobalExceptionHandler` centralizes error -> HTTP mapping**: feature-specific exceptions (`<Feature>NotFoundException`) stay declarative; only one place decides what HTTP status/body they become.
