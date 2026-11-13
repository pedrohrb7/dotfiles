# Lua - <project name>

<!-- Reverse-engineered understanding of the Lua code as it actually exists today, not aspirational. One block per Lua unit chosen in onboard step 2: "## <unit path>" ("## ." when the whole repo is the unit), with the sections below one level down. Other units keep their own documents (BACKEND.md, FRONTEND.md, MOBILE.md); a Lua service such as an OpenResty gateway goes here, not in BACKEND.md. An item that does not apply to the unit's runtime says so ("not applicable: library without UI"), never a placeholder. -->

## <unit path>

### Stack

- Runtime: <!-- Neovim plugin, Neovim config, LÖVE, OpenResty, standalone, or embedded with the host's name -->
- Lua version and where it is declared:
- Minimum Neovim version (Neovim only):
- Key dependencies: <!-- rocks, plugins such as plenary -->
- Tools: <!-- tests, lint, format, mise -->

### Folder structure

<!-- The real tree, annotated with what's actually there - not what a template says should be there. -->

```
```

### Design patterns in use

<!-- What the codebase actually does, observed from the code, not assumed. -->

- Module organization and public API:
- Entry points and loading: <!-- plugin/, setup, lazy-loading, commands, host entry -->
- Configuration and validation:
- Async and event loop: <!-- vim.uv/luv, vim.schedule, coroutines -->
- UI: <!-- windows, buffers, extmarks, highlights; or raw mode and alternate screen; or "not applicable" -->
- Error handling and notification:
- Health check:
- Testing: <!-- framework, minimal_init, helpers, where tests live -->

### Conventions observed

- Naming:
- File organization:
- LuaCATS annotations:

### Inconsistencies

<!-- Places where the same concern is solved differently in different parts of the unit. -->

-

### Recommendations

<!-- Compared against the conventions of the neovim-plugin and lua-tui skills (there is no Lua STRUCTURE.md). What's already solid, what's worth realigning, in priority order. A starting point for a conversation, not a mandate to refactor. -->

-

### Open questions

<!-- Things that couldn't be determined from the code alone. -->

-
