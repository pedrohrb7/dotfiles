# Node/TypeScript React - Project Structure

This is the contents of `services/frontend/` in the [project-root](../project-root/STRUCTURE.md) wrapper - not a repo root by itself.

```
services/frontend/
  Dockerfile
  README.md                    # how to run/test just this service (filled-in skeleton: see README.md in this template folder)
  CLAUDE.md                    # service-specific agent instructions (stack conventions, gotchas) (filled-in skeleton: see CLAUDE.md in this template folder)
  src/
    main.tsx                 # entrypoint, mounts <App/> - wiring only
    App.tsx                  # top-level routes/providers only, no page logic
    routes/ (or pages/)      # one file per route, thin - composes components, no heavy logic
    components/
      ui/                    # generic, reusable, no business logic (the design-system primitives)
      <feature>/             # feature-specific components, not meant to be reused elsewhere
    hooks/                   # reusable stateful logic extracted out of components
    lib/                     # api clients, formatting, pure utility functions
    state/                   # global state (store/context), only for state that's truly cross-cutting
    styles/
      tokens.css (or theme.ts)  # design tokens: spacing scale, type scale, color palette, breakpoints
    types/                   # shared types not owned by a single feature
  public/                    # static assets served as-is
  test/
    e2e/                     # Playwright/Cypress specs driving the real running app
  .storybook/                # optional: isolate/document components outside the app shell
  package.json
  tsconfig.json
  vite.config.ts (or next.config.ts)
```

## Why this shape

- **`components/ui/` vs `components/<feature>/`**: a hard line between generic design-system primitives (Button, Input, Card) and feature-specific composites keeps primitives reusable and prevents feature logic leaking into shared components.
- **`tokens.css`/`theme.ts` exists from day one**: even a single-page app benefits from naming its spacing/color/type values once, so the `design-system` skill has something concrete to check layouts against.
- **Routes/pages stay thin**: a route file composes components and wires data; if it grows business logic, that logic belongs in a hook or `lib/`, kept testable outside of any component tree.
- **`state/` is not the default**: most state should live in the component that needs it or be passed as props. Only promote state here when multiple unrelated routes actually need it.
- **`test/e2e/` over relying only on component tests**: component tests catch logic bugs, but layout/interaction regressions (the ones the pixel-perfection standard cares about) only show up end-to-end.
