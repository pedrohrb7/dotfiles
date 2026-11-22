# agent-audit: git_commit matches only the commit subcommand (regression: commit-tree and other commit-creating commands)

- **Status:** Fixed
- **Reported:** 2026-11-14
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: feature audit-shell-lexer, Task 3 (A2), automated security review of commit 5a47cc4
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Evidence

- `.claude/hooks/agent_audit_classify.py`: `_is_git_commit` / `_git_walk` match only `commit` as the git subcommand (A2).
- The old regex matched `git commit-tree`; it is no longer `git_commit`.
- Other commit-creating or ref-moving commands are not `git_commit` either: `update-ref`, `merge`, `cherry-pick`, `revert`, `am`, `rebase`.

## Steps to reproduce

1. Classify `git commit-tree <tree> -m x`, `git update-ref`, `git merge`, `git cherry-pick`, `git revert`, `git am`, `git rebase` (synthetic JSON only).

## Expected behavior

Commit-creating and ref-moving commands get the same ask as `git commit`, or at least `commit-tree` keeps its previous classification.

## Actual behavior

Not classified as `git_commit`; allowed without the ask.

## Root cause

A2 narrowed the match to the exact `commit` subcommand in `_is_git_commit` / `_git_walk`.

## Fix

Fixed 2026-11-16 (scope widened by user decision: `git_commit` now covers every command that creates or moves commits). Changed: `.claude/hooks/agent_audit_classify.py` and tests.

- Whole subcommands (`_GIT_COMMIT_SUBCOMMANDS`): commit, commit-tree, merge, cherry-pick, revert, am, rebase, update-ref, pull, fast-import, filter-branch.
- Per form (`_GIT_COMMIT_FORMS`): subtree (any form but bare/-h/--help), notes add|edit|append|copy|merge, replace non-list, symbolic-ref writes, hash-object -w, stash create|store, reset (mode flag, or a non-HEAD revision outside `<rev> -- paths`; ambiguous fails closed), branch -f/--force/-M/-C, checkout -B, switch -C/--force-create, worktree add -B, fetch with a local-destination refspec or --stdin/--refmap.
- Long options match git unique prefixes (`_is_long`, fail closed). `git rebase -x/--exec` value is read as shell code (`_git_exec_code`).
- git_push is no longer masked by git_commit (except plain commit). Canary verbs: the subcommand set plus fast-import/filter-branch. Heredoc-as-data exemptions stay commit-only (`_is_git_commit` unchanged).
- Root cause: `_is_git_commit` matched only the exact subcommand `commit` after 5a47cc4 (A2) replaced the `^git (\S+ )*commit\b` regex; `_classify_segment` flagged git_commit only through it.
- Regression tests: `test_classify.py` `GitCommitSubcommand` (test_gc1_*), `test_heredoc.py` `DataSinkHeredocsAreStripped.test_git_merge_heredoc_message_is_not_exempted_like_commit`, `test_uncertainty.py` `DenyTokenCanary.test_un9_an_unflagged_commit_creating_verb_is_recorded_like_commit`.
- Checks: claude-hooks full suite passes; code-reviewer and security-reviewer, 4 rounds.
