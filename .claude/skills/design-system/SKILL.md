---
name: design-system
description: Apply consistent design-system and UI/UX thinking when building or reviewing a layout - spacing/type scales, tokens, hierarchy, accessibility. Use when user says "design system", "layout", "UI/UX", or is building new screens or components.
disable-model-invocation: true
---

# Design System

Before building a layout or component:

1. Read the project's `DESIGN_SYSTEM.md` (root of the project, shared across every UI service) for its design tokens: spacing scale, type scale, color palette, breakpoints. If the file doesn't exist yet, copy it from `~/.claude/templates/project-root/DESIGN_SYSTEM.md` - but before filling its tables with generic defaults, call the `frontend-design` skill to establish a real aesthetic direction (palette, type pairing, layout concept, signature element) for a greenfield UI, then encode that direction's values into the tables instead of a generic 4/8px-grid guess. If it exists but a table is missing a value the current work needs, fill that value in in place rather than inventing a one-off value elsewhere.
2. Establish visual hierarchy first: what is the single most important element on this screen, and does the layout make that obvious at a glance?
3. Reuse existing components before creating new ones. A new component must match the token system, not introduce one-off values.
4. Check accessibility basics: color contrast, focus states, semantic HTML/ARIA, keyboard navigation, touch target size on mobile.
5. Check responsive behavior at the project's actual breakpoints, not just desktop.

After building, do a pixel-level pass: alignment, spacing consistency, and anything that "looks off" even if unrelated to the current task - fix it along the way.
