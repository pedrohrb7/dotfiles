# Rust - Project Structure

This is the contents of `services/<service-name>/` in the [project-root](../project-root/STRUCTURE.md) wrapper - not a repo root by itself.

```
services/<service-name>/
  Dockerfile
  README.md                    # how to run/test just this service
  CLAUDE.md                    # service-specific agent instructions (stack conventions, gotchas)
  src/
    main.rs                  # binary entrypoint, wiring only (omit if this is a pure library)
    lib.rs                   # public API surface, if this crate is also used as a library
    <domain>/
      mod.rs
      service.rs              # business logic
      repository.rs           # data access, isolates the DB/client
      types.rs
  tests/                      # integration tests - black-box, exercise only the public API
  benches/                    # criterion benchmarks, only if performance is an actual requirement
  examples/                   # runnable examples of the public API, doubles as documentation
  Cargo.toml
  Cargo.lock
```

## Why this shape

- **`tests/` only calls the public API**: integration tests that reach into private modules couple the tests to implementation details; unit tests for internals belong in `#[cfg(test)]` modules next to the code they cover.
- **`lib.rs` + `main.rs` split**: even a single-binary project benefits from a thin binary crate over a library crate, since it makes the core logic reusable (by `tests/`, `examples/`, or a future second binary) without depending on the binary.
- **`benches/` and `examples/` are opt-in, not scaffolded empty**: only add them when there's a real performance budget to protect or a public API worth demonstrating - empty stub folders just add noise.
