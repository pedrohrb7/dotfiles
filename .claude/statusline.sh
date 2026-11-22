#!/bin/sh
# Statusline do Claude Code (statusLine em settings.json). Mostra o modelo e os
# limites do plano ("Opus 5.5 · 5h 12% · 7d 40%").
#
# O Claude Code passa o JSON da sessão no stdin a cada atualização. rate_limits
# só vem para assinantes do claude.ai, e cada janela (five_hour, seven_day) só
# enquanto o resets_at dela não passou: janela ausente quer dizer que zerou.

jq -r '
	[.model.display_name // empty]
	+ ([["5h", .rate_limits.five_hour], ["7d", .rate_limits.seven_day]]
		| map(select(.[1] != null) | "\(.[0]) \(.[1].used_percentage | round)%"))
	| join(" · ")' 2>/dev/null
