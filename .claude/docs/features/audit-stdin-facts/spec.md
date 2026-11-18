# audit-stdin-facts - fatos de stdin derivados da própria análise (ponto fixo), sem passada paralela

- **Date:** 2026-11-18
- **Status:** Approved (2026-11-18, com as respostas da seção Decisões do usuário)
- **Source:** [2026-11-18-audit-stdin-facts-from-main-analysis.md](../../backlog/refactor/2026-11-18-audit-stdin-facts-from-main-analysis.md) (refactor sem plan; não há `plan.md` nesta pasta). Fecha o bug [2026-11-18-audit-stdin-facts-pass-diverges.md](../../backlog/bugs/2026-11-18-audit-stdin-facts-pass-diverges.md) e, por decisão do usuário (decisão 6), parte de [2026-11-18-audit-stdin-alias-fifo-movers-and-dotdot.md](../../backlog/bugs/2026-11-18-audit-stdin-alias-fifo-movers-and-dotdot.md)
- **Implementation log:** [log.md](log.md) (criado pelo `/implement` na primeira task)
- **Pré-requisito:** o run `fix-bug` de [2026-11-18-audit-duplicate-expansion-regex-head-dynamic.md](../../backlog/bugs/2026-11-18-audit-duplicate-expansion-regex-head-dynamic.md) (que também corrige [parallel-command-line](../../backlog/bugs/2026-11-18-audit-parallel-command-line-not-read-as-code.md), [fish-csh-option-scan](../../backlog/bugs/2026-11-18-audit-fish-csh-option-scan-stops-at-value.md) e [at-version-option-listing](../../backlog/bugs/2026-11-18-audit-at-version-option-listing.md)) entra antes da Task 1; esta spec parte do código e da suite que ele deixar e não refaz nenhuma dessas correções

## Summary

O modelo de stdin do classificador do hook `agent-audit` precisa de três fatos do texto inteiro antes de classificar cada comando: os **fifos** criados no texto (nomes, ou "desconhecido"), **`moved`** (o texto muda de diretório ou cria links, também em código aninhado do mesmo shell) e o **mapa de descritores do `exec`** na ordem do texto. Hoje uma passada separada (`_stdin_facts`, `_nested_facts`, `_site_code_facts`, `_mentions_fifo_maker`, `_bare_exec`, `_Run.resolved`, `_stdin_resolver`) calcula esses fatos e reimplementa a resolução que a análise principal já faz (variantes de cabeça, valores atribuídos, expansões que podem sumir, wrappers, aliases e config do git, valores posicionais de funções, aspas em strings aninhadas). Cada rodada de revisão de segurança do último fix achou uma divergência nova; duas seguem abertas, e esta spec mostra mais sete.

Esta spec troca a passada separada por um **ponto fixo sobre a análise principal**: a classificação roda com os fatos assumidos; cada análise aninhada devolve, pelo seu valor de retorno interno, os fatos que observou; se os fatos observados no fim diferem dos assumidos, a análise roda de novo com a união, até um teto de rodadas (`MAX_FACT_ROUNDS = 3`), e falha fechado no teto (nível B, `analysis_budget`). Uma só resolução: o fato vem da mesma leitura que classifica o comando. Junto, `compound_procsub_stdin` passa a usar o estado que o walker já calcula (`Site.given`), em vez de reler os compostos.

| Camada | Arquivo | Mudança |
|---|---|---|
| Parser (puro) | `.claude/hooks/agent_audit_shell.py` | novo valor imutável `Facts`; `StdinContext.facts()` e `StdinContext.of(...)`; `Site.given` (estado que os redirecionamentos de um composto dão ao corpo, Task 7). `Fifos`, `fd_states`, `exec_fds`, `stdin_alias` sem mudança de API |
| Classificador (puro) | `.claude/hooks/agent_audit_classify.py` | `_analyze` interno devolve `(Analysis, Facts)` e itera rodadas; `_Text` (estado por texto, calculado uma vez) separado de `_Run` (estado por rodada); observação dos fatos nas leituras finais; `_code_text` e `_heredoc_code` devolvem os fatos filtrados pelo tipo de aninhamento; saem `_stdin_facts`, `_nested_facts`, `_site_code_facts`, `_CODE_PROGRAMS`, `_changes_directory`, `_stdin_resolver`, `_Run.resolved`, `_Run.head_readings`, `_Run.compound_procsub_stdin` e o bloqueio aninhado de `moved` |
| Hook | `.claude/hooks/agent-audit.py` | sem mudança: `analyze_command(command)` e `Analysis` de três campos ficam iguais |
| Config | `.claude/hooks/agent-audit.json`, `.claude/settings.json` | sem mudança; nenhum motivo novo |
| Testes | `.claude/hooks/tests/` | módulo novo `test_stdin_facts.py`; casos novos em `test_shell_lexer.py`; os testes existentes (1101 em `46ae3a7`, mais os que o run de pré-requisito acrescentar) ficam sem edição |
| Docs (fim, `docs-writer`) | `.claude/README.md` (seção hooks), `CLAUDE.md` da raiz (a contagem da suite já diz 1101; atualizar só com o total final), ponteiro no Adendo 2026-11-18 (2) da spec `audit-shell-lexer` | needs_docs |

Sem serviço, API, banco, feature flag nem migração.

## Background

### O desenho atual (HEAD `46ae3a7`)

`analyze_command(command, _depth, _env, _budget, _code, cwd, _cwd, _fn, _same, _stdin)` faz, nesta ordem:

1. `shell.parse` e `_Run(...)` (estado da análise: valores, funções, vereditos, memo de prefixos).
2. `sites = iter_sites(script, initial)` sem contexto.
3. **Passada de fatos**: `_stdin_facts(sites, _stdin, run.head_readings, ..., run.resolved)` devolve `Fifos`, `moved` e os sites de `exec` puro. Por dentro, `_site_code_facts` acha as strings de código (`_code_args`, corpos de heredoc de shell, corpos de alias `!` do git) de cada site com token de `_CODE_PROGRAMS` ou com expansão, e `_nested_facts` as parseia e anda por elas até `MAX_CODE_DEPTH`, procurando `mkfifo`/`mknod`, `cd`/`ln`, cabeças dinâmicas e menções.
4. `_stdin_resolver` monta um `StdinContext` por trecho do texto (um antes de todo `exec`, um depois de cada `exec` que muda os descritores) e uma segunda caminhada `iter_sites(script, initial, resolve)` dá a cada site o seu contexto.
5. Bloqueios de texto aninhado do mesmo shell: `moved` novo (`eval 'cd /dev/fd'`) e `exec` que muda descritores (`eval 'exec < <(x)'`) são `dynamic_code`.
6. Classificação: `run.simple` por site; o código aninhado desce por `_code_text` -> `analyze_command(_depth + 1, ...)`, que devolve só `Analysis`.
7. `compound_heredocs`, `compound_procsub_stdin` (relê `iter_compounds` e o corpo de cada composto com `<(...)`).

A passada 3 decide quais textos aninhados existem e como resolver cada cabeça sem passar pelo caminho 6. Tudo o que a análise principal aprendeu a resolver (valores V1-V4, operadores de parâmetro H4, brace M2, wrappers e lançadores, aliases e config do git M1/V4, funções que repassam argumentos D1/E, `export` de `GIT_CONFIG_*`) precisa ser espelhado ali. As rodadas 4 a 7 do run `bug-audit-stdin-other-sources-family` foram esse espelhamento: gate por substring (rodada 4), operandos de arquivo lidos como código e prefixos não seguidos (5), gate por token literal e grafias de alias (6), valores posicionais e `GIT_CONFIG_*` exportado (7, ainda abertos).

### Divergências medidas (sondas em Python, nada executado, HEAD `46ae3a7`)

