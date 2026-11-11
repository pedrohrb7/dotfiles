-- Configuração compartilhada pelas duas colunas do conky (right.conf e
-- left.conf): janela, fonte, desenho, atualização, paleta Tokyo Night (a mesma
-- de awesome/config/styles/color.lua) e templates. Cada coluna chama
-- config(overrides) com o que é só dela (alinhamento, lua_load, mouse hook).
-- Referência das variáveis: `man conky` ou https://conky.cc/variables
--
-- O conky só recarrega sozinho o arquivo passado em -c: depois de editar este,
-- salvar right.conf e left.conf (ou reiniciar o conky).

local M = {}

local BASE = {
	-- Janela: tipo "desktop" + hints fazem o conky ficar no fundo, em todas as
	-- tags, sem decoração e fora da tasklist. A regra "Conky" em
	-- awesome/config/rules.lua garante o mesmo do lado do awesome.
	own_window = true,
	own_window_type = "desktop",
	own_window_class = "Conky",
	own_window_hints = "undecorated,below,sticky,skip_taskbar,skip_pager",

	-- Fundo semitransparente, formato #AARRGGBB: AA é a opacidade
	-- (00 = transparente, ff = opaco). Precisa do picom rodando.
	-- No conky 1.24+ own_window_argb_visual/argb_value não funcionam mais.
	own_window_colour = "#a61a1b26",

	-- Posição e tamanho: alignment fica em cada coluna. gap_y deixa a wibar livre.
	gap_x = 12,
	gap_y = 36,
	minimum_width = 260,
	maximum_width = 260,
	border_inner_margin = 14,

	-- Texto
	use_xft = true,
	font = "FiraCode Nerd Font:size=9",
	uppercase = false,
	use_spacer = "none",
	short_units = true,
	format_human_readable = true,
	top_name_width = 18,

	-- Desenho
	double_buffer = true,
	draw_borders = false,
	draw_outline = false,
	draw_shades = false,
	draw_graph_borders = false,
	default_bar_height = 4,
	default_graph_height = 22,

	-- Atualização
	update_interval = 2,
	cpu_avg_samples = 2,
	net_avg_samples = 2,
	no_buffers = true,
	if_up_strictness = "address",

	-- Paleta (color0..color9 são usadas em conky.text como ${colorN})
	default_color = "a9b1d6", -- texto (gray_lighter)
	color0 = "ffffff", -- valores em destaque
	color1 = "bb9af7", -- títulos de seção (primary / magenta)
	color2 = "565f89", -- rótulos
	color3 = "36424c", -- linhas separadoras
	color4 = "7aa2f7", -- barras e gráficos (blue)
	color5 = "73daca", -- download / ok (green)
	color6 = "e0af68", -- upload / atenção (yellow)
	color7 = "f7768e", -- crítico (red)

	-- Templates: ${templateN arg1 arg2} substitui \1, \2 pelos argumentos.
	-- template0: cabeçalho de seção  -> ${template0 <ícone> <título>}
	template0 = "${color1}${font FiraCode Nerd Font:bold:size=9}\\1  \\2${font} ${color3}${voffset -1}${hr 1}${voffset 1}${color}",
	-- template1: linha "rótulo .... valor"  -> ${template1 <rótulo> <valor>}
	template1 = "${color2}\\1${alignr}${color0}\\2${color}",
	-- template2: processo do top por CPU  -> ${template2 <posição>}
	template2 = "${color}${top name \\1}${goto 160}${color0}${top cpu \\1}%${alignr}${color}${top mem \\1}%",
	-- template3: processo do top por memória  -> ${template3 <posição>}
	template3 = "${color}${top_mem name \\1}${goto 160}${color0}${top_mem mem_res \\1}${alignr}${color}${top_mem mem \\1}%",
	-- template4: interface de rede  -> ${template4 <iface>}
	template4 = [[
${color2}IP${alignr}${color0}${addr \1}
${color5}󰁅 ${color0}${downspeed \1}${goto 149}${color6}󰁝 ${color0}${upspeed \1}
${downspeedgraph \1 22,125 73daca 73daca}${goto 149}${upspeedgraph \1 22,125 e0af68 e0af68}
${color2}Total ${color}${totaldown \1}${goto 149}${color2}Total ${color}${totalup \1}]],
}

-- BASE com as chaves de overrides por cima.
function M.config(overrides)
	local result = {}
	for k, v in pairs(BASE) do
		result[k] = v
	end
	for k, v in pairs(overrides) do
		result[k] = v
	end
	return result
end

return M
