# Deploy - <project name>

<!-- How this project actually ships, kept current with the real pipeline - a stale deploy doc is worse than none. If a step changes in CI, update it here in the same change. -->

## Environments

| Environment | URL | Deploys from | Purpose |
|---|---|---|---|
| Local | `services/docker-compose.yml` | - | Development |
| Staging | | | |
| Production | | | |

## Deploying a service

<!-- One subsection per service that ships independently. If every service deploys together, one section is enough - say so. -->

### `services/<name>`

- Trigger:
- Pipeline: <link to the CI config that runs it>
- Steps a human takes, if any beyond "merge to `<branch>`":

## Secrets and config

<!-- Where secrets actually live (vault/secrets manager/CI env vars) - never in this file, never committed. How to add a new one for a new service or integration. -->

-

## Rollback

<!-- Concrete steps per service. "Revert the commit and redeploy" is a valid answer if that's genuinely how it works - just say so instead of leaving this blank. -->

-

## Monitoring and alerts

<!-- Links to dashboards, log aggregation, alerting/on-call config. -->

-

## Infra

<!-- Hosting provider, what's provisioned where, and where the infra-as-code (if any) lives. -->

-
