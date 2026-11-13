# lua-agent - stack agent `lua`, skills `neovim-plugin` e `lua-tui` (etapa I)

- **Date:** 2026-11-13
- **Status:** Implemented
- **Plan:** [agent-workflow.md, seção 15.2 "Etapa I - agent `lua`"](../../../agent-workflow.md#152-etapa-i---agent-lua-adendo-2026-11-12) (Status: Approved, 2026-11-13; decisão D23 a-j, regras 1-50). Não há `plan.md` nesta pasta: o plan não é copiado para cá.
- **Implementation log:** [log.md](log.md) (criado pelo `/implement` na primeira task)

## Summary

A etapa I dá um dono ao código Lua: um stack agent novo, `lua`, com o know-how de Neovim e de TUI em duas skills novas, e a integração dele ao workflow (hook, roteamento, gate, testes, onboarding). Tudo muda dentro de `.claude/` deste repo (ligado a `~/.claude` por symlink peça a peça). Não há serviço, API, banco nem flag.

| Camada | Arquivos | Mudança |
|---|---|---|
| Hook (Python) | `hooks/agent-audit.py`, `hooks/tests/test_classify.py`, `hooks/tests/test_hook_main.py` | `lua` em `IMPLEMENTERS`; classificação de busted, `luarocks test`, `nvim --headless` com plenary ou mini.test, tasks do mise, `mise exec`, luacheck, selene, stylua e treefmt; prefixo `timeout` removido; casos L1-L25 e LE1-LE5 |
| Contract e design | `skills/implementer-contract/SKILL.md`, `skills/design-system/SKILL.md` | `lua` nas descriptions; seção 5 do contract vale para UI de terminal e Neovim; passo 1 da `design-system` sem pedido de escopo para Neovim e TUI sem o arquivo |
| Skills novas | `skills/neovim-plugin/SKILL.md`, `skills/lua-tui/SKILL.md` | know-how de plugin Neovim e de UI (Neovim e terminal) |
| Agent novo | `agents/lua.md` | runtime e versão, ferramentas, regras de Lua, checks estreitos, política de UI, report |
| Roteamento | `skills/implement/SKILL.md`, `agents/specker.md`, `templates/docs-structure/features/_template/spec.md` | `Stack: lua` e os marcadores de inferência |
| Gate e testes | `agents/test-runner.md`, `agents/test-writer.md`, `skills/tdd/SKILL.md` | suites Lua sem `## Test suites`; `minimal_init` ausente = `blocked`; frameworks Lua; stub `error("not implemented")` |
| Onboarding | `skills/onboard/SKILL.md`, `templates/onboarding/LUA.md` (novo) | unidades Lua (repo inteiro, serviço OpenResty, pasta embarcada); um `LUA.md` na raiz, um bloco por unidade |

*Adendo 2026-11-13:* o stub Lua da `tdd` devolve valor vazio do tipo certo, não `error("not implemented")`; o hook aceita toda forma GNU do `timeout`, as flags globais do mise e do luarocks e classifica os shell escapes do Neovim, com os casos LR1-LR7 e LE6-LE7; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A1-A5.

`README.md` e `agent-workflow.md` ficam com o `docs-writer`, no fim (Design, seção 12).

## Background

**Decisões do plan que esta spec implementa** (15.2): D23 a-j e as regras 1-50. As que pesam no desenho técnico:

- D23 (a), (c) e regras 1-3: agent no padrão de `backend-go` (sonnet, effort médio, todas as tools), corpo curto, know-how de Neovim e TUI nas skills; quatro skills pré-carregadas.
- D23 (f) e regra 46: o hook classifica comandos Lua como as outras stacks; `suite_by_non_runner` (E9) passa a valer para o `lua`.
- D23 (h), (j) e regras 48-50: `onboard` escreve um só `LUA.md` na raiz, um bloco por unidade Lua.
- D23 (i) e regras 24, 31: TUI de terminal sem `DESIGN_SYSTEM.md` usa as 16 cores ANSI nomeadas, sem pedido de escopo.

**Decisões desta spec** (técnicas, tomadas aqui; o usuário confirma ao aprovar):

| # | Decisão |
|---|---|
| S1 | **Stacks das tasks**: `backend-python` para o hook; `frontend-react` para as tasks de markdown, pela convenção das specs [design-director](../design-director/spec.md) (S2) e [skills-docs-root](../skills-docs-root/spec.md) (ele pré-carrega a `design-system`, útil para a `lua-tui`). O `lua` não escreve a própria config: agents novos só aparecem numa sessão nova do Claude Code, e o frontmatter dele exige as skills já criadas |
| S2 | **Files** com caminhos relativos à raiz do git (`.claude/...`); todo `.md` novo listado pelo caminho exato, para não gerar `md_outside_docs` (regra M6 da [audit-md-outside-docs](../audit-md-outside-docs/spec.md)) |
| S3 | **Hook, onde cada regra mora**: busted, `luarocks test`, luacheck, selene, stylua e treefmt entram nas regex genéricas (`TEST_RUNNERS`, `NARROW_HINT`, `LINT`), porque se comportam como os runners das outras stacks; `mise` e `nvim` ganham ramos próprios, porque a categoria depende do nome da task ou do comando passado ao Neovim; a dica `--filter` do busted vale só para o busted, para `pnpm --filter api test` continuar `test-package` (C12). A lógica de dicas (completo, estreito, pacote) vira uma função `test_scope()`, usada pelo ramo genérico e pelo do mise |
| S4 | **Formas do mise além da tabela da regra 46**, todas da doc oficial: `mise tasks run <task>`, o atalho `mise <task>`, várias tasks com `:::` e flags antes do nome da task. `mise test-tool` (comando do próprio mise) não é task |
| S5 | `luarocks test` = teste completo (roda o comando de teste do rockspec); `treefmt` (com ou sem `--ci`) = lint, como formatador que é (regras 11 e 41 o citam) |
| S6 | **`timeout` como prefixo**: `strip_prefixes` remove `timeout [opções] <duração>`. O `lua` limita runs de `nvim --headless` com `timeout` (um teste headless travado prende o `Bash` por minutos); sem isso, `timeout 300 mise run test` escaparia de `suite_by_non_runner`. Vale para todas as stacks (`timeout 60 pytest` passa a ser `test-full`) |
| S7 | **Binário com caminho**: `./.luarocks/bin/busted` e `.luarocks/bin/luacheck` (forma real do claudinho.nvim) contam pelo nome do arquivo, só para `busted`, `luacheck`, `selene`, `stylua` e `nvim` |
| S8 | **Marcadores de roteamento**: além dos da regra 38, `.stylua.toml` (o StyLua aceita os dois nomes; o claudinho.nvim usa este) e `selene.toml` |
| S9 | **`design-system`, passo 1**: além da description (plan), um bullet diz que UI no Neovim e TUI de terminal sem o arquivo não abrem pedido de escopo. Sem ele, a skill pré-carregada mandaria o `lua` terminar `blocked`, em conflito com as regras 24 e 31; duas instruções em conflito dependem do julgamento do modelo |
| S10 | **Tamanhos**: `agents/lua.md` entre 3.400 e 4.600 bytes (faixa dos irmãos, critério do plan); cada skill nova com no máximo 120 linhas e 7.000 bytes (a `react-native-core` tem 108 linhas e 5,9k) |

*Adendo 2026-11-13:* S6 aceita toda forma GNU do `timeout` e falha fechada; S3 ganha as flags globais do mise e do luarocks, as formas `test_harness` e `require"mini.test"` e os shell escapes do Neovim; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A2-A4.

**Código existente que o desenho reaproveita:**

- `hooks/agent-audit.py`: `strip_prefixes()` (tira `rtk`, `sudo`, `time`, atribuições de env; normaliza `npx`/`pnpm exec`); `classify_command()` (divide em segmentos por `SEGMENT_SPLIT`, classifica cada um, devolve categorias e flags ordenadas); `main()` acrescenta `suite_by_non_runner` quando `test-full`, `test-package` ou `test-load` vem de um ator em `IMPLEMENTERS | {"quality-fixer", "test-writer"}`. `IMPLEMENTERS` também decide `out_of_scope_write`, `docs_write_by_implementer` e a isenção M6 de `md_outside_docs`. Nenhuma categoria nova; `agent-audit.json` e `agent-metrics.py` não mudam (as métricas já mostram flags e categorias por ator).
- `hooks/tests/test_classify.py`: `COMMAND_TABLE` (C1-C37) e `PREFIX_TABLE` (X1-X14), um `subTest` por comando. `hooks/tests/test_hook_main.py`: o literal `IMPLEMENTERS` comparado com o do hook (E9) e os laços de E9 sobre ele.
- Suite `claude-hooks` (`## Test suites` do `CLAUDE.md` da raiz): 259 testes, verde em 2026-11-13.
- Stack agents: `backend-go.md` (62 linhas, 3.453 bytes) como forma; `frontend-react.md` como precedente de agent de UI que pré-carrega a `design-system`.
- Projeto real de referência: `/home/void/workspace/claudinho.nvim` (plugin Neovim; busted em `./.luarocks/bin/busted`; luacheck com `std = "luajit+busted"`; `.stylua.toml` e `treefmt.toml`; `mise.toml` com tasks `setup`, `check`, `test`, `format`, `format-check`, `all`; Neovim mínimo 0.8 pelo README e pelo `health.lua`; sem `## Test suites` no `CLAUDE.md`). Serve de cenário real para 46, 47 e 49.

## Design

### 1. Convenções de execução neste repo

- **Caminhos**: os agents escrevem pelo caminho real (`/home/void/dotfiles/.claude/...`), nunca por `~/.claude/...`.
- **Gate**: suite `claude-hooks` (gate `task`) pelo `test-runner`. As tasks de markdown não têm suite: o gate delas são os checks V da seção Testing, rodados pelo agent da task e repetidos na Verification.
- **Hook ativo** (`enforce`) durante o run: `.md` novos listados no **Files** não geram `md_outside_docs` (S2); editar arquivos existentes com `Edit`.
- **Idioma**: agent, skills e template em inglês, como toda a config. Esta spec em pt-BR, como o `agent-workflow.md`.
- **Ativação**: o hook vale na próxima chamada depois da task 1; agent e skills novos só numa sessão nova do Claude Code.

### 2. Hook: `.claude/hooks/agent-audit.py`

#### 2.1 `IMPLEMENTERS`

```python
IMPLEMENTERS = {
    "backend-node", "backend-spring", "backend-go", "backend-rust", "backend-python",
    "frontend-react", "mobile-react-native", "lua",
}
```

`"lua"` na mesma linha de `mobile-react-native` (aqui e no literal de `test_hook_main.py`), para o check V4 achar os dois numa linha só. Efeito: escopo de run por `allowed_paths`, `docs_write_by_implementer`, isenção M6 e `suite_by_non_runner` passam a valer para o `lua` (regra 37).

#### 2.2 Regex genéricas (S3, S5)

| Constante | Acréscimo |
|---|---|
| `TEST_RUNNERS` | `busted`, `luarocks test` |
| `NARROW_HINT` | `\S+_(spec|test)\.lua\b` (arquivo único de teste Lua, em qualquer comando de teste) |
| `LINT` | `luacheck`, `selene`, `stylua`, `treefmt` |
| `BUSTED_NARROW` (nova) | `\s(--filter|--tags?)(=|\s)`; consultada só quando o segmento começa com `busted` |

#### 2.3 `strip_prefixes()` (S6, S7)

Dentro do laço de prefixos:

- `mise exec ... -- <cmd>` e `mise x ... -- <cmd>`: com `--` na lista de tokens, remove tudo até ele, inclusive (as versões de ferramenta e as flags do mise ficam de fora); sem `--` (forma `-c "<shell>"`), não remove nada.
- `timeout`: remove `timeout`, as opções (`-s SIG`, `-k D`, `--signal=SIG`, `--kill-after=D`, `--preserve-status`, `--foreground`, `-v`) e a duração (`^\d+(\.\d+)?[smhd]?$`). Duração que não casa: não remove nada.

O laço continua depois de cada remoção, então `rtk timeout 60 mise exec -- busted x_spec.lua` chega a `busted x_spec.lua`. Depois do laço e da normalização de `npx`/`pnpm`: um primeiro token com `/` cujo nome final está em `PATH_TOOLS = {"busted", "luacheck", "selene", "stylua", "nvim"}` vira só o nome.

*Adendo 2026-11-13:* o bullet `timeout` foi substituído (toda forma GNU, falha fechada), o `mise exec`/`x` pula as flags globais e `luarocks [flags globais] test` vira `luarocks test`; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A2 e A4.

#### 2.4 `classify_command()`: ramos novos

Antes de `LOAD_RUNNERS`:

```python
elif seg == "mise" or seg.startswith("mise "):
    categories.extend(mise_categories(seg))
elif seg == "nvim" or seg.startswith("nvim "):
    categories.append(nvim_category(seg))
elif TEST_RUNNERS.match(seg):
    categories.append(test_scope(padded, busted=seg.startswith("busted")))
```

`test_scope(padded, busted=False)`: `FULL_HINT` -> `test-full`; `NARROW_HINT` (ou `BUSTED_NARROW` com `busted=True`) -> `test-narrow`; `PACKAGE_HINT` -> `test-package`; senão `test-full`. É a ordem atual, extraída para uma função.

**`mise_categories(seg)`** (regra 46, S4):

| Passo | Regra |
|---|---|
| Tokens depois de `mise` | pula flags (tokens com `-`; `-C`/`--cd`, `-E`/`--env`, `-j`/`--jobs`, `-o`/`--output`, `-t`/`--tool` consomem o token seguinte quando não usam `=`) |
| Forma | `run` ou `r`: as tasks vêm depois; `tasks run`: idem; outro token: é o nome da task (atalho `mise <task>`) |
| Várias tasks | separadas por `:::`; cada grupo: flags puladas, nome, argumentos |
| Nome `test*` (`^test(?!-tool$)[\w:*-]*$`) | `test_scope(" " + argumentos + " ")`, como `make test` (completo sem dica) |
| Nome `lint*`, `format*`, `fmt*` | `lint` |
| Nome `all`, `check`, `ci` | `test-full` (rodam a suite; regra 32) |
| Outro nome (`setup`, `clean`, `install`, `ls`, `exec` sem `--`) | `other` |

**`nvim_category(seg)`** (regra 46):

| Condição (na ordem) | Categoria |
|---|---|
| sem o token `--headless` | `other` (o comando fica no registro; métrica de 14.2) |
| `PlenaryBustedFile`, ou `MiniTest.run_file` / `MiniTest.run_at_location` (também `require('mini.test').run_file`) | `test-narrow` |
| `PlenaryBustedDirectory [<pasta>]` | `test-package` quando a pasta, sem `./` no começo e `/` nas pontas, ainda tem `/` (`tests/unit`); senão `test-full` (`tests`, `tests/`, sem pasta) |
| `MiniTest.run(` (também `require('mini.test').run(`) | `test-full` |
| senão (`checkhealth`, `+qa`, script qualquer) | `other` |

As buscas são por regex no texto do segmento, não por token: `SEGMENT_SPLIT` corta `-c "lua MiniTest.run(); vim.cmd('qa!')"` no `;`, e o primeiro pedaço ainda traz `MiniTest.run(` (caso L13).

*Adendo 2026-11-13:* `_MISE_VALUE_FLAGS` completo (A2); shell escapes de `-c`/`--cmd`/`+` classificados como comando próprio (A3); `test_harness`, `require"mini.test"` e pasta absoluta em `nvim_category`, e qualquer arquivo `.lua` no busted (A4); ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança).

