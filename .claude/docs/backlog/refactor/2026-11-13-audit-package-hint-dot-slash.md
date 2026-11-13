# agent-audit: PACKAGE_HINT treats ./spec and ./tests as package paths

- **Status:** Proposed
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py` (`PACKAGE_HINT`); metrics only
- **Source:** agent run: feature lua-agent, code-reviewer and security-reviewer (2026-11-13)

## Motivation

Inconsistent metrics: `busted ./spec` is test-package while `busted spec` is test-full; same for `pytest ./tests`.

## Current state

`./spec` and `./tests` count as a package path.

## Proposed change

Normalize the leading `./` before the hint.

## Risks

Not recorded.

## Out of scope

Not recorded.
