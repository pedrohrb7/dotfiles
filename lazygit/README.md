# lazygit

Catppuccin Mocha theme for lazygit (`config.yml`).

## Install

lazygit reads `~/.config/lazygit/config.yml`. Symlink it to this repo:

```sh
mkdir -p ~/.config/lazygit
ln -sf ~/dotfiles/lazygit/config.yml ~/.config/lazygit/config.yml
```

Without this link lazygit falls back to its default theme, where the selected
line background is ANSI `blue` (kitty `color4` = `#89b4fa`), which makes the
highlighted text hard to read. The theme here sets `selectedLineBgColor` to
`#313244`.
