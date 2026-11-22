# agent-audit: a code string registered by complete -C or bind -x is not read as code

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-stdin-other-sources-family, out_of_scope_collected
- **Related:** [stdin family entries](2026-11-18-audit-exec-stdin-not-followed.md)

## Evidence

- `bind -x '"a":git push'` gives flags [] (maybe also PROMPT_COMMAND).

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

The registered string is analyzed as same-shell code.

## Actual behavior

Not flagged.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
