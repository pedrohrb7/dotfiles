#!/bin/sh
# Statusline do Claude Code (statusLine em settings.json). Mostra o modelo e os
# limites do plano ("Opus 5.5 · 5h 12% · 7d 40%") e grava os limites em
# $XDG_CACHE_HOME/claude/rate-limits.json, que a seção CLAUDE do conky lê
# (conky/claude.sh).
#
# O Claude Code passa o JSON da sessão no stdin a cada atualização. rate_limits
# só vem para assinantes do claude.ai, e cada janela (five_hour, seven_day) só
# enquanto o resets_at dela não passou: janela ausente quer dizer que zerou.
# Sem nenhuma janela (sessão que ainda não falou com a API) o cache fica como
# está.

cache_dir=${XDG_CACHE_HOME:-$HOME/.cache}/claude
input=$(cat)

limits=$(printf '%s' "$input" | jq -c --argjson now "$(date +%s)" '
	(.rate_limits // {}) | {five_hour, seven_day}
	| with_entries(select(.value != null))
	| select(length > 0)
	| . + {updated_at: $now}' 2>/dev/null)

if [ -n "$limits" ] && mkdir -p "$cache_dir"; then
	tmp="$cache_dir/rate-limits.json.$$"
	printf '%s\n' "$limits" >"$tmp" && mv -f "$tmp" "$cache_dir/rate-limits.json"
fi

printf '%s' "$input" | jq -r '
	[.model.display_name // empty]
	+ ([["5h", .rate_limits.five_hour], ["7d", .rate_limits.seven_day]]
		| map(select(.[1] != null) | "\(.[0]) \(.[1].used_percentage | round)%"))
	| join(" · ")' 2>/dev/null
