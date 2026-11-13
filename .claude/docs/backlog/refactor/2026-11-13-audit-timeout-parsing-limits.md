# agent-audit: timeout parsing limits (locale strtod, nested unknown durations)

- **Status:** Proposed
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py`
- **Source:** agent run: feature lua-agent, code-reviewer and security-reviewer (2026-11-13)

## Motivation

The timeout wrapper handling has edge cases that misread commands.

## Current state

- Locale-dependent strtod: `timeout 0,5` under a comma-decimal LC_NUMERIC.
- More than 3 nested unknown-duration timeouts stop adding alternate readings.

## Proposed change

Not recorded.

## Risks

Not recorded.

## Out of scope

Not recorded.
