# agent-audit: unquoted heredoc body with command substitution is stripped as data

- **Status:** Fixed (rule HD2 of the audit-shell-lexer spec, uncommitted, 2026-11-14)
- **Reported:** 2026-11-13
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** specker, feature audit-shell-lexer, 2026-11-13; pre-existing at HEAD eee112a
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md) (rule HD2), [audit-shell-lexer](../refactor/2026-11-13-audit-shell-lexer.md)

## Evidence

Both classify as `(['other'], [])`:

- `cat <<EOF` + `$(docker restart x)` + `EOF`
- `cat > f <<EOF` + a backtick `git push` + `EOF`

## Steps to reproduce

1. Classify a command whose heredoc for cat/tee has an unquoted delimiter and a body holding `$(docker restart x)`.
2. Repeat with a backtick `git push` in the body of `cat > f <<EOF`.

## Expected behavior

The body is not data: the shell executes `$(...)` and backticks in an unquoted heredoc, so the inner commands are classified (`docker_lifecycle`, `git push`).

## Actual behavior

The body is stripped as data and nothing is flagged.

## Root cause

The heredoc stripping for cat/tee ignores whether the delimiter is quoted. Not otherwise diagnosed.

## Fix

Fixed by rule HD2 ("heredoc by receiver") of the [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md): an unquoted delimiter body is read for `$(...)` and backticks. Gate 811 tests green; see the [log](../../features/audit-shell-lexer/log.md). Uncommitted.
