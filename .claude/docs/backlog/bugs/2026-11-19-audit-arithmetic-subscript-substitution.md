# agent-audit: unquoted data in arithmetic or name-taking builtins can run a subscript substitution

- **Status:** Open
- **Reported:** 2026-11-19
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-regex-and-tables-46ae3a7, out_of_scope_collected (pre-existing)
- **Related:** none

## Evidence

- `let "$(cat f)"` passes. Same family: `(( ))`, `$(( ))`, `[[ -v ]]`, `test -v`, `declare`, `unset`, `typeset -i` (pre-existing; unverified for zsh).

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

Tainted data in these positions fails closed (array subscript `a[$(cmd)]` runs cmd).

## Actual behavior

No flag.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