Todas passam hoje (flags vazias); a análise principal resolve cada forma (com `git push` no lugar do fifo, as duas primeiras dão `git_push`), só a passada de fatos não.

| # | Forma | Por que diverge |
|---|---|---|
| D1 | `f() { $1 -c 'mk""fifo p'; }; f sh; bash < p` | valores posicionais da chamada (bug aberto) |
| D2 | `export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.x GIT_CONFIG_VALUE_0='!mk""fifo p'; git x; bash < p` | `GIT_CONFIG_*` só lido das atribuições do próprio comando (bug aberto) |
| D3 | `mkfifo p; { exec 3<&0; } < p; bash <&3` | o stdin de entrada do `exec` vem da caminhada sem contexto, que não vê o fifo |
| D4 | `e=exec; $e -- 3< <(x); bash <&3` | `_bare_exec` decide sobre a cabeça crua, sem as variantes de valor |
| D5 | `f() { $1 /dev/fd; }; f cd; echo x \| source 0` | `moved` também ignora os valores posicionais |
| D6 | `{ bash; } <<E` / `mkfifo p` / `E` / `bash < p` | corpo de heredoc de composto fica fora da passada e da regra de menção |
| D7 | `mkfifo p; bash -c 'mv p q'; bash < q` e `mkfifo p; eval 'mv p q'; bash < q` | a regra "mover um fifo" só vale no texto de cima |

Mais duas lacunas, que esta spec fecha por decisão do usuário (decisões 1 e 2): `cd /dev/fd; echo x | eval 'source 0'` e `cd /dev/fd; echo x | bash -c 'source 0'` passam (o contexto que desce não leva `moved`); `sudo ln -s /dev/fd d; echo x | bash d/0` e `timeout 5 ln -s /dev/fd d; ...` passam (`ln` atrás de wrapper).

### Decisões que esta spec herda e não muda

