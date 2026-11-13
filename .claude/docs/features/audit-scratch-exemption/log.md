# Implementation log - audit-scratch-exemption

<!-- Written by /implement only, append-only. One "Run" section per /implement run and one block per task, filled from the agents' YAML reports. The stack agents read this file before coding and follow the decisions recorded here; never re-decide something already logged without a scope request. -->

## Run 2026-11-12

Open questions of the spec, resolved by the user before the run: (1) missing or invalid `scratchpad_dir` -> no exemption, record `scratch: unavailable`, action stays `warn` (option a; no derived-path or old-prefix fallback); (2) the refactor entry is linked to the spec and moved to In progress by `backlog-keeper`.

### Task 1 - Isenção de scratch pelo scratchpad_dir do payload (done)

- **Files:** `.claude/hooks/agent-audit.py` (`SCRATCH_BASES`, `tempfile`, `fnmatch` removed; `session_scratchpad()`, `is_scratch(target, scratchpad)`, `evaluate_write(..., scratchpad=)`, `scratch` record field, `main()` wiring), `.claude/hooks/tests/_support.py` (removed the `SCRATCH_BASES` patch, `REAL_SCRATCH_BASES`, `use_real_scratch_bases()`, `assert_not_scratch()`; added `make_scratchpad()` and `scratchpad=` on `eval_at()` and `payload()`), `.claude/hooks/tests/test_write_scope.py` (two old tests removed; `SessionScratchpad` SC1-SC17), `.claude/hooks/tests/test_hook_main.py` (`ScratchpadPayload` SC18-SC19), `.claude/hooks/tests/test_hook_process.py` (SC20)
- **Decisions:** tests pass `scratchpad_dir` as `str(sp)` like the real payload (SC17: a non-str value gives None); `evaluate_write`'s `scratchpad` parameter typed `object` since `session_scratchpad` validates it; the `scratch` key is set only in the outside-repo branch for fixed-scope actors with an active run (the except fallback adds none); `make_scratchpad()` resolves the temp base because Claude Code's value is realpath'd; SC19 checks the `scratchpad_dir` value is not stored as a record value or key (the target's own rel/path legitimately contain it); SC4 also runs a literal `/tmp/claude-audit-test-<uuid>` subTest (skips if `/tmp` is not writable).
- **Assumptions / approved scope / migrations / env vars:** none
- **Docs pending:** `.claude/README.md` hooks section (scratch definition, `scratch` field, report line, `_support` API changes); `.claude/agent-workflow.md` 13.7 (scratch definition).
- **Checks:** test-runner (task): 226 tests OK, normal (5.1 s wall) and with `TMPDIR` under a scratchpad `claude-*` dir (6.1 s wall); hook config, metrics and `settings.json` unchanged; no `__pycache__` under tests. Note: the suite is now over the 5 s target of the audit-hook-test-suite spec (later attributed to machine load by code-reviewer: 3.4-4.1 s on an idle machine; the 22 new tests cost about 0.4 s).

### Task 2 - Linha de scratch no relatório de métricas (done)

- **Files:** `.claude/hooks/agent-metrics.py` (`SCRATCH_LABELS`; scratch line inside the `## Writes` block, right after the totals line), `.claude/hooks/tests/test_agent_metrics.py` (R10)
- **Decisions:** the line uses the write records (categories == ["write"]) outside `PreToolUse`; records with any other `scratch` value are ignored.
- **Assumptions / approved scope / migrations / env vars / docs pending:** none
- **Checks:** test-runner (task): 227 tests OK, normal and with `TMPDIR` under a scratchpad `claude-*` dir; `agent-audit.json` and `settings.json` unchanged.

**Review:** security-reviewer verdict safe (no bypass found; prefix collisions, symlinks, `..`, invalid `scratchpad_dir`, errors all fail closed; unverified: subagent payloads carrying `scratchpad_dir` in a real run, a Pre/Post TOCTOU that only matters if `out_of_scope_write` is promoted to block, and `scratchpad_dir` trusted as given). code-reviewer verdict ship, 2 minor findings plus 1 question, fixed in the same round by `backend-python`:
- `test_hook_process.py` SC20 builds `sp` from `self.tmp.resolve()`.
- `test_write_scope.py` SC16 asserts `scratch` per subTest (`no-match` for the glob-approved target, `match` for the sp target).
- User decision on the reviewer's question: the "elsewhere" bucket is split. Line: `- outside the repo during a run: N (session scratchpad: a; approved glob: g; out of scope: o; no scratchpad known: c)`; `g` = `no-match` without `out_of_scope_write` in flags (a missing `flags` key counts as without), `o` = `no-match` with it. Recorded in the spec as the 2026-11-12 addendum (by `specker`).
- R10 rewritten around a typed local helper `w(rel, event, scratch, flags)` (fixes the Pyright `str | bool` warnings). It is a superset of the addendum's R10: it adds a `no-match` record without a `flags` key, so it expects `6 (session scratchpad: 2; approved glob: 2; out of scope: 1; no scratchpad known: 1)` instead of the addendum's `5 (2; 1; 1; 1)`; it also checks that the `PreToolUse` record is excluded and that `unavailable` with `out_of_scope_write` counts in `c`.
- No blockers, so no second review.
