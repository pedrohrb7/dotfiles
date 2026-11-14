# agent-audit: active_run crashes on a run state that is not a JSON object

- **Status:** Fixed (implemented by the spec audit-hook-hardening (2026-11-13); the change is uncommitted and has no PR yet)
- **Spec:** [audit-hook-hardening](../../features/audit-hook-hardening/spec.md)
- **Reported:** 2026-11-12
- **Severity:** medium
- **Environment:** local (hook run by Claude Code)
- **Source:** agent run: audit-md-outside-docs, code-reviewer (2026-11-13); predates that change
- **Related:** [audit-md-outside-docs](../../features/audit-md-outside-docs/spec.md)

## Evidence

`.claude/hooks/agent-audit.py:530`, in `active_run`: `data.get("phase")` runs outside the `try`, so a valid JSON that is not an object (a list, a string, a number) raises `AttributeError`. Found by code review; not reproduced by the keeper.

## Steps to reproduce

1. In a repo, write `.claude/runs/x.json` containing `[]`.
2. Do any Write/Edit in that repo.
3. `evaluate_write` raises `AttributeError` and falls into the fail-closed branch.

## Expected behavior

A run state that is not an object is ignored, the same way invalid JSON is.

## Actual behavior

Every write in that repo hits the fail-closed branch: area is outside, and `md_outside_docs`, `docs_write_by_implementer` and `backlog_write_by_other` are lost for every actor.

## Root cause

Not diagnosed beyond the unguarded `.get` on a non-dict (see Evidence).

## Fix

Not fixed yet.
