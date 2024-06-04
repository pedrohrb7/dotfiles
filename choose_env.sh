#!/bin/zsh

# Lista de ambientes de desktop disponíveis
environments=("i3" "Awesome" "Qtile" "Exit")

# Função para exibir o menu e obter a escolha do usuário
show_menu() {
    echo "Selecione o ambiente de desktop que deseja iniciar:"
    PS3="Digite o número correspondente à sua escolha: "
    select env in "${environments[@]}"; do
        if [[ -n "$env" ]]; then
            echo "Você selecionou $env"
            if [[ "$env" == "Exit" ]]; then
                exit 0
            else
                startx /home/pedro/dotfiles-config/$env/.xinitrc
            fi
        else
            echo "Opção inválida. Tente novamente."
        fi
    done
}

# Executa a função show_menu
show_menu
