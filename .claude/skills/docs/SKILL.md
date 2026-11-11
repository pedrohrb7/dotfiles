---
name: docs
description: Know-how of the documentation pass - which docs a change needs, how to check them against the code, and how to write them in the project's own style and language. Preloaded by the docs-writer agent, which owns the pass; the main session delegates documentation to docs-writer instead of applying this skill itself.
---

# Docs

For the needs reported by the agents (`needs_docs`) and the change they describe (diff, implementation log):

1. Identify what documentation should exist for it, based on what the project already uses elsewhere: README section, env var table and `.env.example`, API description file, `docs/requests/` entry, concept doc, root `CLAUDE.md` agent sections (`Services`, `Local runtime`, `Test suites`). Doc comments and API annotations inside the code (godoc, rustdoc, docstrings, OpenAPI decorators) are part of the code and belong to the agent that wrote it, not to the documentation pass.
2. Check whether that documentation already exists and is still accurate, reading the code it describes - never the agent's summary alone.
3. Write in the language the root `CLAUDE.md` sets under "Documentation language" (code, identifiers and inline code comments are always English). If no language is set and the existing docs don't make it obvious, don't guess: ask (a subagent returns the question as `needs_input`).
4. If missing, create it. If outdated, update it. Match the project's existing doc style and location - don't invent a new doc system.
5. Document intent, constraints and usage a reader can't get from the code itself. Don't restate what well-named code already makes obvious.

Skip generated/auto-generated files - never hand-edit those.
