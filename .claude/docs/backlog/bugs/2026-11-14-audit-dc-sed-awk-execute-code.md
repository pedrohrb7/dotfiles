# agent-audit: dc, GNU sed e and awk system() execute commands without classification

- **Status:** Open
- **Reported:** 2026-11-14
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: feature audit-shell-lexer, security-reviewer
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Evidence

- `dc` runs `!cmd` read from stdin.
- GNU sed `e` and `s///e`, and awk `system()`, in arguments or in stdin scripts, are not classified.
- `sed -nf/dev/stdin <<< ...` misses the data-reader check because of the `-nf` cluster.

## Steps to reproduce

1. Classify `dc` with a here-string `!<cmd>` holding a blocked command.
2. Classify sed `e`, `s///e`, awk `system()` and `sed -nf/dev/stdin <<< ...` (synthetic JSON only).

## Expected behavior

These interpreters' code is classified, or the call is level B.

## Actual behavior

Allowed; the here-string is treated as data for the `-nf` form.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.

## Seen again (2026-11-14)

Source: automated security review of commit 5a47cc4 (feature audit-shell-lexer), `agent_audit_classify.py`.

Data-reader angle: sed, awk and gawk are in `_STDIN_DATA`, so a here-string fed to them is treated as data. A sed script with an `e` command or `s///e` flag, or an awk program with `system(`, `|` pipes or `cmd | getline`, executes the data fed on stdin.

Suggested fix: treat the stdin as data only when the program cannot run commands, else as code or level B; or remove sed/awk/gawk from `_STDIN_DATA`.
