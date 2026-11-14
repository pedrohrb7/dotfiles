# agent-audit: ${!x[@]} with a tainted x is classified dynamic_code (false positive)

- **Status:** Open
- **Reported:** 2026-11-14
- **Severity:** low
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: feature audit-shell-lexer, fix part D1
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Evidence

- Log, fix part D1: `${!x[@]}` with a tainted `x` is over-approximated as `dynamic_code` (level B).

## Steps to reproduce

1. Classify a text that assigns `x` from quoted text with a command substitution and then uses the indirect key list of `x`.

## Expected behavior

Listing the keys of an array is not code evaluation.

## Actual behavior

Level B `dynamic_code`.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
