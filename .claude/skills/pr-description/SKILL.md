---
name: pr-description
description: Draft a PR description and changelog entry from the current diff and the feature's plan, spec and implementation log. Delivery phase of the workflow. Use when the user says "escreve o PR", "descrição do PR", "PR description", "write the PR", or "changelog entry".
---

# PR Description

From the diff between the current branch and its base, plus the feature's documents when there is one (plan, spec and implementation log, resolved with the `project-docs` skill) or the bug's backlog entry:

1. Check the root `CLAUDE.md` for a "Documentation language" setting and write in that language. If there's no such setting, ask - English or Portuguese - before drafting (code/diff excerpts quoted in the description stay as written).
2. Summarize what changed and why - why matters more than what, since the diff already shows what. The plan's goal and the log's decisions are the best source of the why; link the feature folder or the bug entry.
3. List a test plan as a checklist: what was verified (gates, local checks with their requests) and what still needs manual testing (the "Para validar localmente" items).
4. Flag anything risky: migrations (and whether they are safe on production data), new env vars and config changes, breaking changes, feature flags.
5. If the project has a CHANGELOG file, draft an entry in its existing format and ask before adding it.

Keep the description short enough to read in under a minute. Never add attribution lines (agent, LLM, provider or tool). Only draft the text - do not create the PR, push, or commit anything. Never use the em dash; use "-".
