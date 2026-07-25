#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 --n <session-name>" >&2
  exit 1
}

session=""
while [ $# -gt 0 ]; do
  case "$1" in
    --n)
      session="${2:-}"
      shift 2
      ;;
    --n=*)
      session="${1#--n=}"
      shift
      ;;
    *)
      usage
      ;;
  esac
done

[ -n "$session" ] || usage

path="$(pwd)"

if tmux has-session -t "$session" 2>/dev/null; then
  echo "Session '$session' already exists" >&2
  exit 1
fi

# Window 1: split in two panes, new pane sized to 30%
tmux new-session -d -s "$session" -c "$path"
tmux split-window -h -l 30% -t "$session" -c "$path"

# Window 2: normal
tmux new-window -t "$session" -c "$path"

# Window 3: normal, renamed to "git"
tmux new-window -t "$session" -c "$path"
tmux rename-window -t "$session" git

# Leave the user on the first window
tmux select-window -t "$session:^"
