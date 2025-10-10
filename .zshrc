# If you come from bash you might have to change your $PATH.
export PATH=$HOME/bin:/usr/local/bin:$PATH
export PATH=$HOME/.local/bin:$PATH

export PATH=$HOME/.cargo/bin:$PATH

export PATH="${ASDF_DATA_DIR:-$HOME/.asdf}/shims:$PATH"

. /etc/profile.d/fzf.zsh
export FZF_DEFAULT_OPTS='--ansi --preview="bat --style=numbers --color=always {}" --preview-window=right:50%:wrap'
source <(fzf --zsh)

export EDITOR='/usr/bin/nvim'
export XDG_CONFIG_HOME=$HOME/.config
export XDG_CUSTOM_DOTFILES=$HOME/dotfiles
export NVM_SYMLINK_CURRENT=true

alias svim='NVIM_APPNAME=smoothvim nvim'

# source more
source ~/private.zsh
source ~/dmk3.zsh

source ~/.config/fzf-git.sh/fzf-git.sh
. "$HOME/.cargo/env"

# Path to your oh-my-zsh installation.
export ZSH=$HOME/.oh-my-zsh

ZSH_THEME="half-life"

plugins=(git sdk asdf zsh-autosuggestions zsh-syntax-highlighting)

source $ZSH/oh-my-zsh.sh

# User configuration
## Custom config
alias cdir='mkdir -p'
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

# personal settings and shortcuts
alias spacman='sudo pacman'
alias cdir='mkdir -p'
alias rm='rm -I --preserve-root=all'
alias mv='mv -i'
alias errors="journalctl -b -p err | less"

alias projects='cd /mnt/data/projects'
alias ldocker='lazydocker'
alias lgit='lazygit'
alias ldkr='lazydocker'

# end of personal settings and shortcuts

alias startdb="/mnt/data/projects/databases/docker_databases.sh"

# sonar configs
export SONAR_URL="http://127.0.0.1:9003"

alias sonarltsc="docker run -d -m4g --name sonarqubeLTScommunity -p 9003:9000 -p 9092:9092 sonarqube:lts-community"
alias sonar98c="docker run -d -m4g --name sonarqube98community -p 9003:9000 -p 9092:9092 sonarqube:9.8.0-community"
alias sonar10c="docker run --name sonarqube10community -p 9003:9000 -p 9092:9092 sonarqube:10.1-community"

alias sonaru="docker start sonarqube10community"
alias sonarr='docker run --rm -ti -v ${PWD}:/usr/src --link sonarqube10community sonarsource/sonar-scanner-cli sonar-scanner -D"sonar.sources=." -D"sonar.host.url=$SONAR_URL" -D"sonar.token=$SONAR_TOKEN" -D"sonar.projectVersion=$(git rev-parse --symbolic-full-name --abbrev-ref HEAD)" -X'

# General docker shortcuts
alias ddown='docker-compose down'
alias dupd='docker-compose up -d'
alias dup='docker-compose up'
alias dklist='docker ps -a --format "{{.ID}} - {{.Names}} - {{.Status}}"'

alias dockerdown="sudo systemctl stop docker.service docker.socket"
alias dockerup="sudo systemctl start docker.service docker.socket"
alias dockerstatus="sudo systemctl status docker.service docker.socket"

alias shutupdocker='docker stop $(docker ps -aq) -t0'
alias startupdocker='docker start $(docker ps -aq)'
alias dkkill='docker rm -f $(docker ps -aq)'
# End of docker shortcuts

# Android ENV
export ANDROID_HOME=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_HOME/emulator
export PATH=$PATH:$ANDROID_HOME/tools
export PATH=$PATH:$ANDROID_HOME/tools/bin
export PATH=$PATH:$ANDROID_HOME/platform-tools

# NVM config
# export NVM_DIR="$HOME/.config/nvm"
# [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
# [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# This config allow NVM find and use .nvmrc on root folder in project
# place this after nvm initialization!
# autoload -U add-zsh-hook
# load-nvmrc() {
#   local nvmrc_path="$(nvm_find_nvmrc)"
#
#   if [ -n "$nvmrc_path" ]; then
#     local nvmrc_node_version=$(nvm version "$(cat "${nvmrc_path}")")
#
#     if [ "$nvmrc_node_version" = "N/A" ]; then
#       nvm install
#     elif [ "$nvmrc_node_version" != "$(nvm version)" ]; then
#       nvm use
#     fi
#   elif [ -n "$(PWD=$OLDPWD nvm_find_nvmrc)" ] && [ "$(nvm version)" != "$(nvm version default)" ]; then
#     echo "Reverting to nvm default version"
#     nvm use default
#   fi
# }
# add-zsh-hook chpwd load-nvmrc
# load-nvmrc

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

export FZF_DEFAULT_OPTS="--color=fg:${fg},bg:${bg},hl:${purple},fg+:${fg},bg+:${bg_highlight},hl+:${purple},info:${blue},prompt:${cyan},pointer:${cyan},marker:${cyan},spinner:${cyan},header:${cyan}"

# -- Use fd instead of fzf --
export FZF_DEFAULT_COMMAND="fd --hidden --strip-cwd-prefix --exclude .git"
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
export FZF_ALT_C_COMMAND="fd --type=d --hidden --strip-cwd-prefix --exclude .git"

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

# ----- Bat (better cat) -----
alias cat="bat"

# ---- Eza (better ls) -----
alias ls="eza --color=always --long --git --icons=always"

fd() {
  preview="git diff $@ --color=always -- {-1}"
  git diff $@ --name-only | fzf -m --ansi --preview $preview
}
