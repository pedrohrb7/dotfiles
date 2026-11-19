# hooks tests: SP8 linearity test compares CPU times with a 5x ratio (flake risk)

- **Status:** Open
- **Reported:** 2026-11-14
- **Severity:** low
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: feature audit-shell-lexer, Task 7
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Evidence

- Task 7 note: SP8 in `.claude/hooks/tests/test_shell_properties.py` compares CPU times with a 5x ratio and could flake under heavy load (not seen in the gate runs).

## Steps to reproduce

1. Run the suite several times under heavy load (load above 6 on 4 cores).

## Expected behavior

The test is stable.

## Actual behavior

Not observed failing; risk only.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.

## Seen again (2026-11-19)

Source: agent run: audit-stdin-facts, gate. Same class of wall-time flake: `tests.test_hook_process.HardeningProcess.test_p_hh2_stray_and_huge_run_states_do_not_break_the_run_tags` uses a 2.0 s wall-time bound and failed once at 2.06 s under load average 8; it passed on rerun and in 6 other runs. Fix idea: use a looser bound or CPU time.
