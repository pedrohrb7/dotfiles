# agent-audit: timeout parsing limits (locale strtod, nested unknown durations)

- **Status:** Done (implemented by the spec audit-hook-hardening (2026-11-13); the change is uncommitted and has no PR yet)
- **Spec:** [audit-hook-hardening](../../features/audit-hook-hardening/spec.md)
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py`
- **Source:** agent run: feature lua-agent, code-reviewer and security-reviewer (2026-11-13)

## Motivation

The timeout wrapper handling has edge cases that misread commands.

## Current state

- Locale-dependent strtod: `timeout 0,5` under a comma-decimal LC_NUMERIC.
- More than 3 nested unknown-duration timeouts stop adding alternate readings.

- Seen again (2026-11-13, automated security review of commit 5f73e6c, medium): the depth/variant cap is a fail-open path for blocked commands such as docker_lifecycle and git_push.

## Proposed change

Suggested by the security review: fail closed when the depth or variant cap is reached. If ambiguous timeout prefixes remain, or readings were truncated to 8, flag the segment the way `_nvim_nested` does, with the most restrictive category plus a flag such as `prefix_unclassified`. Alternatively, strip repeated timeouts in a loop instead of recursing.

Related: [hook hardening](2026-11-13-audit-hook-hardening.md) (same spec); [heredoc sink bug](../bugs/2026-11-13-audit-heredoc-sink-runs-sh.md).

## Risks

Not recorded.

## Out of scope

Not recorded.
