---
name: neovim-plugin
description: Neovim plugin and config know-how in Lua - plugin layout and lazy-loading, setup(opts) with vim.validate, user commands and <Plug> mappings, autocmds in augroups, vim.uv callbacks through vim.schedule, minimum-version guards, :checkhealth, and headless tests (busted, plenary, mini.test, minimal_init). Preloaded by the lua agent. Use when writing, reviewing or testing Lua for Neovim - a plugin with lua/ + plugin/, an init.lua config, or code calling vim.api, vim.fn or vim.uv.
---

# Neovim plugin

Rules for Lua that runs inside Neovim. When unsure about a recent API, use the stable form or check `:help <api>`; never guess a signature.

## Plugin or config

- `lua/` plus `plugin/` (or a rockspec) is a plugin. `init.lua` plus `lua/` without `plugin/` is a user config.
- In a config, apply no plugin convention (`setup`, `health.lua`, `<Plug>`): the existing structure rules.

## Layout and loading

- `plugin/<name>.lua` stays minimal: a double-load guard (`if vim.g.loaded_<name> then return end`, then `vim.g.loaded_<name> = 1`), then commands and mappings only.
- Defer `require("<name>")` into the command or mapping callback, so startup loads nothing.
- Commands: `vim.api.nvim_create_user_command(name, fn, opts)`. Mappings: expose `<Plug>(name-action)`; never set a default keymap unless asked.
- Modules return a table `M`; no globals, no work at `require` time beyond defining functions.

## setup and configuration

- Keep defaults in one table. `setup(opts)` only overrides: `vim.tbl_deep_extend("force", defaults, opts or {})`.
- Validate the merged config with `vim.validate`, in the form the minimum version supports: `vim.validate(name, value, validator[, optional][, message])` from 0.11, the table form before it (deprecated later). Check `:help vim.validate`.
- `setup` is idempotent: calling it twice must not duplicate autocmds, commands or timers.

## Autocmds

- Always inside a named group: `vim.api.nvim_create_augroup("<Name>", { clear = true })`, passed as `group`.
- Buffer-local (`buffer = bufnr`) when tied to one buffer.
- Removed on teardown: clear the group or delete by id.

## Async

- A callback from `vim.uv` (or any fast event context, e.g. `vim.uv` handles, `vim.uv.new_timer` timers, `vim.system` callbacks; not `vim.fn.jobstart`, which runs on the main loop) cannot safely call most `vim.api`/`vim.fn` functions: wrap with `vim.schedule` or `vim.schedule_wrap` first (see `:help api-fast`).
- Close every handle and timer you open (`handle:close()`, `timer:stop()` then `timer:close()`), including on error paths.
- With a minimum version below 0.10, use `local uv = vim.uv or vim.loop`.
- Re-check `nvim_buf_is_valid` / `nvim_win_is_valid` before using an id after any async gap.

## Minimum version

- Find it, in order: README, CI matrix, `health.lua`, `vim.fn.has("nvim-0.x")` guards, `mise.toml`/tool versions. Report it in `notes`.
- Use no API newer than it. For an optional newer API, guard with `vim.fn.has("nvim-0.x") == 1` or a feature check (`if vim.foo then`).
- Prefer `vim.api.nvim_*` and long-stable `vim.fn`/`vim.*` helpers over recent shortcuts.

## Health

- `lua/<name>/health.lua` exports `check()` and uses `vim.health.start/ok/warn/error` (older versions: `report_*`, check `:help health`).
- Cover the config and each external dependency (executables, optional plugins, version).
- Update it in the same task when the task adds or changes one of those.

## Headless tests

- Pick the runner the project already uses; never add another:
  - plain busted (`.busted`, `busted` binary, often with a `vim` mock or helper);
  - plenary: `nvim --headless -u tests/minimal_init.lua -c "PlenaryBustedFile <file>"` (`PlenaryBustedDirectory <dir> { minimal_init = "..." }` for many files);
  - mini.test: `nvim --headless -u tests/minimal_init.lua -c "lua MiniTest.run_file('<file>')"`.
- The command is narrow: one test file, the project's `minimal_init`, wrapped in `timeout`.
- Never create a `minimal_init` unasked; if missing, report it as blocked or a `manual_checks` item.
- Neovim runs only with `--headless`; never an interactive session.
- Tests set up and tear down their own state (buffers, augroups, globals) so order never matters.

## UI

- Windows, floating panels and scratch buffers used as UI follow `lua-tui`.

## Checklist before the report

- `plugin/` file minimal, guarded, requires deferred.
- `setup(opts)` validated and idempotent; no keymap defaults.
- Every autocmd in a named, cleared group; torn down.
- Every `vim.uv` callback reaches `vim.api` through `vim.schedule`; handles closed.
- No API newer than the minimum version, or a guard for it.
- Health updated if config or dependencies changed.
- Test run is one file, headless, with `timeout` and the project's `minimal_init`.
