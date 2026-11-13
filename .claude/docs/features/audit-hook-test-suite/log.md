# Implementation log - audit-hook-test-suite

<!-- Written by /implement only, append-only. One "Run" section per /implement run and one block per task, filled from the agents' YAML reports. The stack agents read this file before coding and follow the decisions recorded here; never re-decide something already logged without a scope request. -->

## Run 2026-11-12

Open questions of the spec, resolved by the user before the run: (1) the refactor entry was retitled to "Versioned unittest suite for agent-audit hook" by `backlog-keeper`; (2) `/home/void/dotfiles/CLAUDE.md` is created by `docs-writer` at the end, with `Workflow` and `Test suites`; (3) the four findings were registered by `backlog-keeper` (bugs `2026-11-12-audit-python3-test-commands-not-classified`, `2026-11-12-audit-tests-fail-under-tmp-claude`; refactors `2026-11-12-audit-docs-write-flag-implementers-only`, `2026-11-12-audit-md-exemption-basename`).

### Task 1 - Base da suite: ambiente hermético, _support e divisão do arquivo atual (done)

- **Files:** `.claude/hooks/tests/__init__.py` (hermetic env: `AGENT_AUDIT_DIR` temp dir removed at exit, `GIT_*` vars dropped), `.claude/hooks/tests/_support.py` (new), `.claude/hooks/tests/test_heredoc.py` (new, 12 heredoc classes moved unchanged), `.claude/hooks/tests/test_write_scope.py` (new, `ParallelTasksScope`, `OutsideRepoWrites`, `OutsideRepoHardening` moved), `.claude/hooks/tests/test_agent_audit.py` (removed)
- **Decisions:** `_support.py` exposes `audit`/`metrics`, `HOOKS_DIR`/`CLAUDE_DIR`, `TEST_CONFIG`/`config()`, `assert_not_scratch`/`assert_no_git_root`, `TempRepoCase`, `payload`, `call_main`/`HookResult`, `HookProcess`, `read_jsonl`. `TempRepoCase` patches `audit.SCRATCH_BASES` to `()` by default (`REAL_SCRATCH_BASES = False`) and asserts the repo dir is not scratch; `use_real_scratch_bases()` is idempotent and registered as cleanup (the two scratch-exemption tests use it, after `make_dir()`). `call_main(payload, config=None)` uses `TEST_CONFIG` when config is None and patches `load_config` and `METRICS_DIR` per call. `payload()`: actor `main` has no agent keys, `subagent` has `agent_id` only, any other name has `agent_type` and `agent_id`; `tool_input` defaults to `{}` when a tool is given. `HookProcess` copies `agent-audit.py` and `agent-metrics.py` to `tmp/hook/`; config None means no json file, str means raw content. Later modules import from `._support` (e.g. `from ._support import audit, TempRepoCase, call_main`). Write files with Write/Edit, not Bash heredocs; run python with `-B`.
- **Assumptions:** none
- **Approved scope:** none
- **Migrations / env vars:** none
- **Docs pending:** none
- **Checks:** test-runner (task): 82 tests OK, normal and with `TMPDIR` under a scratchpad `claude-*` dir; no `__pycache__` under `.claude/hooks/tests`. ruff/mypy not installed.

Tasks 2-7 ran in parallel after task 1. Every spec case matched the current hook, config and metrics behavior; none was dropped or changed.

### Task 2 - Classificação de comandos (done)

- **Files:** `.claude/hooks/tests/test_classify.py` (new: `CommandTable` C1-C37, `PrefixesAndSegments` X1-X14)
- **Decisions:** table-driven module-level lists (`COMMAND_TABLE`, `PREFIX_TABLE`), exact equality on (categories, flags) including list order; rows with several commands get one subTest per command under the same case id; only `classify_command` is exercised (`strip_prefixes` indirectly via X1, X3, X8, X13).
- **Assumptions / approved scope / migrations / docs pending:** none

### Task 3 - Áreas de escrita, docs_roots e escopo dentro do repo (done)

