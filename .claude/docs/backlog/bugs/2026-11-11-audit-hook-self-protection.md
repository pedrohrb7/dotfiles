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

## Note (2026-11-13)

The protection must also cover the new module file `.claude/hooks/agent_audit_shell.py` (added by [audit-shell-lexer](../../features/audit-shell-lexer/spec.md)).

## Note (2026-11-14, audit-shell-lexer, security-reviewer)
- The protection must also cover `.claude/hooks/agent_audit_classify.py` (new) next to `agent_audit_shell.py`, and `.claude/hooks/__pycache__/`.
- A planted checked-hash `.pyc` carrying the current source hash is served: PEP 552 checks staleness, not integrity. `__pycache__` is gitignored, so a planted file never shows in `git status`.
- Fixed part: a `BaseException` (`SystemExit`, `KeyboardInterrupt`) at module import now fails closed (`classifier_error` for Bash, file writes still checked).
- Observation: a Write to `$HOME/.claude/hooks/agent-audit.py` under a scratch HOME got no decision from the hook.
- A stray `.claude/hooks/__pycache__/agent-audit.json` (13 Nov 19:43) of unknown origin exists.
Source: [log](../../features/audit-shell-lexer/log.md).
