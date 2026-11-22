# agent-audit: time and ! after a pipe are not parsed (lex_error, fail closed)

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** low
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-pipe-procsub-stdin-family, reviewers (see Evidence)
- **Related:** [pipe-readers entry](2026-11-16-audit-pipe-readers-not-piped-shell.md)

## Evidence

Noise, not a bypass: `echo x | time bash` and `echo x | ! bash` give lex_error (fail closed).

All via `analyze_command` on synthetic strings (nothing executed), flags `[]` for the passing forms.

## Steps to reproduce

1. Classify each command above.

## Expected behavior

`time` and `!` after `|` are parsed, and the pipeline is classified like `| bash`.

## Actual behavior

lex_error.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
