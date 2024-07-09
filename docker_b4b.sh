#!/bin/zsh

# Salva o diretório atual
current_dir=$(pwd)

# Troca para o diretório desejado
cd /myhome/new-way/projects/b4b

# Executa o docker-compose em background
docker compose up -d

# Retorna ao diretório original
cd "$current_dir"
