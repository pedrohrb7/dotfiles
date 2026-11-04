# Global Agent Instructions

- Never commit to git
- Never use the em dash "—". Use plain dash "-" instead
- Never manually modify any files that are marked as auto-generated
- When making technical decisions, do not give much weight to development cost.
  Instead, prefer quality, simplicity, robustness, scalability, and long term maintainability.
- When doing bug fixes, always start with reproducing the bug in an E2E setting as closely aligned with how an end user would experience it as possible.
  This makes sure you find the real problem so your fix will actually solve it.
- When end-to-end testing a product, be picky about the UI you see and be obsessed with pixel perfection.
  Fix what looks off when it is caused by the current change or is part of the task. Visual problems that were already there
  are not fixed; log them as bugs in `docs/backlog/bugs/` with the `project-docs` skill (screen, platform/viewport, what is
  wrong), following the same rules as the lint and test rule below.
- Apply that same high standard to engineering excellence: lint, test failures, and test flakiness.
  Fix only the ones caused by the current change or named in the task. Pre-existing ones in code you did not touch
  are not fixed; log them with the `project-docs` skill - failing/flaky tests and type/build errors as bugs in
  `docs/backlog/bugs/`, lint violations and code smells as refactors in `docs/backlog/refactor/` (one entry per root
  cause, deduplicated against the folder's Index). If the project has no `docs/backlog/`, list them in your reply instead.
- Ask before acting when: (1) the task is ambiguous, (2) there are multiple reasonable approaches,
  (3) changes span 5+ files, or (4) you would be modifying config, CI, or infrastructure files.
- Be concise. Prefer direct answers. Do not add code explanation or summaries unless asked.
  Output no more than 3-4 lines of text before using tools.
- Always read a file before editing it. Never overwrite files without reading them first.
- Always validate if there is a documentation, if no then start to create a documentation for every change.

@RTK.md
