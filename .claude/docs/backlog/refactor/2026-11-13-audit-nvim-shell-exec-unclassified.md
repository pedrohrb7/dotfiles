# agent-audit: nvim shell-execution forms not classified

- **Status:** Done (via [audit-shell-lexer](2026-11-13-audit-shell-lexer.md), uncommitted); `vim.cmd` forms remain open in a separate entry
- **Spec:** [audit-shell-lexer](../../features/audit-shell-lexer/spec.md)
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

## Result (2026-11-14)
Covered by Task 4 of the [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md) ([log](../../features/audit-shell-lexer/log.md)): the X6 list of nvim shell-execution forms is classified like `bash -c`. Not covered, kept open: `vim.cmd("!cmd")`, `vim.api.nvim_command("!cmd")` and `:execute` with a variable, see [nvim ex commands with a bang](2026-11-14-audit-nvim-vim-cmd-bang.md).
