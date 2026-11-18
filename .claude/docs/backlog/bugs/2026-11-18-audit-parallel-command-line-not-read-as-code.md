# agent-audit: the GNU parallel command line is not classified or read as code

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-stdin-other-sources-family, out_of_scope_collected (pre-existing) and round-2 security review (user decision)
- **Related:** none

## Evidence

- `parallel ::: 'git push'`, `parallel eval ::: ...`, `parallel bash -c ::: ...` run their arguments as commands: only deny_token_unmatched.
- `parallel -j4 'git push {}' ::: a` and `parallel "bash -c 'git push {}'" ::: a` give no git_push flag.
- Not read as code: `parallel 'bash -c {}'`, `'eval {}'`, `echo {} '|' bash`, `nice sh -c`, `--pipe 'cat | bash'`.

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

The command template and the ::: arguments are classified as code.

## Actual behavior

No flag beyond deny_token_unmatched.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