Do [Adendo 2026-11-18 (2) da spec audit-shell-lexer](../audit-shell-lexer/spec.md#adendo-2026-11-18-2---stdin-de-outras-fontes-código-aninhado-traps-exec-fifos-aliases-e-leitores) e do [log](../audit-shell-lexer/log.md) (Addendum 2026-11-18 (2) e anteriores): o estado do stdin como motivo (`None`, `piped_shell`, `dynamic_code`); código aninhado herda o estado do site, corpo de heredoc não; `trap` (EXIT com o estado de quem define unido ao fim do texto, outros sinais `dynamic_code`, EXIT em função `dynamic_code`); `exec` puro vale para todo site posterior (sobre-aproximação) e `exec` em texto aninhado do mesmo shell é `dynamic_code`; fifo de nome ilegível faz todo arquivo lido por shell bloquear; `moved` falha fechado em texto aninhado ilegível ou dinâmico (`source $f`); cabeça glob sob estado ativo bloqueia; leitores e `_OTHER_SHELLS`; X7. A lista completa de falsos positivos e limitações aceitos está em Design 9 e é fixada por teste antes de qualquer mudança (Task 1).

## Design

### 1. Visão geral

```
antes:  parse -> sites sem contexto -> PASSADA DE FATOS (resolução própria) -> resolver -> sites com contexto -> classificação
depois: parse -> [rodada k: contextos a partir dos fatos assumidos -> sites com contexto -> classificação que OBSERVA fatos]
                 repete enquanto observados ∪ assumidos != assumidos, no máximo MAX_FACT_ROUNDS
```

O fato passa a ser um subproduto da leitura que já classifica: o `mkfifo` que conta é o que a classificação viu como programa numa leitura final (depois de valores, variantes, aliases, posicionais); o `cd` idem; o texto aninhado que conta é o que a classificação analisou, e os fatos dele chegam pelo retorno de `_analyze`.

### 2. Os fatos

`Facts` (novo, `agent_audit_shell.py`, imutável, `__slots__`):

| Campo | Tipo | Significado | Sobe para o pai |
|---|---|---|---|
| `fifos` | `frozenset[str]` | nomes normalizados (`normalize_name`) de fifos criados | sempre (um fifo criado por um filho existe para o pai) |
| `fifo_unknown` | `bool` | algum fifo de nome ilegível: todo arquivo pode ser um | sempre |
| `moved` | `bool` | o texto muda de diretório ou cria links | só de texto do mesmo shell (`_SAME`) e de corpo de função (`_BODY`) |

Métodos: `join(other) -> Facts` (união; `fifo_unknown`/`moved` por `or`), `for_parent(kind) -> Facts` (`_CHILD` zera `moved`), `__eq__`/`__hash__` por campos, `__bool__`. Constantes de módulo: `NO_FACTS = Facts()` e `UNKNOWN_FACTS = Facts(frozenset(), True, True)` (instâncias de classe, aceitas por BIO11).

Os **descritores do `exec`** não sobem: são locais ao texto (um `exec` em texto aninhado do mesmo shell continua `dynamic_code` pela decisão herdada; o de um filho só vale no filho). Por texto, cada rodada guarda a lista de `exec` puros observados, `ExecSeen(start, end, redirects, incoming)` (namedtuple no classificador), com `incoming = PIPED` para estágio > 0, senão `site.stdin` da caminhada da própria rodada. O estado do ponto fixo de um texto é `(Facts, chave dos exec)`, chave = `tuple((start, incoming) ...)` em ordem de `start`.

`StdinContext` mantém `fds`, `fifos` (`Fifos`), `moved`, `end` e a API atual (os testes de `StdinNames` usam `Fifos()` e `StdinContext(...)` diretamente). Ganha `facts() -> Facts` (o que o contexto sabe de fifos e `moved`) e o construtor de classe `StdinContext.of(fds, facts, end=None)`, que monta o `Fifos` a partir de `facts`. `Fifos` continua mutável só durante a construção (`of`); nenhum código o muta depois.

### 3. Observação na análise principal

**Por leitura final** (`_Run.reading`, depois de `head_variants`, `_arg_variants` e `_git_alias_variants`; `tokens`/`words` já resolvidos), método novo `_Run.observe_reading(site, tokens, words, readings)`:

| Regra | Hoje (passada) | Depois |
|---|---|---|
| criador de fifo | `_fifo_operands` na cabeça simples (`_plain_head`) das palavras cruas, mais `head_readings` | `_fifo_operands` na cabeça simples de **cada leitura resolvida**; nome de valor (palavra `None`), expansão ou glob -> `fifo_unknown`. Criador em outro início da leitura (atrás de wrapper: `sudo mkfifo p`, `xargs mkfifo`) -> `fifo_unknown` (os operandos podem vir de fora: `xargs`) |
| muda diretório | `head in _CHANGING_HEADS` na cabeça simples crua | `_program_name(tokens[s]) in _CHANGING_HEADS` em **todo início** `s` de cada leitura resolvida (decisão 2) |
| move fifo | `head in _MOVING_HEADS` na cabeça simples crua | idem, em todo início (decisão 2) |
| `exec` puro | `_bare_exec` nas palavras cruas | `_bare_exec(site, tokens, words)` (a mesma lógica de opções `--`, `-a NOME`, `-c`, `-l`, `command`/`builtin`, operandos que podem sumir) sobre **cada leitura resolvida**: `e=exec; $e -- 3< <(x)` passa a contar |
| código de conteúdo desconhecido | `_site_code_facts`: `CodeArg(None, "dynamic_code")` e config do git ilegível (`more`/`unreadable`) -> `fifos.unknown`, e `moved` se a cabeça é carregador do mesmo shell | o mesmo, no ponto em que a classificação decide: `code_arguments` com `CodeArg(None, "dynamic_code")` (inclusive o operando de `source`/`.` sob estado ativo, que hoje faz `source $f` marcar `moved`) e `variant` com `dynamic_code` vindo de `_git_alias_variants` -> `fifo_unknown`; `moved` quando a cabeça está em `_SAME_SHELL_LOADERS`. Um operando de arquivo comum (`source ./env.sh`) segue sem fato |

**Por site** (`_Run.simple`, uma vez por site, depois das leituras):

- **Menção** (regra herdada, sem mudança): nenhuma leitura do site foi criadora de fifo e `_mentions_fifo_maker(site, tokens)` (tokens, alvos de redirecionamento, corpos de heredoc) -> `fifo_unknown`.
- **Cabeça que fica expansão** (o mesmo predicado com que `simple` chama `function_call(..., True)`: `head_unresolved`, ou cabeça dinâmica/glob sem `/` literal fora de variante): no texto de cima (`depth == 0`), a regra de hoje, `_bare_program(text)` (o texto sem as expansões que podem sumir) em `mkfifo`/`mknod` -> `fifo_unknown`, em `_CHANGING_HEADS` -> `moved`; em texto aninhado (`depth > 0`), como `_nested_facts` faz hoje: `fifo_unknown` e, se o texto é `_SAME` ou `_BODY`, `moved`. A expressão regular dessa regra é a que o run de pré-requisito separa de `_EXPANSION` (nome sugerido no bug: `_STRIPPABLE_EXPANSION`); esta spec reusa o nome que o fix escolher e não toca `_EXPANSION` nem `_head_is_dynamic` (decisão 5).
- `exec` de cabeça dinâmica de uma palavra com redirecionamentos (`$cmd < <(x)`, falso positivo aceito) -> `ExecSeen`, como hoje.

**No fim da rodada**: `moving and (assumidos ∪ observados).fifos` -> `fifo_unknown` (regra herdada, agora também em texto aninhado, o que fecha D7).

**Textos aninhados.** Todo `_code_text` devolve os fatos do texto analisado, já filtrados por `for_parent(kind)`, e quem chamou os junta em `self.observed`. O tipo vem de quem roda o texto:

| Quem chama `_code_text` | Texto | `kind` |
|---|---|---|
| `code_arguments` com cabeça em `_SAME_SHELL_LOADERS` (`eval`, `source`, `.`, `trap`, `mapfile`/`readarray -C`, `emulate -c`) | string de código | `_SAME` |
| `code_arguments`, outras cabeças (shells `-c`, `su -c`, `env -S`, `sudo -s`, `watch`, `mise exec -c`, `parallel`, `at`, nvim, git `-x`/`--exec`...) | string de código | `_CHILD` |
| `variant` (`alias_code`: alias `!` e chaves de config que rodam código) | código do git | `_CHILD` |
| `forwarded_calls` (corpo de função com os argumentos substituídos) | corpo | `_BODY` (roda neste shell) |
| `_heredoc_code` | corpo de heredoc / here-string | `_SAME` quando `same_shell` (carregador ou cabeça desconhecida), senão `_CHILD` |
| `compound_heredocs` | corpo em composto | `_SAME` (sobre-aproximação: o composto pode conter um carregador) |
| `zsh_hooks` (`functions[NOME]=CORPO` de função implícita) | corpo | `_SAME` |

O parâmetro `same_shell`/`_same` de hoje vira `kind`. Os bloqueios que hoje dependem de `_same` (função definida em string de carregador; `exec` aninhado que muda descritores) valem para `kind == _SAME` como hoje; `_BODY` não os dispara (o corpo já está no texto de cima, que o caminha).

**Falhas**: texto aninhado que não parseia, passa do orçamento ou do aninhamento do parser devolve `UNKNOWN_FACTS` (hoje `_nested_facts` faz `fifos.unknown = True` e `moved = moved or same`; o filtro por `kind` reproduz isso). Texto além de `MAX_CODE_DEPTH` (o atalho `nested_shell_depth` de `_code_text`) devolve `NO_FACTS`, como hoje (o texto já é nível B). `command_too_long` em texto aninhado devolve `UNKNOWN_FACTS`.

**Contexto que desce**: `_stdin_context`, `trap_stdin` e `zsh_hooks` passam a montar o contexto com `StdinContext.of(fds, ctx.facts())`, isto é, com `moved` além dos fifos (decisão 1). Com isso o bloqueio aninhado "`_same and moved and not _stdin.moved and ...`" fica sem efeito na rodada que converge (o pai já sabe do `moved` pelo retorno) e sai na Task 6.

### 4. O ponto fixo

```python
def _analyze(command, depth=0, env=None, budget=None, code=False, cwd=None, fn=None, kind=_CHILD, stdin=None):
    # comprimento, orçamento, parse: falhas -> (_level_b(motivo) ou too_long, UNKNOWN_FACTS)
    text = _Text(command, depth, env, budget, code, script, cwd, fn, kind)   # uma vez por texto
    assumed = stdin.facts() if stdin is not None else shell.NO_FACTS
    execs = ()
    for n in range(MAX_FACT_ROUNDS):
        if n and not text.charge(TEXT_COST + len(command)):                  # rodada extra custa como um texto
            return _level_b("analysis_budget"), shell.UNKNOWN_FACTS
        run = _Run(text, assumed, execs, stdin)
        analysis = run.classify()
        facts = assumed.join(run.observed)
        if facts == assumed and run.exec_key() == _exec_key(execs):
            return analysis, facts
        assumed, execs = facts, run.execs
    return _level_b("analysis_budget"), shell.UNKNOWN_FACTS                   # sem convergir: falha fechado
```

- **Rodada 1** assume só o que o contexto herdado traz (fifos e `moved` do pai, descritores do pai). Texto sem nenhum fato (a maioria) converge na rodada 1: custo igual ao de hoje menos a passada removida.
- **Convergência.** Hoje a observação não depende dos fatos assumidos: os textos aninhados analisados, as leituras resolvidas e os `exec` puros vêm das palavras, dos valores e das funções, nunca de um `StdinContext` (as funções que leem contexto, `_site_stdin`, `_path_code`, `_stdin_code`, `function_call`, `trap_stdin`, só bloqueiam ou devolvem `CodeArg(None, ...)`). Então a rodada 2 confirma o que a 1 achou e o ponto fixo fecha em no máximo 2 rodadas. O `incoming` de um `exec` vem da caminhada da rodada e pode mudar de uma rodada para a outra (D3); a chave dos `exec` entra na comparação, e o teto cobre qualquer oscilação. `MAX_FACT_ROUNDS = 3` deixa uma rodada de folga para uma dependência futura; no teto, nível B `analysis_budget` (decisão 4).
- **O que é calculado uma vez por texto** (`_Text`, compartilhado pelas rodadas): árvore, valores (`_values`, `_views`), funções e vereditos (`function_verdicts`, cobrados uma vez), funções que repassam argumentos e seus spans, `_fn_spans`, memo de prefixos (`steps`), leituras por comando (`tokens`, `_token_readings`, por `id(cmd)`), `_code_evaluation`, `_heredocs_disqualified`, `_rebound_spans`, `_grouped_commands`, a leitura dos aliases do repo (`repo_aliases`) e um memo de `_git_external_exists` por nome (as duas únicas chamadas que passam pelos `RESOLVERS` do hook e fazem I/O: nunca repetidas por rodada), `cwd_moved` (confiança na leitura do repo, outro conceito, sem mudança).
- **Bloqueios de texto** decididos nessas computações únicas (funções implícitas que leem código, função definida em string de carregador, `_code_evaluation`, orçamento esgotado dentro de `function_verdicts`) ficam em `_Text.blocks` e entram no resultado de toda rodada. Sem isso, a rodada 2 perderia um bloqueio que só a rodada 1 registrou.
- **Por rodada** (`_Run`): contextos (`_contexts(assumed, execs, stdin)`, o atual `_stdin_resolver` sem o parâmetro `sites`, recebendo os `ExecSeen`), uma caminhada `iter_sites(script, initial, resolve)` (sempre com `resolve`; sem `exec` ele devolve sempre o mesmo contexto), `categories`, `flags`, `reasons`, `raws`, `forwarded`, `in_fwd`, os observados e o bloqueio "`exec` aninhado do mesmo shell que muda descritores" (lê o resolvedor da rodada).
- **Fatos devolvidos ao pai**: os convergidos (`facts`, herdados incluídos); a união no pai é idempotente.
- **Sem memo de análises aninhadas entre rodadas**: uma rodada 2 refaz as análises aninhadas (com o contexto novo elas convergem numa rodada). O custo fica limitado pelo teto e pelo orçamento compartilhado (seção 6); um memo por chave estrutural de `env`/contexto fica como otimização futura (Trade-offs).

### 5. Contratos

| Item | Hoje | Depois |
|---|---|---|
| `analyze_command` | `(command, _depth=0, _env=None, _budget=None, _code=False, cwd=None, _cwd=None, _fn=None, _same=False, _stdin=None) -> Analysis` | `(command, _depth=0, _budget=None, cwd=None) -> Analysis` = `_analyze(command, _depth, None, _budget, False, cwd)[0]`. O hook (`_classify_in`), `classify_command`, os mocks `lambda command, _depth=0` e os testes com `_budget=` continuam valendo |
| `Analysis` | namedtuple `categories flags uncertainty` | igual (três campos; testes constroem `Analysis([...], [], [])`). Fatos não viram campo público: o hook não precisa deles |
| `_analyze` | - | novo, interno: `(command, depth, env, budget, code, cwd, fn, kind, stdin) -> tuple[Analysis, shell.Facts]` |
| `_code_text` | `(text, categories, flags, reasons, _depth, budget, code=False, env=None, fn=None, same_shell=False, stdin=None) -> None` | `(text, categories, flags, reasons, depth, budget, code=False, env=None, fn=None, kind=_CHILD, stdin=None) -> shell.Facts` (filtrado por `for_parent(kind)`) |
| `_heredoc_code` | `-> None` | `-> shell.Facts` (união dos corpos) |
| `_Run.code_text` | `(text, env, code=True, named=True, same_shell=False, stdin=None)` | `(text, env, code=True, named=True, kind=_CHILD, stdin=None)`; junta os fatos em `self.observed` |
| `_Run` | estado da chamada inteira | estado da rodada; `_Text` novo com o estado do texto |
| `StdinContext` | `(fds, fifos, moved, end)` | igual, mais `facts()` e `of(fds, facts, end=None)` |
| `Facts`, `NO_FACTS`, `UNKNOWN_FACTS` | - | novos em `agent_audit_shell.py` |
| `Site` | `cmd ... stdin ctx` | mais `given` (Task 7) |
| `_kind` | - | constantes `_CHILD = "child"`, `_SAME = "same"`, `_BODY = "body"` no classificador |
| `MAX_FACT_ROUNDS` | - | `3` no classificador |
| Removidos | | `_stdin_facts`, `_nested_facts`, `_site_code_facts`, `_CODE_PROGRAMS`, `_changes_directory`, `_stdin_resolver` (vira `_contexts`), `_Run.resolved`, `_Run.head_readings`, `_Run.compound_procsub_stdin` (Task 7), o bloqueio aninhado de `moved` em `analyze_command`. Ficam e passam a ser usados pela observação: `_plain_head`, `_fifo_operands`, `_bare_exec`, `_mentions_fifo_maker`, `_CHANGING_HEADS`, `_MOVING_HEADS` |

### 6. Custo linear

- **Rodadas.** 1 para texto sem fatos; 2 para texto com fatos (no nível de cima, um `cd x && pytest` comum paga 2 rodadas, cerca de +0,3 ms na mediana de 0,37 ms; o custo do processo do hook é dominado pela partida do Python, cerca de 70 ms). Em texto aninhado, a rodada 2 do pai desce os fatos e o filho converge numa rodada; o pior caso teórico é `MAX_FACT_ROUNDS` por nível (`MAX_CODE_DEPTH` = 3), mas o orçamento corta antes.
- **Orçamento.** Toda rodada extra cobra `TEXT_COST + len(command)` do `Budget` compartilhado (`MAX_LEX_CHARS`), como um texto novo; a árvore não é reparseada. Assim o trabalho total continua limitado pelo orçamento, que falha fechado (`analysis_budget`). A passada removida também cobrava `TEXT_COST` por string de código; o total de cargas fica parecido. `test_every_text_and_every_value_combination_is_charged` segue valendo (textos sem fatos, uma rodada).
- **Guardas existentes** (sem edição): `test_the_wrapper_search_stays_linear` (conta `_flag_step`), `test_l2_a_long_chain_of_names_is_linear`, os testes de tempo de `ReviewFixB1`, `test_a_function_called_in_a_long_pipe_list_is_analyzed_in_linear_time`, `test_nested_code_exec_and_procsub_texts_are_analyzed_in_linear_time`, `test_fifo_and_named_descriptor_texts_are_analyzed_in_linear_time`, todos abaixo de 1,0 s de CPU. Medido em HEAD (melhor de 3, carga 0,8): `echo x | { eval 'echo y | cat'; }` x400 156 ms; `{ :; } < <(x)` x400 54 ms; `exec 3< <(x)` x400 47 ms; `mkfifo pN; bash < pN` x400 62 ms; `exec {fd}< <(x)` x400 48 ms; função em lista de pipes 60 ms.
- **Guardas novas** (Testing): fatos que só aparecem em texto aninhado repetidos (`eval 'mkfifo pN'; bash < pN` x200), três níveis (`bash -c 'eval "mkfifo pN"'; bash < pN` x100), chamadas repassadas até `MAX_CODE_ARGS`, 400 `cd /dev/fd; echo x | bash 0`, 400 `exec` com fifo; cada uma abaixo de 1,0 s de CPU e com no máximo 2 rodadas no nível de cima.

### 7. Pureza dos módulos

`Facts` e `StdinContext.of` usam só `frozenset` e `__slots__`: `agent_audit_shell.py` segue importando só `re` e `__future__` (BIO11), sem estado mutável de módulo (`NO_FACTS`/`UNKNOWN_FACTS` são instâncias imutáveis). `agent_audit_classify.py` segue com `re`, `functools`, `collections`, `__future__` e o parser (BIO12); `ExecSeen` é `collections.namedtuple`. Nenhum import novo, nenhuma I/O nova; as duas leituras pelos `RESOLVERS` passam a acontecer no máximo uma vez por análise (antes, uma vez por `_Run`, e só o texto de cima lê o repo: `cwd=False` em texto aninhado).

### 8. `compound_procsub_stdin` unificado com o walker (Task 7)

Hoje o walker já dá ao corpo de um composto o estado dos seus redirecionamentos (`fd_state(cmd.redirects, fed, ctx)`), e `compound_procsub_stdin` refaz o trabalho: percorre `iter_compounds`, procura `<(...)` nos alvos e roda `_compound_reads_code` sobre o corpo inteiro (um `iter_sites` por composto). Os dois cobrem `{ bash; } < <(x)`; só o segundo cobre corpo com `eval`, `xargs`, `at`, função do texto, cabeça dinâmica ou leitura incompleta, e também os falsos positivos aceitos `{ bash <<< x; } < <(y)` e `f() { bash; } < <(x)` sem chamada.

Novo:

- `_walk` recebe `given` (como `in_compound`). Num `Compound` (inclusive definição de função, cujos redirecionamentos valem a cada chamada), `own = fd_states(cmd.redirects, None, ctx)`; `given_here = DYNAMIC` quando `DYNAMIC in own.values()` (decisão 3 (b)): todo `DYNAMIC` que os redirecionamentos do próprio composto produzem, seja `<(...)` no alvo, seja `<&3` ou `/dev/fd/3` de um `exec` de procsub. Tudo o que é caminhado dentro dos corpos (sites, substituições, compostos internos, corpos de função) recebe `given = given or given_here`. `PIPED` vindo de fifo fica fora: pipe segue a regra por site do Adendo 2026-11-16 (2).
- `Site.given` (slot novo).
- Predicado por site `_site_reads_code(words, readings, functions)`: o laço interno de `_compound_reads_code` (leitura incompleta, cabeça em `_STDIN_CODE_READERS`, shell versionado, função do texto, cabeça dinâmica). `_compound_reads_code` passa a usá-lo (segue servindo `function_verdicts` e `compound_heredocs`).
- Em `_Run.simple`: `site.given and _site_reads_code(...)` -> `block(site.given)`. Ignora os redirecionamentos do próprio site, como hoje, então `{ bash <<< x; } < <(y)` segue bloqueado (falso positivo aceito).
- Sai `_Run.compound_procsub_stdin` e o gate `"<(" in command`.

### 9. O que não muda

- **Níveis, motivos e config**: níveis A e B, o conjunto de motivos (o teto usa `analysis_budget`, que já existe), `agent-audit.json`, `agent-metrics.py`.
- **Falsos positivos aceitos** (seguem bloqueados): `ls | while read f; do bash "$f"; done`; shell que lê arquivo comum num texto que menciona `mkfifo` de forma não resolvida (por exemplo `mkfifo "$n"; bash x.sh`); `echo x | bash ~user/x`; `$cmd < <(x)`; a sobre-aproximação de `trap` (sinal que não é EXIT), `exec` (todo site posterior) e `xargs`; `fish -c`, `csh -c`, `tcsh -c`; `cmd | bash < script.sh`; `cmd | while read l; do sh; done < list`; `{ bash <<< x; } < <(y)`; `f() { eval "$1"; }; echo x | f a`; nome redefinido; `command`/`sudo`/`env`/`timeout f` sob pipe; `f() { bash; } < <(x)` sem chamada; `f() { cat; }; g() { f; }; echo x | g`; `echo x | $UNKNOWN` com função que lê código; `eval 'x=$(f() { :; }; f)'`.
- **Limitações aceitas** (seguem como estão): fifo criado fora do texto (`exec 3<> p; bash <&3` sem `mkfifo` passa); interpretadores estrangeiros (`python3 -`, `perl`, `node -`, X7); `source $f` marca `moved` para o texto inteiro; função de chamada anterior não resolvida; função definida em `bash -c` ou corpo de heredoc vista só no filho.
- A limitação "a passada de fatos duplica a resolução da passada principal" deixa de existir.

### 10. Mudanças de comportamento pretendidas (aprovadas pelo usuário em 2026-11-18)

| Forma | Hoje | Depois |
|---|---|---|
| D1-D7 (Background) | passa | `unclassified_command` (`piped_shell` ou `dynamic_code`) |
| `cd /dev/fd; echo x \| eval 'source 0'`, `... \| bash -c 'source 0'` | passa | bloqueado (decisão 1) |
| `sudo ln -s /dev/fd d; echo x \| bash d/0`, `timeout 5 ln ...` | passa | bloqueado (decisão 2) |
| `mkfifo p; sudo mv p q; bash < q` | bloqueado só pela regra de menção, se houver | bloqueado também pela regra "mover fifo" em todo início (decisão 2) |
| `env cd x; echo y \| bash z.sh`, `sudo cd x; ...` (não mudam nada de verdade) | passa | bloqueado: sobre-aproximação aceita, só sob estado ativo com operando relativo (decisão 2) |
| `echo x \| eval 'cd /dev/fd'` sem leitura depois | bloqueado (`dynamic_code`, bloqueio aninhado) | passa: nada lê o stdin depois, e o pai aplica `moved` ao que vier (decisão 1) |
| `echo x \| eval 'cd /dev/fd; source 0'` | `dynamic_code` + `piped_shell` | `piped_shell` (segue bloqueado) |
| `exec 3< <(x); { eval y; } <&3` | passa | `dynamic_code`, falso positivo aceito da mesma classe de `{ bash <<< x; } < <(y)` (decisão 3) |
| `eval '$s p'` com `s=mkfifo` conhecido, depois `bash x.sh` | bloqueado (cabeça aninhada dinâmica = desconhecido) | passa: o valor resolve o nome `p` |

### 11. Risco do hook ao vivo e ordem segura

`~/.claude/hooks/agent_audit_classify.py` e `agent_audit_shell.py` são os arquivos deste repo (link): um módulo que não importa faz o hook negar todo Bash com `classifier_error` (log da audit-shell-lexer, Task 2: "the live hook's mid-edit state denied every Bash call"). Regras para cada task:

1. **Adicionar, trocar, apagar.** Código novo entra como funções e classes inteiras, cada Edit deixando o módulo importável e o comportamento igual (nada as chama ainda); a troca de caminho é um Edit pequeno e único; a remoção vem depois, uma função sem referências por Edit. As Tasks 3 e 4 não mudam nenhum resultado; a Task 5 é a única que muda resultados de stdin; a Task 6 só apaga código morto.
2. **Só Edit/Write** nos módulos do hook; nunca heredoc de Bash, `sed -i` ou script que reescreve o arquivo.
3. **Se um Bash voltar com `classifier_error`**: não repetir o Bash; corrigir o último Edit com Edit (Edit e Write não dependem do classificador) e só então rodar a checagem estreita.
4. **Checagem por task**: os três módulos parseiam (`python3 -I -B -c "import ast,sys; [ast.parse(open(p).read()) for p in sys.argv[1:]]" ...`), suite estreita da task verde, e um Bash comum da sessão não é negado.
5. **Erro em tempo de execução** numa forma rara: `analyze_command` levanta, o hook nega com `classifier_error` (falha fechado); os testes de propriedade e o replay pegam antes do fim.
6. **Válvula**: `"mode": "audit"` em `agent-audit.json` (só registra) segue disponível ao usuário; nenhuma task a usa.

### 12. Segurança, observabilidade e rollout

- **Segurança**: nenhuma forma sai de bloqueada para limpa, exceto as da seção 10, aprovadas pelo usuário. Sondas e testes só chamam funções Python; nenhum payload é executado em shell real (incidente da revisão de segurança de 2026-11-14). Os testes montam as formas bloqueadas por pedaços (`"mk" + "fifo"`), como os módulos atuais.
- **Observabilidade**: sem métrica, campo de registro ou log novo; o teto aparece como `analysis_budget` nas métricas de nível B que já existem.
- **Rollout**: sem flag. Cada task é um commit revertível sozinho; reverter a Task 5 volta à passada antiga (que só sai na Task 6).

## Alternatives considered

| Critério | A. Ponto fixo sobre a análise inteira (escolhida) | B. Decisões de stdin adiadas (uma passada simbólica) | C. Manter a passada, compartilhando helpers | D. Modo "só fatos" da mesma análise (sempre 2 passadas) | E. A + rastreio de fatos consultados |
|---|---|---|---|---|---|
| Correção | uma resolução: o fato vem da leitura que classifica | uma resolução, mas cada leitor de contexto vira "registrar e avaliar depois"; um leitor que esquecer de adiar lê contexto incompleto e falha aberto em silêncio | duas travessias que precisam visitar os mesmos textos; cada recurso novo de resolução precisa de espelho | uma resolução, mas o modo pula caminhos (convite a divergência) | como A |
| Simplicidade | um laço em volta da análise; a passada (cerca de 250 linhas) sai | divide cerca de 15 funções (`_site_stdin`, `_path_code`, `_stdin_code`, `_shell_code`, `_at_code`, `_parallel_code`, `function_call`, `trap_stdin`, `fd_states`, `exec_fds`...) e o mapa de `exec` em ordem depende de efeitos pendentes | a mais barata agora, a mais cara a cada rodada | flag de modo espalhada | rastreio de consultas que precisa subir pelo aninhamento junto com os fatos |
| Robustez | teto + orçamento falham fechado; teste de propriedade aninhado = inline | depende de disciplina em cada leitor | as 7 rodadas mostram o resultado | média | como A, com mais estado |
| Custo | 1 rodada sem fatos, 2 com fatos | linear por construção | 1 passada + a passada de fatos | 2 passadas para todo comando | evita a rodada 2 quando nenhum site leu o fato que mudou |
| Manutenção | regra nova de stdin só precisa ler o contexto; os fatos vêm sozinhos | toda regra nova precisa saber adiar | toda resolução nova precisa de espelho | toda regra nova precisa saber em que modo roda | como A |

**F. Pré-varredura sintática no parser** (o desenho antes da rodada 4): não resolve valores nem aliases; para falhar fechado teria de tratar toda expansão como desconhecida, bloqueando a maior parte dos textos com variável. Rejeitada.

**Escolha: A.** É a única que elimina a classe de bug (dois resolvedores) sem criar outra (leitor que esquece de adiar, modo que pula caminho). O custo extra é uma rodada só para textos com fatos, medido em décimos de milissegundo frente a um processo de cerca de 70 ms. E fica como otimização futura, se o replay mostrar necessidade.

## Trade-offs

- **Ganha**: uma resolução para fatos e classificação; as sete divergências medidas fecham por construção, e as próximas formas de resolução (valores, aliases, wrappers) valem para os fatos sem código novo; cerca de 250 linhas a menos; `compound_procsub_stdin` deixa de reler a árvore.
- **Cede**: texto com fatos roda a classificação duas vezes (resultado da rodada 1 descartado); o orçamento passa a cobrar as rodadas, então um texto enorme com fatos chega antes ao `analysis_budget` (16 KB com fatos cobram cerca de 32 KB de `MAX_LEX_CHARS` = 128 KB, mais os aninhados); o contrato interno de `_code_text` e `_Run` muda (as tasks mudam todos os chamadores juntos).
- **Sem memo entre rodadas**: refazer as análises aninhadas na rodada 2 é mais simples e sem risco de chave incompleta; o memo (chave estrutural de `env` e contexto) e a opção E ficam para depois, se o replay pedir.
- **Mudanças de resultado da seção 10**: fecham falsos negativos e abrem duas classes pequenas de falso positivo (decisões 2 e 3), aceitas pelo usuário em 2026-11-18.

## Testing

Suite `claude-hooks` (tabela `Test suites` do `CLAUDE.md` da raiz): `python3 -I -B -m unittest discover -s .claude/hooks/tests -t .claude/hooks`; estreita por módulo com `-p 'test_<módulo>.py'`. Os testes existentes (1101 em `46ae3a7`, mais os que o run de pré-requisito acrescentar; o total de partida é o da suite depois dele) ficam verdes **sem edição** (inclusive `StdinOtherSources`, `StdinOtherSourcesRound2` a `Round7`, `PipeReceivers`, `PipedStdin`, `StdinNames`, as guardas de linearidade, BIO11 e BIO12). Nenhuma task lista `test_command_positions.py` em `Files`: se um teste existente precisar mudar, é uma scope request.

### `test_stdin_facts.py` (novo; `load_tests` devolve `ForkedSuite`; formas bloqueadas montadas por pedaços)

| Classe | Task | Casos |
|---|---|---|
| `AcceptedBehaviour` | 1 | cada falso positivo aceito da seção 9 bloqueado; cada limitação aceita no estado de hoje (`exec 3<> p; bash <&3` sem `mkfifo` limpo; `python3 - < p` limpo; `exec 3< <(x); source $f; bash < 3` bloqueado e `source $f; ls` limpo); comandos do dia a dia limpos (`cd x && pytest -k a`, `mkfifo p; echo hi > p &`, `eval cd /tmp; ls`, `f() { "$@"; }; f cd /tmp; ls`, `source "$HOME/.cargo/env"`, `bash -c 'make'`) |
| `ResolverReads` | 1 | com `RESOLVERS` falsos que contam: `git_aliases` chamado no máximo uma vez por análise de topo e `git_external` no máximo uma vez por nome, inclusive num texto com `cd` (duas rodadas a partir da Task 5) |
| `ObservedFacts` | 4 | `_analyze(text)[1]` para fifo literal, `mknod p p`, nome dinâmico (`fifo_unknown`), `cd`, `pushd`, `ln`, `mv` de fifo, `exec` puro (lista de `ExecSeen`), aninhado `_CHILD` (sem `moved`), `_SAME` e `_BODY` (com `moved`), falha de parse aninhada (`UNKNOWN_FACTS`), além de `MAX_CODE_DEPTH` (`NO_FACTS`) |
| `ObservedCoversTheFactsPass` | 4 (sai na 6) | diferencial: para o corpus (abaixo), os fatos observados contêm os da passada antiga (`_stdin_facts` chamado no mesmo texto); para D1-D7 a observação tem o fato que a passada não tem |
| `StdinFactsFromAnalysis` | 5 | D1-D7 bloqueados (com o motivo); decisão 1: `cd /dev/fd; echo x \| eval 'source 0'` e `cd /dev/fd; echo x \| bash -c 'source 0'` bloqueados, `echo x \| eval 'cd /dev/fd'` limpo, `echo x \| eval 'cd /dev/fd; source 0'` bloqueado com `piped_shell`; decisão 2: `sudo ln -s /dev/fd d; echo x \| bash d/0`, `timeout 5 ln -s /dev/fd d; echo x \| bash d/0` e `mkfifo p; sudo mv p q; bash < q` bloqueados, `sudo ln -s a b; ls` e `env cd x; ls` limpos (sem estado ativo), `sudo mkfifo p; bash x.sh` segue bloqueado (criador atrás de wrapper = desconhecido); seção 10, linha "valor resolve", limpa; fixed-point: a rodada final assume exatamente os fatos que observa (espião em `_Run`) |
| `FactRounds` | 5 | contagem de rodadas (espião em `_Run.classify`): 1 para texto sem fatos, no máximo 2 para todo o corpus e seus embrulhos; teto: com `MAX_FACT_ROUNDS = 1` e um texto de 2 rodadas, `analysis_budget`; observação forçada a crescer a cada rodada (`_Run.observe_reading` trocado por um que inventa um fifo novo) -> `analysis_budget`, nível B |
| `FactsLinearity` | 5 | as guardas novas da seção 6, cada uma abaixo de 1,0 s de CPU |
| `NestedEqualsInline` | 6 | propriedade: para cada texto interno X do corpus e cada embrulho W, `facts(W(X)) == facts(X).for_parent(kind(W))`. Embrulhos `_SAME`: `eval 'X'`, `source /dev/stdin <<'E'` + X, `trap 'X' EXIT`; `_CHILD`: `bash -c 'X'`, `sh -c`, `timeout 5 bash -c`, `su -c`, `git -c alias.x='!X' x`, `parallel ::: 'X'` (aspas com `_sh_quote`). Mais uma composição com semente fixa de 1 a 3 embrulhos sobre X sorteado (200 casos por fragmento, abaixo de 0,5 s cada, como `test_shell_properties.py`) |
| `RemovedFactsPass` | 6 | `classifier` não tem mais `_stdin_facts`, `_nested_facts`, `_site_code_facts`, `_CODE_PROGRAMS`, `_stdin_resolver`, `compound_procsub_stdin` (Task 7); guarda contra reintrodução |
| `CompoundGiven` | 7 | todos os casos de composto com `<(...)` de `PipeReceivers` repetidos por nome de regra; `{ eval y; } < <(x)`, `{ xargs sh; } < <(x)`, `{ f; } < <(x)` com função que lê código, `{ $c; } < <(x)` bloqueados; `{ cat; } 3< <(x)` limpo; decisão 3 (b): `exec 3< <(x); { eval y; } <&3` e `exec 3< <(x); { eval y; } < /dev/fd/3` bloqueados, `mkfifo p; { eval y; } < p` limpo (fifo é pipe, regra por site); `{ :; } < <(x)` x400 abaixo de 1,0 s |

**Corpus** (constante do módulo): os textos internos das sondas de `StdinOtherSources`, `Round2` a `Round7` e `StdinNames`, mais D1-D7: criadores de fifo em várias grafias (`mk""fifo p`, `mk\fifo p`, `mkn""od p p`, `mkfifo -m 600 p q`, `mkfifo -- p`, `command mkfifo p`, `s=mkfifo; $s p`, `${S:-mkfifo} p`), `cd`/`pushd`/`popd`/`ln -s`, `mkfifo p; mv p q`, alias e config do git (`-c`, `ALIAS.x`, `GIT_CONFIG_*` no comando e exportado), funções com posicionais, `exec` em todas as grafias, e textos sem fatos (`echo hi`, `ls`, `make`). Ficam fora da propriedade os textos cujos fatos dependem da profundidade (cabeça que fica expansão: regra do nível de cima diferente da aninhada), cobertos por `ObservedFacts`.

### `test_shell_lexer.py`

| Classe | Task | Casos |
|---|---|---|
| `FactsValue` | 2 | `join` (união, `or`), `for_parent(_CHILD)` zera `moved`, igualdade e hash por campos, `NO_FACTS` falso, `UNKNOWN_FACTS`; `StdinContext.of(fds, facts).fifos.match_text` e `.moved`; `ctx.facts()` ida e volta |
| `SiteGiven` | 7 | `Site.given` para corpo de `{ }`, `( )`, `while`, `if`, `case`, função, composto aninhado, substituição dentro do corpo; `None` para pipe, fifo e corpo sem redirecionamento; decisão 3 (b): `DYNAMIC` também para `{ :; } <&3` e `{ :; } < /dev/fd/3` depois de `exec 3< <(x)` (contexto com `fds = {3: DYNAMIC}`) |

### Regras -> testes

| Regra | Testes |
|---|---|
| R1 uma resolução: fatos só das leituras da classificação | `ObservedFacts`, `NestedEqualsInline`, `RemovedFactsPass`, `StdinFactsFromAnalysis` (D1-D7) |
| R2 ponto fixo: a rodada final assume o que observa | `StdinFactsFromAnalysis` (espião), `FactRounds` |
| R3 teto e falha fechada | `FactRounds` (teto, observação crescente), `ObservedFacts` (falha de parse aninhada) |
| R4 custo linear | guardas existentes sem edição, `FactsLinearity`, `FactRounds` (no máximo 2 rodadas) |
| R5 pureza, sem import novo | BIO11 `ShellModuleInvariant`, BIO12 `ClassifierModuleInvariant` (sem edição) |
| R6 aceitos não mudam | `AcceptedBehaviour`, as classes existentes da família stdin |
| R7 I/O dos resolvedores uma vez por análise | `ResolverReads` |
| R8 tipo de aninhamento decide o que sobe | `ObservedFacts`, `NestedEqualsInline` |
| R9 composto: estado do walker | `CompoundGiven`, `SiteGiven`, `PipeReceivers` (sem edição) |
| R10 contrato público igual | `test_hook_main.py`, `test_watchdog.py` (mocks de `analyze_command`), `test_classify.py` (`Analysis` de três campos), sem edição |

## Implementation order

### Task 1 - Testes que fixam o comportamento aceito e as leituras dos resolvedores

- **Stack:** backend-python
- **Files:** `.claude/hooks/tests/test_stdin_facts.py`
- **Depends on:** - (o run `fix-bug` do pré-requisito já entrou: a entrada `2026-11-18-audit-duplicate-expansion-regex-head-dynamic.md` está `Fixed`; se não estiver, o `/implement` para e avisa)
- **Done when:** `test_stdin_facts.py` existe com `load_tests` (`ForkedSuite`), `AcceptedBehaviour` e `ResolverReads` (Testing), todos verdes contra o HEAD de partida (depois do pré-requisito) sem mudar nenhum módulo do hook; suite estreita `-p 'test_stdin_facts.py'` verde; a suite inteira tem os testes do HEAD de partida + os novos.
- **Status:** pending

### Task 2 - Valor `Facts` e contexto montado a partir de fatos no parser

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent_audit_shell.py`, `.claude/hooks/tests/test_shell_lexer.py`
- **Depends on:** -
- **Done when:** `Facts`, `NO_FACTS`, `UNKNOWN_FACTS`, `StdinContext.facts()` e `StdinContext.of(...)` existem conforme Design 2; `Fifos`, `fd_states`, `exec_fds` e `StdinContext(...)` sem mudança de API; `FactsValue` verde; `StdinNames`, `PipedStdin` e BIO11 verdes sem edição; o classificador não muda; um Bash comum da sessão não é negado.
- **Status:** pending

### Task 3 - Estado por texto (`_Text`) separado do estado por rodada (`_Run`), sem mudança de resultado

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent_audit_classify.py`
- **Depends on:** Task 1
- **Done when:** `_Text` guarda o que Design 4 lista como "uma vez por texto", incluindo `blocks` e os memos de `repo_aliases` e `_git_external_exists`; `_Run` recebe um `_Text`; `analyze_command` ainda usa a passada de fatos; nenhum teste editado; a suite estreita de `test_command_positions.py`, `test_classify.py`, `test_uncertainty.py`, `test_heredoc.py` e `test_stdin_facts.py` verde; os três módulos parseiam.
- **Status:** pending

### Task 4 - Observação dos fatos e retorno interno `(Analysis, Facts)`, ainda sem uso

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent_audit_classify.py`, `.claude/hooks/tests/test_stdin_facts.py`
- **Depends on:** Task 2, Task 3
- **Done when:** `_analyze` existe e `analyze_command` delega a ele (assinatura pública de Design 5); `_code_text`, `_heredoc_code` e `_Run.code_text` devolvem ou juntam `Facts` filtrados por `kind` (`_CHILD`, `_SAME`, `_BODY`, tabela de Design 3); `_Run.observe_reading` e a observação por site e por fim de rodada preenchem `run.observed` e `run.execs`; os contextos ainda vêm da passada antiga, então nenhum resultado muda; `ObservedFacts` e `ObservedCoversTheFactsPass` verdes; os testes existentes verdes sem edição.
- **Status:** pending

### Task 5 - Ponto fixo com teto de rodadas; a passada antiga deixa de ser chamada

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent_audit_classify.py`, `.claude/hooks/tests/test_stdin_facts.py`
- **Depends on:** Task 4
- **Done when:** `_analyze` itera rodadas conforme Design 4 (`MAX_FACT_ROUNDS = 3`, cobrança por rodada extra, `analysis_budget` no teto), com contextos de `_contexts(assumed, execs, stdin)` e o contexto que desce (`_stdin_context`, `trap_stdin`, `zsh_hooks`) levando `moved` (decisão 1); `_CHANGING_HEADS` e `_MOVING_HEADS` observados em todo início de cada leitura resolvida (decisão 2); `StdinFactsFromAnalysis`, `FactRounds` e `FactsLinearity` verdes; D1-D7 e as linhas da seção 10 conforme a tabela; os testes existentes verdes sem edição; `analyze_command` não chama mais `_stdin_facts` (a função ainda existe só para o diferencial).
- **Status:** pending

### Task 6 - Remoção da passada de fatos duplicada e teste de propriedade

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent_audit_classify.py`, `.claude/hooks/tests/test_stdin_facts.py`
- **Depends on:** Task 5
- **Done when:** saem `_stdin_facts`, `_nested_facts`, `_site_code_facts`, `_CODE_PROGRAMS`, `_changes_directory`, `_stdin_resolver`, `_Run.resolved`, `_Run.head_readings` e o bloqueio aninhado de `moved` (decisão 1); a regra de cabeça que fica expansão usa a regex que o run de pré-requisito separou de `_EXPANSION`, sem renomear nem tocar `_EXPANSION` e `_head_is_dynamic` (decisão 5); `ObservedCoversTheFactsPass` sai; `NestedEqualsInline` e `RemovedFactsPass` verdes; nenhuma referência aos nomes removidos no módulo nem nos testes; docstrings de `_analyze`, `_Run` e `StdinContext` descrevem o ponto fixo; os testes existentes verdes sem edição.
- **Status:** pending

### Task 7 - `compound_procsub_stdin` unificado com o estado do walker (`Site.given`)

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent_audit_shell.py`, `.claude/hooks/agent_audit_classify.py`, `.claude/hooks/tests/test_shell_lexer.py`, `.claude/hooks/tests/test_stdin_facts.py`
- **Depends on:** Task 6
- **Done when:** `_walk` calcula `given` e `Site.given` existe conforme Design 8 (decisão 3 (b): todo `DYNAMIC` dos redirecionamentos do próprio composto); `_site_reads_code` é usado por `_compound_reads_code` e por `_Run.simple`; `_Run.compound_procsub_stdin` sai; `SiteGiven` e `CompoundGiven` verdes; `PipeReceivers` (inclusive `{ bash <<< x; } < <(y)` e `f() { bash; } < <(x)`), `StdinOtherSources*`, BIO11 e BIO12 verdes sem edição.
- **Status:** pending

## Verification

1. **Suite** `claude-hooks` pelo `test-runner`, 3 execuções (uma com `TMPDIR` sob um diretório `claude-*` do scratchpad, como nas runs anteriores): os testes do HEAD de partida (1101 em `46ae3a7`, mais os do run de pré-requisito) + os novos, todos verdes, sem skip, sem teste instável; tempo no máximo 0,5 s acima do HEAD na mesma máquina (hoje cerca de 12-13 s). Estreitas por task: `-p 'test_stdin_facts.py'`, `-p 'test_command_positions.py'`, `-p 'test_shell_lexer.py'`, `-p 'test_bounded_io.py'`.
2. **Sondas** (sessão principal, script Python no scratchpad, formas montadas por pedaços, nada executado em shell): D1-D7 e as formas da seção 10 por `analyze_command`, resultado conforme a tabela; as sondas de HEAD deste Background reproduzem os mesmos números de antes nas formas sem fatos.
3. **Replay** (sessão principal, scripts no scratchpad, como a seção 8 da spec audit-shell-lexer): corpus dos comandos Bash das transcrições locais (`~/.claude/projects/**/*.jsonl`) e dos `cmd` das métricas, HEAD contra a versão nova, decisão por `decide` com o `agent-audit.json` real. Esperado: toda diferença é uma linha da seção 10; nenhuma forma bloqueada vira limpa fora dela; contagem por motivo antes e depois; `analyze_command` com mediana e p99 no máximo 10% acima do HEAD; distribuição de rodadas (proporção de textos com 2 rodadas, nenhum no teto).
4. **Latência do processo**: PreToolUse de `pytest tests/test_a.py`, 50 execuções intercaladas HEAD e nova; mediana no máximo +3 ms (orçamento de processo decidido na audit-shell-lexer).
5. **Revisão**: `code-reviewer` e `security-reviewer` sobre o diff, com a regra de nunca executar payload (só funções Python, ou binários stub conferidos antes).
6. **Backlog** (fim do `/implement`, `backlog-keeper`): fechar `2026-11-18-audit-stdin-facts-pass-diverges.md`; fechar a parte coberta de `2026-11-18-audit-stdin-alias-fifo-movers-and-dotdot.md` (cabeças de `cd`/`ln` feitas por variável; `ln`/`mv` atrás dos wrappers seguidos), deixando abertos a ordem de `..` em `stdin_alias`, `cp -s`, `rsync`, `tar`, `find -exec mv` e nomes com `~` (decisão 6); a entrada de refactor passa a `Done` com o link desta spec.
7. **Checagens manuais do usuário** (nada visual): numa sessão nova do Claude Code, comandos comuns (`ls`, `git status`, um `pytest` estreito, um `cd x && ...`) sem negação `classifier_error`; `~/.claude/metrics` sem registros `classifier_error` novos depois de um dia de uso.

## Decisões do usuário (2026-11-18)

As seis perguntas da versão Draft, respondidas pelo usuário em 2026-11-18, junto com a aprovação da spec. O texto acima já está escrito com elas.

1. **`moved` desce para o código aninhado: (a).** `_stdin_context`, `trap_stdin` e `zsh_hooks` montam o contexto com `StdinContext.of(fds, ctx.facts())`. `cd /dev/fd; echo x | eval 'source 0'` e `| bash -c 'source 0'` passam a bloquear. O bloqueio aninhado de `moved` vira código morto e sai na Task 6. `echo x | eval 'cd /dev/fd'` sem leitura depois passa a limpo.
2. **`cd`/`ln` (`moved`) e `mv`/`ln`/`cp` de fifo valem em todo início de cada leitura resolvida: (a).** `sudo ln`, `timeout 5 ln` e `sudo mv p q` contam. `env cd x` e `sudo cd x` também contam: sobre-aproximação aceita, que só pesa sob estado ativo com operando relativo. Criador de fifo segue só na cabeça simples; atrás de wrapper ele é desconhecido (por causa de `xargs`).
3. **O composto dá ao corpo o estado do walker: (b).** `Site.given = DYNAMIC` para todo `DYNAMIC` que os redirecionamentos do próprio composto produzem (`<(...)`, ou `<&3` e `/dev/fd/3` de um `exec` de procsub). `exec 3< <(x); { eval y; } <&3` bloqueia: falso positivo aceito, da mesma classe de `{ bash <<< x; } < <(y)`.
4. **Teto: 3 rodadas, com `analysis_budget` no teto.** O conjunto de motivos não muda.
5. **`_EXPANSION` duplicado: (a), corrigido antes pelo `fix-bug`.** É uma regressão do commit `46ae3a7`, registrada em [2026-11-18-audit-duplicate-expansion-regex-head-dynamic.md](../../backlog/bugs/2026-11-18-audit-duplicate-expansion-regex-head-dynamic.md). O mesmo run corrige também os bugs de tabela [parallel-command-line](../../backlog/bugs/2026-11-18-audit-parallel-command-line-not-read-as-code.md), [fish-csh-option-scan](../../backlog/bugs/2026-11-18-audit-fish-csh-option-scan-stops-at-value.md) e [at-version-option-listing](../../backlog/bugs/2026-11-18-audit-at-version-option-listing.md). Ele entra antes da Task 1, e as tasks partem do código e da suite que ele deixar. Nenhuma task refaz essas correções, nem renomeia ou toca `_EXPANSION` e `_head_is_dynamic`. A regra de cabeça que fica expansão usa a regex que o fix separou.
6. **Bug de movers: sim.** No fim do `/implement`, o `backlog-keeper` fecha a parte de [stdin-alias-fifo-movers-and-dotdot](../../backlog/bugs/2026-11-18-audit-stdin-alias-fifo-movers-and-dotdot.md) que esta spec cobre: cabeças de `cd`/`ln` feitas por variável, e `ln`/`mv` atrás dos wrappers seguidos. Ficam abertos a ordem de `..` em `stdin_alias`, `cp -s`, `rsync`, `tar`, `find -exec mv` e nomes com `~` (Verification 6).

**Nota sobre a contagem da suite.** O `CLAUDE.md` da raiz já diz 1101 testes. A nota de docs desatualizada do relatório do specker (que dizia 951) não vale. No fim, o `docs-writer` só troca o número pelo total final.

## Open questions

Nenhuma em aberto.
