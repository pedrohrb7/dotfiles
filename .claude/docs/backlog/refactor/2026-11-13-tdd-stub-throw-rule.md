# tdd skill: step 2 allows not-implemented throws, step 4 requires assertion failures

- **Status:** Proposed
- **Opened:** 2026-11-13
- **Scope:** `skills/tdd/SKILL.md`, stub guidance of the stack agents
- **Source:** agent run: feature lua-agent, code-reviewer and security-reviewer (2026-11-13)

## Motivation

In frameworks that report thrown errors as errors, not failures, a throwing stub fails like the Lua case did.

## Current state

Step 2 still allows "throw a not-implemented error" stubs for other stacks; step 4 requires every failure to be an assertion. Lua was fixed (empty values).

## Proposed change

Decide the generic rule (for example, stubs return empty values of the right type for every stack). Needs a decision.

## Risks

Not recorded.

## Out of scope

Not recorded.
