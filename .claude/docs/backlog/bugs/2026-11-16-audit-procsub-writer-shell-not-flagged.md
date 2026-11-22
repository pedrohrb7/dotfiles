# agent-audit: a shell reading stdin from a process-substitution writer is not flagged

- **Status:** Fixed
- **Reported:** 2026-11-16
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix of audit-pipe-into-group-not-flagged, reviewers
- **Related:** [pipe-into-group entry](2026-11-14-audit-pipe-into-group-not-flagged.md)

## Evidence

- `echo 'git push' > >(bash)` gives `['other']`, no flags.

## Steps to reproduce

1. Classify `echo 'git push' > >(bash)` through `analyze_command` (synthetic input, no real execution).

## Expected behavior

The shell inside `>(...)` reads the writer's output, so the text is classified like `| bash` (`git push`).

## Actual behavior

Flags are `['other']`; the command is allowed.

## Root cause

`_walk` / `_walk_redirects` in `.claude/hooks/agent_audit_shell.py` passed the enclosing stdin state to `>(...)` scripts, because `part_scripts` / `Word.scripts` dropped the `procsub_out` vs `procsub_in` distinction.

## Fix

`part_script_items` / `Word.script_items` carry a writer flag, and a `>(...)` script is always piped. Regression tests: `test_shell_lexer.py` PipedStdin (`test_a_process_substitution_writer_script_is_piped`).

Fixed on 2026-11-18 (not committed yet). Run: `.claude/runs/bug-audit-pipe-procsub-stdin-family.json`. Suite: 989 tests pass.