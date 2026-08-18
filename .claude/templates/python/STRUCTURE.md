# Python - Project Structure

This is the contents of `services/<service-name>/` in the [project-root](../project-root/STRUCTURE.md) wrapper - not a repo root by itself.

```
services/<service-name>/
  Dockerfile
  README.md                    # how to run/test just this service
  CLAUDE.md                    # service-specific agent instructions (stack conventions, gotchas)
  src/
    <package_name>/
      __init__.py
      main.py               # entrypoint, wiring only
      config.py             # typed settings (e.g. pydantic-settings), validated at startup
      <domain>/
        __init__.py
        service.py           # business logic
        repository.py        # data access, isolates the DB/client
        models.py            # data types/schemas owned by this domain
  tests/
    e2e/                     # black-box tests against the running app/CLI
    conftest.py              # shared fixtures
  pyproject.toml              # dependencies, build system, and tool config (ruff/black/mypy) in one file
```

## Why this shape

- **`src/` layout, not a flat package at the repo root**: forces tests to import the installed package rather than accidentally picking up files from the working directory, which is a common source of "works on my machine" bugs.
- **`config.py` validates at import/startup**: same reasoning as the Node template's `env.ts` - a missing or malformed setting should fail immediately and loudly.
- **Domain folders under `src/<package_name>/`**: same feature-first reasoning as the Node and Go templates - logic, data access, and types for one concern stay together.
- **Everything in `pyproject.toml`**: avoids the historical sprawl of `setup.py`, `setup.cfg`, `requirements.txt`, and separate tool config files each drifting independently.
