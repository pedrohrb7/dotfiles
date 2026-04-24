# Oh my zshell config
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="robbyrussell"
plugins=(git sdk zsh-autosuggestions zsh-syntax-highlighting)
source $ZSH/oh-my-zsh.sh

# If you come from bash you might have to change your $PATH.
export PATH=$HOME/bin:/usr/local/bin:$PATH
export PATH=$HOME/.local/bin:$PATH
export PATH=$HOME/.cargo/bin:$PATH

export EDITOR='nvim'

export XDG_CONFIG_HOME=$HOME/.config
export XDG_CUSTOM_DOTFILES=$HOME/dotfiles

# Android ENV
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/emulator
export PATH=$PATH:$ANDROID_HOME/tools
export PATH=$PATH:$ANDROID_HOME/tools/bin
export PATH=$PATH:$ANDROID_HOME/platform-tools

# source more
source ~/private.zsh
source ~/dmk3.zsh
source $ZSH/oh-my-zsh.sh

# ---- FZF -----
# Set up fzf key bindings and fuzzy completion
eval "$(fzf --zsh)"

# --- setup fzf theme ---
fg="#CBE0F0"
bg="#011628"
bg_highlight="#143652"
purple="#B388FF"
blue="#06BCE4"
cyan="#2CF9ED"

alias zshrestart="source ~/.zshrc"
alias zshconfig="nvim ~/.zshrc"
alias ohmyzsh="nvim ~/.oh-my-zsh"

# ls
alias l='ls -lh'
alias ll='ls -lah'
alias la='ls -A'
alias lm='ls -m'
alias lr='ls -R'
alias lg='ls -l --group-directories-first'

# filesystem usage, default human readable sizes
alias df='df -h'
alias du='du -h'

# git
alias gcl='git clone --depth 1'
alias sgcl='git clone --config core.sshcommand="ssh -i ~/.ssh/private/id_ed25519"'
alias gi='git init'
alias ga='git add'
alias gc='git commit'
alias gck='git checkout'
alias gps='git push -u origin'
alias gpl='git pull'
alias gm='git merge'
alias gss='git stash save'
alias gsp='git stash pop'
alias gil='git log --decorate --graph --stat --all'

# personal settings and shortcuts
alias spacman='sudo pacman'
alias cdir='mkdir -p'
alias rm='rm -I --preserve-root=all'
alias mv='mv -i'
alias errors="journalctl -b -p err | less"

alias projects='cd /mnt/data/projects'
alias ldocker='lazydocker'
alias lgit='lazygit'

# ----- Docker ------

alias vdockerup="sudo ln -s /etc/sv/docker /var/service"
alias vdockerdown="sudo rm /var/service/docker"

#

# ----- Bat (better cat) -----
alias cat="bat"

# ---- Eza (better ls) -----
alias ls="eza --color=always --long --git --icons=always"

# end of personal settings and shortcuts

alias startdb="/mnt/data/projects/server/databases/docker_databases.sh"

export NVM_DIR="$HOME/.config/nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

autoload -U add-zsh-hook
load-nvmrc() {
  local nvmrc_path="$(nvm_find_nvmrc)"

  if [ -n "$nvmrc_path" ]; then
    local nvmrc_node_version=$(nvm version "$(cat "${nvmrc_path}")")

    if [ "$nvmrc_node_version" = "N/A" ]; then
      nvm install
    elif [ "$nvmrc_node_version" != "$(nvm version)" ]; then
      nvm use
    fi
  elif [ -n "$(PWD=$OLDPWD nvm_find_nvmrc)" ] && [ "$(nvm version)" != "$(nvm version default)" ]; then
    echo "Reverting to nvm default version"
    nvm use default
  fi
}
add-zsh-hook chpwd load-nvmrc
load-nvmrc

# Use fd (https://github.com/sharkdp/fd) for listing path candidates.
# - The first argument to the function ($1) is the base path to start traversal
# - See the source code (completion.{bash,zsh}) for the details.
_fzf_compgen_path() {
  fd --hidden --exclude .git . "$1"
}

# Use fd to generate the list for directory completion
_fzf_compgen_dir() {
  fd --type=d --hidden --exclude .git . "$1"
}

# Advanced customization of fzf options via _fzf_comprun function
# - The first argument to the function is the name of the command.
# - You should make sure to pass the rest of the arguments to fzf.
 _fzf_comprun() {
  local command=$1
  shift

  case "$command" in
    cd)           fzf --preview 'eza --tree --color=always {} | head -200' "$@" ;;
    export|unset) fzf --preview "eval 'echo \$'{}"         "$@" ;;
    ssh)          fzf --preview 'dig {}'                   "$@" ;;
    *)            fzf --preview "bat -n --color=always --line-range :5000 {}" "$@" ;;
  esac
}

fd() {
  preview="git diff $@ --color=always -- {-1}"
  git diff $@ --name-only | fzf -m --ansi --preview $preview
}

#THIS MUST BE AT THE END OF THE FILE FOR SDKMAN TO WORK!!!
export SDKMAN_DIR="$HOME/.sdkman"
[[ -s "$HOME/.sdkman/bin/sdkman-init.sh" ]] && source "$HOME/.sdkman/bin/sdkman-init.sh"