#### 2.5 Docstring

A linha "Bash commands" do docstring do módulo passa a citar os runners Lua (busted, Neovim headless com plenary ou mini.test) e as tasks do mise. `WHY`, `decide()` e `what_to_do()` não mudam: `suite_by_non_runner` já diz o que fazer.

### 3. Contract e design system

**`skills/implementer-contract/SKILL.md`**

- `description`: a lista de stack agents ganha `lua` depois de `mobile-react-native`.
- Seção 5 passa a `## 5. UI (frontend, mobile, Neovim and terminal)`:
  - bullet 1 ganha: `nvim --headless` só para testes e checks não interativos; nunca abrir um Neovim interativo, rodar um app TUI ou jogo LÖVE, nem executar ou recarregar um app hospedeiro (wezterm, hammerspoon, awesome, conky) ou o nginx;
  - bullet 2: "tokens from `DESIGN_SYSTEM.md`" ganha "or, where the stack's skill says so, the platform theme (Neovim highlight groups, terminal ANSI colors)";
  - bullet 3: `manual_checks` também com o comando, keymap ou ação que abre a UI e o tamanho de janela ou terminal (inclusive redimensionar e pequeno demais).
- Seção 4 sem mudança (o `lua` a aplica ao OpenResty pelo corpo do agent).

**`skills/design-system/SKILL.md`**

- `description`: "Preloaded by frontend-react, mobile-react-native, lua and design-director." (resto igual).
- Passo 1, bullet novo antes do bullet do `design-director` (S9): "You build UI inside Neovim, or a terminal TUI, and the file is missing (or `Principles` is empty): this step does not apply and there is no scope request - Neovim UI links to the standard highlight groups, a terminal TUI uses the 16 named ANSI colors and attributes (`lua-tui`). With the file, its tokens win in a terminal TUI."

### 4. Skill `skills/neovim-plugin/SKILL.md` (nova; regras 15-19, 27, 29-30)

```yaml
---
name: neovim-plugin
description: Neovim plugin and config know-how in Lua - plugin layout and lazy-loading, setup(opts) with vim.validate, user commands and <Plug> mappings, autocmds in augroups, vim.uv callbacks through vim.schedule, minimum-version guards, :checkhealth, and headless tests (busted, plenary, mini.test, minimal_init). Preloaded by the lua agent. Use when writing, reviewing or testing Lua for Neovim - a plugin with lua/ + plugin/, an init.lua config, or code calling vim.api, vim.fn or vim.uv.
---
```

Sem `user-invocable: false` (regra 29). Corpo em inglês, até 120 linhas e 7.000 bytes (S10), regras curtas em bullets, sem tutorial:

| Seção | Regras-chave | Regras do plan |
|---|---|---|
| Plugin or config | `lua/` + `plugin/` (ou rockspec) = plugin; `init.lua` + `lua/` sem `plugin/` = config; na config, nenhuma convenção de plugin (`setup`, `health.lua`, `<Plug>`): a estrutura existente manda | 19 |
| Layout and loading | `plugin/<name>.lua` mínimo, com guarda de carga dupla e `require` adiado para dentro de comandos e mapeamentos; comandos com `nvim_create_user_command`; mapeamentos `<Plug>`, nenhum keymap padrão sem pedido | 15 |
| setup and configuration | defaults numa tabela; `setup(opts)` só sobrescreve (`vim.tbl_deep_extend("force", ...)`); config mesclada por `vim.validate` na forma da versão mínima (`vim.validate(name, value, validator[, optional][, message])` desde 0.11; a forma de tabela é deprecated) | 15 |
| Autocmds | sempre num augroup nomeado com `clear = true`; buffer-local quando presos a um buffer; removidos no teardown | 15, 18 |
| Async | toda chamada de `vim.api` vinda de callback de `vim.uv` (ou outro contexto assíncrono) passa por `vim.schedule`/`vim.schedule_wrap` (citação da doc); handles e timers fechados; `vim.uv or vim.loop` com mínimo abaixo de 0.10 | 16, 18 |
| Minimum version | de onde vem (README, matriz da CI, `health.lua`, guardas `vim.fn.has('nvim-0.x')`, `mise.toml`); nenhuma API mais nova que ela; guarda `has()` quando uma API nova é opcional | 9 |
| Health | `lua/<name>/health.lua` com `vim.health.start/ok/warn/error`, cobrindo config e dependências externas; atualizado quando a task muda uma delas | 15 |
| Headless tests | busted puro, plenary (`PlenaryBustedFile`, `PlenaryBustedDirectory` com `minimal_init`) ou mini.test (`MiniTest.run_file`); comando estreito de um arquivo, com o `minimal_init` do projeto e `timeout`; nunca criar `minimal_init` sem pedido; nunca Neovim interativo | 27, 32, 33 |
| UI | ponteiro para a `lua-tui` (janelas e buffers como UI) | 27-28 |
| Checklist | 6-8 itens de conferência antes do report | - |

*Adendo 2026-11-13:* guarda de carga dupla com as duas linhas e exemplos de contexto rápido corrigidos; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A6.

### 5. Skill `skills/lua-tui/SKILL.md` (nova; regras 17-18, 20-26, 28-31)

```yaml
---
name: lua-tui
description: User interfaces in Lua - inside Neovim (floating windows, scratch buffers as UI, extmarks, highlight groups linked to the theme, layout on VimResized, cleanup on close) and standalone terminal TUIs (raw mode with guaranteed restore, alternate screen, luv event loop, SIGWINCH, named ANSI colors, no-TTY and NO_COLOR). Preloaded by the lua agent. Use when building or reviewing a Lua UI in Neovim or in the terminal.
---
```

Mesmo limite de tamanho. Seções:

