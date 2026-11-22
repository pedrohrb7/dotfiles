# agent-audit: Bash-based file writes are not audited as writes

- **Status:** Proposed
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py` (Bash command classification)
- **Source:** agent run: skills-docs-root, security-reviewer, 2026-11-13 (pre-existing limit, noted in the audit-scratch-exemption spec)

## Motivation

File writes done through Bash (`echo`/`sed -i`/`mkfifo` redirections, heredocs) are not judged as writes, so an agent can bypass the Write/Edit checks (scope, docs, backlog, md_outside_docs) through Bash.

## Current state

Only the Write/Edit tools go through the path checks. No existing backlog entry covers Bash writes (the heredoc entry is about command classification).

## Proposed change

Not defined. Needs a spec: parsing redirections and in-place editors reliably is hard in shell, so decide best-effort detection versus a different control.

## Risks

False positives from parsing shell text; false sense of coverage.

## Out of scope

Blocking mode (warn->block promotion).

## Seen again (2026-11-16)

Source: agent run: fix of audit-git-config-keys-run-commands, out_of_scope_issues.

Direct edits of `.git/config` or `~/.gitconfig`, by the Write/Edit tool or by a command the classifier cannot see into, can set value-running keys (`core.pager`, `core.fsmonitor`, `core.hooksPath`, `hook.*`) that later run on builtin git calls. Neither the Write/Edit path checks nor the git config model (which covers `git config` and `-c`, not file writes) reach this; no existing write-scope entry covered it, so it is recorded here. Related: [hook self-protection](../bugs/2026-11-11-audit-hook-self-protection.md). Pre-existing.
