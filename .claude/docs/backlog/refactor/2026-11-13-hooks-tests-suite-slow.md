# hooks tests: claude-hooks suite exceeds the 5 s target (8.4-8.8 s for 317 tests)

- **Status:** Proposed
- **Opened:** 2026-11-13
- **Source:** agent run: lua-agent, test-runner, 2026-11-13
- **Scope:** `.claude/hooks/tests/`

## Motivation

The `claude-hooks` suite takes 8.4-8.8 s wall time for 317 tests. The target in `.claude/docs/features/audit-hook-test-suite/spec.md` was under 5 s, and the suite ran in about 4 s at 259 tests. A slow suite discourages running it often and makes the narrow per-task runs costly.

## Current state

The growth comes mostly from the newer process-level and timing tests: the analysis-timeout guard tests, the length-cap and regex timing tests, and the decision-before-recording tests. Some of them sleep or spawn subprocesses. Individual test timings have not been profiled yet.

## Proposed change

- Profile the slowest tests first.
- Shorten sleeps and timeouts with the test-only override.
- Share `HookProcess` setups where possible.
- Or mark the slow timing tests so the narrow per-task runs can skip them.

The choice between these depends on the profile. If the marker changes the suite's contract, it needs a spec.

## Risks

Shorter timeouts can make timing tests flaky. Shared `HookProcess` setups can leak state between tests.

## Out of scope

Changes to the hook itself (`agent-audit.py`).
