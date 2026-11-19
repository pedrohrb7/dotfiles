# agent-audit: stdin set by exec is not followed

- **Status:** Fixed
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-pipe-procsub-stdin-family, reviewers (see Evidence)
- **Related:** [pipe-readers entry](2026-11-16-audit-pipe-readers-not-piped-shell.md)

## Evidence

Code review of the fix (pre-existing). These pass: `exec < <(x); bash`, `exec 0< <(x); { bash; }`.

All via `analyze_command` on synthetic strings (nothing executed), flags `[]` for the passing forms.

## Steps to reproduce

1. Classify each command above.

## Expected behavior

After `exec` rebinds fd 0 to a process substitution, later shells reading stdin are dynamic_code.

## Actual behavior

Not flagged.

## Root cause

The stdin state of the audit walker was a bool (piped or not), nested code was analyzed with clean stdin, and nothing modeled where fd 0 could come from besides a pipe: trap actions had no firing context, mapfile -C callbacks, bare exec redirects, fifos and fds opened elsewhere, stdin aliases other than the exact `_STDIN_FILES` names (`/dev/fd/N`, `/proc/*/fd/N`, `..`, cd/ln moves), and readers outside the table (fish/csh/tcsh, ksh variants, busybox/toybox applets, at/batch/parallel), glob program heads and zsh implicit hook functions.

## Fix

Fixed 2026-11-18 (not committed yet). The stdin state is now a reason per fd (`piped_shell` / `dynamic_code`) carried by the walker (`agent_audit_shell.py`), through nested code (eval, `-c`, mapfile -C) and traps (EXIT uses the final state, other signals `dynamic_code`); bare `exec` is modeled in all spellings, including the `{fd}` unknown descriptor; fifos created in the text are tracked and unresolved forms fail closed; stdin alias normalization covers `/dev/fd`, `/proc/*/fd`, `/proc/<pid>/root|cwd`, relative `..` and cd/ln moves; new readers (fish/csh/tcsh as stdin readers with `-c` as `dynamic_code`, ksh variants, busybox/toybox applets, at/batch/parallel); glob program heads under a state, glob receiver heads, zsh implicit hook functions and their registration (`agent_audit_classify.py`). Regression tests: classes StdinOtherSources, StdinOtherSourcesRound2-7 and StdinNames in `test_command_positions.py` and `test_shell_lexer.py`. Suite: 1101 tests pass.

## Seen again (2026-11-19)

Feature [audit-stdin-facts](../../features/audit-stdin-facts/spec.md) (not committed yet) extends the exec model: a bare exec copying input is a stdin reader, a copy of a descriptor no exec of the text opens is dynamic_code, and in a function or loop body it is dynamic_code. No change of status.
