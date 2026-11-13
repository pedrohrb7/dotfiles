# Implementation log - skills-docs-root

<!-- Written by /implement only, append-only. One "Run" section per /implement run and one block per task, filled from the agents' YAML reports. The stack agents read this file before coding and follow the decisions recorded here; never re-decide something already logged without a scope request. -->

## Run 2026-11-12

Open questions of the spec, resolved by the user before the run: (1) single source of the docs root is the `- docs root:` line in the git-root `CLAUDE.md` `## Workflow` (option a; `docs_roots` leaves `agent-audit.json`); (2) no automated test against hard-coded `docs/` paths in skills and agents in this change, only the V1 grep (option a); (3) the refactor entry is linked and moved to In progress by `backlog-keeper`. The user explicitly authorized editing the global `.claude/CLAUDE.md` in task 3 (path references in the Workflow section only; rules unchanged).

### Task 1 - Hook lê a raiz de docs do CLAUDE.md da raiz git (done)

- **Files:** `CLAUDE.md` (first edit: `## Workflow` gets `- docs root: .claude/docs/` and the rewritten paragraph, Design 6), `.claude/hooks/agent-audit.py` (`docs_roots`/`DEFAULT_DOCS_ROOTS` removed; `DEFAULT_DOCS_ROOT`, regexes, `normalize_docs_root()`, `project_docs_root()`; `evaluate_write` uses `roots or [project_docs_root(root)]` per root; `main()` drops `docs_roots(config)`; `WHY`, module docstring, `DOC_FILES` comment), `.claude/hooks/agent-audit.json` (`docs_roots`/`_docs_roots` removed, `_docs_root` comment), `.claude/hooks/agent-metrics.py` (`FLAG_LABELS` say docs root), `.claude/hooks/tests/_support.py` (`TEST_CONFIG` loses `docs_roots`; `declare_docs_root()`, `TempRepoCase.declare()`), `.claude/hooks/tests/test_write_areas.py` (D1-D11 replaced by `DocsRootDeclaration` DR1-DR9, DR17 and `DocsRootEffect` DR10-DR16), `.claude/hooks/tests/test_config_contract.py` (F4a, F4b), `.claude/hooks/tests/test_hook_process.py` (P-DR)
- **Decisions:** control characters are checked on the stripped value (a tab inside the value is invalid); `WORKFLOW_HEADING` is matched against `line.strip()`, `SECTION_END` on the raw line; DR14 asserts only the inner repo's `rel` and `area`; DR8 skips as root.
- **Assumptions / approved scope / migrations / env vars / docs pending:** none
- **Notes:** the live hook was a syntax error for a moment (unescaped quotes in `WHY`), caught by the first `ast.parse` check and fixed. Two plain text replacements went through a Bash python snippet instead of Edit. Pyright reports `rel` as possibly None in `agent-audit.py` around lines 595-627 and an inline `._support` import at `test_write_areas.py:235` (for review).
- **Checks:** test-runner (task): 235 tests OK, normal and with `TMPDIR` under a scratchpad `claude-*` dir (3.5-3.7 s); `settings.json` unchanged; `agent-audit.json` valid.

### Task 2 - project-docs define a raiz de docs; templates (done)

- **Files:** `.claude/skills/project-docs/SKILL.md` (**Docs root** and **Docs root offer** in **Layouts and path resolution**, before **Two layouts**, text from Design 7; the rest of the section 7 table applied: description, opening and diagram, path map with resolved note, scaffold, add entry, migrate; every docs path is `<docs>/...`), `.claude/templates/docs-structure/features/_template/spec.md` (Source comment `[<entry>](../../backlog/refactor/<entry>.md)`), `.claude/templates/project-root/CLAUDE.md` (commented docs root hint after `- docs layout: features`)
- **Decisions:** the "resolved:" note under the path map is a separate paragraph below the table. Remaining `docs/` mentions in `SKILL.md` are intended (the default, the Docs root text, fallback rules, scaffold steps 1 and 6).
- **Assumptions / approved scope / migrations / env vars / docs pending:** none
- **Checks:** done-criteria grep on `project-docs/SKILL.md` finds nothing; no em dash. No automated suite for markdown.

Tasks 3 and 4 ran in parallel after task 2.

### Task 3 - Skills consumidoras e CLAUDE.md global (done)

