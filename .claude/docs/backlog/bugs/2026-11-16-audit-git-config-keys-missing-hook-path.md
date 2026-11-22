# agent-audit: git config keys gc.recentObjectsHook and man.<tool>.path not modeled

- **Status:** Open
- **Reported:** 2026-11-16
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** automated security review of commit 02a51c3
- **Related:** Follow-up of [git-config-keys entry](2026-11-14-audit-git-config-keys-run-commands.md)

## Evidence

Value-running config keys still missing from the config rules: `gc.recentObjectsHook`, `man.<tool>.path`; section `gc` is not covered. (`instaweb.httpd` is already covered by the pattern near line 929 and the instaweb level B of the git-subcommands fix.)

## Steps to reproduce

1. Classify a command using the items above with a blocked command or a write outside scope (synthetic input).

## Expected behavior

Add the keys and the `gc` section; consider deny-by-default for unknown keys ending in cmd/command/hook/program/path/helper.

## Actual behavior

Allowed, or only an unmatched-token result; no flag.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
