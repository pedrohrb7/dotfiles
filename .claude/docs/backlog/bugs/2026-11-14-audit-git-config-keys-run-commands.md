# agent-audit: git config keys that execute commands are not modeled (and cross-call aliases)

- **Status:** Open
- **Reported:** 2026-11-14
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: feature audit-shell-lexer, security-reviewer (out of scope of the closing round)
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Evidence

- Keys not modeled: `core.pager`, `core.sshCommand`, `core.fsmonitor`, `credential.helper`, `diff.external`, set through `-c`, `GIT_CONFIG_*` or `git config`.
- Cross-call alias: `git config alias.c commit` then `git c -m x` is a silent commit (aliases are resolved only within one text).

## Steps to reproduce

1. Classify `git -c core.pager=<cmd> log` with a blocked command as the value.
2. Classify `git config alias.c commit` and, in a later call, `git c -m x`.

## Expected behavior

A key whose value runs a program is classified like code, and the alias makes `git c` a `git_commit` ask.

## Actual behavior

Allowed, nothing flagged (the alias case is a silent commit).

## Root cause

Value-running keys are outside the model; aliases are known only within one text.

## Fix

Not fixed yet.
