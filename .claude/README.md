# Claude Code global config

## skills/

Personal, explicit-invocation-only skills (`disable-model-invocation: true` - call with `/name`, never auto-triggered). Compose with each other the way `review` calls `codebase-standards`, or `tdd` calls `grill-me` and `scaffold`.

| skill | purpose |
|---|---|
| `scaffold` | Placeholder files with correct types/exports/TODOs |
| `code-simplify` | Remove unnecessary complexity/duplication, preserve behavior |
| `codebase-standards` | Compare recent changes against the codebase's own conventions |
| `grill-me` | Interview the user until a plan/design is fully resolved |
| `review` | Two-phase review: feature correctness, then standards |
| `tdd` | grill-me -> scaffold -> failing tests, then hand off to implement |
| `bug-repro` | Reproduce a bug end-to-end before attempting a fix |
| `docs` | Check/create/update documentation for the current change |
| `pr-description` | Draft a PR description and changelog entry from a diff |
| `dep-audit` | Audit dependencies for outdated/vulnerable packages |
| `design-system` | Apply design tokens, hierarchy, and accessibility when building a layout |
| `new-project` | Scaffold a new project's structure from `templates/` |
| `onboard` | Document folder structure, patterns, and conventions of an existing project per service |

`frontend-design` is not in this folder - it's the official `frontend-design:frontend-design` plugin (auto-invocation follows the plugin's own frontmatter, not the explicit-only convention above). `design-system` calls it for aesthetic direction (palette, type, layout concept) on greenfield UI, then keeps what it produces consistent (tokens, hierarchy, accessibility) afterward.

## templates/

Reference docs for how a new project should be structured, one per stack, each a `STRUCTURE.md` with the folder tree plus a "why this shape" section explaining the reasoning (so it can be adapted, not followed blindly). Used by the `new-project` skill; also readable directly.

`project-root` is the wrapper every new project gets: root-level `CLAUDE.md`/`PRD.md`/`TASKS.md`/`OPEN_QUESTIONS.md`/`CONSTRAINTS.md`/`DEPLOY.md`/`DESIGN_SYSTEM.md`, a `docs/` folder (module specs/plans, reference SQL), and a `services/` folder holding one subfolder per service plus `docker-compose.yml`.

Each of the other templates describes the contents of one `services/<name>/` folder, not a repo root by itself: `node-nestjs-api`, `node-express-typeorm-api`, `node-express-prisma-api`, `spring-boot-api` (backend), `node-ts-react` (frontend), `react-native` (mobile), plus the generic `go`, `python`, `rust`.

Structures favor feature-first organization (folders per domain, not per technical layer), a thin wiring-only entrypoint, isolated data access, and validated config that fails fast - consistent with the global CLAUDE.md preference for robustness and long-term maintainability over short-term dev cost.

`onboarding/` holds the `BACKEND.md`/`FRONTEND.md`/`MOBILE.md` skeletons the `onboard` skill fills in when reverse-engineering an existing project - documents current reality, not the prescriptive shape the other templates describe.
