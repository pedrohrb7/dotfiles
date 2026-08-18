# Go - Project Structure

This is the contents of `services/<service-name>/` in the [project-root](../project-root/STRUCTURE.md) wrapper - not a repo root by itself.

```
services/<service-name>/
  Dockerfile
  README.md                    # how to run/test just this service
  CLAUDE.md                    # service-specific agent instructions (stack conventions, gotchas)
  cmd/
    <binary-name>/
      main.go               # wiring only: parse flags/env, build dependencies, start the app
  internal/                 # code private to this module - the compiler enforces this boundary
    <domain>/
      service.go            # business logic
      repository.go         # data access, isolates the DB/client from the rest of the domain
      types.go
  pkg/                      # code intended for import by other modules - only if that's real, not aspirational
  api/                      # proto/openapi definitions, if the service exposes a formal contract
  test/
    e2e/                    # black-box tests against a running binary
  scripts/
  Makefile                  # build/test/lint/run targets - one obvious entrypoint per task
  go.mod
  go.sum
```

## Why this shape

- **`cmd/<binary>/main.go` is wiring only**: if the project ever needs a second binary (a CLI alongside a server, say), it's a new folder under `cmd/`, not a refactor of business logic out of `main.go`.
- **`internal/` by default, `pkg/` only when justified**: Go's compiler refuses external imports of `internal/`, which is the safe default. Move something to `pkg/` only when another module genuinely needs to import it - not preemptively.
- **Domain folders under `internal/`, not a `handlers/`, `services/`, `models/` split**: keeps logic, data access, and types for one domain together, same reasoning as the Node API template's feature-first modules.
- **`Makefile` as the single entrypoint**: `make test`, `make lint`, `make run` stay stable even if the underlying tool (golangci-lint version, test flags) changes.
