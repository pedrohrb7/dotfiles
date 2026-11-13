# agent-audit: scratch exemption accepts any /tmp/claude-* dir

- **Status:** Done (implemented by the spec, uncommitted, no PR yet)
- **Opened:** 2026-11-11
- **Spec:** [audit-scratch-exemption](../../features/audit-scratch-exemption/spec.md)
- **Scope:** `.claude/hooks/agent-audit.py` (scratch path check)

## Motivation

The scratch exemption for out-of-repo writes accepts any `<tempdir>/claude-*` or `/tmp/claude-*` directory, including other sessions' scratchpads and agent-created dirs, so a fixed-scope actor can write there without `out_of_scope_write`. Source: bug fix outside-git-root, code-reviewer, 2026-11-11 (out of scope of that fix).

## Current state

Prefix match only. Accepted for now.

## Proposed change

Per the spec (rules B1-B4):

- B1: the exemption applies only strictly inside the session scratchpad given by the payload field `scratchpad_dir`, compared as given and never resolved, or inside an approved absolute glob.
- B2: other sessions' scratchpads and other `/tmp/claude-*` dirs are flagged.
- B3: subagents use the parent session's scratchpad (whatever the payload carries).
- B4: a missing or invalid `scratchpad_dir` gives no exemption: the record gets `scratch: unavailable` and the action stays warn (user decision, 2026-11-12).
- `SCRATCH_BASES` is removed.

## Risks

A stricter rule may flag legitimate scratch use if the session's scratchpad path is not available to the hook. Mitigated by the documented `scratchpad_dir` payload field, plus a metrics line (`agent-metrics.py`, `## Writes`) that tracks `unavailable` hits.

## Out of scope

The nested repo run lookup (see the nested-repo entry).
