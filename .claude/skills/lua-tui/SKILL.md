---
name: lua-tui
description: User interfaces in Lua - inside Neovim (floating windows, scratch buffers as UI, extmarks, highlight groups linked to the theme, layout on VimResized, cleanup on close) and standalone terminal TUIs (raw mode with guaranteed restore, alternate screen, luv event loop, SIGWINCH, named ANSI colors, no-TTY and NO_COLOR). Preloaded by the lua agent. Use when building or reviewing a Lua UI in Neovim or in the terminal.
---

# Lua UI: Neovim and terminal

Check the APIs below against `:help` (`api-floatwin`, `nvim_set_hl()`, `api-extended-marks`, `luv-tty`) when unsure; do not guess.

## Which world

- Neovim: the editor owns the terminal. Use `vim.api` windows, buffers and extmarks, never raw escape sequences.
- Terminal: the program owns the TTY (raw mode, escape sequences, `luv`). Never `vim.api` there.
- Do not mix the two in one module. Shared logic (state, layout math) is pure Lua with no `vim.*` and no I/O.

## Neovim: buffers and windows

- UI buffer: `nvim_create_buf(false, true)`, then set `buftype=nofile`, `swapfile=false`, `bufhidden=wipe`, `modifiable=false` between renders.
- Floating window: `nvim_open_win(buf, enter, { relative = "editor", row, col, width, height, style = "minimal", border = "rounded" })`.
- Size from the usable area: `vim.o.columns` and `vim.o.lines - vim.o.cmdheight`, minus the tabline (`showtabline`), a `winbar` if set and the statusline when shown (`laststatus` 2 or 3, or 1 with 2+ windows); see `:help 'laststatus'`. Clamp to that area with a minimum.
- Keymaps are buffer-local (`vim.keymap.set(mode, lhs, rhs, { buffer = buf, nowait = true })`); close key (`q`, `<Esc>`) always present.

## Neovim: highlights and extmarks

- One namespace per plugin or feature: `nvim_create_namespace("<plugin>.<feature>")`. Clear it on every re-render with `nvim_buf_clear_namespace(buf, ns, 0, -1)`.
- Own groups link to standard ones, with `default = true` so user overrides win: `nvim_set_hl(0, "MyPluginTitle", { link = "Title", default = true })`. Candidates: `NormalFloat`, `FloatBorder`, `FloatTitle`, `Comment`, `Title`, `Diagnostic*`.
- Never a literal color: no hex strings, no `guifg`/`guibg`, no fixed cterm numbers. The colorscheme and the user's overrides must apply.
- Re-apply links on `ColorScheme` only if the group is defined with attributes; plain `link` survives a colorscheme change.
- Apply with `nvim_buf_set_extmark` or `vim.hl.range` (`vim.highlight.range` before 0.11); not `matchadd` on a UI window.

## Neovim: layout and redraw

- Recompute size and position on `VimResized` (autocmd in the UI's own augroup) with `nvim_win_set_config`. Below the minimum, show a short warning line instead of a broken layout.
- Batch writes: one `nvim_buf_set_lines` for all lines, then extmarks. No `:redraw` in a loop; call `vim.cmd.redraw()` only once after a long synchronous step.
- Code running from a `vim.uv` callback, a job or a timer touches the API only inside `vim.schedule` / `vim.schedule_wrap`.

## Neovim: lifecycle

- Close by every path: `:q`, `<C-w>o`, the plugin command, a tabpage switch. Listen to `WinClosed` (pattern is the window id as a string) and `BufWipeout` on the buffer.
- Teardown clears the augroup, stops and closes timers and `vim.uv` handles, clears extmarks, and resets module state. Opening again must behave like the first time.
- A late async result checks `nvim_buf_is_valid(buf)` and `nvim_win_is_valid(win)` and is dropped when false. Cancel the request on close when possible.

## Terminal: dependencies

- Raw ANSI sequences plus `luv` (`vim.uv` inside Neovim; `require("luv")` standalone, started with `uv.run()`).
- Use a TUI library only when the project already uses one; then follow it and skip the hand-rolled parts below.

## Terminal: raw mode and restore

- Input: `local tty = uv.new_tty(0, true)`; `tty:set_mode(1)` for raw, `0` for normal (`:help luv-tty`); read with `tty:read_start`. Output through `io.stdout:write` in one buffered string per frame.
- Restore on every exit path with one idempotent function: `tty:set_mode(0)`, show cursor (`ESC[?25h`), leave alternate screen (`ESC[?1049l`), reset attributes (`ESC[0m`); `uv.tty_reset_mode()` as a last resort.
- Paths: normal end; error (wrap the main loop in `xpcall(run, debug.traceback)`, restore, then print the traceback); SIGTERM and SIGHUP through `uv.new_signal()` + `signal:start(name, cb)`.
- In raw mode Ctrl-C is the byte `0x03` on input, not SIGINT: handle it as quit and restore. Keep a SIGINT signal handler for non-raw phases.

## Terminal: screen and resize

- Enter the alternate screen (`ESC[?1049h`) and hide the cursor at start; leave on restore. Move with `ESC[<row>;<col>H`, clear with `ESC[2J`.
- `SIGWINCH`: `uv.new_signal():start("sigwinch", cb)`, read `tty:get_winsize()`, recompute layout, redraw. Read the size once at start too.

## Terminal: no TTY and NO_COLOR

- Check `uv.guess_handle(0)` and `uv.guess_handle(1)`: when either is not `"tty"`, do not enter raw mode and emit no control sequences; print plain text as the feature spec says.
- `os.getenv("NO_COLOR")` non-empty turns colors off; attributes may stay only when output is a TTY.

## Terminal: colors

- With a `DESIGN_SYSTEM.md`, its tokens win; map each token to the nearest named color or attribute the terminal supports.
- Without the file: only the 16 named ANSI colors (SGR 30-37, 90-97 foreground; 40-47, 100-107 background) and attributes (bold 1, dim 2, underline 4, reverse 7). They follow the user's terminal theme. No 256-color or RGB sequences. No scope request for the file.

## States

- Cover in code: loading, empty, error, success, area too small (warning, not a broken layout) and resize.
- A late async result never writes to a closed buffer, window or terminal.

## manual_checks

- The command, keymap or action that opens the UI; window or terminal size, including resize and too small.
- Theme: light and dark colorscheme in Neovim; light and dark terminal theme in a TUI.
- Each state above and the expected result. TUI: "Ctrl-C and an error leave the terminal normal".

## Checklist

- No literal color anywhere; highlights are links (Neovim) or named ANSI (terminal).
- One namespace, one augroup, cleared or deleted on close; reopen works.
- Every `vim.uv` callback reaches the API through `vim.schedule`.
- Every terminal exit path restores raw mode, cursor and screen; error printed after.
- No-TTY and `NO_COLOR` handled; resize handled; too-small warning present.
- Never run the UI interactively; list the checks for the user.
