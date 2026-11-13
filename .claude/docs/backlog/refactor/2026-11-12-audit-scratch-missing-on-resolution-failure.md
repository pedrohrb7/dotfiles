# agent-audit: out_of_scope_write fallback sets no scratch key

- **Status:** Proposed
- **Opened:** 2026-11-12
- **Scope:** `.claude/hooks/agent-audit.py` (`evaluate_write` except fallback), `.claude/hooks/agent-metrics.py`
- **Source:** feature audit-scratch-exemption, review, code-reviewer, 2026-11-12

## Motivation

When path resolution fails for a fixed-scope actor in a run, the except fallback flags `out_of_scope_write` but sets no `scratch` key. Those writes never appear in the new metrics line (`outside the repo during a run`), so the warn -> block promotion analysis undercounts them.

## Current state

Matches the spec today: a known gap in B7 coverage, not a bug.

## Proposed change

Set `scratch` in the fallback (for example `unavailable`, or a new `error` value) and count it in the metrics line.

## Risks

A new `scratch` value changes the metrics line; keep it consistent with the `unavailable` count.

## Out of scope

Changing the exemption rules B1-B4.
