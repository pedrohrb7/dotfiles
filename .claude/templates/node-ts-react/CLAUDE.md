# CLAUDE.md - <service name> (Frontend)

<!-- Service-specific agent instructions. Project-wide conventions live in the root CLAUDE.md - don't repeat them here, only what's specific to working in this service. -->

## Conventions

- `components/ui/` = generic, reusable primitives, no business logic. `components/<feature>/` = feature-specific, not meant to be reused elsewhere. A new component belongs in `ui/` only if a second feature would plausibly reuse it as-is.
- Routes/pages stay thin: compose components and wire data, delegate logic to a hook or `lib/`.
- Design tokens live in the project root's `DESIGN_SYSTEM.md`, mirrored into `styles/tokens.css` (or `theme.ts`) here. Never hardcode a one-off spacing/color/type value - extend the token file instead, in both places.
- `state/` is not the default - most state belongs in the component that needs it. Promote to `state/` only when 2+ unrelated routes need the same state.

## Testing

- Unit/component tests colocated with the code they cover.
- `test/e2e/` (Playwright/Cypress) against the running app - run before any layout or interaction change is considered done, not just before a release.

## Gotchas

<!-- Project-specific footguns as they're discovered - fill in over time, don't leave this section aspirational. -->

-

## Reference

Root `DESIGN_SYSTEM.md` for tokens · Root `PRD.md` for product context · `frontend-design` skill for aesthetic direction on new/greenfield UI · `design-system` skill for consistency, tokens, and accessibility on any layout
