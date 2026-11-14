# agent-audit: hook hardening (metrics file, run state size, timeouts)

- **Status:** Done (implemented by the spec audit-hook-hardening (2026-11-13); the change is uncommitted and has no PR yet)
- **Spec:** [audit-hook-hardening](../../features/audit-hook-hardening/spec.md)
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py`
- **Source:** agent run: feature lua-agent, code-reviewer and security-reviewer (2026-11-13)

## Motivation

Base for a dedicated hook-hardening spec (the user's decision). The hook has resource and robustness gaps that lose records or slow decisions.

## Current state

- The metrics file is opened without O_NONBLOCK/O_NOFOLLOW/S_ISREG checks. A FIFO there blocks the record step: it can no longer delay a decision, but the record is lost.
- `active_run` reads every `.claude/runs/*.json` with no size or count limit. A 156 MB file took 9.75 s. Related bug: [active_run non-object state](../bugs/2026-11-12-audit-active-run-non-object-state.md) (linked, not merged).
- Premise corrected (2026-11-13, spec Background in [spec.md](../../features/audit-hook-hardening/spec.md)): CPython's `re` is interrupted by SIGALRM. What SIGALRM does not interrupt is a single long C call on large input (`json.loads` on 36 MB) or a syscall stuck on a hung filesystem.
- A Post record is lost when its recording step times out.
- Related bug: [heredoc sink after command substitution](../bugs/2026-11-13-audit-heredoc-sink-runs-sh.md).
- Both items below belong to this hook-hardening spec: [heredoc sink bug](../bugs/2026-11-13-audit-heredoc-sink-runs-sh.md) (including the `strip_prefixes` first-reading angle) and [timeout parsing limits](2026-11-13-audit-timeout-parsing-limits.md) (fail-open at the depth/variant cap).

## Proposed change

Needs a spec.

## Risks

Not recorded.

## Out of scope

Not recorded.
