---
name: bug-repro
description: Reproduce a bug end-to-end exactly as the end user would experience it before attempting any fix. Use when the user reports a bug, says "reproduce", or asks to fix an issue.
disable-model-invocation: true
---

# Bug Repro

Given a bug report, reproduce it end-to-end as closely as possible to how the end user experiences it (real UI flow, real CLI invocation, real API call) before touching any code.

1. Restate the bug as a concrete, observable symptom: input -> expected vs actual.
2. Find or build a minimal E2E repro - not an isolated unit test, unless the bug already lives at that boundary.
3. Run it and capture the actual failure: error, screenshot, log, stack trace.
4. Only once the failure is reproduced and understood, identify the root cause.
5. Hand off to the fix. Re-run the same repro afterward to confirm it passes and that the fix addresses the cause, not just a downstream symptom.

If the bug can't be reproduced, stop and report that explicitly instead of guessing at a fix.
