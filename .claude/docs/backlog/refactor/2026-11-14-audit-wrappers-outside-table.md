# agent-audit: wrappers and launchers outside the table are recorded only by the canary

- **Status:** Proposed
- **Opened:** 2026-11-14
- **Scope:** `.claude/hooks/agent_audit_classify.py` (`_WRAPPERS`)
- **Source:** agent run: feature audit-shell-lexer; [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Motivation

A blocked command behind these wrappers is allowed with only the canary: `doas`, `pixi exec`, hatch `env:cmd`, `strace`, `unshare`, `bundle exec`, `direnv exec`, `npx -c`.

## Current state

Spec decision 5: the wrapper scope is the table plus zsh precommands, `command`, `exec`, `builtin`; extra wrappers are metrics-driven. Also left out: `setsid`, `flock`, `chrt`, `taskset`, `find -exec`, `parallel`.

## Proposed change

Add wrappers by weekly metrics (canary hits), not speculatively.

## Risks

Not recorded.

## Out of scope

Not recorded.

## Seen again (2026-11-16)

Source: agent run: fix of audit-git-commit-subcommand-regression, reviewers.

The canary does not reach git fed by xargs: `echo fast-import | xargs git` and `echo commit | xargs git` classify as `other` with no flag. Pre-existing; `xargs` is another launcher outside the table.

## Seen again (2026-11-16, second)

Source: agent run: fix of audit-git-config-keys-run-commands, out_of_scope_issues.

`find . -exec|-execdir git commit|push|<alias> ... \;` classifies as `other` with only deny_token_unmatched; commits and pushes through `find -exec` are not asked. Same root cause (`find -exec` is a launcher outside the table); the impact is a missed `git_commit`/push ask, so consider prioritizing `find -exec` over the metrics-driven rule. Pre-existing.
