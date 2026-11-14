# agent-audit: env with a dynamic NAME stops the wrapper reading before GIT_CONFIG_PARAMETERS

- **Status:** Open
- **Reported:** 2026-11-14
- **Severity:** low
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: feature audit-shell-lexer, fix part E
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Evidence

- `env $N=x GIT_CONFIG_PARAMETERS=... git p` stops the wrapper reading at the dynamic word; level A only, the operand after it is not read.

## Steps to reproduce

1. Classify `env $N=x GIT_CONFIG_PARAMETERS=<alias> git p` with synthetic input.

## Expected behavior

The operands after the dynamic word are still read (or the call is level B).

## Actual behavior

Level A only; nothing blocks.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
