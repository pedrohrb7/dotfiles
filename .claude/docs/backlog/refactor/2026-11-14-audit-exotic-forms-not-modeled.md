# agent-audit: exotic forms not modeled (trap DEBUG, zparseopts -A, same-text aliases)

- **Status:** Proposed
- **Opened:** 2026-11-14
- **Scope:** `.claude/hooks/agent_audit_classify.py`
- **Source:** agent run: feature audit-shell-lexer; [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Motivation

Forms that run or rename commands outside the model.

## Current state

- `trap '...' DEBUG` runs code on every command.
- zsh `zparseopts -A` can change a known name.
- Same-text aliases (`alias g=git`, then `g push`): unverified whether Claude Code's zsh eval expands them.

## Proposed change

Verify the alias behavior first; the rest is low value unless metrics show them.

## Risks

Not recorded.

## Out of scope

Not recorded.

## Seen again (2026-11-14)

Source: automated security review of commit 5a47cc4 (feature audit-shell-lexer), `agent_audit_classify.py`. Review severity: high.

- Alias rebinding is not handled by `_rebound_spans`: `alias cat=bash` or `alias jq=sh` (and bash `shopt -s expand_aliases`) can make a later heredoc sink or here-string data reader run a shell. Any aliased command name also has an unknown program.
- Still unverified whether Claude Code's zsh eval expands an alias defined earlier in the same command string; until verified, treat it as a possible bypass.
- Suggested fix: treat `alias` and `shopt -s expand_aliases` as rebinding (read bodies as code, unknown program for aliased names), or classify as level B when the text defines an alias.

## Seen again (2026-11-18)

Source: fix bug-audit-pipe-procsub-stdin-family, reviewers. Same-text alias as a pipe receiver: `alias g=bash; echo x | g` passes. Trap actions with stdin context are in [the trap stdin bug](../bugs/2026-11-18-audit-trap-action-stdin-context.md).