| Seção | Regras-chave | Regras do plan |
|---|---|---|
| Which world | Neovim (API do editor) ou terminal (TTY próprio); as duas partes não se misturam | 28 |
| Neovim: buffers and windows | buffer de UI `buftype=nofile`, sem swap, `bufhidden` definido; janela flutuante relativa ao editor, tamanho limitado à área útil (`columns`, `lines` menos `cmdheight` e statusline) e com mínimo; keymaps buffer-local | 17 |
| Neovim: highlights and extmarks | um namespace por plugin ou feature, limpo a cada re-render; grupos próprios com `link` a grupos padrão (`NormalFloat`, `FloatBorder`, `Comment`, `Diagnostic*`) e `default = true`; nunca hex, `guifg`/`guibg` ou cor fixa | 17, 31 |
| Neovim: layout and redraw | recalcula em `VimResized` (autocmd no augroup da UI); atualizações em lote (linhas de uma vez), sem redraw em laço | 17 |
| Neovim: lifecycle | fechar por qualquer caminho (`:q`, `<C-w>o`, comando, troca de tabpage; `WinClosed`/`BufWipeout`) limpa autocmds, timers, handles e extmarks; reabrir funciona como da primeira vez; resposta assíncrona depois do fechamento confere `nvim_buf_is_valid`/`nvim_win_is_valid` e é descartada | 18, 26 |
| Terminal: dependencies | sequências ANSI diretas e `luv`; biblioteca de TUI só se o projeto já usa uma | 20 |
| Terminal: raw mode and restore | raw mode pelo `luv` (`new_tty`, `set_mode`); restauração (sair do raw mode, mostrar o cursor, sair do alternate screen) em toda saída: término normal, erro (tratador com traceback em volta do loop) e SIGINT/SIGTERM (`new_signal`); o erro é impresso depois da restauração | 21 |
| Terminal: screen and resize | alternate screen ao entrar, saída dele ao terminar; `SIGWINCH` relê o tamanho e refaz o layout | 22 |
| Terminal: no TTY and NO_COLOR | entrada ou saída redirecionada (`guess_handle`): sem raw mode nem sequências de controle, saída em texto como a spec da feature disser; `NO_COLOR` não vazio desliga cores | 23 |
| Terminal: colors | com `DESIGN_SYSTEM.md`, os tokens dele vencem; sem o arquivo, só as 16 cores ANSI nomeadas (8 básicas e 8 brilhantes) e atributos (negrito, dim, sublinhado, reverso), que herdam o tema do terminal; nada de cor 256 ou RGB; nenhum pedido de escopo | 24, 31 |
| States | carregando, vazio, erro, sucesso, área pequena demais (aviso, não layout quebrado) e redimensionamento, no código | 25 |
| manual_checks | o que listar por task de UI (Neovim e terminal), com "Ctrl-C e erro deixam o terminal normal" na TUI | 34 |

*Adendo 2026-11-13:* a área útil desconta a tabline, a winbar e a statusline condicional; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A6.

### 6. Agent `agents/lua.md` (novo; regras 1-14, 32-36)

#### 6.1 Frontmatter

```yaml
---
name: lua
description: Lua specialist with depth in Neovim and terminal UIs. Use proactively when building or changing Lua code - Neovim plugins and configs, UI inside Neovim, terminal TUIs, LÖVE games, OpenResty, libraries and scripts, and embedded configs (wezterm, hammerspoon, awesome, conky) - and their tests.
model: sonnet
effort: medium
skills:
  - implementer-contract
  - design-system
  - neovim-plugin
  - lua-tui
color: blue
---
```

Sem linha `tools:` (todas as tools, como os irmãos). A description é a redação final da regra 2. `blue` é a cor dos stacks de backend e a da marca Lua (as oito cores já estão em uso).

#### 6.2 Corpo

Em inglês, 3.400 a 4.600 bytes (S10), na forma do `backend-go.md`: frase de papel, "Follow the preloaded `implementer-contract`...; Neovim know-how lives in `neovim-plugin`, UI know-how in `lua-tui`", e as seções:

| Seção | Conteúdo | Regras |
|---|---|---|
| 1. Before coding | tabela compacta de runtime (sinal -> runtime -> Lua padrão) da regra 5; declaração explícita vence o padrão, conflito = menor versão em `assumptions` (6); Neovim mínimo (9); dois runtimes = o do módulo parecido mais próximo, a spec pode fixar (10) | 5, 6, 9, 10 |
| 2. Tools and dependencies | ferramentas do projeto (busted/plenary/mini.test, luacheck/selene, stylua/treefmt, `mise exec --`), nunca uma que duplique; sem framework de teste: não adiciona, `scope_requests` se a task pede testes, senão lint e formatador e a falta em `notes`; dependência nova só nomeada pela task; ferramenta ausente no ambiente: não instala, check `blocked` com o comando para o usuário | 11-14 |
| 3. Implementation rules | idiomas de Lua em 4-6 bullets (tudo `local`, módulo retorna tabela, nenhuma global nova além da API do hospedeiro, erros na convenção do projeto - `error(msg, level)` ou `nil, err`); limites por versão (sem `//`, bit a bit nativo e `utf8` abaixo de 5.3; sem `<const>`/`<close>` abaixo de 5.4; `goto` só LuaJIT ou 5.2+; camada de compatibilidade existente); embarcado (API do hospedeiro como globais, subconjunto 5.1-5.4 quando a versão é desconhecida); Neovim e UI pelas skills, com as duas regras duras repetidas em uma linha cada (`vim.schedule` em callbacks de `vim.uv`; highlights só por link, nunca cor fixa) | 7, 8, 15-26 |
| 4. Tests and narrow checks | um arquivo ou nome de teste (busted com o arquivo; `nvim --headless` com plenary ou mini.test num arquivo, com o `minimal_init` do projeto e `timeout`); lint e verificação de formato nos arquivos tocados; nunca a suite nem tasks do mise, Makefile ou justfile que rodam suites (`test`, `all`, `check`) | 32 |
| 5. UI and runtime | `nvim --headless` só para testes e checks; nunca Neovim interativo, app TUI, jogo LÖVE, hospedeiro ou nginx (nem para "conferir"); `manual_checks` de UI e config embarcada pelos itens da regra 34 ("recarregar `<app>`" no embarcado); OpenResty faz a seção 4 do contract, recarga do nginx em `manual_checks`; os outros runtimes deixam `local_checks` vazio | 33-35 |
| 6. Scaffold and generated files | fase `scaffold`: módulo com a forma real (tabela retornada, assinaturas, anotações LuaCATS) e corpos `error("not implemented")`; `doc/tags` e vimdoc gerado são regenerados, nunca editados | 36 |
| 7. Report extras | `notes`: runtime, versão de Lua e Neovim mínimo detectados; `needs_docs`: README, vimdoc escrito à mão (`doc/<plugin>.txt`), opções novas de `setup` (anotações LuaCATS são código); `manual_checks` (seção 5) | 36 |

Fennel, MoonScript e Teal: uma linha em `notes` quando a task exigiria a outra linguagem (caso de borda).

*Adendo 2026-11-13:* seção 3 com Neovim em Lua 5.1 e recursos só do LuaJIT atrás de uma checagem de `jit`; seção 7 com a cláusula LuaCATS restaurada (A6); seção 6 com stubs de valor vazio do tipo certo, não `error("not implemented")` (A7); ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança).

### 7. Roteamento

**`skills/implement/SKILL.md`, seção 4**, item do stack, depois de "React Native/Expo means `mobile-react-native`":

