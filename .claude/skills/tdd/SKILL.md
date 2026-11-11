---
name: tdd
description: Test-Driven Development where the user implements - from a feature description, settle the behavior (grill-me), scaffold stubs that compile, have test-writer write tests against them, and confirm every test fails for the right reason (an assertion, never a missing module) before handing off. Use when the user says "tdd", "vamos fazer com TDD" or wants tests first and to write the code themselves. For TDD inside an approved spec with the agents implementing, use `/implement <feature> --tdd` instead.
---

# TDD

The rule this skill enforces: **a test starts red for the right reason.** It must fail because the behavior is missing (an assertion: `expected 202, received 501`), never because the code does not exist (`Cannot find module`, a compile error, an undefined symbol). That is what the stubs are for: with them, every test runs for real and fails on its assertion.

Given a feature description from the user:

1. **Behavior.** If the behavior is not settled yet, run `grill-me` until it is: inputs, outputs, errors and edge cases, concrete enough to become test cases. Explore the codebase for conventions and constraints instead of asking what the code can answer.
2. **Scaffold.** Detect the project's conventions (framework, module system, test setup, file placement) and list the files to create: the modules the tests will import, with their real types, signatures and exports. Ask the user to confirm the list, then create them in dependency order. Every body is a stub that compiles and does nothing useful: throw a not-implemented error, or return an empty or zero value of the right type. No logic, no TODO-only files that fail to import. Run the typecheck (or compile) on them if the project has one.
3. **Tests.** Delegate to `test-writer` in **tdd mode**, with the behavior from step 1 and the stub files: it writes the tests against the stubs, following the project's test conventions, and does not touch the stubs.
4. **Red for the right reason.** Delegate to `test-runner`, scoped to the new test files. Every failure must have `failure_kind: assertion`. A `compile`, `import` or `runtime` failure means a stub is missing or wrong: fix the stub (step 2) and run again, once. A test that passes against a stub tests nothing: send it back to `test-writer`.
5. **Hand off.** Tell the user which files hold the stubs and which tests define the behavior, one line per test. Do not implement the behavior: that is the user's part.

Never commit. Never use the em dash; use "-".
