# agent-audit: _brace_words keeps the empty alternative ({git,} push passes)

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-stdin-other-sources-family, out_of_scope_collected (pre-existing)
- **Related:** none

## Evidence

- `{git,} push` becomes `git "" push` and passes.
- `echo x | {bash,}` and `{/bin/bash,}` pass.
- Location: `agent_audit_classify.py:2747` (`_brace_words`).

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

An empty brace alternative is dropped, so `{git,} push` is `git push` and `{bash,}` is `bash`.

## Actual behavior

The empty alternative is kept as an empty word.

## Root cause

`_brace_words` keeps the empty alternative as a word.

## Fix

Not fixed yet.