> , Lua means `lua` (`.lua` files in the task, or `*.rockspec`, `.luarc.json`, `stylua.toml`/`.stylua.toml`, `selene.toml`, `.luacheckrc`, or `lua/` + `plugin/` near the task's files). The task's own files decide: files of another stack go to that stack's agent, even in a repo with Lua markers.

**`agents/specker.md`**, item **Stack** da seção 3:

> - **Stack**: backend-node, backend-spring, backend-go, backend-rust, backend-python, frontend-react, mobile-react-native or lua (Lua files, or the Lua markers of the `implement` skill near them). One task, one stack: Lua work and another stack's work go in separate tasks;

**`templates/docs-structure/features/_template/spec.md`**, linha **Stack**: `... | mobile-react-native | lua>`.

### 8. Gate e testes

**`agents/test-runner.md`, seção 2**

- Passo 2: "project scripts" passa a "project scripts (package scripts, Makefile/justfile targets, `mise.toml` tasks)".
- Tabela de padrões, linha nova e a linha Makefile/justfile ampliada:

| Ecosystem | Lint | Typecheck | Test |
|---|---|---|---|
| Lua (prefix `mise exec --` when the project uses mise) | `luacheck .` or `selene .` when configured (`.luacheckrc`, `selene.toml`); format check `stylua --check .` or `treefmt --ci` when configured | | `busted` when there is `.busted` or `spec/`; Neovim: `nvim --headless` with the project's `minimal_init` and `PlenaryBustedDirectory <dir>` (plenary) or `lua MiniTest.run()` (mini.test) |
| Makefile/justfile/mise | `make lint`, `just lint`, `mise run lint` | | `make test`, `just test`, `mise run test` |

**`agents/test-runner.md`, seção 3**, bullet novo: "A Neovim suite that needs the project's `minimal_init` (or the init file its command names) that does not exist: `blocked` with the reason; never create one. Never run Neovim without `--headless`."

**`agents/test-writer.md`, seção 2**: a lista de frameworks ganha "busted, plenary.nvim (busted style under `nvim --headless`), mini.test"; a de nomes, "`*_spec.lua`, `*_test.lua`, `tests/test_*.lua`"; bullet novo: "For Neovim code, load the `neovim-plugin` skill for the headless setup (`minimal_init`)". A regra "Never introduce a new test framework" fica.

**`skills/tdd/SKILL.md`, passo 2**, depois de "return an empty or zero value of the right type": "(Lua: a module with the real shape - the returned table, function signatures, LuaCATS annotations - and bodies `error("not implemented")`; check that each stub loads instead of a typecheck)".

*Adendo 2026-11-13:* decisão do usuário: o stub Lua devolve valor vazio ou zero do tipo certo, nunca `error("not implemented")`; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A1.

### 9. Onboarding

**`skills/onboard/SKILL.md`**

| Ponto | Mudança | Regras |
|---|---|---|
| `description` | "one doc per service (backend/frontend/mobile), plus `LUA.md` for Lua units, ..." | 48 |
| Passo 2 | além das pastas de serviço, detecta **unidades Lua**: o repo inteiro (sem pastas de serviço e com sinais Lua na raiz: os marcadores do `implement` ou os sinais de runtime do agent `lua`, inclusive config de Neovim e config embarcada); um serviço Lua (ex.: gateway OpenResty em `services/`); uma pasta Lua de topo num repo misto (ex.: `awesome/`, `conky/`). Pergunta ao usuário quais unidades e serviços onboardar, numa pergunta só | 43, 48 |
| Passo 4 | para uma unidade Lua, os itens das seções do `LUA.md` (seção 9.1); `Recommendations` comparando com as convenções das skills `neovim-plugin` e `lua-tui` (não há `STRUCTURE.md` de Lua) | 49 |
| Passo 5 | as unidades Lua escolhidas vão para um só `LUA.md` na raiz, um bloco por unidade; um serviço Lua vai para o `LUA.md`, não para o `BACKEND.md`; as outras unidades seguem com os seus documentos; item que não se aplica diz isso explicitamente | 48, 50 |
| Passo 7, `Local runtime` | só quando o Lua roda como serviço (OpenResty); plugin, config, LÖVE, biblioteca e embarcado não têm a seção | 43 |
| Passo 7, `Test suites` | num projeto Lua: CI primeiro, depois tasks do mise, Makefile/justfile, `.busted` e pastas de teste | 43 |

#### 9.1 Template `templates/onboarding/LUA.md` (novo; regra 49)

Mesma forma de `BACKEND.md`: título, comentário de topo e seções com comentários-guia.

```markdown
# Lua - <project name>

<!-- Reverse-engineered understanding of the Lua code as it actually exists today, not aspirational. One block per Lua unit chosen in onboard step 2: "## <unit path>" ("## ." when the whole repo is the unit), with the sections below one level down. Other units keep their own documents (BACKEND.md, FRONTEND.md, MOBILE.md); a Lua service such as an OpenResty gateway goes here, not in BACKEND.md. An item that does not apply to the unit's runtime says so ("not applicable: library without UI"), never a placeholder. -->

## <unit path>

### Stack

- Runtime: <!-- Neovim plugin, Neovim config, LÖVE, OpenResty, standalone, or embedded with the host's name -->
- Lua version and where it is declared:
- Minimum Neovim version (Neovim only):
- Key dependencies: <!-- rocks, plugins such as plenary -->
- Tools: <!-- tests, lint, format, mise -->

### Folder structure
<!-- The real tree, annotated. -->

### Design patterns in use

- Module organization and public API:
- Entry points and loading: <!-- plugin/, setup, lazy-loading, commands, host entry -->
- Configuration and validation:
- Async and event loop: <!-- vim.uv/luv, vim.schedule, coroutines -->
- UI: <!-- windows, buffers, extmarks, highlights; or raw mode and alternate screen; or "not applicable" -->
- Error handling and notification:
- Health check:
- Testing: <!-- framework, minimal_init, helpers, where tests live -->

### Conventions observed

- Naming:
- File organization:
- LuaCATS annotations:

### Inconsistencies

### Recommendations
<!-- Compared against the conventions of the neovim-plugin and lua-tui skills (there is no Lua STRUCTURE.md). A starting point for a conversation, not a mandate to refactor. -->

### Open questions
```

(`Folder structure` com a cerca de código vazia, como no `BACKEND.md`; cada seção vazia com `-`, como nos outros templates.)

### 10. Segurança e privacidade

- O `lua` tem as mesmas tools e o mesmo contract dos irmãos; nenhuma ferramenta de rede nova. Instalar ferramentas (`mise install`, `luarocks install` global) e dependências novas é sempre pedido de escopo (regras 13-14).
- Nada interativo: Neovim só `--headless`, nenhum app TUI, LÖVE, hospedeiro ou nginx executado; isso protege o terminal e a sessão do usuário e evita um `Bash` preso.
- OpenResty: validação de runtime só em host local, com os dados de teste do contract (seção 4).
- Hook: só rótulos novos de categoria; nenhuma categoria ou ação nova; o registro continua sem conteúdo de arquivo e com o comando truncado em 300 caracteres. Os regex novos são lineares (sem aninhamento ambíguo) e rodam sobre um segmento por vez.

*Adendo 2026-11-13:* `timeout` e mise com falha fechada (A2) e shell escapes do Neovim classificados, com profundidade limitada (A3); ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança).

### 11. Observabilidade

| Sinal | Onde | Alvo (15.2, 14.2) |
|---|---|---|
| `suite_by_non_runner` com ator `lua` | JSONL do hook; `## Flags` e `## Actions by category` do `agent-metrics.py` | 0 |
| Categorias `test-narrow` e `lint` do `lua` | `## Actions by category` (por ator) | checks estreitos presentes |
| `nvim` sem `--headless`, `love`, app TUI, hospedeiro ou recarga de nginx com ator `lua` | comando gravado no JSONL (busca da Verification, item 4) | 0 |
| Escritas do `lua` fora de `allowed_paths` | `out_of_scope_write` | 0 |
| Tasks de UI do `lua` com `manual_checks` | report do agent, conferido no transcript | 100% |

### 12. Rollout e reversão

- **Ordem**: hook -> contract e design -> skills -> agent -> roteamento; `test-runner`, `test-writer`/`tdd` e `onboard` em paralelo depois das suas dependências. O hook vem primeiro para que o primeiro uso real do `lua` já saia com os sinais certos; as skills vêm antes do agent porque o frontmatter as pré-carrega.
- **Desligar sem reverter**: o hook não tem flag nova (os rótulos de categoria só alimentam `suite_by_non_runner`, que segue em `agent-audit.json`). Tirar o `lua` de uso = não roteá-lo (sem `Stack: lua`).
- **Reverter**: cada task é um commit do usuário; reverter a task 1 volta à classificação atual (comandos Lua como `other`).
- **Documentação (pelo `docs-writer`, no fim; não é task)**:
  - `.claude/README.md`: linha do `lua` na tabela de agents (sonnet, medium, todas as tools, as quatro skills, auto-invocável); linhas de `neovim-plugin` e `lua-tui` na tabela de skills; `lua` em "preloaded by" da `design-system` e do `implementer-contract`; "the seven agent files" vira "eight"; o parágrafo de `onboarding/` cita o `LUA.md`; na seção do hook, os comandos Lua, as tasks do mise e o prefixo `timeout` na classificação.
  - `.claude/agent-workflow.md`: Registro de execução da etapa I; os rótulos "(etapa I, Draft)" que ficaram para trás em 12.1, 12.2, 14.2, na tabela da seção 15 e em D23 (16.1), enquanto a 15.2 diz Approved; a frase repetida em 16.2; na 15.2, as decisões S3-S9 desta spec (formas do mise, `luarocks test`, `treefmt`, `timeout`, marcadores `.stylua.toml`/`selene.toml`, bullet da `design-system`).

## Alternatives considered

| Tema | Alternativa | Por que não |
|---|---|---|
| Classificação no hook | tudo nas regex genéricas (`TEST_RUNNERS` com `mise run test`, `NARROW_HINT` com `--filter`, `nvim --headless .*Plenary`) | `--filter` em `NARROW_HINT` tornaria `pnpm --filter api test` estreito (quebra C12); a categoria do mise depende do nome da task e do `:::`, e a do Neovim do comando dentro de `-c`: regex única ficaria ilegível e frágil. Escolhido: genérico onde o runner se comporta como os outros, ramos próprios para `mise` e `nvim` (S3) |
| | um módulo `lua_commands.py` separado | o hook é um arquivo só, carregado por caminho no `settings.json` e testado por `_loader.py`; um segundo módulo muda o contrato de carga sem ganho |
| Formas do mise | só `mise run` e `mise r` (tabela da regra 46) | `mise test` e `mise tasks run test` estão na doc oficial e rodam a mesma suite; ficar de fora deixaria o `lua` rodar a suite sem sinal (S4) |
| `timeout` | não remover (fora do plan) | o `lua` deve limitar runs headless com `timeout`; sem a remoção, toda suite atrás dele escaparia de `suite_by_non_runner`, para todas as stacks (S6) |
| Binários com caminho | casar qualquer primeiro token pelo nome final | mudaria a classificação de comandos de outras stacks sem caso de teste que a justifique; a lista fechada cobre o caso real (S7) |
| Stack das tasks de markdown | `Stack: lua` para as skills e o agent | o agent não existe na sessão do run (agents novos só aparecem numa sessão nova) e o frontmatter dele exige as skills; seria um bootstrap circular (S1) |
| | `backend-python` para tudo | não pré-carrega a `design-system`; a `lua-tui` precisa do domínio de UI. A convenção das specs anteriores é `frontend-react` |
| Bullet da `design-system` | só a description (tabela de arquivos do plan) | a skill pré-carregada mandaria o `lua` terminar `blocked` sem o arquivo, contra as regras 24 e 31 (S9) |
| Sinais de Lua | uma lista canônica numa skill, citada por `implement`, `specker` e `onboard` | `implement` e `specker` precisam da lista no próprio texto para não depender de carga de outra skill; a lista é curta e o check V4 confere as três. Fica a duplicação (Trade-offs) |
| Guarda contra Neovim interativo | categoria nova no hook (`interactive_app`, `block`) para `nvim` sem `--headless`, `love`, hospedeiros | fora do plan; precisa de desenho próprio (`nvim --version`, `nvim -l`, `nvim -es` são legítimos; a lista de hospedeiros é aberta). Fica como pergunta em aberto, com os dados da métrica de 14.2 |

## Trade-offs

- **Nomes de task do mise fora do padrão** (`spec`, `unit`) rodam a suite sem sinal; o padrão segue o de `make`/`just` (risco aceito no plan; nomes novos entram com dados, 13.3). `mise run check` conta como suite mesmo onde só roda lint (caso do claudinho.nvim): sinaliza a mais, nunca a menos.
- **`busted <arquivo>.lua` com nome fora de `_spec`/`_test`** é `test-package` (o caminho casa `PACKAGE_HINT`) e sinaliza `suite_by_non_runner` com o `lua`; o projeto que nomeia testes assim já configura o padrão no `.busted`. `busted spec` (pasta de topo) é suite completa, de propósito.
- **`PlenaryBustedDirectory tests/unit`** é pacote e `tests/` é completo; os dois sinalizam, então a diferença só aparece nas métricas.
- **Runners via `nvim -l`** (ex.: `nvim -l tests/minit.lua`) ficam `other`; entram quando os dados mostrarem (13.3).
- **`mise fmt`** (comando do próprio mise, formata o `mise.toml`) cai em `lint`; inofensivo.
- **`timeout` vale para todas as stacks**: comandos que antes eram `other` (`timeout 60 pytest`) passam a ter categoria e podem sinalizar `suite_by_non_runner`; é o comportamento correto, mas é uma mudança fora do Lua.
- **Marcadores de Lua em três textos** (`implement`, `specker`, `onboard`): duplicação curta, conferida pelo V4; uma mudança futura precisa tocar os três.
- **Quatro skills pré-carregadas** pesam em toda task Lua (contract 11k + design-system 3k + duas skills até 7k cada + agent até 4,6k); mitigado pelo limite S10 e medido contra o baseline de tokens (14.2). Se pesar, o detalhe sai para `references/` sob demanda.

