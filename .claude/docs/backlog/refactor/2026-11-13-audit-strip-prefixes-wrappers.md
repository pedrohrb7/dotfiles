# agent-audit: strip_prefixes does not strip env, nice and nohup wrappers

- **Status:** Merged into [audit-shell-lexer](2026-11-13-audit-shell-lexer.md)
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py` `strip_prefixes` (around line 223)
- **Source:** agent run: specker, feature lua-agent (spec `../../features/lua-agent/spec.md`)

## Motivation

A suite run behind a wrapper, for example `env CI=1 pytest`, escapes `suite_by_non_runner` for every stack.

## Current state

The prefix set is `{"rtk", "proxy", "sudo", "time", "command", "exec"}` plus env assignments. `env`, `nice` and `nohup` are not stripped. The lua-agent spec only adds `timeout`.

- Seen again (2026-11-13, code-reviewer and security-reviewer, feature lua-agent): unclassified wrapper forms: `mise exec -c '<shell>'` / `mise x --command`, and path-prefixed non-Lua binaries and wrappers (`/usr/bin/docker`, `./bin/docker`, `/usr/bin/timeout`, `~/.local/bin/mise`).

## Proposed change

Strip `env` (with its assignments and flags), `nice` (with `-n N`) and `nohup`. Needs care with each wrapper's arguments; add tests to the hook suite.

## Risks

Wrongly consuming a wrapper's flags and misreading the command.

## Out of scope

Other wrappers beyond `env`, `nice`, `nohup` and `timeout`.
