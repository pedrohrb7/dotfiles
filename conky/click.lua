-- Cliques no conky (lua_mouse_hook = "on_mouse" em conky.conf).
-- Coordenadas do evento são relativas à janela do conky.
-- O conky procura funções globais com prefixo conky_.
---@diagnostic disable: lowercase-global

-- A área clicável da seção Bluetooth é medida a partir do fim da janela: o
-- texto de conky.text abaixo dela é renderizado com conky_parse no momento do
-- clique e as linhas são contadas, então a conta acompanha as seções que mudam
-- de altura (bateria). As seções abaixo do Bluetooth não podem ter gráficos,
-- que deixam a linha mais alta que LINE_HEIGHT.
local LINE_HEIGHT = 16 -- altura de uma linha com FiraCode Nerd Font size=9
local MARGIN = 14 -- border_inner_margin
local CONF = os.getenv("HOME") .. "/.config/conky/conky.conf"
local MARKER = "${lua_parse bluetooth}"

-- Trecho de conky.text depois da seção Bluetooth. O conky recarrega o Lua ao
-- salvar conky.conf, então basta ler uma vez.
local function text_below_bluetooth()
	local env = { conky = {} }
	local chunk = loadfile(CONF, "t", env)
	if chunk == nil or not pcall(chunk) or type(env.conky.text) ~= "string" then
		return nil
	end
	local _, finish = env.conky.text:find(MARKER, 1, true)
	return finish and env.conky.text:sub(finish + 1)
end

local below = text_below_bluetooth()

local function in_bluetooth(y)
	if below == nil then
		return false
	end
	-- O conky não desenha a linha vazia depois de um "\n" final.
	local _, lines_below = conky_parse(below):gsub("\n$", ""):gsub("\n", "")
	local finish = conky_window.height - MARGIN - lines_below * LINE_HEIGHT
	return y >= finish - bluetooth_lines * LINE_HEIGHT and y <= finish
end

function conky_on_mouse(ev)
	if conky_window == nil or ev.type ~= "button_down" or ev.button ~= "left" then
		return false
	end
	if in_bluetooth(ev.y) then
		os.execute("blueman-manager >/dev/null 2>&1 &")
		return true
	end
	return false
end