*Adendo 2026-11-13:* o bullet do `busted <arquivo>.lua` deixou de valer (todo arquivo `.lua` fora de valor de flag é estreito) e o do `timeout` ganhou os casos LR7 e LE6; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A4 e A5.

## Testing

Suite: `claude-hooks` (tabela `Test suites` do `CLAUDE.md` da raiz; 259 testes hoje). Markdown não tem teste automatizado: checks V (estáticos, rodados pelo agent da task e na Verification) e checks de uso real (cenários 46-55 e U1-U8, pelo usuário). Classes e testes novos citam esta spec na docstring.

*Adendo 2026-11-13:* a suite tem 268 testes; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A5.

### `test_classify.py` - `LuaCommands` (nova; tabela `LUA_TABLE`, um `subTest` por comando)

| # | Comandos | Categorias | Regra |
|---|---|---|---|
| L1 | `busted` | `test-full` | 46 |
| L2 | `busted tests/config_test.lua`, `busted spec/orders_spec.lua` | `test-narrow` | 46 |
| L3 | `busted --filter export`, `busted --filter=export`, `busted -t unit`, `busted --tags=unit` | `test-narrow` | 46, S3 |
| L4 | `busted spec/unit`, `busted lua/orders/` | `test-package` | 46 |
| L5 | `busted spec` | `test-full` | Trade-offs |
| L6 | `./.luarocks/bin/busted --coverage -v tests/a_test.lua`; `.luarocks/bin/busted` | `test-narrow`; `test-full` | S7 |
| L7 | `luarocks test` | `test-full` | S5 |
| L8 | `nvim --headless -u tests/minimal_init.lua -c "PlenaryBustedFile tests/a_spec.lua"` | `test-narrow` | 46 |
| L9 | `nvim --headless -c "PlenaryBustedDirectory tests/ {minimal_init = 'tests/minimal_init.lua'}"`, `nvim --headless -c "PlenaryBustedDirectory tests"` | `test-full` | 46 |
| L10 | `nvim --headless -c "PlenaryBustedDirectory tests/unit {minimal_init = 'tests/minimal_init.lua'}"` | `test-package` | 46 |
| L11 | `nvim --headless --noplugin -u scripts/minimal_init.lua -c "lua MiniTest.run_file('tests/test_a.lua')"`, `... -c "lua MiniTest.run_at_location({file = 'tests/test_a.lua', line = 3})"` | `test-narrow` | 46 |
| L12 | `nvim --headless --noplugin -u scripts/minimal_init.lua -c "lua MiniTest.run()"`, `nvim --headless -c "lua require('mini.test').run()"` | `test-full` | 46 |
| L13 | `nvim --headless -c "lua MiniTest.run(); vim.cmd('qa!')"` | `other`, `test-full` | 2.4 |
| L14 | `nvim --headless -c checkhealth -c qa`, `nvim --headless +qa`, `nvim lua/a.lua`, `nvim`, `nvim -c "PlenaryBustedFile tests/a_spec.lua"`, `/usr/bin/nvim --version` | `other` | 46 (negativos) |
| L15 | `mise run test`, `mise r test`, `mise tasks run test`, `mise test`, `mise run test:unit`, `mise run 'test:*'`, `mise run --force test`, `mise run -j 4 test`, `rtk mise run test` | `test-full` | 46, S4 |
| L16 | `mise run test tests/a_spec.lua` | `test-narrow` | 46 |
| L17 | `mise run lint`, `mise r lint:lua`, `mise run format`, `mise run format-check`, `mise run fmt` | `lint` | 46 |
| L18 | `mise run all`, `mise run check`, `mise run ci`, `mise check` | `test-full` | 46 |
| L19 | `mise run setup`, `mise run clean`, `mise install`, `mise ls`, `mise test-tool node`, `mise exec -c busted` | `other` | 46, S4 |
| L20 | `mise exec -- busted tests/a_spec.lua`, `mise x -- busted tests/a_spec.lua`, `mise exec lua@5.4 -- busted tests/a_spec.lua`, `mise x -C sub -- busted tests/a_spec.lua` | `test-narrow` | 46 |
| L21 | `mise exec -- busted` | `test-full` | 46 |
| L22 | `mise x -- luacheck lua/` | `lint` | 46 |
| L23 | `luacheck lua/ tests/`, `./.luarocks/bin/luacheck lua/ --no-unused-args`, `selene lua/`, `stylua lua/`, `stylua --check lua/`, `treefmt`, `treefmt --ci` | `lint` | 46, S5, S7 |
| L24 | `mise run format ::: test` | `lint`, `test-full` | S4 |
| L25 | `timeout 120 nvim --headless -u tests/minimal_init.lua -c "PlenaryBustedFile tests/a_spec.lua"`, `timeout --signal=KILL 60 busted tests/a_spec.lua`; `timeout -k 5 300 mise run test`, `timeout 60 pytest`; `timeout x busted` | `test-narrow`; `test-full`; `other` | S6 |

Flags esperadas: `[]` em todos. C1-C37 e X1-X14 continuam iguais (C12 `pnpm --filter api test` = `test-package` prende S3).

*Adendo 2026-11-13:* casos novos LR1-LR7 (na `LUA_TABLE` e em `TIMEOUT_CROSS_STACK`, LR7 com flags); ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A5.

### `test_hook_main.py` (por `call_main`)

| # | Caso | Esperado |
|---|---|---|
| LE1 | literal `IMPLEMENTERS` com `"lua"` na linha de `mobile-react-native`; `test_e9_actor_sets_match_the_literals_below` | passa; os laços atuais de E9 passam a cobrir o `lua` (`pytest`, `pnpm --filter api test`, `k6 run x.js` sinalizados; `pytest tests/test_a.py` não) |
| LE2 | `PostToolUse` Bash do `lua`: `busted`, `busted spec/unit`, `luarocks test`, `mise run test`, `mise run all`, `mise exec -- busted`, `timeout 300 mise run test`, `nvim --headless -c "PlenaryBustedDirectory tests/"`, `nvim --headless -c "lua MiniTest.run()"` | `suite_by_non_runner` em todos |
| LE3 | mesmo, comandos estreitos: `busted tests/config_test.lua`, `./.luarocks/bin/busted tests/a_spec.lua`, `busted --filter export`, `nvim --headless -u tests/minimal_init.lua -c "PlenaryBustedFile tests/a_spec.lua"`, `nvim --headless -c "lua MiniTest.run_file('tests/test_a.lua')"`, `luacheck lua/`, `stylua --check lua/`, `mise run lint`, `nvim --headless -c checkhealth -c qa` | sem `suite_by_non_runner` |
| LE4 | `main` e `test-runner` com `busted` e `mise run test` | sem `suite_by_non_runner` |
| LE5 | `lua` com run ativo (`allowed_paths` `{"1": ["lua/**"]}`): `PostToolUse` Write em `lua/a.lua`, em `plugin/a.lua` e Edit em `README.md` | `[]`; `out_of_scope_write`; `docs_write_by_implementer` presente |

*Adendo 2026-11-13:* casos novos LE6 e LE7; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A5.

### Checks estáticos (V)

| # | Check | Como rodar | Task |
|---|---|---|---|
| V1 | Frontmatter do agent | script stdlib (`python3 -I`): o bloco entre os dois `---` de `agents/lua.md` tem `name: lua`, `model: sonnet`, `effort: medium`, nenhuma linha `tools:`, `skills` exatamente `implementer-contract`, `design-system`, `neovim-plugin`, `lua-tui` (nessa ordem), a description da Design 6.1 palavra por palavra; cada skill listada tem `.claude/skills/<nome>/SKILL.md` | 5 |
| V2 | Frontmatter das skills | o mesmo script: `name` igual à pasta; `description` contém "Preloaded by the lua agent" e "Use when"; nenhuma linha `user-invocable` | 3, 4 |
| V3 | Tamanhos | `wc -c .claude/agents/lua.md` entre 3400 e 4600; `wc -l -c` de cada skill nova: no máximo 120 linhas e 7000 bytes | 3, 4, 5 |
| V4 | `lua` em toda lista de stack | `grep -n 'mobile-react-native' .claude/hooks/agent-audit.py .claude/hooks/tests/test_hook_main.py .claude/skills/implement/SKILL.md .claude/agents/specker.md .claude/templates/docs-structure/features/_template/spec.md .claude/skills/implementer-contract/SKILL.md .claude/skills/design-system/SKILL.md \| grep -vw lua` sem saída; `grep -c 'stylua.toml' .claude/skills/implement/SKILL.md` >= 1 | 1, 2, 6 |
| V5 | Sem em dash | `grep -nP '\x{2014}' <arquivos da task>` sem saída | todas |
| V6 | Template `LUA.md` | `grep -n '^#' .claude/templates/onboarding/LUA.md` mostra, nesta ordem, `# Lua - <project name>`, `## <unit path>`, `### Stack`, `### Folder structure`, `### Design patterns in use`, `### Conventions observed`, `### Inconsistencies`, `### Recommendations`, `### Open questions`; `grep -c 'not aspirational'` = 1; `grep -c 'one level down'` = 1 | 9 |
| V7 | `onboard` | `grep -n 'LUA.md' .claude/skills/onboard/SKILL.md` acha a description e os passos 2, 4 e 5; `grep -n 'OpenResty'` acha a regra do `Local runtime`; `grep -n 'mise'` acha as fontes de `Test suites` | 9 |
| V8 | `test-runner` | `grep -n 'minimal_init' .claude/agents/test-runner.md` acha a linha da tabela e o bullet de `blocked`; `grep -n 'mise.toml'` acha o passo 2; `grep -c '| Lua'` = 1 | 7 |
| V9 | `test-writer` e `tdd` | `grep -n 'busted' .claude/agents/test-writer.md` acha busted, plenary e mini.test na lista; `grep -n 'error("not implemented")' .claude/skills/tdd/SKILL.md` acha o passo 2 | 8 |
| V10 | Contract e design system | `grep -n 'nvim --headless' .claude/skills/implementer-contract/SKILL.md` acha a seção 5; `grep -n '^## 5' .claude/skills/implementer-contract/SKILL.md` mostra o título novo; `grep -n 'no scope request' .claude/skills/design-system/SKILL.md` acha o bullet S9 | 2 |
| V11 | Cobertura das regras | checklist do review: cada seção do agent e das skills cobre as regras da sua tabela (Design 4, 5, 6.2); a regra 46 tem um caso L ou LE por linha | 1, 3, 4, 5 |
| V12 | Escopo | `git diff --stat` da task mostra só os arquivos do **Files**; `agent-audit.json`, `agent-metrics.py` e `settings.json` intactos | todas |

