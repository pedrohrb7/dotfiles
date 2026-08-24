# If you come from bash you might have to change your $PATH.
export PATH=$HOME/bin:/usr/local/bin:$PATH
export PATH=$HOME/.local/bin:$PATH
export PATH=$HOME/.cargo/bin:$PATH

# export ASDF_DATA_DIR="/home/phrb/.asdf"
# export PATH="$ASDF_DATA_DIR/shims:$PATH"

# . /etc/profile.d/fzf.zsh
export FZF_DEFAULT_OPTS='--ansi --preview="bat --style=numbers --color=always {}" --preview-window=right:50%:wrap'
source <(fzf --zsh)

export EDITOR='nvim'
export XDG_CONFIG_HOME=$HOME/.config
export XDG_CUSTOM_DOTFILES=$HOME/dotfiles
export NVM_SYMLINK_CURRENT=true

# Path to your oh-my-zsh installation.
export ZSH=$HOME/.oh-my-zsh

ZSH_THEME="robbyrussell"

plugins=(git sdk zsh-autosuggestions zsh-syntax-highlighting)

# User configuration
## Custom config
alias rm='rm -I --preserve-root=all'
alias mv='mv -i'

# omz
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
alias gpm='git push -u origin master'
alias gpmain='git push -u origin main'
alias gps='git push -u origin'
alias gpl='git pull'
alias gm='git merge'
alias gss='git stash save'
alias gsp='git stash pop'
alias gpsb='git push bitbucket'
alias gil='git log --decorate --graph --stat --all'

alias ldocker='lazydocker'
alias lgit='lazygit'

# end of personal settings and shortcuts

# General docker shortcuts
alias ddown='docker-compose down'
alias dupd='docker-compose up -d'
alias dup='docker-compose up'
alias dockerlist='docker ps -a --format "{{.ID}} - {{.Names}} - {{.Status}}"'

alias shutupdocker='docker stop $(docker ps -aq) -t0'
alias startupdocker='docker start $(docker ps -aq)'

# Android ENV
# export ANDROID_HOME=$HOME/Android/Sdk
# export PATH=$PATH:$ANDROID_HOME/emulator
# export PATH=$PATH:$ANDROID_HOME/tools
# export PATH=$PATH:$ANDROID_HOME/tools/bin
# export PATH=$PATH:$ANDROID_HOME/platform-tools

# NVM config
export NVM_DIR="$HOME/.config/nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# This config allow NVM find and use .nvmrc on root folder in project
# place this after nvm initialization!
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

# -- Use fd instead of fzf --
export FZF_DEFAULT_COMMAND="fd --hidden --strip-cwd-prefix --exclude .git"
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
export FZF_ALT_C_COMMAND="fd --type=d --hidden --strip-cwd-prefix --exclude .git"

_fzf_compgen_path() {
  fd --hidden --exclude .git . "$1"
}

_fzf_compgen_dir() {
  fd --type=d --hidden --exclude .git . "$1"
}

export FZF_CTRL_T_OPTS="--preview 'bat -n --color=always --line-range :500 {}'"
export FZF_ALT_C_OPTS="--preview 'eza --tree --color=always {} | head -200'"

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

# Override sdkman's auto-env hook to install missing candidates from
# .sdkmanrc automatically instead of just erroring out ("sdk env install"
# installs anything missing - keeping the shell's current default - then
# switches, same as the "sdk env" load it replaces).
function sdkman_auto_env() {
	if [[ -n $SDKMAN_ENV ]] && [[ ! $PWD =~ ^$SDKMAN_ENV ]]; then
		sdk env clear
	fi
	if [[ -f .sdkmanrc ]]; then
		sdk env install
	fi
}
