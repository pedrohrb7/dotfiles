# Design System - <project name>

<!-- Source of truth for every UI-facing service (web frontend, mobile). The `design-system` skill reads and extends this file directly - keep it current instead of letting one-off values drift into components. -->

## Principles

<!-- 2-4 sentences on the visual direction: what this product should feel like, and any hard rule that shapes every decision below (e.g. "dense, data-heavy, no wasted whitespace" vs "generous whitespace, editorial"). -->

## Color

<!-- Semantic tokens, not raw hex sprinkled through components. Name by role, not by appearance (`accent`, not `blue`) so the value can change without renaming every usage. Provide both light and dark values if the product supports dark mode. -->

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

Font family: <family, with fallback stack>

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
