# agent-audit: a pipe into a code string (eval, bash -c) is not followed

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-pipe-procsub-stdin-family, reviewers (see Evidence)
- **Related:** [pipe-readers entry](2026-11-16-audit-pipe-readers-not-piped-shell.md)

## Evidence

Reviewers of the fix (pre-existing). `_code_text` / `analyze_command` carry no stdin state, so these pass:
- `echo 'git push' | eval bash`, `echo x | bash -c bash`, `echo x | sh -c 'bash'`
- `echo x | eval "{ bash; }"`, `f() { bash; }; echo x | eval f`
- `| builtin eval f`, `| { eval f; }`, `eval f < <(x)`

All via `analyze_command` on synthetic strings (nothing executed), flags `[]` for the passing forms.

## Steps to reproduce

1. Classify each command above.

## Expected behavior

The code string inherits the pipe or procsub stdin, so the inner shell reading it is classified like `| bash`.

## Actual behavior

Not flagged.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
