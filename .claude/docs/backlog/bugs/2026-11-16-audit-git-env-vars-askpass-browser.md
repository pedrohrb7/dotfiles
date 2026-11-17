# agent-audit: env vars SSH_ASKPASS, SSH_ASKPASS_REQUIRE and BROWSER not modeled as program kind

- **Status:** Open
- **Reported:** 2026-11-16
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** automated security review of commit 02a51c3
- **Related:** Follow-up of [git-config-keys entry](2026-11-14-audit-git-config-keys-run-commands.md)

## Evidence

`SSH_ASKPASS`, `SSH_ASKPASS_REQUIRE` and `BROWSER` (program kind) are missing from `_GIT_ENV_VARS`, and their hints from `_GIT_ENV_HINTS`, in `.claude/hooks/agent_audit_classify.py`.

## Steps to reproduce

1. Classify a command using the items above with a blocked command or a write outside scope (synthetic input).

## Expected behavior

Add them as program-kind variables with hints.

## Actual behavior

Allowed, or only an unmatched-token result; no flag.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
