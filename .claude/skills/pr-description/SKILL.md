---
name: pr-description
description: Draft a PR description and changelog entry from the current diff. Use when user says "PR description", "write the PR", or "changelog entry".
disable-model-invocation: true
---

# PR Description

From the diff between the current branch and its base:

1. Check the root `CLAUDE.md` for a "Documentation language" setting and write in that language. If there's no such setting, ask - English or Portuguese - before drafting (code/diff excerpts quoted in the description stay as written).
2. Summarize what changed and why - why matters more than what, since the diff already shows what.
3. List a test plan as a checklist: what was verified, what still needs manual testing.
4. Flag anything risky: migrations, config changes, breaking changes, feature flags.
5. If the project has a CHANGELOG file, draft an entry in its existing format and ask before adding it.

Keep the description short enough to read in under a minute. Only draft the text - do not create the PR, push, or commit anything.