*Adendo 2026-11-13:* o V9 da `tdd` procura o texto novo do stub; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A1.

### Regras do plan -> testes

| Regras | Testes |
|---|---|
| 1-4 (definição, description, corpo, listas) | V1, V3, V4, V11 |
| 5-10 (runtime e versão) | cenários 46, 52, 53; V11 |
| 11-14 (ferramentas, sem framework, dependência, ferramenta ausente) | cenários 46, 51; U1, U2 |
| 15-19 (Neovim) | cenários 46, 47, 51; U3; V11 |
| 20-24 (TUI de terminal) | cenário 48; U4; V11 |
| 25-26 (estados, assíncrono depois de fechar) | cenários 47, 48; U3 |
| 27-31 (skills, uso sozinhas, compactas, `design-system`) | V2, V3, V10; cenário 48; U7 |
| 32 (checks estreitos) | L1-L25, LE2, LE3; cenário 46 |
| 33-35 (nada interativo, `manual_checks`, OpenResty) | cenários 46-48, 50, 52; Verification item 4; V10 |
| 36 (scaffold, gerados, report) | cenários 46, 47; U5 |
| 37 (hook) | LE1-LE5; cenário 55 |
| 38-40 (roteamento, template) | V4; cenário 50; U8 |
| 41-42 (`test-runner`) | V8; cenário 49 |
| 43, 48-50 (`onboard`, `LUA.md`) | V6, V7; cenário 54; U6 |
| 44 (contract, design system) | V4, V10 |
| 45 (docs) | passe do `docs-writer` (Design 12) |
| 46 (classificação) | L1-L25, LE2-LE4; cenário 55 |
| 47 (`test-writer`, `tdd`) | V9; U5 |

*Adendo 2026-11-13:* as linhas 32, 37 e 46 ganham LR1-LR7, LE6 e LE7; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A5.

Checks extras de uso real, para regras sem cenário em 14.3 (Verification):

| # | Situação | Esperado |
|---|---|---|
| U1 | pedir ao `lua` uma função com testes num projeto Lua sem framework de teste | `blocked` com `scope_requests` propondo o framework (busted; plenary ou mini.test em Neovim, pela skill); nada adicionado |
| U2 | projeto com `mise.toml` cuja tool `luajit` não está instalada | nada instalado; check em `blocked` com o comando que o usuário roda |
| U3 | na janela flutuante do cenário 47, ler o diff | teardown em `WinClosed`/`BufWipeout` (autocmds, timers, extmarks); callbacks assíncronos conferem `nvim_buf_is_valid`/`nvim_win_is_valid`; `vim.schedule` nos callbacks de `vim.uv` |
| U4 | na TUI do cenário 48, ler o diff | sem TTY (`guess_handle`) não entra em raw mode; `NO_COLOR` desliga cores |
| U5 | `/tdd` num módulo Lua pequeno | stubs com a forma real e `error("not implemented")`; todas as falhas com `failure_kind: assertion` |
| U6 | `onboard` neste dotfiles, escolhendo só `awesome/` e `conky/`, numa worktree descartável | proposta de `LUA.md` na raiz com dois blocos (`## awesome`, `## conky`), runtime embarcado com o nome do hospedeiro, UI e health check "not applicable" onde couber; nenhum `BACKEND.md` |
| U7 | na sessão principal, editar a config Neovim de um projeto sem chamar o `lua` | a `neovim-plugin` é carregada pela description |
| U8 | spec antiga sem **Stack**, com uma task que só toca `.lua` | o `implement` mostra `lua` na tabela de tasks |

*Adendo 2026-11-13:* U5 espera stubs com valor vazio ou zero do tipo certo; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A1.

## Implementation order

### Task 1 - Hook: lua em IMPLEMENTERS e classificação de comandos Lua

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/tests/test_classify.py`, `.claude/hooks/tests/test_hook_main.py`
- **Depends on:** -
- **Done when:** `IMPLEMENTERS` e o literal de `test_hook_main.py` têm `"lua"` na linha de `mobile-react-native`; `strip_prefixes`, `test_scope`, `mise_categories`, `nvim_category` e as regex seguem a Design, seção 2; L1-L25 passam em `LuaCommands` (um `subTest` por comando) e LE1-LE5 em `test_hook_main.py`; C1-C37 e X1-X14 sem mudança; o docstring cita os runners Lua e as tasks do mise; `python3 -I -B -m unittest discover -s .claude/hooks/tests -t .claude/hooks` verde (259 + os novos); V4 (parte do hook), V5 e V12 *Adendo 2026-11-13:* vale também o texto de A2-A5 do adendo (268 testes)
- **Status:** done

### Task 2 - Contract e design-system: lua nas descriptions e UI de Neovim e terminal

- **Stack:** frontend-react
- **Files:** `.claude/skills/implementer-contract/SKILL.md`, `.claude/skills/design-system/SKILL.md`
- **Depends on:** -
- **Done when:** as duas descriptions listam o `lua`; a seção 5 do contract tem o título e os três bullets da Design 3 (`nvim --headless` só para testes; nada interativo, hospedeiro ou nginx; `manual_checks` com abertura e tamanho); o passo 1 da `design-system` tem o bullet S9; o resto dos dois arquivos não muda; V4 (parte), V5, V10, V12
- **Status:** done

### Task 3 - Skill neovim-plugin

- **Stack:** frontend-react
- **Files:** `.claude/skills/neovim-plugin/SKILL.md`
- **Depends on:** -
- **Done when:** frontmatter da Design 4, palavra por palavra; o corpo tem as seções da tabela da Design 4, na ordem, cada uma com as regras-chave; V2, V3, V5, V12; checklist V11 (regras 9, 15-19, 27, 32, 33) *Adendo 2026-11-13:* vale também o texto de A6 do adendo
- **Status:** done

### Task 4 - Skill lua-tui

- **Stack:** frontend-react
- **Files:** `.claude/skills/lua-tui/SKILL.md`
- **Depends on:** -
- **Done when:** frontmatter da Design 5, palavra por palavra; o corpo tem as seções da tabela da Design 5, na ordem; nenhuma cor hex, `guifg`/`guibg`, 256 ou RGB recomendada (`grep -nE '#[0-9a-fA-F]{6}|38;5;|38;2;'` sem saída fora de um exemplo do que evitar); V2, V3, V5, V12; checklist V11 (regras 17-18, 20-26, 31, 34) *Adendo 2026-11-13:* vale também o texto de A6 do adendo
- **Status:** done

### Task 5 - Agent lua

- **Stack:** frontend-react
- **Files:** `.claude/agents/lua.md`
- **Depends on:** Task 2, Task 3, Task 4
- **Done when:** frontmatter da Design 6.1 (V1); o corpo tem as sete seções da Design 6.2, na ordem, com a tabela de runtime, os limites por versão, os comandos estreitos com `timeout`, a política de UI e os extras do report; V3 (3.400 a 4.600 bytes), V5, V12; checklist V11 (regras 1-14, 32-36) *Adendo 2026-11-13:* vale também o texto de A6 e A7 do adendo
- **Status:** done

### Task 6 - Roteamento: Stack lua no implement, no specker e no template de spec

- **Stack:** frontend-react
- **Files:** `.claude/skills/implement/SKILL.md`, `.claude/agents/specker.md`, `.claude/templates/docs-structure/features/_template/spec.md`
- **Depends on:** Task 5
- **Done when:** o item do stack da seção 4 do `implement`, o item **Stack** do `specker` e a linha **Stack** do template seguem a Design 7 (marcadores com `.stylua.toml` e `selene.toml`; arquivos da task vencem os marcadores; uma task, um stack); `git diff` de cada arquivo mostra só essas linhas; V4, V5, V12
- **Status:** done

### Task 7 - test-runner: suites Lua sem Test suites

- **Stack:** frontend-react
- **Files:** `.claude/agents/test-runner.md`
- **Depends on:** -
- **Done when:** passo 2 com as tasks do `mise.toml` entre os scripts do projeto; tabela com a linha Lua e a linha Makefile/justfile/mise da Design 8; seção 3 com o bullet do `minimal_init` ausente e do Neovim só headless; frontmatter intacto; V5, V8, V12
- **Status:** done

### Task 8 - test-writer e tdd conhecem Lua

- **Stack:** frontend-react
- **Files:** `.claude/agents/test-writer.md`, `.claude/skills/tdd/SKILL.md`
- **Depends on:** Task 3
- **Done when:** a seção 2 do `test-writer` tem busted, plenary.nvim e mini.test, os nomes de arquivo Lua e o bullet da `neovim-plugin`, com "Never introduce a new test framework" intacto; o passo 2 da `tdd` tem a forma do stub Lua da Design 8; V5, V9, V12 *Adendo 2026-11-13:* vale também o texto de A1 do adendo (stub com valor vazio)
- **Status:** done

### Task 9 - onboard reconhece unidades Lua; template LUA.md

- **Stack:** frontend-react
- **Files:** `.claude/skills/onboard/SKILL.md`, `.claude/templates/onboarding/LUA.md`
- **Depends on:** Task 3, Task 4
- **Done when:** a `onboard` segue a tabela da Design 9 (description, passos 2, 4, 5 e 7); `LUA.md` segue a Design 9.1 (comentário de topo, um bloco por unidade, seções um nível abaixo, comentários-guia, "not applicable" explícito); `BACKEND.md`, `FRONTEND.md` e `MOBILE.md` intactos; V5, V6, V7, V12
- **Status:** done

## Verification

1. **Suite**, pelo `test-runner`: `claude-hooks` inteira, verde (259 + os novos). Não há suite `on-demand` neste repo.

   *Adendo 2026-11-13:* 268 testes; o cenário 55 cobre também LE6-LE7 e LR1-LR7; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A5.
2. **Estáticos**, pela sessão principal, só leitura: V1-V12 (Testing), com `git diff --stat main` mostrando só os arquivos das tasks.
3. **Sem runtime local nem request**: a config não tem serviço.
4. **Uso real, pelo usuário, numa sessão nova do Claude Code** (agents e skills novos só aparecem nela):

| Cenário (14.3) | Montagem | O que conferir |
|---|---|---|
| 46 | `/home/void/workspace/claudinho.nvim`, numa branch ou worktree descartável; uma spec pequena com `Stack: lua` (ex.: uma validação nova em `lua/claudecode/config.lua` com teste em `tests/config_test.lua`), ou o pedido direto ao `lua` | `notes` com runtime Neovim plugin, LuaJIT e Neovim mínimo 0.8; `checks_run` só com o arquivo de teste (`./.luarocks/bin/busted tests/config_test.lua`, direto ou por `mise exec --`) e luacheck nos arquivos tocados; nenhum `mise run test`/`check`/`all`; `vim.uv or vim.loop` se a mudança usar `vim.uv` (mínimo abaixo de 0.10) |
| 47 | no claudinho.nvim, uma janela flutuante pequena (ex.: um painel de status) | highlights com `link` e `default = true`, sem hex; layout refeito em `VimResized`; `manual_checks` com o comando de abertura, redimensionar, terminal com 40 colunas, `:colorscheme` claro e escuro, cada estado e `:q` + reabrir (exemplo da 15.2) |
| 48 | TUI de terminal de teste em `~/sandbox/lua-tui-*` (git init, `main.lua`, busted), uma vez sem e outra com `DESIGN_SYSTEM.md` | restauração na saída normal, no erro e em Ctrl-C, lida no código; `SIGWINCH`; sem o arquivo, só ANSI nomeadas e nenhum pedido de escopo; com o arquivo, os tokens; nenhuma dependência nova; o app não foi executado |
| 49 | `test-runner` com escopo `full` no claudinho.nvim (sem `## Test suites`); depois, numa cópia sem `tests/minimal_init.lua` | detecção pela CI (`mise run check`, `mise run test`, `mise run format-check`); na cópia, a suite Neovim em `blocked` com o motivo e nada criado |
| 50 | repo de teste com um serviço Go e um gateway OpenResty em `services/`; pedir a spec ao `specker` | tasks separadas por stack (`backend-go`, `lua`); a task OpenResty com `local_checks` (ou `skipped` com o `curl`) |
| 51 | config de Neovim de teste (`init.lua` + `lua/`, sem testes) | nenhuma convenção de plugin; nenhum framework adicionado; `manual_checks` |
| 52 | neste dotfiles, numa branch, um ajuste pequeno em `awesome/config/` | API do awesome respeitada; nada executado nem recarregado; `manual_checks` com "recarregar awesome" |
| 53 | biblioteca de teste com `std = "lua51"` no `.luacheckrc` e rockspec `lua >= 5.1, < 5.2` | nenhum `//`, bit a bit nativo, `utf8`, `<const>`/`<close>` nem `goto` |
| 54 | `onboard` no claudinho.nvim, numa worktree descartável | projeto reconhecido como Lua; `LUA.md` com `## .` e todas as seções; `Test suites` proposto e escrito só depois do sim; sem `Local runtime` |
| 55 | coberto pela suite (LE1-LE5, L1-L25) | - |

