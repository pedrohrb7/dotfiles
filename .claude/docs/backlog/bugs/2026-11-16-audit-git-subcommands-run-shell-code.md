# agent-audit: git subcommands that run shell code are not read as code

- **Status:** Fixed
- **Reported:** 2026-11-16
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix of audit-pipe-into-group-not-flagged, reviewers
- **Related:** [pipe-into-group entry](2026-11-14-audit-pipe-into-group-not-flagged.md)

## Evidence

- `filter-branch --*-filter` (any unique prefix, `=value` or next word), `bisect run <cmd...>`, `submodule foreach <code>`, `difftool`/`mergetool -x/--extcmd/--tool-cmd`.
- Source: automated security review of commit 7a4e1e5.

## Steps to reproduce

1. Classify each form above with a blocked command as the code (synthetic input).

## Expected behavior

The code is read like `rebase -x` (`_git_exec_code`), or the result is unresolved (level B).

## Actual behavior

Allowed, the code is not classified.

## Root cause

`_git_exec_code` (`.claude/hooks/agent_audit_classify.py`) read code only for `git rebase -x`; `_prefix_steps` had no `git bisect run` case; filter-branch was only git_commit; no other git CLI option that runs a program was modeled.

## Fix

Committed with the fix. Per-subcommand table `_GIT_CODE_OPTIONS` (filter-branch filters/--setup, difftool -x/--extcmd, clone -u/--upload-pack, fetch/pull/fetch-pack --upload-pack, ls-remote --upload-pack/--exec, push/send-pack --receive-pack/--exec, archive --exec, grep -O), send-email *-cmd with Getopt::Long spellings, submodule foreach, bisect run command start, ext:: URLs in transport verbs, clone -c/--config through the config rules (also via aliases). Level B for instaweb, send-email --smtp-server program paths, custom merge strategies (incl. cherry-pick/revert --strategy, pull.twohead/octopus), daemon --access-hook, merge-index. A `--` right after an option without `=` is that option's value (fail closed); send-pack is git_push. 3 review rounds (code + security).

Changed files: `.claude/hooks/agent_audit_classify.py`, `.claude/hooks/tests/test_classify.py`, `.claude/hooks/tests/test_command_positions.py`.
Regression tests: `tests/test_classify.py` `test_gc2_*`, `test_gc3_*`, `test_gc4_*` (class GitCommitSubcommand); `tests/test_command_positions.py` class `GitSubcommandsRunningCode`.
Checks: full claude-hooks suite 951 OK; pyright at the 20-error baseline.
