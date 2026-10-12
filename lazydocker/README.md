# lazydocker

Catppuccin Mocha theme for lazydocker (`config.yml`), matching `../lazygit`.

## Install

lazydocker reads `~/.config/lazydocker/config.yml`. Symlink it to this repo:

```sh
mkdir -p ~/.config/lazydocker
ln -sf ~/dotfiles/lazydocker/config.yml ~/.config/lazydocker/config.yml
```

Without this link lazydocker falls back to its default theme, where the
selected line background is ANSI `blue` (kitty `color4` = `#89b4fa`), which
makes the highlighted text hard to read. The theme here sets
`selectedLineBgColor` to `#313244`.
