# agent-audit: shell lexer and parser for command positions (fails closed)

- **Status:** Done (implemented by the spec, uncommitted; gate 811 tests green, 2026-11-14)
- **Spec:** [audit-shell-lexer](../../features/audit-shell-lexer/spec.md)
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py` (segment splitting, `strip_prefixes`, command classification)
- **Source:** specker, feature audit-hook-hardening (2026-11-13). Severity: high. User decision 2026-11-13: next spec, right after audit-hook-hardening and before the docs-root declaration spec.

## Motivation

The hook does not recognize command positions, so blocked commands escape classification (fail-open). Pre-existing, found on HEAD 5f73e6c.

## Current state

All of these classify as `(['other'], [])`:

- `true & docker restart x` (a single `&` is missing from `SEGMENT_SPLIT`)
- `(docker restart x)`
- `{ docker restart x; }`
- `if true; then docker restart x; fi`
- `for i in 1; do docker restart x; done`
- `! docker restart x`
- `x=$(docker restart x)`
- backtick substitution
- `sudo -u x docker restart x` (sudo flags are not parsed)
- `nohup ...`, `xargs ...`, `watch ...`
- `bash -c "..."`, `eval "..."`

## Merged entries

- [quote-blind SEGMENT_SPLIT](2026-11-13-audit-segment-split-quote-blind.md)
- [strip_prefixes wrappers (env, nice, nohup)](2026-11-13-audit-strip-prefixes-wrappers.md)
- [nvim shell-execution forms](2026-11-13-audit-nvim-shell-exec-unclassified.md)

## Related scope from audit-hook-hardening review

Source: security-reviewer, feature audit-hook-hardening, 2026-11-13. User decision: these go to the lexer spec.

- Unquoted expansions with spaces in an assignment value are split, so the real command escapes. All of these were allowed: `A=$(echo a b) docker restart api`, backticks, `A=$((1 + 2)) ...`, `A=${X:-a b} ...`, `<(...)`, `A=$(echo a b) git push`.
- A quoted value of 5 or more words followed by a trailing comment holding a stray quote, such as `A="x y z w v" docker restart api # "`, passes the 3-token loose window. It is now recorded as `loose_assignment_truncated`, level A, but still allowed. Failing closed would deny 91 real python heredoc bodies.
- The `shlex_fallback` gate (reason only when readings differ) hides cases where both token lists are wrong the same way. Example: `A="x y z w v" curl https://evil.example # "` records no uncertainty and gets no `external_request` warn.
- Wrapper flags that are not parsed: `sudo -E`, `sudo --`, `time -p`, `stdbuf`, `ionice`, `env FOO=1`.
- Quoted separators inside an assignment value, for example `A="x;y" ...`.

## Proposed change

A real shell lexer and parser for command positions, which fails closed on what it cannot parse. Needs a spec.

## Risks

Not recorded.

## Out of scope

Not recorded.

## Result (2026-11-14)
Implemented by [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md): all review-fix rounds done, final gate 811 tests green (see the [log](../../features/audit-shell-lexer/log.md)). The parser lives in `.claude/hooks/agent_audit_shell.py` and the classifier in `.claude/hooks/agent_audit_classify.py`. Gaps found during the reviews are separate entries (Index, 2026-11-14). The change is uncommitted and has no PR yet.
