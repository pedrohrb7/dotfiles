---
name: docs
description: Check whether documentation exists for the code being changed, and create or update it to match. Use when user says "docs", "document this", or after finishing a feature or change.
disable-model-invocation: true
---

# Docs

For the current change (diff or recently modified files):

1. Identify what documentation should exist for it: README section, module-level doc, API reference, ADR, or an inline doc comment - based on what the project already uses elsewhere.
2. Check whether that documentation already exists and is still accurate.
3. Check the root `CLAUDE.md` for a "Documentation language" setting and write in that language. If there's no such setting, ask - English or Portuguese - before writing prose (code, identifiers, and inline code comments are always English regardless of the answer).
4. If missing, create it. If outdated, update it. Match the project's existing doc style and location - don't invent a new doc system.
5. Document intent, constraints, and usage a reader can't get from the code itself. Don't restate what well-named code already makes obvious.

Skip generated/auto-generated files - never hand-edit those.
