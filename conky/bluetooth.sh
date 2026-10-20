#!/bin/sh
# Seção Bluetooth do conky (chamado por bluetooth.lua): um bloco por adaptador,
# com os dispositivos conectados nele. O adaptador é "Dongle" quando o USB é
# removível e "Interno" quando é fixo na placa.
# Lê tudo do BlueZ numa única chamada D-Bus (GetManagedObjects).

objects=$(busctl --json=short call org.bluez / org.freedesktop.DBus.ObjectManager GetManagedObjects 2>/dev/null) || {
	printf '${color2}Serviço${alignr}${color7}bluetoothd parado${color}\n'
	exit 0
}

adapters=$(printf '%s' "$objects" | jq -r '
	.data[0] | to_entries[] | select(.value["org.bluez.Adapter1"])
	| "\(.key | ltrimstr("/org/bluez/")) \(.value["org.bluez.Adapter1"].Powered.data)"' | sort)

if [ -z "$adapters" ]; then
	printf '${color2}Adaptador${alignr}${color}Nenhum\n'
	exit 0
fi

sep=$(printf '\037')

printf '%s\n' "$adapters" | while read -r hci powered; do
	label=Interno
	[ "$(cat "/sys/class/bluetooth/$hci/device/../removable" 2>/dev/null)" = removable ] && label=Dongle

	if [ "$powered" != true ]; then
		printf '${color2}%s${alignr}${color7}Desligado${color}\n' "$label"
		continue
	fi

	# Uma linha por dispositivo: nome (até 22 caracteres, "$" escapado como
	# "$$" para o conky não interpretar) e bateria, separados por \037.
	devices=$(printf '%s' "$objects" | jq -r --arg adapter "/org/bluez/$hci" --arg sep "$sep" '
		.data[0][]
		| select(.["org.bluez.Device1"].Adapter.data == $adapter and .["org.bluez.Device1"].Connected.data)
		| "\(.["org.bluez.Device1"].Alias.data[0:22] | gsub("\\$"; "$$"))\($sep)\(.["org.bluez.Battery1"].Percentage.data // "")"')
	count=$(printf '%s' "$devices" | grep -c .)

	case $count in
	0) status='${color}sem conexões' ;;
	1) status='${color0}1 conectado' ;;
	*) status="\${color0}$count conectados" ;;
	esac
	printf '${color2}%s${alignr}${color5}Ligado${color2}  ·  %s${color}\n' "$label" "$status"

	[ "$count" -eq 0 ] && continue
	printf '%s\n' "$devices" | while IFS="$sep" read -r name battery; do
		if [ -n "$battery" ]; then
			color='${color0}'
			[ "$battery" -le 20 ] && color='${color7}'
			printf '${goto 24}${color}%s${alignr}%s󰥉 %s%%${color}\n' "$name" "$color" "$battery"
		else
			printf '${goto 24}${color}%s\n' "$name"
		fi
	done
done
