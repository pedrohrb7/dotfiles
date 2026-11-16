# agent-audit: git subcommands that run shell code are not read as code

- **Status:** Open
- **Reported:** 2026-11-16
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix of audit-pipe-into-group-not-flagged, reviewers
- **Related:** [pipe-into-group entry](2026-11-14-audit-pipe-into-group-not-flagged.md)

## Evidence

- `filter-branch --*-filter` (any unique prefix, `=value` or next word), `bisect run <cmd...>`, `submodule foreach <code>`, `difftool`/`mergetool -x/--extcmd/--tool-cmd`.
- Source: automated security review of commit 7a4e1e5.

## Steps to reproduce

1. Classify each form above with a blocked command as the code (synthetic input).

## Expected behavior

The code is read like `rebase -x` (`_git_exec_code`), or the result is unresolved (level B).

## Actual behavior

Allowed, the code is not classified.

## Root cause

Not diagnosed yet; `rebase -x` is already handled in `_git_exec_code`.

## Fix

Not fixed yet.
