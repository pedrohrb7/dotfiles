# agent-audit: duplicate `_EXPANSION` breaks `_head_is_dynamic` for double-quoted path heads (fail open)

- **Status:** Fixed (2026-11-19, not committed)
- **Reported:** 2026-11-18
- **Severity:** high
- **Environment:** local
- **Source:** agent run: audit-stdin-facts, specker (spec open question 5), confirmed by the main session against both commits
- **Related:** [audit-stdin-facts spec](../../features/audit-stdin-facts/spec.md); regression from commit 46ae3a7 (round 4 of the stdin family fix)

## Evidence

`.claude/hooks/agent_audit_classify.py` defines `_EXPANSION` twice:

- line 3440: `_EXPANSION = re.compile(r"[$`]")`, used at line 3481 by `_head_is_dynamic`.
- line 5320: `_EXPANSION = re.compile(r"\$\{[^}]*\}|\$[A-Za-z_]\w*")`, used at lines 5332 and 5461 (expansion-stripped heads).

The second definition, added by 46ae3a7, overrides the first at import time, so `$(`, backticks and `$1` are no longer seen by `_head_is_dynamic`.

`analyze_command` on synthetic strings (nothing executed):

- `"/usr/bin/$1" restart x`: flags [] and uncertainty [] at 46ae3a7; unclassified_command + dynamic_code at 571d2b8.
- `bash -c '"/usr/bin/$(printf docker)" restart x'`: only the level-A canary at 46ae3a7; unclassified_command + dynamic_code at 571d2b8.

## Steps to reproduce

1. Call `analyze_command` with `"/usr/bin/$1" restart x` at HEAD (46ae3a7).
2. Call it with `bash -c '"/usr/bin/$(printf docker)" restart x'`.
3. Compare with the same calls at 571d2b8.

## Expected behavior

A double-quoted path head containing `$(`, a backtick or `$1` is dynamic: unclassified_command + dynamic_code, as at 571d2b8.

## Actual behavior

No flags and no uncertainty (fail open) for the first string; only the canary for the second.

## Root cause

Name collision: the round-4 regex in `agent_audit_classify.py` rebound the module-level `_EXPANSION` that `_head_is_dynamic` uses.

## Fix

Renamed the round-4 regex to `_STRIPPABLE_EXPANSION`, added a source test that `_EXPANSION` is bound once, and made path-prefixed substitution heads level B (fail closed). Fix run: .claude/runs/bug-audit-regex-and-tables-46ae3a7.json. Gate: 1145 tests pass. Not committed yet.
