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
