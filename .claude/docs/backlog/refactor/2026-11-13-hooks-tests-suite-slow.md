# hooks tests: claude-hooks suite exceeds the 5 s target (8.4-8.8 s for 317 tests)

- **Status:** Proposed (partly covered, stays open)
- **Spec:** [audit-hook-hardening](../../features/audit-hook-hardening/spec.md) - Task 6 only
- **Opened:** 2026-11-13
- **Source:** agent run: lua-agent, test-runner, 2026-11-13
- **Scope:** `.claude/hooks/tests/`

## Spec coverage (2026-11-13)

Partly covered by the audit-hook-hardening spec: its Task 6 keeps the suite at or under 8.5 s. The under-5 s target stays open, so this entry stays open after that run. See also [hook performance](2026-11-13-audit-hook-launcher-performance.md).

## Result of audit-hook-hardening (2026-11-13)

The suite went from about 16 s down to about 6 s with 462 tests, within the 8.5 s budget of Task 6. It reached 4.2-5.4 s at 436 tests, but is about 6 s now. Kept open for the under-5 s goal. The change is uncommitted and has no PR yet.

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

## Result of audit-shell-lexer (2026-11-14)
Task 7 budget of 8.5 s not met: 811 tests take 9.9-11 s at load 1.5-2.9 (earlier runs 8.3-9.5 s for 655 tests at load 4-6). Estimate on an idle 4-core machine about 6.5-7 s at 655 tests. The under-5 s goal stays open. Source: [log](../../features/audit-shell-lexer/log.md).

## Budget revised (2026-11-14)
User decision (audit-shell-lexer): the Task 7 budget was revised to 12 s for 811 tests (measured 9.9-11.0 s), so it is met. This entry stays Proposed to lower the time further.
