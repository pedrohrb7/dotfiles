# agent-audit: a function or coproc used as a pipe receiver is not followed

- **Status:** Fixed
- **Reported:** 2026-11-16
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix of audit-pipe-into-group-not-flagged, reviewers
- **Related:** [pipe-into-group entry](2026-11-14-audit-pipe-into-group-not-flagged.md)

## Evidence

- `f() { bash; }; echo 'git push' | f` gives only `deny_token_unmatched`.
- `coproc { bash; }` fed via `>&${COPROC[1]}` is the same.

## Steps to reproduce

1. Classify `f() { bash; }; echo 'git push' | f`.
2. Classify a `coproc { bash; }` fed through `>&${COPROC[1]}`.

## Expected behavior

The function or coproc body is a shell reading the pipe, classified like `| bash`.

## Actual behavior

Only `deny_token_unmatched`; piped text is not classified.

## Root cause

`_NO_STDIN_KINDS` included coproc, and `classify` never resolved a call to a function defined in the text.

## Fix

Coproc bodies are always piped (user decision 2026-11-18, reverses the 2026-11-16 line). `_Run.function_call` with cached `function_verdicts` / `_function_readers` resolves calls on every head variant; unresolved, dynamic and glob heads without a literal `/` count for every code-reading function. The outer function map reaches eval, trap, source, `.`, `bash -c` and heredoc bodies. A definition inside a same-shell string (`_SAME_SHELL_LOADERS`: eval, trap, source, `.`, mapfile, readarray, emulate) is dynamic_code. A `command_not_found_handle` that reads code is dynamic_code. Regression tests: `test_shell_lexer.py` `test_a_coproc_body_is_always_piped`, `test_command_positions.py` class PipeReceivers.

Fixed on 2026-11-18 (not committed yet). Run: `.claude/runs/bug-audit-pipe-procsub-stdin-family.json`. Suite: 989 tests pass.