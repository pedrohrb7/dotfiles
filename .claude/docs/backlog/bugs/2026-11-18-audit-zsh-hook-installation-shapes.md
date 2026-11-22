# agent-audit: zsh function table misses hook installation shapes and the functions parameter

- **Status:** Open
- **Reported:** 2026-11-18
- **Severity:** medium
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-stdin-other-sources-family, out_of_scope_collected and round-2 security review (user decision)
- **Related:** [zsh command_not_found_handler entry](2026-11-18-audit-zsh-command-not-found-handler-not-modeled.md)

## Evidence

- `functions[f]=bash; echo x | f` is not resolved (a non-hook name set through the zsh `functions` parameter is not in the function table).
- Not modeled hook installs: `functions[$n]=`, `functions+=([TRAPEXIT]=bash)`, `typeset`/`set -A`, `functions -c -- f`, quoted elements in `zshexit_functions`, `zsh_directory_name_functions`.

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

These installation shapes register the function body like a normal definition.

## Actual behavior

Not flagged.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.

## Partly fixed (2026-11-19)

Feature [audit-stdin-facts](../../features/audit-stdin-facts/spec.md) (not committed yet): `functions[NAME]=BODY` and `functions+=(NAME BODY)` of any name are classified as same-shell code and join the function table, and any word naming the zsh `functions` parameter outside that assignment path (`functions[`, `functions=`, `${functions`, bare name after set/typeset/declare/local/export/readonly/read/print/printf/integer/float) is dynamic_code. So `functions[f]=bash; echo x | f` and the other `functions` parameter forms are handled. Status stays Open: `functions[$n]=` resolution, `set -A`, `functions -c -- f`, quoted elements in `zshexit_functions` and `zsh_directory_name_functions` were not reviewed in that run.
