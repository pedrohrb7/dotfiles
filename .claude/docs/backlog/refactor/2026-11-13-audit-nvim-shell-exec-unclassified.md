# agent-audit: nvim shell-execution forms not classified

- **Status:** Merged into [audit-shell-lexer](2026-11-13-audit-shell-lexer.md)
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py`
- **Source:** agent run: feature lua-agent, code-reviewer and security-reviewer (2026-11-13)

## Motivation

These forms run shell commands but escape classification, the same class as `bash -c`.

## Current state

Not classified: `exe "!..."`, `system()`, `systemlist()`, `os.execute`, `io.popen`, `vim.system`, `jobstart`, `termopen`, `:terminal`.

## Proposed change

Classify them like `bash -c`. Needs a spec.

## Risks

Not recorded.

## Out of scope

Not recorded.
