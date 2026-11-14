#!/bin/sh
# Seção CLAUDE do conky (rodado em segundo plano por claude.lua): limites do
# plano e tokens por modelo do Claude Code.
#
# Limites: % usado da sessão de 5 h e da semana, com o horário em que zeram.
# Vêm do cache que a statusline do Claude Code grava (.claude/statusline.sh),
# então só mudam quando o Claude Code recebe uma resposta; a linha
# "Atualizado" diz de quando é o dado. Janela cujo reset já passou mostra 0%.
#
# Tokens por modelo: somados dos transcripts em ~/.claude/projects (entrada,
# saída, escrita e leitura de cache), dentro da janela de cada limite: desde o
# início da sessão de 5 h e da semana atuais, ou as últimas 5 h e os últimos
# 7 dias quando a janela não é conhecida. Uma resposta aparece em várias linhas
# do transcript (uma por bloco de conteúdo), então conta uma vez por
# message.id + requestId.

limits_file=${XDG_CACHE_HOME:-$HOME/.cache}/claude/rate-limits.json
projects=${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects
now=$(date +%s)
week_ago=$((now - 7 * 86400))

limits=$(jq -c . "$limits_file" 2>/dev/null) || limits='{}'
[ -n "$limits" ] || limits='{}'

# Só os transcripts escritos na última semana podem ter linhas dentro das
# janelas (a da semana começa no máximo 7 dias atrás).
find "$projects" -name '*.jsonl' -newermt "@$week_ago" -print0 2>/dev/null |
	xargs -0 -r grep -h '"usage"' 2>/dev/null |
	jq -nrR --argjson now "$now" --argjson limits "$limits" '
		# 1234 -> 1.2k, 38200000 -> 38.2M; inteiro a partir de 100.
		def human:
			(if . >= 1e9 then [1e9, "G"] elif . >= 1e6 then [1e6, "M"]
			 elif . >= 1e3 then [1e3, "k"] else [1, ""] end) as [$d, $u]
			| (. / $d) as $v
			| (if $v >= 100 or $d == 1 then $v | floor else $v * 10 | floor / 10 end | tostring) + $u;

		# claude-opus-5-5 -> Opus 5.5, claude-3-5-sonnet-20241022 -> Sonnet 3.5
		def model_name:
			sub("^claude-"; "") | split("-") | map(select(test("^[0-9]{8}$") | not))
			| (map(select(test("^[0-9]+$") | not)) | join(" ")) as $family
			| (map(select(test("^[0-9]+$"))) | join(".")) as $version
			| ($family[:1] | ascii_upcase) + $family[1:] + (if $version != "" then " " + $version else "" end);

		def color: if . >= 90 then 7 elif . >= 75 then 6 else 0 end;
		def bar_color: if . >= 90 then 7 elif . >= 75 then 6 else 4 end;

		def day: strflocaltime("%Y-%m-%d");
		def weekday: ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"][localtime[6]];
		# Mesmo dia: 18:40. Outro dia da semana: sáb 09:00. Mais longe: 07/11 09:00.
		def when:
			if day == ($now | day) then strflocaltime("%H:%M")
			elif (. - $now | fabs) < 6 * 86400 then "\(weekday) \(strflocaltime("%H:%M"))"
			else strflocaltime("%d/%m %H:%M") end;

		# Janela de um limite: início, % usado e reset (null se já passou ou
		# não é conhecido).
		def window($key; $length):
			$limits[$key] as $l
			| if $l != null and $l.resets_at > $now then
				{start: ($l.resets_at - $length), percent: ($l.used_percentage | round), reset: $l.resets_at}
			  elif $l != null then
				{start: ($now - $length), percent: 0, reset: null}
			  else
				{start: ($now - $length), percent: null, reset: null}
			  end
			| .since = (.start | todate[:19]);

		def section($title; $w; $usage):
			([$usage[] | select(.ts >= $w.since)]
			 | group_by(.model)
			 | map({model: .[0].model, tokens: (map(.tokens) | add)})
			 | sort_by(-.tokens)) as $models
			| ($models | map(.tokens) | add // 0) as $total
			| (if $w.percent == null then
				"${color2}\($title)${alignr}${color}sem limite"
			   else
				"${color2}\($title)${alignr}${color\($w.percent | color)}\($w.percent)%"
				+ (if $w.reset != null then "${color2}  ·  ${color}\($w.reset | when)" else "" end),
				"${color\($w.percent | bar_color)}${lua_bar claude_percent \($w.percent)}"
			   end),
			  (if $models == [] then "${color2}Sem uso"
			   else $models[]
				| "${color}\(.model | model_name)${goto 160}${color0}\(.tokens | human)${alignr}${color}\(.tokens * 100 / $total | round)%"
			   end);

		[inputs | fromjson? | select(.type == "assistant" and .message.usage != null)
		 | select((.message.model // "") | startswith("claude-"))
		 | {key: "\(.message.id) \(.requestId)", ts: .timestamp, model: .message.model,
		    tokens: (.message.usage | [.input_tokens, .output_tokens, .cache_creation_input_tokens, .cache_read_input_tokens] | map(. // 0) | add)}]
		| unique_by(.key) as $usage
		| section("Sessão 5h"; window("five_hour"; 5 * 3600); $usage),
		  section("Semana"; window("seven_day"; 7 * 86400); $usage),
		  (if $limits.updated_at != null then
			"${color2}Atualizado${alignr}${color}\($limits.updated_at | when)"
		   else
			"${color2}Limites${alignr}${color}sem dados da statusline"
		   end)'
