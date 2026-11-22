# agent-audit: git config keys that execute commands are not modeled (and cross-call aliases)

- **Status:** Fixed
- **Reported:** 2026-11-14
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: feature audit-shell-lexer, security-reviewer (out of scope of the closing round)
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Evidence

- Keys not modeled: `core.pager`, `core.sshCommand`, `core.fsmonitor`, `credential.helper`, `diff.external`, set through `-c`, `GIT_CONFIG_*` or `git config`.
- Cross-call alias: `git config alias.c commit` then `git c -m x` is a silent commit (aliases are resolved only within one text).

## Steps to reproduce

1. Classify `git -c core.pager=<cmd> log` with a blocked command as the value.
2. Classify `git config alias.c commit` and, in a later call, `git c -m x`.

## Expected behavior

A key whose value runs a program is classified like code, and the alias makes `git c` a `git_commit` ask.

## Actual behavior

Allowed, nothing flagged (the alias case is a silent commit).

## Root cause

`_git_aliases` (`.claude/hooks/agent_audit_classify.py`) kept only `alias.*` from the `-c`/`--config-env`/`GIT_CONFIG_*` pairs it already collected; no other key was read as code or as unknown. Config from files (include, `GIT_CONFIG_GLOBAL`/`SYSTEM`), `git config` writes, config-driven refspecs and unknown subcommands (git-other) were not modeled, so cross-call aliases were silent commits.

## Fix

Fixed (user decisions 2026-11-16), committed with the fix:
- New ask category `git_config_exec` for risky `git config` writes (and remote/submodule `ext::`/`fd::` URLs).
- Keys and env vars whose value is shell code (GIT_PAGER, GIT_EDITOR, EDITOR, VISUAL, PAGER, LESSOPEN, GIT_SSH_COMMAND, ...) are read as code; program/file keys and env vars are level B unless empty.
- `remote.*.fetch` into local refs is `git_commit`.
- An unknown subcommand is resolved through builtins, text aliases, a hook-time repo alias read (trusted only under an allowlist of read-only commands) and `git-<name>` on PATH; otherwise blocked as `git_unknown_subcommand`.
- 4 review rounds (code + security).
- Changed: `.claude/hooks/agent_audit_classify.py`, `agent-audit.py`, `agent-audit.json`, `agent-metrics.py`, and tests.
- Regression tests: `tests/test_command_positions.py` ReviewFixB2 sections 6b/6c; `tests/test_classify.py` GitConfigWrites, GitConfigWritesRound2; `tests/test_uncertainty.py` GitUnknownSubcommand (+Round2/3/4), GitConfigProgramKeysLevelB; `tests/test_hook_main.py` test_e5_*, ResolverHermeticity, ReadGitAliases; `tests/test_config_contract.py` f2/f6.
- Checks: full claude-hooks suite 911 OK twice; pyright at the 20-error baseline.

## Seen again (2026-11-14)

Source: automated security review of commit 5a47cc4 (feature audit-shell-lexer), `agent_audit_classify.py`.

More alias vectors: `_git_aliases` reads only command-line/env `alias.*`. Aliases can also come from `include.path`, `includeIf.*`, or `GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` set on the command line or env (pulling a file); and from `git config [--local|--global] alias.*` writes followed by an unknown git subcommand.

Suggested fix: when include/`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` are set, the result is unresolved (level B); an unknown non-builtin git subcommand is unresolved.

## Seen again (2026-11-16)

Source: agent run: fix of audit-git-commit-subcommand-regression, reviewers.

Config-driven ref writes are not modeled: `git fetch origin` with a `remote.*.fetch` refspec targeting refs/heads (writes local refs without a visible refspec), and `-c sequence.editor=<cmd>` on rebase (runs a command).

## Seen again (2026-11-16, second)

Source: automated security review of commit 7a4e1e5. The config-driven fetch ref writes (`-c remote.*.fetch`, `remote.*.url`, `GIT_CONFIG_*`) were reported again; same root cause, nothing new.
