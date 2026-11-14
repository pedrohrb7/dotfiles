# agent-audit: hook compiled on every call (launcher with cached bytecode)

- **Status:** Done (overtaken by audit-shell-lexer part C, 2026-11-14)
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

## Decision and note (2026-11-13)

User decision: this gets its own spec right after [audit-shell-lexer](2026-11-13-audit-shell-lexer.md). The lexer spec loads its parser as a sibling module through the source loader with cached bytecode, so the launcher can reuse that mechanism. Compile cost is now 27 ms of the hook call (1984 lines).

## Facts after audit-shell-lexer (2026-11-14, no decision taken)
- The classifier moved to the cached sibling module `.claude/hooks/agent_audit_classify.py` (3,263 lines), next to `agent_audit_shell.py`; both are loaded by a path-based `_load_module` with a checked-hash `.pyc` (PEP 552) before any fork.
- The hook script now compiles about 1.1k lines (1,118), down from 4,178 before the classifier split.
- Process latency median about 70 ms (67.8 ms after the split) vs 84-88 ms at eee112a.
- The suite still takes about 10-11 s for 811 tests (see [suite slow](2026-11-13-hooks-tests-suite-slow.md)).
- The user has not decided whether this entry is still needed. Source: [log](../../features/audit-shell-lexer/log.md). Self-protection of the new modules and `__pycache__`: [self-protection bug](../bugs/2026-11-11-audit-hook-self-protection.md).

## Closed (2026-11-14)
User decision: closed as Done, overtaken by audit-shell-lexer part C (spec A13/A25/A29). The classifier moved to the cached sibling module `agent_audit_classify.py` (checked-hash `.pyc`), the hook script compiles about 1.1k lines, and the hook process median is about 70 ms vs about 88 ms at eee112a. The remaining suite time belongs to [suite slow](2026-11-13-hooks-tests-suite-slow.md).
