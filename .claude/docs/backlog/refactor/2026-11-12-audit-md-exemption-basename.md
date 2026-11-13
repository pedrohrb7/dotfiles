# agent-audit: md_outside_docs README exemption matches by suffix

- **Status:** Done
- **Implementation:** implemented by the spec [audit-md-outside-docs](../../features/audit-md-outside-docs/spec.md); change is uncommitted, no PR yet.
- **Opened:** 2026-11-12
- **Scope:** .claude/hooks/agent-audit.py
- **Source:** agent run: audit-hook-test-suite, spec writing, specker
- **Spec:** [audit-md-outside-docs](../../features/audit-md-outside-docs/spec.md) (folded in, rule M4)

## Motivation

Files such as `MY_README.md` are wrongly exempt from `md_outside_docs`.

## Current state

The exemption uses `endswith('README.md')`.

## Proposed change

Compare the basename exactly (`== 'README.md'`).

## Risks

Not recorded.

## Out of scope

The main-session root `.md` false positive (see [md_outside_docs false positive](2026-11-11-audit-md-outside-docs-false-positive.md)).
