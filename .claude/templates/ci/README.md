# CI templates (GitHub Actions)

One workflow per service, each triggered only when that service's code (or its own workflow) changes. Used by the `new-project` skill; also readable directly.

## Files

| Template | Used for | Copied to |
|---|---|---|
| `node.yml` | `node-nestjs-api`, `node-express-prisma-api`, `node-express-typeorm-api`, `node-ts-react` | `.github/workflows/<service>.yml` |
| `react-native.yml` | `react-native` | `.github/workflows/<service>.yml` |
| `spring-maven.yml` / `spring-gradle.yml` | `spring-boot-api` (pick by build tool) | `.github/workflows/<service>.yml` |
| `go.yml` | `go` | `.github/workflows/<service>.yml` |
| `python.yml` | `python` | `.github/workflows/<service>.yml` |
| `rust.yml` | `rust` | `.github/workflows/<service>.yml` |
| `_docker-image.yml` | reusable image build/publish, shared by every containerized service | `.github/workflows/_docker-image.yml` (as-is) |
| `dependabot.yml` | action and dependency updates | `.github/dependabot.yml` |

Replace every `__SERVICE__` with the service's folder name under `services/` (e.g. `backend`, `frontend`, `worker`). It is the workflow name, the path filter, the working directory and the image suffix (`ghcr.io/<owner>/<repo>-<service>`).

## Pipeline

| Job | What it runs | When |
|---|---|---|
| `quality` | lint, typecheck, tests | every PR and push to `main` touching the service |
| `build` | the production build | same, in parallel with `quality` |
| `image` | Docker image build via `_docker-image.yml`, with GitHub Actions cache | after `quality` and `build` pass |
| `image` (publish) | push to GHCR, tags `sha-<short sha>` and `latest` | only on push to `main` |

`react-native.yml` has only `quality`: the app is not built or containerized in CI.

CI levels chosen in `new-project`:
- `ci=full`: all jobs (the default).
- `ci=check`: delete the `image` job (and don't copy `_docker-image.yml` unless another service uses it).
- `ci=none`: no workflows and no `dependabot.yml`.

Deploy is out of scope. The published image is the hand-off point; document the deploy step in the project's `DEPLOY.md` when it exists.

## What each service must provide

The workflows call standard entrypoints, so the service scaffold must define them:

| Stack | Required |
|---|---|
| Node / React / React Native | `.nvmrc`, `package-lock.json`, scripts `lint`, `typecheck` (`tsc --noEmit`), `test` (non-watch), `build` (not for React Native) |
| Spring (Maven) | `mvnw` wrapper, `.java-version`, lint plugins bound to `verify` |
| Spring (Gradle) | `gradlew` wrapper, `.java-version`, lint tasks wired into `check` |
| Go | `go.mod`, `go.sum`, `.golangci.yml`; Makefile targets running the same commands |
| Python | `uv.lock`, `.python-version`, `ruff` and `mypy` configured in `pyproject.toml`, `pytest` |
| Rust | `Cargo.lock` committed, optional `rust-toolchain.toml` |
| Every containerized service | a `Dockerfile` whose final stage is the production runtime |

## Variants

- **pnpm**: before `setup-node`, add `pnpm/action-setup@73e46992e05b19abd31f2f3c20e0e7370d762115 # v6.1.1` (it reads `packageManager` from `package.json`). Set `cache: pnpm` and `cache-dependency-path: services/<service>/pnpm-lock.yaml`, replace `npm ci` with `pnpm install --frozen-lockfile`, and `npm run`/`npm test` with `pnpm run`/`pnpm test`.
- **yarn (berry)**: `cache: yarn`, lockfile `yarn.lock`, `corepack enable` as the first run step, `yarn install --immutable`, `yarn <script>`.
- **Database in tests**: uncomment the `infra:postgres` block in `quality` (backend workflows) and match the env var name the service reads. Spring with Testcontainers needs nothing extra.

## Rules

- **Pinned by full commit SHA**, with the version in a trailing comment. Dependabot (`github-actions` ecosystem) bumps the SHA and the comment together. Never replace a SHA with a tag. When adding a new action, resolve its SHA from the release tag: `git ls-remote https://github.com/<owner>/<repo> refs/tags/<tag>^{}`, falling back to `refs/tags/<tag>` for lightweight tags.
- **Least privilege**: `contents: read` at the workflow level. Only the `image` job gets `packages: write`, and `persist-credentials: false` on every checkout.
- **No untrusted input in `run:`**: pass `${{ }}` values through `env:`, as `_docker-image.yml` does.
- **`concurrency`** cancels superseded runs on PRs only, never on `main`.
- The path filter always lists the service folder, its own workflow file and, for containerized services, `_docker-image.yml`. A change to shared CI re-runs every service that uses it.
