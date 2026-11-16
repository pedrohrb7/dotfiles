# agent-audit: git_commit matches only the commit subcommand (regression: commit-tree and other commit-creating commands)

- **Status:** Open
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

Not fixed yet.
