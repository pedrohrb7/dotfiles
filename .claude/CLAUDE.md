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
  emulator, and never take or read screenshots. List what the user should check instead. When the user explicitly asks
  for a snapshot or screenshot, delegate it to `ui-verifier`, so the images stay out of the main conversation.
- Apply that same high standard to engineering excellence: lint, test failures, and test flakiness.
  Fix only the ones caused by the current change or named in the task. Pre-existing ones in code you did not touch
  (and visual defects the user reports) are not fixed; they are logged once, by `backlog-keeper`, the single writer
  of `docs/backlog/` - failing/flaky tests, type/build errors and visual defects as bugs, lint violations and code
  smells as refactors (one entry per root cause, deduplicated against the folder's Index). Every other agent reports
  them in `out_of_scope_issues`, and the main session hands them to `backlog-keeper` in one call.
- Checks: subagents run only narrow checks (the tests and files they touched). Whole suites run only through `test-runner`.
- Documentation is updated once, at the end of the work, by `docs-writer`, from the `needs_docs` the agents reported.
  No other agent creates or edits doc files (README, `.env.example`, `docs/`, notes, summaries); they list what needs
  documenting in their report. Doc comments and API annotations inside the code are part of the code.
- Ask before acting when: (1) the task is ambiguous, (2) there are multiple reasonable approaches,
  (3) changes span 5+ files, or (4) you would be modifying config, CI, or infrastructure files.
- Be concise. Prefer direct answers. Do not add code explanation or summaries unless asked.
  Output no more than 3-4 lines of text before using tools.
- Always read a file before editing it. Never overwrite files without reading them first.

## Workflow

Route each request to its phase and owner without waiting for the user to name the agent. Check the precondition
first; when it fails, say what is missing instead of proceeding. Plans, specs and logs are found through the
`project-docs` skill (`docs/features/<slug>/`, or `docs/plans` + `docs/specs` in legacy projects).

| The user says (examples) | Phase -> owner | Precondition |
|---|---|---|
| "tenho uma ideia", "vamos pensar em X" | Discover -> `grill-me` skill, one question at a time, then hand off to `planner` | none |
| "vamos planejar", "escreve o plano" | Plan -> `planner` | decisions clear enough; otherwise Discover first |
| "pode especificar", "escreve a spec" | Spec -> `specker` | the plan exists (asking for the spec approves a Draft plan), or a refactor entry |
| "podemos seguir com a implementação", "pode implementar", "go" | Implement -> `implement` skill (`--tdd` when the user says "com TDD") | spec Approved (a Draft spec needs the user's yes) and plan Approved |
| "vamos fazer com TDD" (the user writes the code) | TDD -> `tdd` skill: stubs, tests red by assertion, hand off | the behavior is settled; otherwise `grill-me` first |
| "encontrei um bug", "achei um problema em X", "isso está quebrado" | Register -> `backlog-keeper`, then ask "quer corrigir agora?" | none |
| "só registra esse bug", "anota esse bug" | Register -> `backlog-keeper`, no follow-up question | none |
| "isso merece um refactor", "registra um refactor" | Register -> `backlog-keeper` | none |
| "corrige o bug X", "vamos resolver esse bug", yes to "quer corrigir agora?" | Fix -> `fix-bug` skill: reproduce, diagnose, regression test red, fix, gate, review, docs, close the entry | the bug is registered; if not, `backlog-keeper` registers it first |
| "revisa esse PR", "review" | Review -> `code-reviewer` (+ `security-reviewer` when auth, API, input, secrets or dependencies change) | a PR, branch or diff to review |
| "documenta", "atualiza as docs" | Document -> `docs-writer`, with the collected `needs_docs` (or the diff) | none |
| "pode subir um snapshot", "tira um print de X" | Visual check -> `ui-verifier`, text-only report | the app is already running locally; never start it |
| "escreve o PR", "descrição do PR" | Deliver -> `pr-description` skill (text only) | a diff against the base branch |
| "simplifica isso", "limpa esse código" | Simplify -> the built-in `/simplify` review | show the planned changes and wait for the user's approval before applying them |
| "audita as dependências", "check dependencies" | Audit -> `dep-audit` skill | none; never auto-upgrade |
| "desenha a arquitetura", "faz um diagrama do fluxo" | Diagram -> `archify` skill | none |
| "pode commitar" | Commit | explicit authorization in the current conversation |

- Never pick between several plans or specs: list them with their status and ask.
- Subagents cannot ask the user. When one finishes with `result: needs_input` (a question) or `result: blocked` with
  `scope_requests`, ask the user - one `AskUserQuestion` call for everything pending - and resume the same agent with
  `SendMessage` and the answers.
- The agent workflow hook (`~/.claude/hooks/agent-audit.py`) enforces part of these rules: a call it denies
  ("Agent workflow (<category>): ...") is never retried or worked around; follow its message, and ask the user when
  the action is really needed. Commits and pushes go through a confirmation prompt even after the user authorized them.
