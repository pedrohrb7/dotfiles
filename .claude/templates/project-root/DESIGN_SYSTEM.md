# Design System - <project name>

<!-- Source of truth for every UI-facing service (web, mobile). Created once by the `design-director` agent, from a visual direction the user chose; maintained afterwards by the main session following the `design-system` skill. Subagents never edit it: they propose values in `scope_requests`. -->

## Principles

<!-- 2-4 sentences on the visual direction: what this product should feel like, and any hard rule that shapes every decision below (e.g. "dense, data-heavy, no wasted whitespace" vs "generous whitespace, editorial"). -->

## Layout concept

<!-- Filled by design-director from the chosen direction. Concept: how screens are organized and why (navigation model, density, where the primary action lives). Wireframe: ASCII sketch of the main-task screen - one block per platform in a monorepo (web, mobile). Avoided patterns: each generic pattern this direction could fall into and how it avoids it; elements taken from the brief or CONSTRAINTS.md that match a pattern are listed with source "brief". -->

**Concept:**

**Wireframe - <platform>:**

```text
```

**Avoided patterns:**

| Pattern | How this direction avoids it (or why it is kept) | Source |
|---|---|---|
| | | list / brief / CONSTRAINTS.md |

## Color

<!-- Semantic tokens, not raw hex sprinkled through components. Name by role, not by appearance (`accent`, not `blue`) so the value can change without renaming every usage. Always provide both light and dark values, even when the product ships one theme. -->

| Token | Light | Dark | Usage |
|---|---|---|---|
| `color.background` | | | Page background |
| `color.surface` | | | Card/panel background |
| `color.text.primary` | | | Default text |
| `color.text.secondary` | | | De-emphasized text |
| `color.border` | | | Dividers, input borders |
| `color.accent` | | | Primary actions, links |
| `color.success` | | | Positive state |
| `color.warning` | | | Caution state |
| `color.danger` | | | Destructive state, errors |

Minimum contrast: body text 4.5:1, large text/icons 3:1 (WCAG AA) against its background token.

## Type scale

<!-- Keep to 5-7 steps. More than that and hierarchy stops meaning anything. -->

| Token | Size | Line height | Weight | Usage |
|---|---|---|---|---|
| `text.display` | | | | Hero/marketing headlines only |
| `text.h1` | | | | Page title |
| `text.h2` | | | | Section title |
| `text.h3` | | | | Subsection title |
| `text.body` | | | | Default body copy |
| `text.small` | | | | Secondary/meta text |
| `text.caption` | | | | Labels, timestamps |

### Font family

<!-- Open-license (e.g. SIL OFL) or system families only. Record where each family comes from and its license. In a monorepo the family must work on web and mobile (expo-font). -->

| Role | Family | Weights | Fallback stack | Source | License |
|---|---|---|---|---|---|
| Display | | | | | |
| Text | | | | | |
| Mono | | | | | |

## Spacing scale

<!-- A single grid (commonly 4px or 8px) that every margin/padding/gap value is a multiple of. If a layout needs a value outside this scale, that's a signal to reconsider the layout, not to add a one-off value. -->

| Token | Value |
|---|---|
| `space.xs` | |
| `space.sm` | |
| `space.md` | |
| `space.lg` | |
| `space.xl` | |

## Breakpoints

| Token | Width | Target |
|---|---|---|
| `bp.sm` | | Mobile |
| `bp.md` | | Tablet |
| `bp.lg` | | Desktop |

## Radius and elevation

| Token | Value | Usage |
|---|---|---|
| `radius.sm` | | Inputs, small controls |
| `radius.md` | | Cards, buttons |
| `radius.lg` | | Modals, large surfaces |
| `shadow.sm` | | Resting elevation (cards) |
| `shadow.md` | | Raised elevation (dropdowns, popovers) |

## Component conventions

<!-- Rules for when to add a new component vs. reuse/extend an existing one, and where components live (see the frontend/mobile STRUCTURE.md's components/ui/ vs components/<feature>/ split). -->

-
-

## Accessibility baseline

<!-- Non-negotiables checked on every layout - see the `design-system` skill's build checklist. -->

- Focus states visible on every interactive element, never removed without an equivalent replacement.
- Touch targets at least 44x44px on mobile / touch surfaces.
- Every interactive element reachable and operable by keyboard alone.
- Semantic HTML/ARIA roles over generic `div`s with click handlers.
