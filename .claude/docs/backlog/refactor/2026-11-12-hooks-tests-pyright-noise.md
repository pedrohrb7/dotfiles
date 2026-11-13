# hooks tests: Pyright noise (unresolved _support, possibly unbound out)

- **Status:** Proposed
- **Opened:** 2026-11-12
- **Scope:** .claude/hooks/tests/
- **Source:** agent run: audit-hook-test-suite, task 3, backend-python + code-reviewer
- **Related:** [audit-hook-test-suite spec](../../features/audit-hook-test-suite/spec.md)

## Motivation

Pyright reports false problems in the hooks test package, which hides real ones.

## Current state

- `._support` is reported unresolved: the repo has no pyrightconfig or execution root for `.claude/hooks`.
- "`out` possibly unbound" in the moved `OutsideRepoHardening` tests (`test_path_resolution_error_fails_closed_with_actor_flags`, `test_resolution_error_with_active_run_flags_scoped_actor_but_not_main`). `out` is assigned inside a try whose except calls `self.fail()`, inside `subTest`/`mock.patch` context managers typed with a bool `__exit__`. At runtime it is always bound, so the warning is noise.

- Seen again (2026-11-13, code-reviewer, feature skills-docs-root): Pyright reports "rel possibly None" (10 errors) in `.claude/hooks/agent-audit.py` `_assess_root` around lines 604-636. Predates that change (the code only shifted). `rel` cannot be None at runtime, but the `inside` alias plus reassignment defeats narrowing. Scope extends to `agent-audit.py`; fix by restructuring the narrowing there.

## Proposed change

Add a pyright config for `.claude/hooks`, or restructure those tests so the assignment is not inside a try. Needs a choice before a spec.

## Risks

Not recorded.

## Out of scope

Not recorded.
