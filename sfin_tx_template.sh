#!/bin/zsh

session_name='sisfin'

# tmux has-session -t $session_name
PROJECT_PATH='/mnt/data/projects/jobs/dmk3/itesp/sisfin'

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
  tmux split-window               -v -p 30 -t $session_name:3
 
  tmux send-keys                  -t $session_name:0.0 "cd $PROJECT_PATH/sisfin-api && lazygit" Enter
  tmux send-keys                  -t $session_name:0.1 "cd $PROJECT_PATH/sisfin-front && lazygit" Enter

  tmux send-keys                  -t $session_name:1   "cd $PROJECT_PATH/sisfin-api && svim" Enter
  tmux send-keys                  -t $session_name:2   "cd $PROJECT_PATH/sisfin-front && svim" Enter

  tmux send-keys                  -t $session_name:3.0   "cd $PROJECT_PATH/sisfin-api" Enter
  tmux send-keys                  -t $session_name:3.1   "cd $PROJECT_PATH/sisfin-front" Enter
fi

# tmux attach -t $session_name
