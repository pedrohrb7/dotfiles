# React Native - Project Structure

This is the contents of `services/mobile/` in the [project-root](../project-root/STRUCTURE.md) wrapper - not a repo root by itself. (No `Dockerfile` here - a mobile app isn't containerized; it's absent from this service's folder unlike the others.)

```
services/mobile/
  README.md                    # how to run/test just this service (filled-in skeleton: see README.md in this template folder)
  CLAUDE.md                    # service-specific agent instructions (stack conventions, gotchas) (filled-in skeleton: see CLAUDE.md in this template folder)
  src/
    App.tsx                  # top-level providers/navigation container only
    screens/                 # one file per screen, thin - composes components
    components/
      ui/                    # generic, reusable, no business logic (design-system primitives)
      <feature>/              # feature-specific components
    navigation/               # navigator setup, route param typing
    hooks/
    lib/                      # api clients, storage, pure utility functions
    state/
    theme/                    # design tokens: spacing, color, type scale, shared with web when possible
  assets/
    fonts/ images/
  test/
    e2e/                      # Detox/Maestro specs driving the real app
  ios/  android/               # native project files - generated/managed by the toolchain, never hand-edit blindly
  app.json (or app.config.ts)
  package.json
  tsconfig.json
```

## Why this shape

- **Mirrors the Node/React web template** (`screens/` instead of `routes/`, same `components/ui/` vs `components/<feature>/` split, same `theme/` for tokens): a developer moving between web and native code should recognize the shape immediately, and tokens can realistically be shared between the two.
- **`ios/`/`android/` are treated as generated**: changes there should go through the RN/Expo config layer (`app.config.ts`, config plugins) whenever possible, since hand-edits get silently blown away by `prebuild`/`eject` runs.
- **`test/e2e/` uses a device-level tool** (Detox/Maestro), not just component tests: gesture, navigation, and platform-specific bugs only surface when the app runs on a real simulator/device.
