# Deploy - <project name>

<!-- How this project actually ships, kept current with the real pipeline - a stale deploy doc is worse than none. If a step changes in CI, update it here in the same change. -->

## Environments

| Environment | URL | Deploys from | Purpose |
|---|---|---|---|
| Local | `docker compose up` (root `docker-compose.yml`) | working tree | Development |
| Staging | | | |
| Production | | | |

## CI and images

Each service has its own workflow in `.github/workflows/<service>.yml`, triggered only by changes under `services/<service>/` (or the workflow itself).

| Job | Runs | When |
|---|---|---|
| `quality` | lint, typecheck, tests | PRs and pushes to `main` |
| `build` | production build | PRs and pushes to `main` |
| `image` | Docker build (reusable `_docker-image.yml`) | after `quality` and `build` pass |
| publish | push to `ghcr.io/<owner>/<repo>-<service>` with tags `sha-<short sha>` and `latest` | pushes to `main` only |

<!-- Mobile apps run `quality` only. Remove rows for services that don't exist. -->

## Deploying a service

<!-- One subsection per service that ships independently. Deployment is not automated by the template: the published image is the hand-off point. Document here how an image tag reaches each environment once that exists. -->

### `services/<name>`

- Image: `ghcr.io/<owner>/<repo>-<name>:sha-<short sha>`
- Trigger:
- Pipeline: `.github/workflows/<name>.yml`
- Steps a human takes, if any beyond "merge to `main`":

## Secrets and config

<!-- Where secrets actually live (vault/secrets manager/GitHub Actions secrets and environments) - never in this file, never committed. How to add a new one for a new service or integration. Local values live in .env (from .env.example). -->

-

## Rollback

<!-- Concrete steps per service. Redeploying the previous `sha-` image tag is a valid answer if that's genuinely how it works - just say so instead of leaving this blank. -->

-

## Monitoring and alerts

<!-- Links to dashboards, log aggregation, alerting/on-call config. -->

-

## Infra

<!-- Hosting provider, what's provisioned where, and where the infra-as-code (if any) lives. -->

-
