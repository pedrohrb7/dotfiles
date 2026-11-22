# agent-audit: zsh command_not_found_handler is not modeled

- **Status:** Fixed
- **Reported:** 2026-11-18
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: automated security review of commit 571d2b8 (pipe/procsub stdin fix), confirmed by the main session with analyze_command on synthetic strings
- **Related:** [pipe-readers entry](2026-11-16-audit-pipe-readers-not-piped-shell.md)

## Evidence

Only bash's `command_not_found_handle` is modeled; zsh names it `command_not_found_handler`. The user's shell is zsh.

- `command_not_found_handler() { bash; }; echo 'git push' | zzz` gives flags [] / [deny_token_unmatched]
- `command_not_found_handle() { bash; }; echo x | zzz` gives unclassified_command + dynamic_code

Related, to consider: other zsh hook functions that run implicitly with an inherited stdin: chpwd, precmd, preexec, periodic, zshexit, TRAP<SIG>, TRAPDEBUG, TRAPZERR, TRAPEXIT.

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

The zsh handler is modeled like the bash one, and the implicit zsh hook functions are considered.

## Actual behavior

The flags list is empty for the zsh name.

## Root cause

The stdin state of the audit walker was a bool (piped or not), nested code was analyzed with clean stdin, and nothing modeled where fd 0 could come from besides a pipe: trap actions had no firing context, mapfile -C callbacks, bare exec redirects, fifos and fds opened elsewhere, stdin aliases other than the exact `_STDIN_FILES` names (`/dev/fd/N`, `/proc/*/fd/N`, `..`, cd/ln moves), and readers outside the table (fish/csh/tcsh, ksh variants, busybox/toybox applets, at/batch/parallel), glob program heads and zsh implicit hook functions.

## Fix

Fixed 2026-11-18 (not committed yet). The stdin state is now a reason per fd (`piped_shell` / `dynamic_code`) carried by the walker (`agent_audit_shell.py`), through nested code (eval, `-c`, mapfile -C) and traps (EXIT uses the final state, other signals `dynamic_code`); bare `exec` is modeled in all spellings, including the `{fd}` unknown descriptor; fifos created in the text are tracked and unresolved forms fail closed; stdin alias normalization covers `/dev/fd`, `/proc/*/fd`, `/proc/<pid>/root|cwd`, relative `..` and cd/ln moves; new readers (fish/csh/tcsh as stdin readers with `-c` as `dynamic_code`, ksh variants, busybox/toybox applets, at/batch/parallel); glob program heads under a state, glob receiver heads, zsh implicit hook functions and their registration (`agent_audit_classify.py`). Regression tests: classes StdinOtherSources, StdinOtherSourcesRound2-7 and StdinNames in `test_command_positions.py` and `test_shell_lexer.py`. Suite: 1101 tests pass.
