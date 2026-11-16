# agent-audit: a group or subshell reading a pipe is not flagged

- **Status:** Fixed
- **Reported:** 2026-11-14
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: feature audit-shell-lexer, security-reviewer
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Evidence

- `echo 'git push' | { bash; }` gives only the canary (level A), no `git push` ask.

## Steps to reproduce

1. Classify `echo 'git push' | { bash; }` through `analyze_command` or the hook with synthetic JSON (no real execution).
2. Repeat with a subshell receiver.

## Expected behavior

A shell reading code from a pipe inside a group or subshell is treated like `... | bash`: the piped text is classified (`git push`).

## Actual behavior

Only the canary is recorded; the command is allowed.

## Root cause

`_stdin_code` (`.claude/hooks/agent_audit_classify.py`) flagged `piped_shell` only for `site.stage > 0`. `_walk` (`.claude/hooks/agent_audit_shell.py`) recurses into compound bodies as new scripts whose pipeline index restarts at 0, and `Site` had no field for inherited piped stdin, so `echo x | { bash; }` and similar were allowed.

## Fix

Fixed 2026-11-16 (user decisions), not committed yet. Changed: `.claude/hooks/agent_audit_shell.py`, `.claude/hooks/agent_audit_classify.py`, `.claude/hooks/tests/test_command_positions.py`, `.claude/hooks/tests/test_shell_lexer.py`.

- `Site.piped` is threaded through `_walk`; per-fd stdin state (`_fd_states`, `stdin_piped`, `fd_piped`): redirects are read left to right; under a pipe only a heredoc or here-string replaces the pipe, a file redirect never does (fail closed against stdin aliases); unknown fds inherit; `N<&M` copies; `<&-` keeps the pipe.
- Compound bodies are piped if any fd holds the pipe; function and coproc bodies do not inherit. Substitutions in a simple command's words, here-strings, heredoc bodies and redirect targets read the pipe. `_stdin_code` no longer returns early.
- Accepted false positives: `cmd | bash < script.sh`, `cmd | while read l; do sh; done < list`.
- Regression tests: `tests/test_command_positions.py` class `ReviewFixB1` (a shell in a group fed by a pipe, a redirect that keeps the pipe, a substitution in a piped command, a process substitution after a file redirect, a file redirect under a pipe, paths and descriptors that name the pipe, and the not-blocked tests) and `tests/test_shell_lexer.py` class `PipedStdin`.
- Checks: full claude-hooks suite 846 OK; code-reviewer and security-reviewer, 3 rounds; final security verdict safe.