Mais U1-U8 (Testing). No fim, as métricas da sessão de uso real:

```bash
python3 ~/.claude/hooks/agent-metrics.py --since <data do merge> --merge
grep -h '"actor": "lua"' ~/.claude/metrics/*.jsonl | grep -E '"cmd": "[^"]*\b(nvim|love|wezterm|hs|awesome|awesome-client|conky|nginx|openresty)\b' | grep -v -- '--headless'
```

`suite_by_non_runner` com ator `lua` = 0 fora de LE2; a segunda busca sem saída (uma linha só com `nvim --version` ou `nginx -t` é conferida à mão); `test-narrow` e `lint` do `lua` em `## Actions by category`; no transcript, `manual_checks` em toda task de UI do `lua`.

**Para o usuário conferir na leitura**: o texto de `agents/lua.md` e das duas skills (curto, sem tutorial, regras acionáveis), e o `LUA.md` proposto no cenário 54.

## Open questions

Nenhuma que bloqueie as tasks. Para decidir na aprovação ou depois:

1. **Guarda mecânica contra execução interativa** (fora do plan). Opções: (a) categoria nova no hook (`interactive_app`, `block`) para `nvim` sem `--headless` e fora de modos não interativos (`--version`, `-l`, `-es`), `love` e os binários dos hospedeiros, nesta spec; (b) entrada de refactor agora (pelo `backlog-keeper`), decidida com os dados da métrica de 14.2 depois dos cenários 46-52; (c) só a instrução e a métrica, como o plan prevê. Recomendação: (b). A instrução está no contract e no agent, a métrica mede, e a categoria precisa de desenho próprio (lista aberta de hospedeiros, modos legítimos do `nvim`) que não deve atrasar a etapa.
2. **Decisões S3-S9** (formas do mise, `luarocks test`, `treefmt`, `timeout` para todas as stacks, binários com caminho, marcadores `.stylua.toml`/`selene.toml`, bullet da `design-system`) vão além do texto do plan. Opções: (a) aceitar como estão; (b) tirar o `timeout` (S6), que muda a classificação das outras stacks; (c) tirar outra. Recomendação: (a); cada uma fecha um buraco real visto no claudinho.nvim ou na doc oficial, e todas têm caso de teste.

*Adendo 2026-11-13:* pergunta 3 nova (stub do scaffold do `lua` no `/implement --tdd`), resolvida como (a); ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A7.

## Adendo 2026-11-13 - ajustes do review de código e de segurança

- **Origem**: `code-reviewer` e `security-reviewer`, review de 2026-11-13, mais uma decisão do usuário sobre o stub Lua da `tdd`; tudo já implementado, dentro das tasks feitas.
- **Afeta**: Summary; Background (S3, S6); Design, seções 2.2, 2.3, 2.4, 4, 5, 6.2, 8 e 10; Trade-offs; Testing (LR1-LR7, LE6-LE7, V9, U5, Regras -> testes); Verification, item 1 e cenário 55; Open questions. O **Done when** das Tasks 1 (A2-A5), 3 e 4 (A6), 5 (A6, A7) e 8 (A1) passa a valer com o texto deste adendo; o **Status** das tasks não muda. O texto original fica como registro; onde divergir, vale este adendo.
- **Não muda**: categorias, flags e ações do hook; `agent-audit.json`, `agent-metrics.py` e `settings.json`; L1-L25 e LE1-LE5; o roteamento (Task 6), o `test-runner` (Task 7) e o `onboard` (Task 9).

### A1 - Decisão do usuário: stub Lua da `tdd` devolve valor vazio (Design 8, Task 8)

**Motivo.** O busted reporta como Error, não como Failure, um teste que chega a um `error()`; o `test-runner` classifica isso como `failure_kind: runtime`, e o passo 4 da `tdd` ("red for the right reason", só `assertion`) rejeitaria todo teste escrito contra um stub `error("not implemented")`.

**Texto novo** do parêntese Lua do passo 2 de `skills/tdd/SKILL.md` (substitui o da seção 8), exatamente:

```markdown
(Lua: a module with the real shape - the returned table, function signatures, LuaCATS annotations - and bodies that return an empty or zero value of the right type: `{}` for a table, `""`, `0`, `false`, a documented `nil`, or an empty iterator or callback that fits the signature; never `error("not implemented")`, because busted reports a test that hits `error()` as an Error, not a Failure; check that each stub loads instead of a typecheck)
```

**Plan.** Revisa a redação da D23 (g) e da regra 47 sobre a forma do stub ("corpos `error("not implemented")`"). O texto do plan em `agent-workflow.md` 15.2 (regra 47) e a linha D23 (g) de 16.1 ficam com a redação antiga; o `docs-writer` acrescenta um adendo ao plan.

**Checks.** V9, parte da `tdd` (substitui `grep -n 'error("not implemented")'`): `grep -n 'Error, not a Failure' .claude/skills/tdd/SKILL.md` acha o passo 2. U5 passa a esperar stubs com a forma real e corpos com valor vazio ou zero do tipo certo, nenhum `error("not implemented")`, e todas as falhas com `failure_kind: assertion`. A linha 47 de Regras -> testes não muda (V9; U5).

**Fase `scaffold` do agent `lua`.** A mesma regra vale para os stubs do `/implement` (`--tdd` faz a mesma checagem); aplicada como correção de review da Task 5, ver A7.

### A2 - Segurança (média, corrigido): `timeout` e `mise` em toda forma, com falha fechada (Design 2.3 e 2.4, S6, S3)

**Motivo.** O parse da seção 2.3 só removia formas fixas de `timeout` (`-s SIG`, `-k D`, `--signal=SIG`, ...) e a duração `^\d+(\.\d+)?[smhd]?$`; qualquer outra forma (`timeout -k5 60 ...`, `timeout --kill-after 5 60 ...`, `timeout .5 ...`) deixava o segmento inteiro como `other`. Como S6 vale para todas as stacks, um `docker compose restart`, um `git push` ou uma suite atrás dessas formas escapava de `docker_lifecycle`, `git_push` e `suite_by_non_runner`. O mesmo acontecia com flags globais do mise antes de `exec`/`x`.

**`timeout`** (substitui o bullet `timeout` da seção 2.3; `_timeout_strict_len()` e `_timeout_prefix_len()` em `agent-audit.py`):

| Parte | Formas aceitas (as do getopt do GNU `timeout`) |
|---|---|
| Opções curtas | `-k D`, `-kD`, `-s SIG`, `-sSIG`, `-v`, `-f`, `-p`; clusters (`-vk 5`), o valor de `k`/`s` no resto do cluster ou no token seguinte |
| Opções longas | `--kill-after`, `--signal`, `--foreground`, `--preserve-status`, `--verbose`, com `=` ou com o valor no token seguinte (`--signal KILL`, `--kill-after 5`); abreviação única (`--kill`); `--` encerra as opções |
| Duração | formato do `strtod` com sufixo opcional `s`/`m`/`h`/`d`: `60`, `.5`, `1.5m`, `1e3`, `inf`, `0x10` |
| Forma não entendida (opção desconhecida, abreviação ambígua, duração que não casa) | falha fechada: descarta as opções iniciais (tokens com `-`) e até dois tokens com cara de duração depois delas; o resto é classificado, então o comando real sempre recebe categoria |

`timeout` sozinho, ou só com a duração, continua `other`. Entrada longa ou truncada (`timeout -k`, milhares de `-v`) termina em tempo linear e fica `other`.

**`mise`** (complementa o bullet `mise exec` da seção 2.3 e a linha "Tokens depois de `mise`" da tabela `mise_categories` da seção 2.4; `_skip_mise_flags()`):

- Flags globais antes de `exec`/`x` são puladas pelo mesmo `_skip_mise_flags()` de `mise_categories`: `mise -C /tmp exec -- docker restart x` e `mise -q x -- busted` chegam ao comando depois do `--`.
- `_MISE_VALUE_FLAGS` (flags que consomem o token seguinte sem `=`), completo: `-C`/`--cd`, `-E`/`--env`, `-P`/`--profile`, `--log-level`, `-j`/`--jobs`, `-o`/`--output`, `-t`/`--tool`, `-s`/`--shell`, `--timeout`, `--secrets`, `--allow-env`, `--allow-net`, `--allow-read`, `--allow-write`, `--affected-base`, `--affected-head`, `--task-cache`. Um cluster de flags curtas booleanas terminado numa flag de valor (`-vC dir`) também consome o token seguinte.

