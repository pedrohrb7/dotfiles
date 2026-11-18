# agent-audit: fish/csh/tcsh option scan stops at the value of a value-taking option

- **Status:** Fixed (2026-11-19, not committed)
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: security review of commit 46ae3a7 (stdin family fix), confirmed with analyze_command on synthetic strings
- **Related:** none

## Evidence

- `fish -d 3 -c 'git push'` gives [] / [deny_token_unmatched].
- `fish --comm='git push'` gives [] / [deny_token_unmatched] (long options matched only exactly).
- `fish -o out -c x` gives [].

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

The -c string is read as code whatever options precede it, and abbreviated long options are recognized.

## Actual behavior

The option scan stops at the value of a value-taking option, and long options are matched only exactly, so the command string is not read.

## Root cause

`_other_shell_code` assumed no value options and matched long options exactly.

## Fix

Per-shell option tables (`_FISH_OPTIONS`, `_CSH_OPTIONS`) with value options, long-option prefix matching, unknown options failing closed (dynamic_code); csh/tcsh `-s` and a lone `-` read stdin. Fix run: .claude/runs/bug-audit-regex-and-tables-46ae3a7.json. Gate: 1145 tests pass. Not committed yet.

## Seen again (2026-11-19)

Source: agent run: fix bug-audit-regex-and-tables-46ae3a7, out_of_scope_collected (pre-existing). Unverified notes, not covered by the fix: `tcsh -t SCRIPT`, `tcsh --` handling and long-option prefix semantics; `tcsh -f -- script` and fish `-` with piped stdin may read stdin.
