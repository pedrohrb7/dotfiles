# agent-audit: path checks skip targets outside the git root

- **Status:** Fixed
- **Reported:** 2026-11-11
- **Severity:** low
- **Environment:** local (Claude Code config, hooks)
- **Source:** feature design-director (stage H), /implement run 2026-11-11, security-reviewer (pre-existing, security)
- **Related:** [design-director spec](../../features/design-director/spec.md)

## Evidence

`.claude/hooks/agent-audit.py:~253-260`. Reproduction also showed a read-only agent (code-reviewer) writing outside the repo was not denied.

## Steps to reproduce

1. As a fixed-scope actor, write to a path outside the git root (or in a dir with no git root).
2. As a read-only agent (code-reviewer), write to a path outside any repo.

## Expected behavior

The write is treated as out of scope; a read-only agent's write is denied.

## Actual behavior

Path checks return early; no path-based category fires (except design_director_write_outside). The block category write_by_readonly_agent was skipped too.

## Root cause

`evaluate_write` returned early when the target had no git root, skipping every flag (including the block category `write_by_readonly_agent`) and the run lookup. The root was taken from the target instead of the session cwd, and a `relative_to` failure fell through with an absolute rel.

## Fix

Changed files: `.claude/hooks/agent-audit.py`, `.claude/hooks/tests/test_agent_audit.py`.

- Governing root = git root of the session cwd (fallback: the target's root); a nested target repo is judged by both roots (union).
- Target resolved, "~" expanded, ".." judged in resolved and lexical forms; outside targets get area "outside" and an absolute rel.
- Actor-only flags are computed first and for any path (DESIGN_SYSTEM.md by raw or resolved name); area flags only inside the repo.
- Fixed-scope actors in a run get `out_of_scope_write` outside the repo, unless a literal absolute approved glob (~ expanded, no realpath) matches or the path is scratch (`<tempdir>/claude-*` or `/tmp/claude-*`).
- Resolution errors fail closed.
- Three rounds with code-reviewer (ship) and security-reviewer (round 2 medium on glob realpath widening, fixed in round 3).

Regression tests: `OutsideRepoWrites` and `OutsideRepoHardening` in `.claude/hooks/tests/test_agent_audit.py` (suite 82 tests, `cd .claude/hooks && python3 -m unittest discover -s tests -t .`).

## Verification

Hook payloads: code-reviewer Write outside any repo -> deny (write_by_readonly_agent); backend-node Write outside repo and scratch with an active run -> out_of_scope_write; scratchpad write -> no flag.
