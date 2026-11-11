# agent-audit: heredoc body lines classified as commands (false docker_lifecycle)

- **Status:** Open
- **Reported:** 2026-11-11
- **Severity:** medium
- **Environment:** local (Claude Code config, hooks)
- **Source:** feature design-director (stage H), /implement run 2026-11-11, backend-python
- **Related:** [design-director spec](../../features/design-director/spec.md)

## Evidence

`classify_command` in `.claude/hooks/agent-audit.py`; /implement log task 1 note.

## Steps to reproduce

1. Run a Bash heredoc that writes a file containing a line `docker compose ... restart` or `up`.

## Expected behavior

The heredoc body is data and is not classified.

## Actual behavior

The command is denied as `docker_lifecycle`.

## Root cause

Lines inside a heredoc body are classified as if they were commands.

## Fix

Not fixed yet.
