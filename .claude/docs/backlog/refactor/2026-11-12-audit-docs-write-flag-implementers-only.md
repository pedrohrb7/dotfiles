# agent-audit: docs_write_by_implementer covers only stack implementers

- **Status:** Proposed
- **Opened:** 2026-11-12
- **Scope:** .claude/hooks/agent-audit.py
- **Source:** agent run: audit-hook-test-suite, spec writing, specker

## Motivation

Global rules make docs-writer the only editor of README and docs files, but the hook does not enforce it for every other agent.

## Current state

When quality-fixer or test-writer edit README.md or files under the docs roots, no `docs_write_by_implementer` flag is raised: the flag covers only the stack implementers.

## Proposed change

Extend the flag to all agents except docs-writer. Exact agent set needs confirmation in a spec.

## Risks

New flags may fire on legitimate main-session or backlog-keeper writes; check exemptions.

## Out of scope

Not recorded.
