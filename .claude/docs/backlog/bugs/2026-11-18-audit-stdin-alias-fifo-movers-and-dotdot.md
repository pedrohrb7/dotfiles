# agent-audit: stdin alias `..` order, and fifo movers and link makers inside wrappers or variable heads are not resolved

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-stdin-other-sources-family, out_of_scope_collected and round-2 security review (user decision)
- **Related:** [operand alias entry](2026-11-16-audit-operand-stdin-alias-exact-match.md)

## Evidence

- stdin_alias applies `..` lexically after kernel symlinks: `/proc/self/root/../dev/stdin`, `/dev/fd/../root/dev/stdin`; 9 levels of /proc/self/root do not fail closed.
- Fifo movers and link makers inside wrappers are not resolved: `cp -s`, `busybox ln/mv`, `rsync`, `tar`, `find -exec mv`, `mkfifo /tmp/p; cd /tmp; bash < p`, `~` names.
- Variable-made cd/ln heads do not set moved: `c=cd; $c /dev/fd; source 3` (only fifo-maker heads go through head_readings).

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

The alias is resolved following symlinks before `..`, and the moves/links are tracked or fail closed.

## Actual behavior

Not flagged.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
