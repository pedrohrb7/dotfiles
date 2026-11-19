# agent-audit: derive the stdin facts from the main analysis (second pass to a fixed point)

- **Status:** Done (2026-11-19, not committed yet; spec [audit-stdin-facts](../../features/audit-stdin-facts/spec.md), log [log.md](../../features/audit-stdin-facts/log.md))
- **Opened:** 2026-11-18
- **Scope:** .claude/hooks/agent_audit_shell.py (`_walk`), .claude/hooks/agent_audit_classify.py (`_stdin_facts`, `_nested_facts`, `compound_procsub_stdin`)
- **Priority:** high
- **Source:** agent run: fix bug-audit-stdin-other-sources-family, security reviews and out_of_scope_collected
- **Related:** [facts pass bug](../bugs/2026-11-18-audit-stdin-facts-pass-diverges.md)

## Motivation

Every security round found another divergence between the facts pass and the main analysis: raw-text gates, quoted nested heads, wrappers, resolved heads, git alias spellings, positional values, exported config. The two bugs in the related entry are symptoms.

## Current state

A separate `_stdin_facts` / `_nested_facts` pass computes fifos, moved and exec fds and re-implements head resolution. `compound_procsub_stdin` duplicates the walker stdin state once a compound's procsub redirect sets it.

## Proposed change

Derive the facts (fifos, moved, exec fds) from the main analysis itself, as a second pass run to a fixed point, so there is one resolution. Unify `compound_procsub_stdin` with the walker state. Needs a spec.

## Risks

Linearity and performance of the fixed point (the linearity guard test); fail-closed behavior must stay.

## Out of scope

New readers or alias forms.

## Outcome

Done 2026-11-19 by feature audit-stdin-facts. The separate facts pass (`_stdin_facts`, `_nested_facts`) is replaced by the main analysis's fixed point (at most 4 rounds, then fail closed), and `compound_procsub_stdin` is unified with the walker through `Site.given`. Accepted false positives are documented in the spec and log.
