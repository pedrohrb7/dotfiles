---
name: design-system
description: Apply consistent design-system and UI/UX thinking when building or reviewing a layout - spacing/type scales, tokens, hierarchy, accessibility - and maintain the project's DESIGN_SYSTEM.md as the single source of those values. Preloaded by frontend-react, mobile-react-native and design-director. Creating the visual direction from scratch belongs to the design-director agent. Use when the user says "design system", "layout", "UI/UX", or is building new screens or components.
---

# Design System

Before building a layout or component:

1. Read the project's `DESIGN_SYSTEM.md` (root of the project, shared across every UI service) for its design tokens: spacing scale, type scale, color palette, breakpoints.
   - File missing or `Principles` empty, and the UI services have no tokens of their own in code: the main session offers the `design-director` agent to the user (never calls it without a yes, never defines the direction in the conversation); if refused, continue without inventing tokens, and work that needs them stays stopped or partial. A subagent finishes `result: blocked` with a `scope_requests` entry (`action: create`, `target: DESIGN_SYSTEM.md`, `reason: no visual direction yet; the design-director agent creates it`); a denied request means `partial` or a blocker, with no invented token.
   - File missing or `Principles` empty, but the UI services already have tokens in code (extraction): the main session copies `~/.claude/templates/project-root/DESIGN_SYSTEM.md` and fills it with the values found in the code, citing the source file of each, with no new direction and no agent. A subagent asks for the extraction in `scope_requests` (`action: create`, `target: DESIGN_SYSTEM.md`, `reason: extraction of tokens in <files>`); the `reason` starting with "extraction" is what tells it apart from the missing-direction request.
   - File exists but a table lacks a value the work needs: the main session proposes the value to the user and writes it on a yes. A subagent proposes it in `scope_requests` (`action: edit`, `target: DESIGN_SYSTEM.md`, the token, light and dark, and its use) and never edits the file, even with its path in `allowed_paths`; after the yes the main session writes it and resumes the agent, which then uses the token.
   - You are the `design-director`: this step does not apply; your precondition is the one in your agent file.
2. Establish visual hierarchy first: what is the single most important element on this screen, and does the layout make that obvious at a glance?
3. Reuse existing components before creating new ones. A new component must match the token system, not introduce one-off values.
4. Check accessibility basics: color contrast, focus states, semantic HTML/ARIA, keyboard navigation, touch target size on mobile.
5. Check responsive behavior at the project's actual breakpoints, not just desktop.

After building, do a pixel-level pass **in the code**: alignment, spacing consistency, token usage and every state. Fix what the current change caused. Anything that looks off elsewhere is not fixed along the way: report it as an out-of-scope issue. Visual validation on screen is the user's, on their local run (see the global UI rule).
