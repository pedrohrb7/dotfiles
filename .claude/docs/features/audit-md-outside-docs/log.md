# Implementation log - audit-md-outside-docs

<!-- Written by /implement only, append-only. One "Run" section per /implement run and one block per task, filled from the agents' YAML reports. The stack agents read this file before coding and follow the decisions recorded here; never re-decide something already logged without a scope request. -->

## Run 2026-11-13

Open questions of the spec, resolved by the user at approval and recorded in the spec's 2026-11-13 addendum: (1) promotion of `md_outside_docs` to block is later, with real-use data and after (2); (2) the docs-root declaration issue is the next spec (read the declaration from HEAD + protect the backlog in every candidate tree), not this one; (3) `docs-writer` is exempt from `md_outside_docs` for any `.md` (differs from the spec body's recommendation; the addendum wins); (4) `docs-write-flag-implementers-only` gets its own spec later; (5) the two covered entries are linked and move to In progress when `/implement` starts.

### Task 1 - md_outside_docs para agents, por nome exato e só para arquivo novo (done)

- **Files:** `.claude/hooks/agent-audit.py` (`DOC_FILE_NAMES`, `MD_DOC_NAMES`, `MD_FREE_ACTORS = {main, docs-writer}`, `file_name()`, `write_creates()`, `_creates()`; `_assess_root` computes `allowed` and `declared_md` before the flags; new `md_outside_docs` predicate; case-insensitive `docs_write_by_implementer`; `evaluate_write` uses `write_creates`; `WHY`, module and `evaluate_write` docstrings; `is_design_system` uses `file_name()`), `.claude/hooks/agent-metrics.py` (`FLAG_LABELS["md_outside_docs"]`), `.claude/hooks/tests/test_write_areas.py` (A1-A3 changed; DR10, DR13, DR16 use specker; `MdOutsideDocs` MD1-MD15, MD17), `.claude/hooks/tests/test_design_system.py` (H14: main silent, flags []), `.claude/hooks/tests/test_hook_main.py` (`MdOutsideDocsPayload` MD16a-c, MD18), `.claude/hooks/tests/test_hook_process.py` (P-DR uses specker; P-MD)
- **Decisions:** `keys` computed once before the form loop (run-state `run`/`task` fields still come from it; `scoped_run` reused by the out_of_scope block); the `.md` check in `declared_md` strips backticks first.
- **Assumptions / approved scope / migrations / env vars:** none
- **Docs pending:** `.claude/README.md` hooks section (md_outside_docs definition, case-insensitive DOC_FILES name rule); `.claude/agent-workflow.md` 13.3 item 4, 13.5 (main row), 13.7.
- **Notes:** the hook parsed after every edit. Pyright now reports `.get` on a possibly-None value at `agent-audit.py:637` and `:640` (new; for review), besides the known pre-existing "rel possibly None".
- **Checks:** test-runner (task): 258 tests OK, normal and with `TMPDIR` under a scratchpad `claude-*` dir (about 4.1 s); `agent-audit.json` and `settings.json` unchanged; the old predicate and backlog-entry grep find nothing.

### Task 2 - specker lista os .md que a task cria (done)

- **Files:** `.claude/agents/specker.md` (Design 4 sentence as its own indented continuation line in the **Files** item, right after "Cover the task's own folders, not the whole service;"; the addendum does not touch section 4)
- **Assumptions / approved scope / migrations / env vars / docs pending:** none
- **Checks:** frontmatter parses; `git diff --stat` shows one added line.

**Review (code-reviewer, verdict ship):** fixed in the same round by `backend-python`:
- `_assess_root` guard `if run and scoped_run:` (Pyright narrowing at former lines 637/640; no behavior change); stray `rec ={` restored; P-DR docstring notes it uses `specker` per M1.
- Main-session decision, consistent with M3 ("only new files count"): a failed write creates nothing. `evaluate_write(..., failed=False)` keyword; `main()` passes `failed=event == "PostToolUseFailure"`; when failed, `created = False`, so `md_outside_docs` never fires on `PostToolUseFailure` (other flags unchanged; the record's `failed` field as before). New test MD19 (`test_md19_failed_write_creates_nothing`) in `test_hook_main.py`.
- `_assess_root` drops the unused `tool` parameter (only caller `evaluate_write` updated; no test calls it directly).
- Kept as is (reviewer question): `matches()` stays case-sensitive in the M6 exemption, so a declared `**/*.MD` does not exempt `x.md`, consistent with `out_of_scope_write`.
- Observed during the fix: one `out_of_scope_write` record for an in-scope edit of `agent-audit.py`, produced by the hook's error branch (absolute rel, no run) while the live hook was mid-edit; the following records were normal (in scope, task 1). Transient, not a regression.
- Out of scope (to backlog): `active_run` (`agent-audit.py` around line 530) calls `data.get("phase")` outside the try, so a run-state JSON whose top level is not an object makes every write in that repo fall into the fail-closed branch and lose the area flags.
- Suite after fixes: 259 tests OK. No blockers, so no second review.
