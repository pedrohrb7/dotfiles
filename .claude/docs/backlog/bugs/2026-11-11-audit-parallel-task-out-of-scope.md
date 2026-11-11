# agent-audit: parallel tasks' writes flagged out_of_scope_write

- **Status:** Open
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

Not diagnosed yet (the evidence points to the single `current_task` lookup).

## Fix

Not fixed yet.
