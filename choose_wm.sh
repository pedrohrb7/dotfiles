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
            case $env in
                "i3")
                    exec i3
                    ;;
                "Awesome")
                    exec awesome
                    ;;
                "Qtile")
                    exec qtile
                    ;;
                "Exit")
                    exit 0
                    ;;
                *)
                    echo "Opção inválida. Tente novamente."
                    ;;
            esac
        else
            echo "Opção inválida. Tente novamente."
        fi
    done
}

# Executa a função show_menu
show_menu