- **Files:** `.claude/skills/implement/SKILL.md` (argument-hint `<docs>/`; step 1.1 docs-root sentence and "Never hard-code a docs path"; step 1.2.3 `<docs>/features/README.md`; run-state `feature` is `<docs>/features/<slug>/` plus a resolved-paths paragraph below the JSON), `.claude/skills/fix-bug/SKILL.md` (`<docs>/backlog/bugs/`, resolved with project-docs), `.claude/skills/onboard/SKILL.md` (step 6 records `- docs root: <path>/` when the tree is not at `docs/`, confirm never guess), `.claude/skills/implementer-contract/SKILL.md` (lines 13, 58, 84, 115), `.claude/skills/docs/SKILL.md` (`<docs>/requests/`), `.claude/CLAUDE.md` (only the three Design 8 path references at lines 28, 33, 45; reviewed by the main session: no rule wording changed, the single quoted em dash remains)
- **Approved scope:** global `.claude/CLAUDE.md` edit, authorized by the user before the run.
- **Assumptions / migrations / env vars / docs pending:** none
- **Checks:** V1 grep finds nothing in the six files; `git diff --stat` shows only the six files.

### Task 4 - Agents (done)

- **Files:** the 12 agents in `.claude/agents/` (`planner`, `specker`, `backlog-keeper`, `docs-writer`, `code-reviewer`, `test-writer`, `quality-fixer`, `backend-go`, `backend-node`, `backend-python`, `backend-rust`, `backend-spring`)
- **Decisions:** `planner` and `specker` may write the `docs layout` and `docs root` lines of the root `CLAUDE.md` `## Workflow` when the project-docs migration decision or docs root offer requires it; the scaffold and docs root offer sentence is only in `planner` line 19 (specker line 18 got only "never hard-code a docs path"); frontmatter name/tools/model unchanged (only `description` text in planner, specker, backlog-keeper, docs-writer).
- **Assumptions / approved scope / migrations / env vars / docs pending:** none
- **Checks:** V1 grep finds nothing in `.claude/agents/`; YAML frontmatter of the four changed descriptions parses; diff shows exactly the 12 files.

**Review:** code-reviewer verdict ship (minor findings); security-reviewer verdict fix first (1 medium, 1 low). Fixed in the same round, recorded in the spec as the 2026-11-13 addendum (by `specker`):
- Security (medium, task 1): `project_docs_root()` blocked on a FIFO or a symlink to a blocking device. Now `os.open(O_RDONLY | O_NONBLOCK)`, `os.fstat` + `S_ISREG` on the same fd, read through the fd with the 256 KiB cap, fd closed in `finally`; `O_NOFOLLOW` deliberately not used (a symlink to a regular file keeps working). New tests DR18 (FIFO, skipped without `os.mkfifo`) and DR19 (symlink to `/dev/null`), both through `root_within()` (daemon thread, 2 s join). security-reviewer re-verified: safe (no hang with or without a controlling terminal, no fd leak over 600 calls); only remaining blocking path is a regular file on a stalled FUSE/NFS mount, unreachable from repo content.
- Task 1: A4 test renamed `test_a4_docs_root_paths_are_area_docs_without_md_flag` (the only disallowed V3 hit); Pyright `reportOptionalSubscript` at `test_write_areas.py` fixed with `assert out is not None`.
- Tasks 2-4 (markdown, `frontend-react`): every first use of `<docs>` says how it resolves (definition in `implementer-contract`, pointers from the backend agents; inline in quality-fixer, test-writer, docs, fix-bug, implement; in the `description` of backlog-keeper and specker, YAML-safe without `: `); the Docs root offer line is written by the main session or planner/specker, other subagents relay via `needs_input`; `implement` limits the offer to no declared root and no `docs/`; project-docs invalid values include a control character; specker gets the planner's scaffold / docs root offer clause.
- Low security finding (docs root change raises no flag) and two pre-existing code-reviewer findings (Pyright "rel possibly None" in `_assess_root`; nested repo outer root still adds `md_outside_docs`) go to `backlog-keeper`. No blockers, so no second code review.

**Verification (test-runner, full):** 237 tests OK, normal (3.5 s) and with `TMPDIR` under a scratchpad `claude-*` dir (4.1 s); V1 no hits; V2 49 hits, all with a resolution pointer after the fixes; V3 only F4b and DR16 (allowed); V4 empty; 48 agent/skill frontmatters parse; `agent-audit.json` valid; `settings.json` unchanged.
