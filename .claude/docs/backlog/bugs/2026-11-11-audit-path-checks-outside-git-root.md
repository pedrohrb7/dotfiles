# agent-audit: path checks skip targets outside the git root

- **Status:** Open
- **Reported:** 2026-11-11
- **Severity:** low
- **Environment:** local (Claude Code config, hooks)
- **Source:** feature design-director (stage H), /implement run 2026-11-11, security-reviewer (pre-existing, security)
- **Related:** [design-director spec](../../features/design-director/spec.md)

## Evidence

`.claude/hooks/agent-audit.py:~253-260`.

## Steps to reproduce

1. As a fixed-scope actor, write to a path outside the git root (or in a dir with no git root).

## Expected behavior

The write is treated as out of scope.

## Actual behavior

Path checks return early; no path-based category fires (except design_director_write_outside).

## Root cause

Missing/outside relative path makes the checks return early.

## Fix

Not fixed yet. Idea: for fixed-scope actors, treat missing/outside rel as out of scope.
