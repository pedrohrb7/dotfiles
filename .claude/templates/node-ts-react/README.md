# <service name> (Frontend)

<!-- One-line summary of this service. Full product context: see the project root's PRD.md. -->

## Stack

React + TypeScript, <Vite or Next.js>, <state/data-fetching library, if any>

## Prerequisites

- Node <version>
- <npm/pnpm/yarn> <version>

## Setup

```
cp .env.example .env
npm install
```

## Running locally

```
npm run dev
```

Serves at `http://localhost:<port>`. Or from the project root: `cd services && docker-compose up frontend`.

## Testing

```
npm test           # unit/component tests
npm run test:e2e   # Playwright/Cypress - requires the app running
```

## Building

```
npm run build
```

## Environment variables

| Var | Purpose | Required |
|---|---|---|
| | | |

## Folder structure and conventions

See this service's `CLAUDE.md`.
