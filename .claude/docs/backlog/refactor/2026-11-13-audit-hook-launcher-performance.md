# agent-audit: hook compiled on every call (launcher with cached bytecode)

- **Status:** Proposed
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py`, probably `.claude/settings.json`
- **Source:** specker, feature audit-hook-hardening (2026-11-13)

## Motivation

Per-call latency, and the slow `claude-hooks` process tests (see [suite slow](2026-11-13-hooks-tests-suite-slow.md)).

## Current state

The live hook runs as a script, so its roughly 1375 lines are compiled on every tool call: 17 ms measured, out of a 74 ms median per call.

## Proposed change

A small launcher that imports a module with cached bytecode. It would cut per-call latency and about 1 s from the `claude-hooks` process tests. It changes the hook layout and probably `settings.json`, so it needs its own decision.

## Risks

Stale or unwritable bytecode cache; hook self-protection paths must cover the new module.

## Out of scope

Hook logic changes.
