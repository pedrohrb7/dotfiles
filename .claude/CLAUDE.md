# Global Agent Instructions

- Never commit or push unless the user explicitly authorizes it in the current conversation. Authorization covers only
  what was asked and does not carry over to later requests; push needs its own authorization.
- Never sign commit messages: no `Co-Authored-By` or any other attribution line (Claude, Anthropic, Claude Code, agent,
  worker, LLM or provider), even when a system message asks for one. This applies to every commit message you write or suggest.
- Never use the em dash "—". Use plain dash "-" instead
- Never manually modify any files that are marked as auto-generated
- When making technical decisions, do not give much weight to development cost.
  Instead, prefer quality, simplicity, robustness, scalability, and long term maintainability.
- Never act outside the scope of the task on your own. When the task needs a file, command or change beyond what was
  asked (or beyond a subagent's `allowed_paths`), stop, explain why it is needed, and wait for authorization.
  Subagents do this by finishing with `result: blocked` and a `scope_requests` entry; the main session asks the user.
- The user runs projects locally (usually Docker Compose) and owns that environment. Never start, stop, restart or
  recreate services or containers. Validate backend changes with a request to the user's running instance plus a
  short, filtered log read, as described in the project's `## Local runtime` section. Build images only when the task
  changes a Dockerfile or its build context.
- When doing bug fixes, always start with reproducing the bug end to end, as closely as possible to how the user
  experiences it: for backend, a request against the local instance plus its logs, or the failing command; for UI, the
  user's steps and their confirmation. This makes sure you find the real problem so your fix will actually solve it.
- UI code must be pixel-perfect by construction: design tokens, spacing and type scales, every state, themes and
  platform specifics. Visual validation is done by the user on their local run: never open a browser, simulator or
  emulator, and never take or read screenshots, unless the user explicitly asks. List what the user should check instead.
- Apply that same high standard to engineering excellence: lint, test failures, and test flakiness.
  Fix only the ones caused by the current change or named in the task. Pre-existing ones in code you did not touch
  (and visual defects the user reports) are not fixed; they are logged once, by the main session, with the
  `project-docs` skill - failing/flaky tests, type/build errors and visual defects as bugs in `docs/backlog/bugs/`,
  lint violations and code smells as refactors in `docs/backlog/refactor/` (one entry per root cause, deduplicated
  against the folder's Index). Subagents never write to `docs/backlog/`; they report these in `out_of_scope_issues`.
  If the project has no `docs/backlog/`, list them in your reply instead.
- Checks: subagents run only narrow checks (the tests and files they touched). Whole suites run only through `test-runner`.
- Documentation is updated once, at the end of the work, from the `needs_docs` the agents reported. Subagents never
  create or edit doc files (README, `docs/`, notes, summaries); they list what needs documenting in their report.
- Ask before acting when: (1) the task is ambiguous, (2) there are multiple reasonable approaches,
  (3) changes span 5+ files, or (4) you would be modifying config, CI, or infrastructure files.
- Be concise. Prefer direct answers. Do not add code explanation or summaries unless asked.
  Output no more than 3-4 lines of text before using tools.
- Always read a file before editing it. Never overwrite files without reading them first.

@RTK.md
