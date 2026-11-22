# agent-audit: code fed through xargs to a git code option, and variable clone URLs, get no flag

- **Status:** Open
- **Reported:** 2026-11-16
- **Severity:** low
- **Environment:** local (Claude Code hooks)
- **Source:** automated security review of the git-subcommands fix
- **Related:** Related: [git-subcommands entry](2026-11-16-audit-git-subcommands-run-shell-code.md)

## Evidence

`echo CODE | xargs git difftool -x` (same for `rebase -x`) gets only deny_token_unmatched. `git clone "$U" d` and `git clone "ext::$P" d` (variable URL) get no flag; ext is blocked by git's default protocol policy unless the user's gitconfig allows it. Pre-existing.

## Steps to reproduce

1. Classify a command using the items above with a blocked command or a write outside scope (synthetic input).

## Expected behavior

Flag the xargs-fed code option; treat a dynamic clone URL in transport verbs as level B.

## Actual behavior

Allowed, or only an unmatched-token result; no flag.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
