# agent-audit: parallel tasks' writes flagged out_of_scope_write

- **Status:** Fixed
- **Reported:** 2026-11-11
- **Severity:** medium
- **Environment:** local (Claude Code config, hooks)
- **Source:** feature design-director (stage H), /implement run 2026-11-11, main session, code-reviewer
- **Related:** [design-director spec](../../features/design-director/spec.md)

## Evidence

`.claude/hooks/agent-audit.py:~282-293`; /implement log task 3 note.

## Steps to reproduce

1. Run /implement with tasks executing in parallel, each with distinct `allowed_paths`.
2. Let one task write inside its own allowed paths.

## Expected behavior

A write is checked against the allowed_paths of the task that wrote it.

## Actual behavior

Writes are checked only against `run.current_task`'s `allowed_paths`, so a parallel task's valid writes are flagged `out_of_scope_write`.

## Root cause

`evaluate_write` (`agent-audit.py`) read a scalar `current_task` and checked only that task's `allowed_paths`/`approved_scope`; the same scalar tagged lifecycle records. The hook payload carries no task id and SubagentStart is async, so the hook cannot bind an agent to its task.

## Fix

The run state may carry `running_tasks`. New helper `run_task_keys(run)` returns the valid `running_tasks` entries (str, deduplicated, ordered; malformed shapes and booleans ignored) plus a valid `current_task`. A scoped actor's write is in scope if it matches `allowed_paths` or the approved `approved_scope` of any of those tasks. Records' task is the keys joined with ",".

- `implement/SKILL.md`: set `running_tasks` before a parallel batch; a task leaves it only when marked done (blocked stays listed); a review-fix round sets it to the tasks receiving fixes.
- `fix-bug/SKILL.md`: bug runs stay scalar.
- Accepted trade-off: a running task can write into another running task's paths unflagged.
- Reviewed by code-reviewer (fix first, then ship).

Changed files: `.claude/hooks/agent-audit.py`, `.claude/skills/implement/SKILL.md`, `.claude/skills/fix-bug/SKILL.md`, `.claude/hooks/tests/test_agent_audit.py`.

Regression test: `ParallelTasksScope` in `.claude/hooks/tests/test_agent_audit.py` (23 tests). Suite: `cd .claude/hooks && python3 -m unittest discover -s tests -t .` (50 tests pass).

Verified with a scratch run state (`current_task` 1, `running_tasks` [1,2], `allowed_paths` 1: `services/api/**`, 2: `services/web/**`): a frontend-react Write to `services/web/src/App.tsx` is no longer flagged; without `running_tasks` the scalar behavior is unchanged.
