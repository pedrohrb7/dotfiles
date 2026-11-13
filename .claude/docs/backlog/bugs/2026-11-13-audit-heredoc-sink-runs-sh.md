# agent-audit: heredoc data-sink misjudged after a command substitution (sh body stripped)

- **Status:** Open
- **Reported:** 2026-11-13
- **Severity:** medium
- **Environment:** local (hook run by Claude Code)
- **Source:** agent run: feature lua-agent, code-reviewer and security-reviewer (2026-11-13); exists in HEAD
- **Related:** [hook hardening refactor](../refactor/2026-11-13-audit-hook-hardening.md), [heredoc docker_lifecycle bug](2026-11-11-audit-heredoc-docker-lifecycle.md)

## Evidence

The `)` that closes a command substitution resets `seg_start`, so `sh -s $(true) cat <<EOF` is judged a `cat` sink and its body is stripped, yet `sh` executes it. Reported by the reviewers; not reproduced by backlog-keeper.

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

Not diagnosed yet.
