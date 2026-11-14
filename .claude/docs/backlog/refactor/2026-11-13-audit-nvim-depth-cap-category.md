# agent-audit: nvim nesting depth cap reuses the docker_lifecycle deny

- **Status:** Done (implemented by the spec audit-hook-hardening (2026-11-13); the change is uncommitted and has no PR yet)
- **Spec:** [audit-hook-hardening](../../features/audit-hook-hardening/spec.md)
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py`
- **Source:** agent run: feature lua-agent, code-reviewer and security-reviewer (2026-11-13)

## Motivation

More than 3 nesting levels fail closed with the `docker_lifecycle` deny, so the message is misleading.

## Current state

Today `nested_shell_unclassified` (suggested name) exists only as an audit flag, not a block category.

## Proposed change

Add a dedicated block category, for example `nested_shell_unclassified`, for the depth cap.

## Risks

Not recorded.

## Out of scope

Not recorded.
