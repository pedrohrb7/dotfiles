# agent-audit: watchdog robustness notes

- **Status:** Proposed
- **Opened:** 2026-11-13
- **Priority:** low
- **Scope:** `.claude/hooks/agent-audit.py`
- **Source:** agent run: feature audit-hook-hardening, code-reviewer and security-reviewer (2026-11-13)

## Motivation

Small robustness gaps left in the watchdog added by [hook hardening](2026-11-13-audit-hook-hardening.md). None is a known failure today.

## Current state

- Unverified: whether the hook can inherit SIGCHLD=SIG_IGN, which would make kill-before-reap unsafe against pid reuse.
- `_Child.close` polls `waitpid` for only 20 ms, a thin margin under load.
- After an analysis timeout or crash, the record gets `run_tags: "timeout"`, which conflates slow tagging with failed analysis in hook health.
- The `WHY["parse_uncertain"]` text only says "more than one plausible reading", but the reasons now cover more cases.

## Partly covered

The [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md) rewrites only the `WHY["parse_uncertain"]` text. SIGCHLD, the `waitpid` margin and `run_tags` stay open. Status stays Proposed.

## Proposed change

Verify the SIGCHLD item first; then widen the `waitpid` margin, give failed analysis its own `run_tags` value, and reword the `parse_uncertain` text. Small enough to do without a spec.

## Risks

Not recorded.

## Out of scope

The shell lexer work ([audit-shell-lexer](2026-11-13-audit-shell-lexer.md)).
