# Write-capable agents can disable or rewrite the audit hook and agent definitions

- **Status:** Open
- **Reported:** 2026-11-11
- **Severity:** medium
- **Environment:** local (Claude Code config, hooks)
- **Source:** feature design-director (stage H), /implement run 2026-11-11, security-reviewer (pre-existing, security)
- **Related:** [design-director spec](../../features/design-director/spec.md)

## Evidence

`.claude/settings.json` allows `Edit(~/.claude/**)` and `Edit(~/dotfiles/.claude/**)` without a prompt; only `settings*.json` is in `ask`. The hook does not flag writes to its own files.

## Steps to reproduce

1. As a write-capable agent, edit `.claude/hooks/agent-audit.json` to set mode `off`, or write invalid JSON (falls back to audit), or edit `agent-audit.py` / `agents/*.md`.

## Expected behavior

Such edits prompt the user, or are blocked for non-main actors.

## Actual behavior

The edits succeed silently.

## Root cause

Permissive Edit allow rules and no self-protection category in the hook.

## Fix

Not fixed yet. Idea: `ask` for `hooks/` and `agents/` dirs, plus a block category for non-main writes under `.claude/hooks/` and `.claude/agents/`.