- **Files:** `.claude/hooks/tests/test_write_areas.py` (new: `AreaFlags` A1-A9, `DocsRoots` D1-D11), `.claude/hooks/tests/test_write_scope.py` (new class `InRepoScope` S1-S11; docstrings only on six moved tests)
- **Decisions:** `InRepoScope` sets `ALLOWED = {"1": ["services/api/**"]}` and writes the run in `setUp`; S6 two subTests (runs folder missing, only a done run); S7 uses `os.utime`; S8 gives the invalid JSON a newer mtime than the valid run; D11 uses `call_main` with a PostToolUse payload and reads `records[0]["flags"]`. A1 docstring cites `md-outside-docs-false-positive`; the two scratch tests cite `audit-scratch-exemption-too-broad` and the four nested-repo tests cite `audit-nested-repo-run-lookup` ("Pins the behavior accepted today. Refactor: <entry path>").
- **Approved scope:** docstring-only edits to the six moved tests in `test_write_scope.py` (inside the task's allowed_paths; the main session had asked to leave moved classes unchanged and clarified it).
- **Assumptions / migrations / docs pending:** none
- **Out of scope:** Pyright "possibly unbound `out`" in moved `OutsideRepoHardening` tests (`self.fail()` in the except branch is not NoReturn to Pyright).

### Task 4 - decide e main em processo (done)

- **Files:** `.claude/hooks/tests/test_decide.py` (new: `Decide` K1-K12 plus a SEVERITY order test), `.claude/hooks/tests/test_hook_main.py` (new: `Modes`, `Events`, `Actor`, `BashRecords`, `Visual`, `WriteRecords`, `MetricsFile`, E1-E16)
- **Decisions:** E14 uses its own helper patching `audit.METRICS_DIR` directly (`call_main` uses a fresh metrics dir per call); E9 builds the implementer list from `audit.IMPLEMENTERS` plus quality-fixer and test-writer; events mostly checked at PostToolUse (E4 asserts Pre of warn/silent records nothing); E12 and E16 use `TempRepoCase.write_run()`. Only `TEST_CONFIG`/`config()`, never the live config.
- **Assumptions / approved scope / migrations / docs pending:** none

### Task 5 - Regras do DESIGN_SYSTEM.md (casos H) (done)

- **Files:** `.claude/hooks/tests/test_design_system.py` (new: `DesignSystemRules` H1-H28)
- **Decisions:** each case sends Pre and Post through `call_main`; cases sharing a temp repo call `remove_run()` before writing their own run; `approved_scope` entries `{task: 1, target, decision: approved}`; cases with "-" in the spec table skip that assertion; H8 uses `config(mode='audit')`; H14 is a separate test citing `md-outside-docs-false-positive`; H23-H25 assert `assert_no_git_root`.
- **Assumptions / approved scope / migrations / docs pending:** none
- **Note:** agent reported an unused `event_extra` parameter in `_payloads` and an inline import of `assert_no_git_root` (left for review).

### Task 6 - Processo real e contrato do config (done)

- **Files:** `.claude/hooks/tests/test_hook_process.py` (new: `StageGRegression` G1-G11, `ProcessContract` P1-P6), `.claude/hooks/tests/test_config_contract.py` (new: `ConfigContract` F1-F6)
- **Decisions:** one `run_hook` helper asserts exit 0 and empty stderr, `output()` asserts a single JSON line; process tests run the `HookProcess` copy and do not patch `SCRATCH_BASES` (safe: the exemption applies only outside the git root and G7/G8/P6 write inside); P3/P4 check the audit fallback; F5 split in two methods (`re.fullmatch` on the PreToolUse matcher); F6 compares full category sets live == `TEST_CONFIG`. `test_config_contract.py` only reads files.
- **Assumptions / approved scope / migrations / docs pending:** none

### Task 7 - Relatório de métricas (done)

- **Files:** `.claude/hooks/tests/test_agent_metrics.py` (new: `DesignDirectorSection` M1-M5, `ReportSections` R1-R9, `Cli` L1-L7, plus extra edge tests; 29 tests)
- **Decisions:** local helpers (`MetricsCase`, `ev`, `write_event`, `section`) in the module; per-section, per-line assertions (no golden file); `metrics.METRICS_DIR` patched in `setUp`; L2-L5 control recency with `os.utime`.
- **Assumptions / approved scope / migrations / docs pending:** none

**Review (code-reviewer, verdict ship):** 2 minor bugs and 5 standards notes, fixed in the same round by `backend-python` (tasks 1, 4, 5, 6 files):
- `test_hook_main.py`: literal `IMPLEMENTERS`/`READ_ONLY_AGENTS` tuples with `test_e9_actor_sets_match_the_literals_below`; E9 iterates the literals (mutation-checked).
- `test_hook_main.py`: new `WriteFlagOrder.test_flags_are_recorded_sorted` pins `sorted(set(flags))` (frontend-react Write `docs/backlog/x.md` -> Pre warns `backlog_write_by_other`, Post flags `[backlog_write_by_other, docs_write_by_implementer]`; mutation-checked).
- `test_design_system.py`: removed unused `event_extra`, top-level `assert_no_git_root` import, `extra: dict` annotation.
- `test_hook_process.py`: module sentinel `_DEFAULT` instead of the `"default"` string.
- `_support.py`: `call_main(..., metrics_dir=None)` and `write_run_state(root, allowed, **extra)` shared by `TempRepoCase.write_run` and `ProcessCase.write_run`.
- `__init__.py`: also sets `GIT_CONFIG_GLOBAL=os.devnull` and `GIT_CONFIG_NOSYSTEM=1` (in-process git no longer reads the user's or system git config; no test commits, so no identity needed).
- Dismissed: Pyright "possibly unbound `out`" (context managers typed with bool `__exit__`) and unresolved `._support` (IDE root). Suite: 207 tests OK. No blockers, so no second review.

**Checks tasks 2-7:** test-runner (task), 3 runs of the whole `claude-hooks` suite: 205 tests OK each (3.2-3.5 s), one with `TMPDIR` under a scratchpad `claude-*` dir; no flakiness; no `__pycache__` under tests; `~/.claude/metrics` file count unchanged (3); hook, config, metrics and `settings.json` diff empty.
