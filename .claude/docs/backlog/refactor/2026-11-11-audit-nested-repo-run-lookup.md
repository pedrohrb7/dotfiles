# agent-audit: nested repo cwd does not consult the parent repo's run

- **Status:** Proposed
- **Opened:** 2026-11-11
- **Scope:** `.claude/hooks/agent-audit.py` (`evaluate_write`, run lookup)

## Motivation

A write judged from a session cwd inside a nested repo or submodule uses the nested root only, so the parent repo's active run (and its approved scope) is never consulted. Scope flags may be missed or misapplied there. Source: bug fix outside-git-root, code-reviewer, 2026-11-11 (out of scope of that fix).

## Current state

The governing root is the git root of the session cwd. With a nested repo, the parent's run is not looked up. Accepted for now.

## Proposed change

Not defined. Revisit in the warn->block promotion analysis; may need a spec.

## Risks

Consulting two runs may produce conflicting scopes; the rule for combining them must be decided.

## Out of scope

The scratch exemption (see the scratch-exemption entry).