### A3 - Segurança (baixa, corrigido): shell escapes do Neovim (Design 2.4 e 10)

**Motivo.** `nvim --headless -c 'PlenaryBustedFile a_spec.lua' -c '!docker restart x'` era só `test-narrow`: o comando de shell rodado pelo Neovim não era classificado e escapava das flags.

**Regra nova** (complementa `nvim_category` da seção 2.4; `nvim_shell_texts()` e `_NVIM_SHELL` em `agent-audit.py`): cada argumento de `-c`, `--cmd`, `--cmd=` ou `+` que começa com `!` ou contém `:!`, `silent !` (ou `sil!`), `w !` ou `r !`, também depois de `|`, tem o texto de shell classificado por `classify_command`; categorias e flags se juntam às do segmento `nvim`. A recursão para na profundidade 3. `-c 'qa!'` não é shell escape. Na seção 10, o bullet do hook ganha: o texto de shell dentro de comandos do Neovim é classificado como comando próprio, com profundidade limitada.

### A4 - Ajustes menores de classificação, corrigidos (Design 2.2 e 2.4, Trade-offs)

| Ponto | Regra nova | Substitui |
|---|---|---|
| busted com arquivo | qualquer argumento `.lua` que não seja valor de flag (`--helper`, `-o`, ...) torna o busted `test-narrow` (`busted tests/test_config.lua`, `busted spec/config.lua`) | o Trade-off "`busted <arquivo>.lua` com nome fora de `_spec`/`_test` é `test-package`" |
| `luarocks test` | `strip_prefixes` pula as flags globais antes de `test` (`luarocks --lua-version 5.1 test`, `luarocks --tree .rocks --local test` -> `luarocks test`; `_LUAROCKS_VALUE_FLAGS` consomem o token seguinte): `test-full` | a entrada `luarocks test` de `TEST_RUNNERS` (seção 2.2) sozinha, que só casava a forma sem flags |
| Runners do Neovim | `require("plenary.test_harness").test_directory(...)` segue a regra de `PlenaryBustedDirectory`, `.test_file(...)` é `test-narrow`; `require"mini.test"` e `require'mini.test'` contam como `MiniTest` | as formas da tabela `nvim_category` (seção 2.4), que só citavam os comandos `Plenary*` e `require('mini.test')` |
| Pasta absoluta | em `PlenaryBustedDirectory`/`test_directory`, um caminho absoluto que termina numa pasta de teste (`test`, `tests`, `spec`, `specs`) é `test-full`; `/home/u/proj/tests/unit` continua `test-package` | a regra "ainda tem `/`" da tabela `nvim_category`, que tornava todo caminho absoluto `test-package` |

### A5 - Testes novos (Testing, Verification)

Suite `claude-hooks`: **268 testes** (259 antes da etapa, 264 depois da Task 1).

**`test_classify.py`**: as linhas LR entram na `LUA_TABLE` da classe `LuaCommands` (um `subTest` por comando; as flags das linhas LR ficam presas só no LR7). Métodos novos: `test_cross_stack_effect_of_timeout_and_shell_escapes` (tabela `TIMEOUT_CROSS_STACK`) e `test_long_or_odd_input_stays_bounded` (entrada longa ou truncada fica `other`, sem custo quadrático).

| # | Cobre | Exemplos | Esperado |
|---|---|---|---|
| LR1 | A2, `timeout` | `timeout -k5 60 docker restart x`, `timeout -sKILL 5 ...`, `timeout --signal KILL 5 ...`, `timeout --kill-after 5 60 ...`, `timeout -vk 5 60 ...`, `timeout --kill 5 60 ...`, `timeout -- 5 ...`, `timeout .5`/`1e3`/`inf`/`0x10`/`1.5m`/`2h ...`; falha fechada: `timeout --unknown-flag 5 ...`, `timeout -Z busted tests/a_spec.lua`; `timeout`, `timeout 5` | a categoria do comando real; `other` nos dois últimos |
| LR2 | A2, `mise` | `mise -C /tmp exec -- ...`, `mise -q x -- ...`, `mise --log-level debug x -- ...`, `mise -P dev x -- ...`, `mise -vC /tmp x -- ...`, `mise --log-level debug run test`, `mise -P dev run test tests/a_spec.lua` | a categoria do comando real; `test-full`; `test-narrow` |
| LR3 | A3 | `-c '!docker restart x'`, `+'!docker restart x'`, `-c ':!docker compose down'`, `--cmd '!git push'`, `-c 'silent !...'`, `-c 'w !...'`; negativos `-c '!ls'`, `-c 'qa!'` | categoria do shell escape junto da do `nvim`; `other` |
| LR4 | A4, busted | `busted tests/test_config.lua`, `busted spec/config.lua`; `busted --helper spec/helper.lua`, `--helper=spec/helper.lua`, `-o utfTerminal.lua` | `test-narrow`; o valor de flag não conta como arquivo |
| LR5 | A4, luarocks | `luarocks --lua-version 5.1 test`, `--lua-version=5.1 test`, `--tree .rocks --local test`; `luarocks install busted` | `test-full`; `other` |
| LR6 | A4, Neovim | `test_harness').test_directory('tests/unit', {})`, `.test_directory('tests')`, `.test_file('tests/a_spec.lua')`; `require"mini.test".run()`, `require'mini.test'.run()`, `require"mini.test".run_file(...)`; `PlenaryBustedDirectory /home/u/proj/tests`, `.../tests/unit` | `test-package`, `test-full`, `test-narrow`; `test-full`, `test-full`, `test-narrow`; `test-full`, `test-package` |
| LR7 | efeito de S6 em outras stacks, com flags | `timeout 5 git push`; `timeout 60 docker compose up -d`; `timeout --kill-after 5 60 docker compose restart api`; `mise -C /tmp x -- docker restart x`; o shell escape do LR3 | `git-push` com `git_push`; `docker-lifecycle` com `docker_lifecycle` |

**`test_hook_main.py`**, classe `LuaActor`:

| # | Caso | Esperado |
|---|---|---|
| LE6 | `PostToolUse` Bash do `lua`: os comandos do LR7 | `docker_lifecycle` ou `git_push` em cada um |
| LE7 | `lua` com suites atrás de formas novas: `timeout -k5 60 busted`, `timeout --signal KILL 60 mise run test`, `mise -q x -- busted` | `suite_by_non_runner` em todos |

**Regras -> testes**: a linha 32 ganha LR1-LR6; a 37 ganha LE6 e LE7; a 46 ganha LR1-LR7, LE6 e LE7. **Verification**: item 1 = 268 testes, verde; o cenário 55 passa a "coberto pela suite (LE1-LE7, L1-L25, LR1-LR7)". O **Done when** da Task 1 vale com A2-A5 e 268 testes.

### A6 - Correções nos markdown (Design 4, 5 e 6.2; Tasks 3, 4 e 5)

| Arquivo | Correção | Seção da Design |
|---|---|---|
| `skills/neovim-plugin/SKILL.md` | a guarda de carga dupla tem as duas linhas (`if vim.g.loaded_<name> then return end`, depois `vim.g.loaded_<name> = 1`); os exemplos de contexto rápido são handles de `vim.uv`, timers (`vim.uv.new_timer`) e callbacks de `vim.system`, não `vim.fn.jobstart` (que roda no loop principal) | 4, linhas "Layout and loading" e "Async" |
| `agents/lua.md` | Neovim mira Lua 5.1: recursos só do LuaJIT (`goto`, `ffi`, `bit`) só atrás de uma checagem de `jit` (substitui "`goto` só LuaJIT ou 5.2+" dos limites por versão); a cláusula "LuaCATS annotations are code, not docs" volta ao `needs_docs` (o log da Task 5 a tinha cortado para caber em S10) | 6.2, seções 3 e 7 |
| `skills/lua-tui/SKILL.md` | a área útil é `vim.o.columns` e `vim.o.lines - vim.o.cmdheight`, menos a tabline (`showtabline`), a `winbar` quando definida e a statusline quando visível (`laststatus` 2 ou 3, ou 1 com duas ou mais janelas) | 5, linha "Neovim: buffers and windows" (substitui "`lines` menos `cmdheight` e statusline") |

Os limites de tamanho de S10 continuam valendo (V3).

### A7 - Stub do scaffold do agent `lua` (Design 6.2, seção 6; Task 5; regra 36)

**Motivo.** Consequência direta de A1: o passo 3 do `/implement --tdd` roda os testes novos pelo `test-runner` com escopo `files` e exige toda falha `assertion`; um `runtime` volta ao scaffold. Com corpos `error("not implemented")`, o busted reportaria Error e toda task Lua em `--tdd` voltaria ao scaffold. Resolve a pergunta 3 deste adendo como (a), sem task nova: é correção de review da Task 5.

**Regra nova** (substitui "corpos `error("not implemented")`" da linha 6 da tabela da Design 6.2): na fase `scaffold`, o `lua` escreve o módulo com a forma real (tabela retornada, assinaturas, anotações LuaCATS) e corpos de função que devolvem um valor vazio ou zero do tipo certo (`{}`, `""`, `0`, `false`, `nil` documentado), nunca `error("not implemented")`; a mesma regra do passo 2 da `tdd` (A1). A regra 36 do plan ganha a mesma ressalva no adendo do plan que o `docs-writer` escreve (A1).

**Checks.** `grep -n 'empty or zero value of the right type' .claude/agents/lua.md` acha a seção 6; `grep -n 'not implemented' .claude/agents/lua.md` sem saída; V3 (3.400 a 4.600 bytes), V5 e V12 continuam valendo. O **Done when** da Task 5 vale com este texto.

### Open questions deste adendo

3. **Stub do scaffold do agent `lua` no `/implement --tdd`**. **Resolvida (2026-11-13): opção (a), sem task nova, como correção de review da Task 5; ver A7.** O motivo de A1 parece valer também para a fase `scaffold` do `lua` (`agents/lua.md`, seção 6), que ainda manda corpos `error("not implemented")`, enquanto o passo 3 do `--tdd` do `implement` exige toda falha `assertion`. Opções: (a) alinhar o `lua.md` à `tdd` (valor vazio do tipo certo) numa task nova desta spec; (b) entrada de refactor pelo `backlog-keeper`, decidida depois; (c) manter, aceitando um retorno ao scaffold por task Lua em `--tdd`. Recomendação: (a); uma regra só para stubs Lua, a mesma nos dois caminhos, e a mudança é uma linha.
