---
name: design-system
description: Apply consistent design-system and UI/UX thinking when building or reviewing a layout - spacing/type scales, tokens, hierarchy, accessibility - and keep the project's DESIGN_SYSTEM.md as the single source of those values. Preloaded by frontend-react and mobile-react-native. Use when the user says "design system", "layout", "UI/UX", or is building new screens or components.
---

# Design System

Before building a layout or component:

1. Read the project's `DESIGN_SYSTEM.md` (root of the project, shared across every UI service) for its design tokens: spacing scale, type scale, color palette, breakpoints.
   - If the file doesn't exist yet, it is a project decision: in the main session, copy it from `~/.claude/templates/project-root/DESIGN_SYSTEM.md` and establish a real aesthetic direction with the user (palette, type pairing, layout concept, signature element; the `frontend-design` skill helps when it is enabled) before filling its tables, instead of a generic 4/8px-grid guess. A subagent reports the missing file in `scope_requests` instead of creating it.
   - If it exists but a table is missing a value the current work needs, propose the value in place (as a scope request when you are a subagent) rather than inventing a one-off value in the code.
2. Establish visual hierarchy first: what is the single most important element on this screen, and does the layout make that obvious at a glance?
3. Reuse existing components before creating new ones. A new component must match the token system, not introduce one-off values.
4. Check accessibility basics: color contrast, focus states, semantic HTML/ARIA, keyboard navigation, touch target size on mobile.
5. Check responsive behavior at the project's actual breakpoints, not just desktop.

After building, do a pixel-level pass **in the code**: alignment, spacing consistency, token usage and every state. Fix what the current change caused. Anything that looks off elsewhere is not fixed along the way: report it as an out-of-scope issue. Visual validation on screen is the user's, on their local run (see the global UI rule).
