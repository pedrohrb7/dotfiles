# agent-audit: the stdin facts pass lacks function positional values and exported GIT_CONFIG_*

- **Status:** Fixed
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-stdin-other-sources-family, security re-review, round 7
- **Related:** [stdin facts refactor](../refactor/2026-11-18-audit-stdin-facts-from-main-analysis.md)

## Evidence

- `f() { $1 -c 'mk""fifo p'; }; f sh; bash < p` passes (positional values of function calls are not known to the facts pass).
- `export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.x GIT_CONFIG_VALUE_0='!mk""fifo p'; git x; bash < p` passes (GIT_CONFIG_* is read only from the command's own assignments, not from an earlier export).

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

Both forms are flagged: the fifo is found and `bash < p` reads code.

## Actual behavior

Flags are empty.

## Root cause

A separate facts pass (`_stdin_facts` / `_nested_facts`) re-implemented resolution and diverged from the main analysis (positional values of function calls, exported GIT_CONFIG_*); see the linked refactor.

## Fix

Fixed 2026-11-19 (not committed yet) by feature [audit-stdin-facts](../../features/audit-stdin-facts/spec.md): the facts are derived from the main analysis (fixed point), so there is one resolution. Regression tests in `.claude/hooks/tests/test_stdin_facts.py`: classes StdinFactsFromAnalysis, NestedEqualsInline and ResolverReads.
