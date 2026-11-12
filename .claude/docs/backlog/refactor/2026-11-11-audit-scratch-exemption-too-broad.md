# agent-audit: scratch exemption accepts any /tmp/claude-* dir

- **Status:** Proposed
- **Opened:** 2026-11-11
- **Scope:** `.claude/hooks/agent-audit.py` (scratch path check)

## Motivation

The scratch exemption for out-of-repo writes accepts any `<tempdir>/claude-*` or `/tmp/claude-*` directory, including other sessions' scratchpads and agent-created dirs, so a fixed-scope actor can write there without `out_of_scope_write`. Source: bug fix outside-git-root, code-reviewer, 2026-11-11 (out of scope of that fix).

## Current state

Prefix match only. Accepted for now.

## Proposed change

Not defined. Likely restrict to the current session's scratchpad directory. Revisit in the warn->block promotion analysis; may need a spec.

## Risks

A stricter rule may flag legitimate scratch use if the session's scratchpad path is not available to the hook.

## Out of scope

The nested repo run lookup (see the nested-repo entry).
