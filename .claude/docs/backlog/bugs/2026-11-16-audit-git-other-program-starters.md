# agent-audit: other git programs that start arbitrary programs are not modeled (svn --authors-prog, hook run, submodule update=!cmd)

- **Status:** Open
- **Reported:** 2026-11-16
- **Severity:** low
- **Environment:** local (Claude Code hooks)
- **Source:** automated security review of the git-subcommands fix
- **Related:** Related: [git-subcommands entry](2026-11-16-audit-git-subcommands-run-shell-code.md)

## Evidence

Not modeled: `git svn --authors-prog`, `git hook run` (runs configured hooks), and `submodule.<n>.update=!cmd` written directly in `.git/config` (a file edit; check overlap with the existing write-scope entries, e.g. [hook self-protection](2026-11-11-audit-hook-self-protection.md)). Pre-existing.

## Steps to reproduce

1. Classify a command using the items above with a blocked command or a write outside scope (synthetic input).

## Expected behavior

Add them to `_GIT_CODE_OPTIONS` or level B; settle the `.git/config` write case against the write-scope entries.

## Actual behavior

Allowed, or only an unmatched-token result; no flag.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
