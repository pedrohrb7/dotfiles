#!/bin/bash

# Função para exibir o menu e capturar a escolha do usuário
escolher_opcao() {
    echo "Escolha uma opção:"
    echo "1) builtin.sh"
    echo "2) external.sh"
    echo "3) twoAbove.sh"
    read -p "Digite o número da sua escolha: " escolha
}

# Função para executar o script escolhido
executar_opcao() {
    case $escolha in
        1)
            echo "Executando builtin.sh..."
            bash ~/.screenlayout/only_builtin.sh
            ;;
        2)
            echo "Executando external.sh..."
            bash ~/.screenlayout/only_vga.sh
            ;;
        3)
            echo "Executando twoAbove.sh..."
            bash ~/.screenlayout/two_monitors_above.sh
            ;;
        *)
            echo "Escolha inválida. Tente novamente."
            escolher_opcao
            executar_opcao
            ;;
    esac
}

# Chama a função para exibir o menu
escolher_opcao
# Chama a função para executar a opção escolhida
executar_opcao
