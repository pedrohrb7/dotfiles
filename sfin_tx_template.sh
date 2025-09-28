#!/bin/zsh

session_name='sisfin'

# tmux has-session -t $session_name

tmux new-session                -d -s $session_name -c ~/projects/sisfin 2>/dev/null
if [ $? = 0 ]
then
  # create session with window lazygit
  tmux split-window               -h -p 40 -t $session_name:0

  # create other windows
  tmux new-window                 -t $session_name:1
  tmux rename-window              -t $session_name:1  api 

  tmux new-window                 -t $session_name:2
  tmux rename-window              -t $session_name:2 front 

  tmux new-window                 -t $session_name:3
  tmux split-window               -h -p 40 -t $session_name:3
 
  tmux send-keys                  -t $session_name:0.0 'cd ~/projects/sisfin/sisfin-api && lazygit' Enter
  tmux send-keys                  -t $session_name:0.1 'cd ~/projects/sisfin/sisfin-front && lazygit' Enter

  tmux send-keys                  -t $session_name:1   'cd ~/projects/sisfin/sisfin-api && svim' Enter
  tmux send-keys                  -t $session_name:2   'cd ~/projects/sisfin/sisfin-front && svim' Enter

  tmux send-keys                  -t $session_name:3.0   'cd ~/projects/sisfin/sisfin-api' Enter
  tmux send-keys                  -t $session_name:3.1   'cd ~/projects/sisfin/sisfin-front' Enter
fi

# tmux attach -t $session_name
