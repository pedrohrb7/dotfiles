# agent-audit: parallel option tables not checked option by option against man parallel

- **Status:** Proposed
- **Opened:** 2026-11-19
- **Scope:** `.claude/hooks/agent_audit_classify.py` (`_PARALLEL_VALUE`, `_PARALLEL_FLAGS`)
- **Source:** agent run: fix bug-audit-regex-and-tables-46ae3a7, out_of_scope_collected (pre-existing)

## Motivation

The parallel allow-list blocks any unknown option, so a wrong table entry either lets an option through as a value or blocks clean commands.

## Current state

Only `-m`, `--plus`, `--shuf` and `-l` were corrected. The rest is not verified against the man page. Also: options in `~/.parallel/config` are invisible to the classifier, so an agent that writes that file injects options.

## Proposed change

Check every entry against man parallel; decide how to treat `~/.parallel/config` (needs a spec).

## Risks

Not recorded.

## Out of scope

Not recorded.
