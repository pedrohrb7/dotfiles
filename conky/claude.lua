-- Seção CLAUDE do conky: ${lua_parse claude} em conky.text, com
-- ${lua_bar claude_percent <n>} nas linhas que claude.sh gera.
-- claude.sh lê os transcripts do Claude Code e pode levar centenas de ms, então
-- não roda dentro do ciclo do conky: a cada INTERVAL segundos é disparado em
-- segundo plano, gravando em OUTPUT (troca atômica com mv), e a seção mostra a
-- última saída completa.
-- O conky procura funções globais com prefixo conky_.
---@diagnostic disable: lowercase-global

local SCRIPT = os.getenv("HOME") .. "/.config/conky/claude.sh"
local INTERVAL = 60 -- segundos entre execuções do script
local OUTPUT = (os.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/conky-claude.txt"

local function quote(s)
	return "'" .. s:gsub("'", "'\\''") .. "'"
end

local RUN = string.format(
	"{ %s > %s && mv -f %s %s; } >/dev/null 2>&1 &",
	quote(SCRIPT),
	quote(OUTPUT .. ".tmp"),
	quote(OUTPUT .. ".tmp"),
	quote(OUTPUT)
)

local updated = -INTERVAL

function conky_claude()
	if os.time() - updated >= INTERVAL then
		os.execute(RUN)
		updated = os.time()
	end
	local f = io.open(OUTPUT, "r")
	if f == nil then
		return "${color2}Carregando..."
	end
	local text = (f:read("*a") or ""):gsub("\n$", "")
	f:close()
	return text
end

-- Valor da barra: o % já vem no argumento, gerado por claude.sh.
function conky_claude_percent(value)
	return tonumber(value) or 0
end
