-- Seção Bluetooth do conky: ${lua_parse bluetooth} em conky.text.
-- O conteúdo vem de bluetooth.sh. Rodar o script daqui (e não por ${execpi})
-- permite guardar quantas linhas ele gerou, que click.lua usa para saber
-- onde fica a seção.
-- O conky procura funções globais com prefixo conky_; bluetooth_lines é
-- global para click.lua (lua_load carrega os dois no mesmo estado Lua).
---@diagnostic disable: lowercase-global

local SCRIPT = os.getenv("HOME") .. "/.config/conky/bluetooth.sh"
local INTERVAL = 5 -- segundos entre execuções do script

local output = ""
local updated = -INTERVAL

-- Linhas da seção, contando o cabeçalho.
bluetooth_lines = 1

function conky_bluetooth()
	if os.time() - updated >= INTERVAL then
		local f = io.popen(SCRIPT)
		if f == nil then
			return output
		end
		output = (f:read("*a") or ""):gsub("\n$", "")
		f:close()
		updated = os.time()
		local _, newlines = output:gsub("\n", "")
		bluetooth_lines = 2 + newlines
	end
	return output
end
