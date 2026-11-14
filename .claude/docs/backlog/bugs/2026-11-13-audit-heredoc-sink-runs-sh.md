# agent-audit: heredoc data-sink misjudged after a command substitution (sh body stripped)

- **Status:** Fixed (implemented by the spec audit-hook-hardening (2026-11-13); the change is uncommitted and has no PR yet)
- **Spec:** [audit-hook-hardening](../../features/audit-hook-hardening/spec.md)
- **Reported:** 2026-11-13
- **Severity:** medium
- **Environment:** local (hook run by Claude Code)
- **Source:** agent run: feature lua-agent, code-reviewer and security-reviewer (2026-11-13); exists in HEAD
- **Related:** [hook hardening refactor](../refactor/2026-11-13-audit-hook-hardening.md), [heredoc docker_lifecycle bug](2026-11-11-audit-heredoc-docker-lifecycle.md)

## Evidence

The `)` that closes a command substitution resets `seg_start`, so `sh -s $(true) cat <<EOF` is judged a `cat` sink and its body is stripped, yet `sh` executes it. Reported by the reviewers; not reproduced by backlog-keeper.

**Seen again (2026-11-13, automated security review of commit 5f73e6c, medium):** same root cause, new angle. `_is_data_sink` reads the prefix through `strip_prefixes`, which returns only the first of the `strip_prefix_variants` readings. A `timeout` prefix whose parse falls back to guessing can make a code-executing command look like a `cat`/`tee`/git/gh sink, so its heredoc body is stripped. Not reproduced by backlog-keeper.

## Steps to reproduce

1. Run `sh -s $(true) cat <<'EOF'` with body `echo RAN-FROM-HEREDOC` and `EOF`.
2. It prints `RAN-FROM-HEREDOC`.

## Expected behavior

The heredoc body is treated as executed code (sink is `sh`), so the hook classifies its lines.

## Actual behavior

The body is stripped as data for `cat`, so commands inside it escape classification.

## Root cause

Not diagnosed yet. Suspect: `seg_start` reset at the `)` closing a command substitution in the heredoc sink detection of `.claude/hooks/agent-audit.py`.

## Fix

Not diagnosed yet. Suggested by the security review (2026-11-13), for the `_is_data_sink` angle:

- Use every reading from `strip_prefix_variants`, and treat the body as data only if every reading has a data-sink head.
- Return False when the `timeout` parse falls back (`_timeout_duration_index` returns None, or the duration is invalid).
- Return False when any prefix token contains `$`, since the shell expands it.
- In short, never strip a heredoc body unless the prefix parsed cleanly.
