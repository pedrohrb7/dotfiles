---
name: onboard
description: Build a structural and design-pattern understanding of an existing, already-running project - one doc per service (backend/frontend/mobile) plus root CLAUDE.md pointers. Use when starting on an unfamiliar existing codebase, or the user says "understand this project", "onboard me", or "map this codebase".
disable-model-invocation: true
---

# Onboard

This documents current reality - it does not change any code.

1. Check the current git branch and its status against the remote. Ask the user to confirm: is this the branch that should be onboarded, and is it up to date? Don't proceed on a stale or wrong branch - wait for confirmation (or a pull/checkout) before exploring any code.
2. Detect which service folders actually exist at the project root: `backend/`, `frontend/`, `mobile/` (or `services/backend`, `services/frontend`, `services/mobile` if the project follows that layout). Ask the user which of the detected services to onboard - one, several, or all - rather than assuming all of them.
3. Check the root `CLAUDE.md` for a "Documentation language" setting. If it names one, write the generated docs' prose in that language. If there's no such setting (or no `CLAUDE.md` yet), ask the user - English or Portuguese - and record the answer under a "Documentation language" section when creating/updating `CLAUDE.md` in step 6. This applies to prose only; quoted code/identifiers stay as written in the source.
4. For each service to onboard, explore the real code (don't assume a template's shape applies) and determine:
   - Stack: language, framework, key libraries, data store(s).
   - Folder structure: the actual tree, annotated with what each top-level folder is really used for.
   - Design patterns in use: module/layer organization, data access, error handling, DI/wiring (backend); component organization, routing, state management, data fetching (frontend); component organization, navigation, state management, native modules (mobile); testing setup and location for all three.
   - Conventions: naming, file organization.
   - Inconsistencies: places where the same concern is solved differently in different parts of the codebase.
   - Recommendations: if a matching stack template exists at `~/.claude/templates/<stack>/STRUCTURE.md`, compare against it and note what's already solid vs. what's worth realigning, in priority order - a starting point for a conversation, not a mandate to refactor.
5. Write findings into the corresponding root file - `BACKEND.md`, `FRONTEND.md`, `MOBILE.md` - copying the matching skeleton from `~/.claude/templates/onboarding/` and filling it in, in the language settled in step 3. Only create files for the services chosen in step 2.
6. Check whether a root `CLAUDE.md` already exists. If it does, add or update a section pointing to the generated docs (and the "Documentation language" section, if step 3 had to ask) without touching unrelated content. If it doesn't, create one with a short project overview learned during exploration plus those pointers.
7. If something couldn't be determined from the code alone (intent behind an odd pattern, a migration in progress, a known workaround), record it under that doc's "Open questions" instead of guessing.
