# audit-hook-hardening - o hook falha fechado na incerteza, com I/O limitado e um watchdog de processo

- **Date:** 2026-11-13
- **Status:** Implemented
- **Source:** [2026-11-13-audit-hook-hardening.md](../../backlog/refactor/2026-11-13-audit-hook-hardening.md) (refactor sem plan; não há `plan.md` nesta pasta). Junta também [bug heredoc sink](../../backlog/bugs/2026-11-13-audit-heredoc-sink-runs-sh.md), [timeout parsing limits](../../backlog/refactor/2026-11-13-audit-timeout-parsing-limits.md), [bug active_run non-object](../../backlog/bugs/2026-11-12-audit-active-run-non-object-state.md), [nvim depth cap category](../../backlog/refactor/2026-11-13-audit-nvim-depth-cap-category.md) e, em parte, [suite lenta](../../backlog/refactor/2026-11-13-hooks-tests-suite-slow.md) (ver Background, "O que entra e o que fica fora")
- **Implementation log:** [log.md](log.md) (criado pelo `/implement` na primeira task)

## Summary

As cinco rodadas de revisão de segurança da lua-agent acharam, cada uma, um caminho mais fundo pelo qual o hook `agent-audit` deixa passar um comando bloqueado: um regex quadrático que estoura os 10 s do hook, um parser de `timeout` que trunca leituras, um heredoc julgado como dado, um I/O que trava. Esta spec troca o remendo por forma por quatro garantias estruturais:

1. **Incerteza nunca vira allow.** Quando o parser sabe que não sabe (leituras ambíguas, limite de leituras, aninhamento além do limite, exceção no classificador, prefixo de heredoc não limpo), ele classifica pela leitura mais restritiva ou bloqueia com uma categoria própria, `unclassified_command`, e registra o motivo.
2. **Nenhum tempo do hook é ilimitado.** A análise roda num processo filho (`os.fork`) com prazo duro e `SIGKILL`; o pai, que não interpreta entrada não confiável, sempre responde a tempo.
3. **Todo arquivo lido ou escrito tem limite.** Config, run states e o arquivo de métricas são abertos sem bloquear, só se forem arquivos regulares, com teto de tamanho e de quantidade.
4. **Nada some em silêncio.** O registro do `PostToolUse` não se perde por lentidão na marcação do run, e um comando em que aparece um programa bloqueado sem que nenhuma regra o pegue fica registrado (`deny_token_unmatched`), para que as falhas restantes apareçam nas métricas.

| Camada | Arquivos | Mudança |
|---|---|---|
| Hook | `.claude/hooks/agent-audit.py` | `_read_bounded`, `_append_line`; `load_config`, `active_run` e a gravação do registro limitados; leituras de comando por conjunto de posições (`command_readings`), sem teto de profundidade; `analyze_command` com motivos de incerteza; profundidade do nvim e exceções viram `unclassified_command`; heredoc só é dado com prefixo limpo; watchdog por `fork` com protocolo de duas mensagens |
| Config | `.claude/hooks/agent-audit.json` | duas categorias: `unclassified_command: block`, `parse_uncertain: audit` (única mudança de config; `settings.json` intacto) |
| Métricas | `.claude/hooks/agent-metrics.py` | rótulos das duas categorias; seção "Parser uncertainty and hook health" (candidatos a falso positivo e a falso negativo) |
| Testes | `.claude/hooks/tests/` | módulos novos `test_bounded_io.py`, `test_uncertainty.py`, `test_watchdog.py`; casos novos em `test_heredoc.py`, `test_hook_main.py`, `test_hook_process.py`, `test_agent_metrics.py`, `test_config_contract.py`; testes que mudam listados em Testing; orçamento de tempo da suite |
| Docs (fim, `docs-writer`) | `.claude/README.md`, `.claude/agent-workflow.md` (13.1, 13.6, 13.8 nova, 14.2) | needs_docs |

Sem serviço, API, banco, feature flag nem migração.

## Background

### Modelo de ameaça

O hook é uma guarda de workflow para agents cooperativos que erram, não uma fronteira contra um adversário: um agent determinado sempre pode escrever um script com `Write` e rodá-lo, e uma lista de bloqueio nunca reconhece toda forma de shell. As revisões de segurança testam formas adversariais porque elas mostram onde o hook falha aberto. Esta spec fecha as falhas **causadas pelos limites do próprio hook** (tempo, exceção, truncamento, I/O, heurística de heredoc) e torna visíveis as que sobram. Formas que o parser não modela (cobertura) ficam para uma spec de lexer (Open questions 4).

### Classes de falha aberta hoje

Conferido no código atual (HEAD `5f73e6c`) e com sondas só de leitura (módulo carregado em processo; nenhuma edição):

| # | Classe | Evidência | Fecha com |
|---|---|---|---|
| F1 | Tempo: o hook passa dos 10 s e o Claude Code ignora o resultado | o `SIGALRM` de 7 s interrompe código Python e o motor `re` (o CPython checa sinais dentro do `_sre`: `test_a_regex_search_is_interrupted_too` passa), mas não uma chamada C única: um `json.loads` de 36 MB com alarme em 0,01 s só foi interrompido em 0,37 s, quando a chamada acabou. Uma syscall presa num sistema de arquivos travado (estado D) também não é interrompida | W1-W6, B1-B5 |
| F2 | Exceção no classificador do Bash | `classify_command` levantando `RecursionError` sai de `main()`, o `except` do `__main__` engole, exit 0 sem saída: **allow** (conferido) | U4, W3 |
| F3 | Truncamento de leituras | `timeout a timeout b timeout c timeout d docker restart x` -> `(['other'], [])`; com três `timeout` o mesmo comando dá `docker_lifecycle`. Causa: recursão de profundidade 3 e `out[:8]` em `strip_prefix_variants` | U1-U3 |
| F4 | Heredoc julgado como dado | `sh -s $(true) cat <<'EOF'` com `docker restart x` no corpo -> `(['other'], [])`; o `)` zera `seg_start` e o prefixo visto é só `cat`. `_is_data_sink` também lê só a primeira leitura de `strip_prefixes` | H1-H4 |
| F5 | Profundidade do nvim | quatro níveis de `nvim -c '!...'` falham fechado, mas com a negação de `docker_lifecycle` (mensagem e métrica erradas) | U3 |
| F6 | I/O sem limite | `active_run` lê todo `.claude/runs/*.json` sem teto (156 MB levaram 9,75 s na revisão); um `[]` lá levanta `AttributeError`; o arquivo de métricas e o `agent-audit.json` abrem sem `O_NONBLOCK` (um FIFO trava a gravação, e no config trava o hook antes de qualquer guarda) | B1-B5 |
| F7 | Registro perdido | quando a marcação do run (`git_root`, `active_run`) estoura o orçamento, o registro inteiro se perde, inclusive no `PostToolUse` | R1 |

A entrada base diz que o `SIGALRM` não interrompe "um regex catastrófico"; a medição mostra que o regex é interrompido e que o buraco real são chamadas C sobre entrada sem limite e syscalls presas. O desenho trata os dois.

### Dados de uso (métricas locais, só leitura)

4 sessões, 2896 registros, 1870 comandos Bash no `PostToolUse` (o `cmd` é truncado em 300 caracteres):

- heredocs: 374; prefixos mais comuns `python3 -` (278, corpo já classificado), `cat > <arquivo>` e `cat >> <arquivo>` (cerca de 40, sete deles com `$` no alvo do redirect: `cat > $SP/tools/run.sh`), `git commit -q ... -F -` (5). Só um heredoc tem `$(` na mesma linha.
- `timeout`: 39, todos com duração literal (`timeout 300 python3 ...`), fora as sondas do revisor.
- decisões: `git_commit` ask 22, `docker_lifecycle` block 7, `command_too_long` block 2, `git_push` ask 1; nenhum `analysis_timeout`.

Conclusão: as regras fail-closed abaixo não tocam o trabalho normal visto, exceto o heredoc com `$` no alvo do redirect, que H2 preserva de propósito.

### O que entra e o que fica fora

| Entrada | Decisão | Motivo |
|---|---|---|
| [audit-hook-hardening](../../backlog/refactor/2026-11-13-audit-hook-hardening.md) | **entra** (fonte) | métricas, run states, `SIGALRM`, registro perdido: B1-B5, W1-W6, R1 |
| [heredoc sink runs sh](../../backlog/bugs/2026-11-13-audit-heredoc-sink-runs-sh.md) | **entra** | a própria entrada base o coloca aqui; mesma causa estrutural (julgar dado com parse não confiável): H1-H4 |
| [timeout parsing limits](../../backlog/refactor/2026-11-13-audit-timeout-parsing-limits.md) | **entra** | o fail-open no teto de profundidade/variantes é F3; o caso de locale (`timeout 0,5`) já é coberto pela união de leituras e fica fixado por teste (UN14), sem parse por locale |
| [active_run non-object](../../backlog/bugs/2026-11-12-audit-active-run-non-object-state.md) | **entra** | `active_run` é reescrito por B2; o bug é uma linha da mesma função |
| [nvim depth cap category](../../backlog/refactor/2026-11-13-audit-nvim-depth-cap-category.md) | **entra** | é um caso da categoria `unclassified_command` (U3) |
| [hooks tests suite slow](../../backlog/refactor/2026-11-13-hooks-tests-suite-slow.md) | **entra em parte** | esta spec acrescenta testes de processo; a Task 6 mantém a suite no tempo de hoje (8,5 s) com o perfil e as acelerações que a entrada propõe. A meta de menos de 5 s fica aberta na entrada (Open questions 5) |
| [segment split quote-blind](../../backlog/refactor/2026-11-13-audit-segment-split-quote-blind.md) | fica fora | cobertura (o parser não modela aspas), não incerteza conhecida. Junto com as posições de comando achadas aqui (`out_of_scope_issues`), pede um lexer de shell: spec própria, sobre o `command_readings` desta |
| [strip_prefixes wrappers](../../backlog/refactor/2026-11-13-audit-strip-prefixes-wrappers.md) | fica fora | cobertura; com `_prefix_steps` (Design 3.2) cada wrapper vira uma linha de tabela, mas cada um precisa do parse dos próprios flags e de testes. Mesma spec do lexer |
| [nvim shell exec unclassified](../../backlog/refactor/2026-11-13-audit-nvim-shell-exec-unclassified.md) | fica fora | cobertura (funções Vimscript/Lua que rodam shell) |
| [interactive app guard](../../backlog/refactor/2026-11-13-audit-interactive-app-guard.md) | fica fora | decisão do usuário (2026-11-13): esperar os dados da métrica 14.2 |
| [bash writes unaudited](../../backlog/refactor/2026-11-13-audit-bash-writes-unaudited.md) | fica fora | outro controle (escrita via Bash), com decisão de produto pendente |
| [docs root declaration unprotected](../../backlog/refactor/2026-11-13-audit-docs-root-declaration-unprotected.md) | fica fora | confiança na fonte da política; decisão do usuário: próxima spec, com leitura do `HEAD` |
| [hook self-protection](../../backlog/bugs/2026-11-11-audit-hook-self-protection.md) | fica fora | permissões e uma categoria de escrita nos arquivos do hook; B1 só limita a **leitura** do config, sem mudar a semântica de config ausente ou inválido (modo `audit`) |

## Design

### 1. Regras

**Princípio.** Incerteza tem dois níveis. **Nível A** (as leituras possíveis são poucas e conhecidas): classificar todas e unir, de modo que a negação de qualquer leitura vale; registrar o motivo. **Nível B** (as leituras não podem ser enumeradas, ou a análise falhou): bloquear com `unclassified_command` e registrar o motivo. Nenhum caminho de incerteza termina em allow silencioso.

| # | Regra |
|---|---|
| U1 | Cada trecho (piece) é lido como um conjunto de inícios de comando, depois dos prefixos (`rtk`, `proxy`, `sudo`, `time`, `command`, `exec`, atribuições, `mise exec ... --`, `timeout ...`). Todas as leituras são classificadas e as categorias unidas; uma leitura alternativa nunca acrescenta `other` (inalterado). Mais de uma leitura: motivo `prefix_readings` (nível A) |
| U2 | As leituras são calculadas sobre posições de token, sem recursão e sem teto de profundidade. Mais de `MAX_READINGS` (8) inícios distintos num trecho: nível B, motivo `readings_cap`; o trecho não é classificado além disso |
| U3 | Texto de shell do nvim (`-c '!cmd'`) ainda presente na profundidade `NVIM_MAX_DEPTH` (3): nível B, motivo `nested_shell_depth`. Sai a negação reaproveitada de `docker_lifecycle` e a flag `nested_shell_unclassified` |
| U4 | Qualquer exceção na análise de uma ferramenta auditada (Bash, escritas, visuais): nível B, motivo `classifier_error`, e o registro guarda o nome da exceção em `error`. `evaluate_write` continua com o próprio fail-closed interno (inalterado) |
| U5 | `shlex` falha num trecho: duas listas de tokens, a do `split()` cru e a mesma sem os caracteres `'` e `"`; as leituras das duas são unidas. Motivo `shlex_fallback` (nível A) |
| U6 | Motivos de nível A acrescentam a flag `parse_uncertain` (categoria `audit`: registra, nunca decide). Nível B acrescenta a flag e a categoria de registro `unclassified_command` / `unclassified`. Todo registro com motivo tem o campo `uncertainty` (lista ordenada) |
| U7 | Canário: no texto cru de um trecho (já sem os corpos de heredoc que são dado, antes de tirar prefixos), um token `docker` ou `docker-compose` (com ou sem caminho) fora da posição 0, seguido depois por um verbo de ciclo de vida (`up`, `down`, `start`, `stop`, `restart`, `rm`, `kill`, `pull`, `create`, `run`, `exec`), ou um token `git` fora da posição 0 seguido depois por `push` ou `commit`, sem que o comando tenha a flag correspondente (`docker_lifecycle`, `git_push`, `git_commit`): motivo `deny_token_unmatched` (nível A). Os tokens vêm de dividir o texto em toda sequência de espaço em branco, aspas simples ou duplas, crase, parênteses, chaves, ponto e vírgula, `&`, barra vertical, `=` e `$` (um único split por classe de caracteres, linear), sem vazios, de modo que `bash -c "git push"`, `x=$(docker restart x)` e `true & docker restart x` expõem os dois tokens |
| H1 | No scanner de heredoc, `(` e `$(` empilham o `seg_start` do comando de fora, e o `)` que fecha restaura esse valor (hoje zera). O prefixo de um abridor é o comando simples inteiro, substituições incluídas |
| H2 | Um corpo de heredoc só é dado (removido) quando o prefixo é **limpo**: além das condições atuais de `_is_data_sink`, o prefixo dá exatamente uma leitura (U1), sem `readings_cap` nem `shlex_fallback`, e nenhum token até a cabeça, inclusive, tem `$`. Com cabeça `git` ou `gh`, nenhum token do prefixo tem `$`. Com cabeça `cat` ou `tee`, `$` depois da cabeça é aceito (alvo de redirect: `cat > $SP/x.sh`) |
| H3 | O texto de fora de um `$(cat <<EOF ...)` (valor de `git commit -m` ou de opção de mensagem do `gh`) segue H2, tokenizado sem as aspas `"` e os espaços do fim |
| H4 | Corpo mantido porque o prefixo não é limpo, mas alguma leitura tem cabeça `cat`, `tee`, `git` ou `gh`: motivo `heredoc_unclean_prefix` (nível A). Heredocs de `python3 -`, `bash` etc. não recebem motivo (o corpo já é código) |
| W1 | A análise (classificação e marcação do run) roda num filho criado por `os.fork`. O pai espera a mensagem de análise até o limite (`_analysis_limit()`, 7 s); estourou: `SIGKILL` no filho e `analysis_timeout` (PreToolUse nega, PostToolUse registra), como hoje |
| W2 | O filho termina sem mensagem válida (morte por sinal, `os._exit`, JSON inválido, mensagem acima de `MAX_CHILD_MESSAGE`): nível B, motivo `analysis_crash` |
| W3 | Exceção dentro do filho: o filho manda `{"error": "<nome>"}` e o pai aplica U4 |
| W4 | O pai imprime a decisão assim que a mensagem de análise chega, antes de esperar a marcação do run (mantém o "decisão antes do registro" da rodada 5) |
| W5 | Sem `os.fork`, ou `fork` falhando (`OSError`): a análise roda no processo, com o `SIGALRM` atual (`_arm_analysis_timer`), e as mesmas regras U4 e R1 |
| W6 | A saída padrão e o erro padrão do filho vão para `/dev/null`: só o pai escreve a decisão; o processo sai sempre com 0 e stderr vazio |
| B1 | `load_config` lê `agent-audit.json` por `_read_bounded`: `O_NONBLOCK`, só arquivo regular, até `MAX_CONFIG_BYTES` (64 KiB). Falha: `{"mode": "audit"}` (semântica atual) |
| B2 | `active_run` lista no máximo `MAX_RUN_ENTRIES` (256) entradas `*.json`, só arquivos regulares, do mais novo para o mais velho por mtime, e lê no máximo `MAX_RUN_READS` (16), cada uma até `MAX_RUN_STATE_BYTES` (256 KiB); acima disso o arquivo é ignorado. JSON que não é objeto é ignorado como JSON inválido (bug). Vence o mais novo com `phase != "done"` (mesmo resultado de hoje dentro dos limites) |
| B3 | O registro é gravado por `_append_line`: `os.open` com `O_WRONLY`, `O_APPEND`, `O_CREAT`, `O_NONBLOCK`, `O_NOFOLLOW` e `O_CLOEXEC`, modo `0600`, só arquivo regular (`fstat`), uma linha por `os.write`. FIFO, link simbólico, diretório ou erro: o registro é descartado em silêncio, nunca bloqueia |
| B4 | `project_docs_root` passa a usar `_read_bounded(..., truncate=True)`; comportamento idêntico (256 KiB, regras R10 da skills-docs-root) |
| B5 | Toda leitura e escrita de arquivo do hook passa por `_read_bounded` ou `_append_line` (o stdin do payload é a única exceção). Um teste estrutural (AST) garante isso |
| R1 | O registro só se perde quando a própria gravação falha (B3). Marcação do run que estoura o orçamento: o registro é gravado sem ela, com `in_run: false` e `run_tags: "timeout"` |
| C1 | `unclassified_command` é categoria `block` (negada para todo ator, sessão principal inclusive, como `analysis_timeout`), com `WHY`, `what_to_do` e rótulo próprios, e entra no piso F2 |
| C2 | `parse_uncertain` é categoria `audit`, com `WHY` e rótulo (F3 exige as mesmas chaves) |
| M1 | O relatório de métricas ganha a seção "Parser uncertainty and hook health": contagem por motivo, candidatos a falso positivo (decisões block/ask com motivo de nível A, e toda negação `unclassified_command`), candidatos a falso negativo (`deny_token_unmatched` sem decisão), `analysis_timeout` e `run_tags: "timeout"` |

### 2. I/O limitado (Task 1)

**Constantes**, ao lado de `MAX_HEREDOC_OPENERS`:

```python
MAX_CONFIG_BYTES = 65536
MAX_RUN_STATE_BYTES = 262144   # the largest run state seen is 7.2 KB
MAX_RUN_ENTRIES = 256
MAX_RUN_READS = 16
RECORD_FLOOR_S = 0.25          # minimum budget of the recording step (today a literal in main)
```

**`_read_bounded(path, limit, *, truncate=False) -> bytes | None`**: `os.open(path, O_RDONLY|O_NONBLOCK|O_CLOEXEC)` (segue link simbólico, como `project_docs_root` já faz), `fstat` exige `S_ISREG`, lê até `limit + 1` bytes; acima de `limit` devolve `None`, ou os primeiros `limit` com `truncate=True`. Qualquer erro: `None`. Nunca levanta. O `fstat` antes do `read` torna um arquivo esparso de 50 MB uma rejeição instantânea.

**`_append_line(path, line) -> bool`**: B3. `METRICS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)` continua antes (dentro do guarda da gravação). Escreve `line.encode()` num laço de `os.write` até o fim; devolve `False` em qualquer erro.

**`active_run(root)`**:

```python
def active_run(root: Path) -> dict | None:
    """Newest run state with phase != "done" (B2): at most MAX_RUN_ENTRIES entries listed, regular files only,
    newest first, at most MAX_RUN_READS read, each up to MAX_RUN_STATE_BYTES; invalid, oversized or non-object
    states are skipped."""
```

`os.scandir` com parada em `MAX_RUN_ENTRIES` entradas `*.json`; `entry.stat()` (segue link) para mtime e `S_ISREG`; ordena por mtime decrescente; lê por `_read_bounded`; `json.loads` só de bytes já limitados; `isinstance(data, dict)` antes de `.get`. Limite documentado: com 16 estados mais novos já terminados, um run ativo mais velho não é visto (o run ativo é o arquivo atualizado por último durante um `/implement`).

**Gravação do registro.** `_write_record(payload, record)` se divide em `_run_tags(payload) -> dict` (`git_root` + `active_run`: `in_run`, `run`, `task`) e `_write_record(record)` (só `_append_line`). Na Task 1 (caminho no processo), `main()` faz a marcação sob o orçamento restante (`max(RECORD_FLOOR_S, limite - decorrido)`); se estourar, `record["in_run"] = False`, `record["run_tags"] = "timeout"`, e a gravação roda em seguida sob um guarda curto próprio (`RECORD_FLOOR_S`). Registros de escrita já trazem `in_run` de `evaluate_write` e não fazem marcação (inalterado).

**Teste estrutural (B5).** Percorre a AST de `agent-audit.py` e falha se `open(`, `os.fdopen(`, `.read_text(`, `.read_bytes(`, `.read(`, `json.load(` ou `os.write(` aparecem fora de `_read_bounded`, `_append_line` e do `json.load(sys.stdin)` de `main`. Uma leitura nova sem limite quebra a suite com o nome da função.

### 3. Leituras e incerteza (Task 2)

#### 3.1 Tipos

```python
MAX_READINGS = 8
NVIM_MAX_DEPTH = 3

class Readings(NamedTuple):
    texts: list[str]          # normalized segments, primary first, deduplicated
    reasons: frozenset[str]   # "prefix_readings", "shlex_fallback", "readings_cap"
    complete: bool            # False when readings_cap was hit (texts is then empty)

class Analysis(NamedTuple):
    categories: list[str]
    flags: list[str]          # never contains "parse_uncertain" (added by main from `uncertainty`)
    uncertainty: list[str]    # sorted reasons
```

#### 3.2 `command_readings(segment) -> Readings`

Substitui `strip_prefixes` e `strip_prefix_variants` (nenhum teste as referencia; `_finish_strip` fica igual).

1. Tokens por `shlex.split(segment, posix=True)`; em `ValueError`, duas listas (U5) e motivo `shlex_fallback`.
2. Para cada lista, `_command_starts(tokens)`: busca sobre posições. `_prefix_steps(tokens, p)` devolve as próximas posições quando `tokens[p]` é prefixo, ou `[]` quando `p` é um início de comando:

| `tokens[p]` | próximas posições |
|---|---|
| atribuição (`ENV_ASSIGN`), `rtk`, `proxy`, `sudo`, `time`, `command`, `exec` | `[p + 1]` |
| `mise` com `exec`/`x` e `--` depois dos flags globais | `[índice depois do --]` |
| `timeout` | `[p + L for L in _timeout_prefix_lengths(tokens, p)]` |
| qualquer outro, ou `p >= len(tokens)` | `[]` (início de comando) |

   Posições visitadas não se repetem, então o custo é linear no número de tokens. A busca para assim que acha `MAX_READINGS + 1` inícios: `complete = False`, motivo `readings_cap`.
3. Leitura primária: a cadeia que segue sempre o primeiro passo de cada posição (mesma ordem de `lengths[0]` de hoje). As demais vêm em ordem crescente de posição. `texts = [_finish_strip(tokens[f:]) ...]`, sem repetição.
4. Mais de um texto: motivo `prefix_readings`.

`_timeout_prefix_lengths(tokens, start=0)` e `_timeout_duration_index(tokens, start=0)` ganham o deslocamento, sem copiar a lista (evita custo quadrático com milhares de `timeout`). As regras de parse do GNU `timeout` não mudam.

#### 3.3 `analyze_command(command, _depth=0) -> Analysis`

O corpo atual de `classify_command`, com:

- `MAX_COMMAND_LEN` checado primeiro (inalterado);
- `_strip_heredocs(command) -> tuple[str, frozenset[str]]` no lugar de `strip_heredoc_bodies` (o fallback de exceção do scanner é o mesmo e `strip_heredoc_bodies` vira o envoltório de uma linha que devolve só o texto);
- por trecho, `command_readings(raw)`; incompleto: categoria `unclassified`, flag `unclassified_command`, nada mais classificado nesse trecho;
- `_nvim_nested` devolve também os motivos do nível de baixo; na profundidade `NVIM_MAX_DEPTH` com texto de shell: `unclassified` / `unclassified_command`, motivo `nested_shell_depth` (U3);
- U7 por trecho, depois da classificação de todos os trechos (a flag correspondente pode vir de outro trecho do mesmo comando), sobre os tokens do texto cru do trecho.

`classify_command(command, _depth=0)` passa a ser `a = analyze_command(...); return a.categories, a.flags`: as 206 linhas de tabela atuais de `test_classify.py` continuam valendo, salvo as que esta spec muda de propósito (Testing).

#### 3.4 `main()`

O bloco de análise ganha `except Exception as exc` ao lado do `except AnalysisTimeout`: `categories = ["unclassified"]`, `flags = ["unclassified_command"]`, `uncertainty = ["classifier_error"]`, `record["error"] = type(exc).__name__` (U4). Depois da análise, `uncertainty` não vazio vai para o registro, e motivos de nível A acrescentam `parse_uncertain` às flags (U6).

#### 3.5 Categoria e textos

`agent-audit.json`: `"unclassified_command": "block"`, `"parse_uncertain": "audit"`.

| Chave | Texto |
|---|---|
| `WHY["unclassified_command"]` | `the hook could not classify this command with certainty (too many possible readings, shell text nested too deep, or an analysis error), so it is blocked and never run` |
| `what_to_do("unclassified_command")` | `Run each program as its own short command, without stacked wrappers (timeout, sudo, mise exec) or nested shells, and write large content to a file with the Write tool.` (vale para todo ator, como `analysis_timeout`) |
| `WHY["parse_uncertain"]` | `the command had more than one plausible reading; every reading was classified and the strictest one applies` (nunca exibido: `audit` não decide) |
| `FLAG_LABELS["unclassified_command"]` | `commands the hook could not classify with certainty, denied (readings cap, nested shell depth, analysis error or crash) - see the uncertainty field (target 0)` |
| `FLAG_LABELS["parse_uncertain"]` | `commands classified under parse uncertainty (several readings, shlex fallback, unclean heredoc prefix, deny token outside a classified command) - review in Parser uncertainty` |

`TEST_CONFIG` ganha as duas; o piso F2 ganha `unclassified_command`.

### 4. Heredoc com prefixo limpo (Task 3)

**H1, em `_scan_heredocs`.** As entradas da pilha de contexto passam a `(kind, outer, saved_seg_start)`. Ao abrir `(` ou `$(` (fora e dentro de aspas duplas) empilha o `seg_start` atual; no `)` que fecha, desempilha e restaura `seg_start = saved_seg_start` em vez de `len(out) + 1`. O resto do scanner (separadores, comentários, aritmética, `_UNMODELED`, `MAX_HEREDOC_OPENERS`, cache por `seg_start`) não muda. Efeito: em `sh -s $(true) cat <<EOF` o prefixo é `sh -s $(true) cat`, e o `_CODE_FEED` (`$(`) já recusa o sink.

**H2-H4, em `_is_data_sink(prefix, rest, outer, depth, reasons=None)`.** O cálculo de cabeça e tokens passa por

```python
def _clean_sink_tokens(prefix: str, *, any_dollar: bool = False) -> list[str] | None:
    """Tokens of the single clean reading of a heredoc prefix, or None (H2): exactly one reading, complete, no
    shlex fallback, and no `$` in the tokens up to the head (in any token when `any_dollar`)."""
```

- cabeça `git`/`gh`: `_clean_sink_tokens(prefix, any_dollar=True)`;
- cabeça `cat`/`tee`: `_clean_sink_tokens(prefix)`;
- texto de fora (H3): `_clean_sink_tokens(outer.rstrip().rstrip('"').rstrip(), any_dollar=True)`, e os regexes `_GIT_MESSAGE_VALUE` / `_GH_MESSAGE_VALUE` aplicados ao texto da leitura;
- `None` com alguma leitura de cabeça `cat`/`tee`/`git`/`gh`: `reasons.add("heredoc_unclean_prefix")` e `False`.

`_scan_heredocs` recebe o conjunto `reasons` e o repassa; `_strip_heredocs` devolve esse conjunto.

**Comportamento resultante** (corpo `docker restart x`, salvo indicação):

| Comando | Hoje | Depois |
|---|---|---|
| `sh -s $(true) cat <<'EOF'` | corpo removido, allow | corpo classificado: `docker_lifecycle` |
| `x=$(true) cat <<EOF` | removido | classificado (`$(` no prefixo) |
| `(sh -s) cat <<EOF` | removido | classificado (cabeça `(sh`) |
| `timeout -s KILL "$T" cat <<EOF` | classificado | classificado, motivo `heredoc_unclean_prefix` |
| `timeout 5 cat <<EOF` | removido | removido (uma leitura) |
| `$X cat <<EOF`, `A=$B cat <<EOF` | classificado / removido | classificado |
| `cat > $SP/tools/run.sh <<EOF` (corpo `docker compose up`) | removido | removido (`$` depois da cabeça) |
| `git $X commit -F - <<EOF` | removido | classificado |
| `git commit -m "$(cat <<'EOF' ...)"` | removido | removido |
| `python3 - <<EOF` | classificado | classificado, sem motivo |

### 5. Watchdog por processo (Task 4)

**Protocolo.** O pai lê o payload e o config (como hoje), decide se a ferramenta é auditada e então:

```
pai                                   filho (os.fork)
 |  pipe r/w, sys.stdout.flush()       |  fecha r; stdout/stderr -> /dev/null (W6)
 |                                     |  analysis = _analysis(payload, event, actor)   (U4: exceção -> {"error": nome})
 |  <- linha 1: {"analysis": {...}}    |  escreve a linha 1
 |  decide(); imprime e dá flush (W4)  |  tags = _run_tags(payload), só se o registro precisar
 |  <- linha 2: {"tags": {...}}        |  escreve a linha 2; os._exit(0) em qualquer caminho
 |  SIGKILL no filho, waitpid(WNOHANG) |
 |  _write_record(record) sob RECORD_FLOOR_S
```

- **Leitura** com `select` e prazo absoluto: linha 1 até `started + limite`; linha 2 até `max(RECORD_FLOOR_S, limite - decorrido)`. Lê no máximo `MAX_CHILD_MESSAGE` (1 MiB) por linha; `json.loads` só de bytes já limitados (B5 conta esse `json.loads` como leitura limitada; não há `open`).
- **Linha 1 ausente no prazo**: `SIGKILL`, `analysis_timeout` (W1). **EOF sem linha 1, linha inválida ou grande demais**: `analysis_crash` (W2). **`{"error": ...}`**: U4 (W3).
- **Linha 2**: só esperada quando haverá registro (PostToolUse, PostToolUseFailure, Subagent*, ou PreToolUse com decisão block/ask). Ausente no prazo: R1. Num PreToolUse sem decisão ou com warn, o pai mata o filho sem esperar a marcação (latência igual à da análise).
- **Filho**: só roda `_analysis` e `_run_tags`; nunca imprime, nunca volta para quem chamou `main()` (um `try/finally` termina em `os._exit(0)`), o que mantém o `unittest` intacto quando `call_main` roda no processo dos testes.
- **Pai**: depois do `fork`, só `select`, `os.read`, `json.loads` de bytes limitados, `decide`, `print` e `_append_line`. O pai não interpreta o comando.
- **Fallback (W5)**: `_fork_available()` é `hasattr(os, "fork")`; `os.fork()` com `OSError` também cai no caminho no processo da Task 1, com o `SIGALRM`.
- **Zumbis e órfãos**: o pai sempre manda `SIGKILL` ao filho antes de sair, e faz um `waitpid(pid, WNOHANG)`; um filho preso em estado D é recolhido pelo init quando o pai sai.

**`_analysis(payload, event, actor) -> dict`**: o corpo atual do bloco de classificação de `main()` (Bash, escritas, visuais), devolvendo `categories`, `flags`, `uncertainty`, `cmd` e os campos de `evaluate_write`. Os dois caminhos (filho e fallback) chamam a mesma função, de modo que as regras U e H valem igualmente.

**Latência medida** nesta máquina (Python 3.14, 4 núcleos): processo do hook inteiro, mediana 74 ms (mínimo 66); `classify_command` no processo 0,065 ms; a mesma análise via `fork` + pipe + `waitpid` 1,8 ms. O custo do watchdog é cerca de 2,4% do tempo do hook, só nas ferramentas auditadas.

### 6. Métricas e falsos positivos (Task 5)

**Relatório** (`agent-metrics.py`), seção nova depois de "Enforcement decisions", contando registros `PostToolUse*` mais `PreToolUse` com decisão block/ask (cada ação conta uma vez):

| Linha | Conteúdo |
|---|---|
| tabela por motivo | `reason`, registros, quantos negados/perguntados, até 3 exemplos (`ator: cmd[:60]`) |
| False-positive candidates | decisões block/ask com motivo de nível A (a negação pode ter vindo de uma leitura alternativa ou de um corpo mantido) e toda negação `unclassified_command` |
| False-negative candidates | registros com `deny_token_unmatched` e sem decisão |
| Hook health | contagem de `analysis_timeout`, `analysis_crash`, `classifier_error` e de `run_tags: "timeout"` |

Sem nenhum motivo no período: a seção diz "None.".

**Medição e ajuste** (vai para `agent-workflow.md` 14.2 pelo `docs-writer`):

1. Antes do merge, a sessão principal reexecuta os comandos Bash das métricas locais nas duas versões do classificador (Verification, item 4); cada diferença é uma mudança pretendida ou um defeito da task.
2. Depois do merge, após cerca de uma semana nas duas máquinas: `agent-metrics.py --since <data do merge> --merge`, seção "Parser uncertainty and hook health".
3. Cada candidato a falso positivo é trabalho legítimo bloqueado? Então a correção é uma regra de parse precisa para aquela forma (teste primeiro, entrada no backlog pelo `backlog-keeper`), nunca tirar o fail-closed nem subir um teto às cegas. `MAX_READINGS` e `NVIM_MAX_DEPTH` são constantes fixadas por teste.
4. Cada candidato a falso negativo é uma forma que escapou: vira entrada para a spec do lexer.
5. Metas: zero negação de trabalho normal; `analysis_timeout`, `analysis_crash` e `classifier_error` em zero.
6. Válvula de emergência: se uma regra bloquear trabalho normal antes da correção, o usuário pode pôr `"mode": "audit"` no config (a suite acusa no F2, de propósito) ou reverter a task.

### 7. Segurança, privacidade e observabilidade

- **Fail-closed tem custo**: um defeito no classificador passa a negar todo Bash em vez de deixar passar. É o efeito pretendido (o defeito aparece na hora, com `error` no registro) e a válvula do item 6.6 existe.
- **Pai mínimo**: a superfície que ainda falha aberto é o código do pai (parse do payload, config, `decide`, `print`), pequeno e coberto por testes; payload inválido continua silencioso (P1, P2).
- **`O_NOFOLLOW` nas métricas**: um link simbólico plantado em `~/.claude/metrics/<sessão>.jsonl` não redireciona a gravação. O diretório em si pode ser um link (escolha do usuário).
- **Privacidade**: campos novos `uncertainty`, `error` (nome da exceção, nunca a mensagem) e `run_tags`. Nenhum conteúdo de comando além do `cmd[:300]` atual.
- **Observabilidade**: M1. O hook não tem request id; a chave de correlação é `session` + `ts`, como hoje.

### 8. Rollout e reversão

Sem feature flag: `~/.claude/hooks` aponta para `.claude/hooks/`, então cada task vale na chamada seguinte ao merge. A ordem das tasks mantém cada estado intermediário seguro: I/O primeiro (só reduz travamentos), depois classificação, heredoc, watchdog, métricas, tempo da suite. Reversão: `git revert` dos commits da task; o único estado é o config (duas chaves acrescentadas, que podem ficar sem efeito se o código for revertido, porque categorias sem flag não fazem nada).

## Alternatives considered

### Tratamento da incerteza

| Opção | Corretude e robustez | Simplicidade e manutenção | Decisão |
|---|---|---|---|
| **Dois níveis: união de leituras (A) e bloqueio dedicado quando não dá para enumerar (B)** | nenhuma incerteza vira allow; `timeout "$T" pytest x` continua permitido | um princípio, uma categoria, motivos no registro | **escolhida** |
| Bloquear toda ambiguidade | também fecha | nega `timeout "$T" pytest tests/a_test.py` e todo `shlex` que falha por divisão sem aspas (`echo "a; b"`): falso positivo em trabalho normal | rejeitada |
| Reusar `docker_lifecycle` (hoje no nvim) | fecha | mensagem errada ("never start containers") e métrica misturada; é a entrada nvim-depth-cap | rejeitada |
| Reusar `analysis_timeout` para os tetos | fecha | mistura "lento" com "estruturalmente incerto"; a métrica deixa de separar as causas | rejeitada |
| Lista de permissão de cabeças de comando | fecharia a cobertura | nega todo programa fora da lista: inviável em projetos variados | rejeitada |

### Leituras do prefixo

| Opção | Por que |
|---|---|
| **Conjunto de posições, sem recursão, teto só em inícios distintos (U2)** (escolhida) | cada posição é visitada uma vez; leituras repetidas colapsam; o teto só é atingido por cadeias adversariais |
| Subir os tetos (profundidade 3, 8 variantes) | continua truncando; só muda o número da próxima sonda |
| Laço iterativo que mantém só a primeira leitura | perde as leituras alternativas e reabre `timeout -s KILL "$T" docker restart x` (LR13) |

### Guarda de tempo

| Opção | Latência | Cobre | Decisão |
|---|---|---|---|
| **`fork` com prazo duro (W1-W6) + I/O limitado** | +1,8 ms medidos (cerca de 2,4%) | código Python, `re`, chamadas C longas, syscalls presas em estado D, morte do processo de análise (sinal, falta de memória) | **escolhida** (Open questions 2) |
| `SIGALRM` + I/O limitado, sem `fork` | zero | código Python, `re`, e chamadas C cujo tempo fica limitado porque toda entrada é limitada (invariante B5) | alternativa; residual: syscall presa, chamada C futura sobre entrada não prevista, crash do interpretador |
| Reexecutar a análise com `subprocess` | +~70 ms (um interpretador novo por chamada) | tudo | rejeitada: dobra o tempo do hook |
| Orçamento explícito de passos no regex | zero | só regex | rejeitada: o `re` da biblioteca padrão não tem orçamento (exigiria o pacote `regex`, e o hook é só stdlib), e o regex já é interrompível |

### Heredoc

| Opção | Por que |
|---|---|
| **Prefixo limpo (H1-H4)** (escolhida) | regra única: só se remove um corpo quando o parse do prefixo é inequívoco; preserva os sinks vistos nas métricas |
| Só corrigir o `seg_start` | fecha a forma da entrada e deixa o ângulo das leituras (`strip_prefixes` só com a primeira) |
| Nunca remover corpo | nega todo `cat > script.sh <<EOF` cujo corpo cite um comando bloqueado; a regra 13.6 existe justamente para isso |
| Recusar `$` em qualquer token, inclusive depois de `cat` | nega `cat > $SP/tools/run.sh <<EOF`, forma vista sete vezes nas métricas |

### Run state inválido

| Opção | Por que |
|---|---|
| **Ignorar, como JSON inválido (B2)** (escolhida) | é o comportamento esperado do bug; as flags que dependem do run são `warn` |
| Tratar como run ativo sem escopo | um arquivo solto em `.claude/runs/` sinalizaria toda escrita de implementer no repo |

### Canário de falso negativo (U7)

| Opção | Por que |
|---|---|
| **Motivo `audit` quando um programa bloqueado aparece fora da cabeça** (escolhida) | torna visível a forma que escapou, sem negar nada; alimenta a spec do lexer |
| Sem canário | as falhas de cobertura continuam silenciosas até a próxima revisão |
| Negar quando o canário dispara | `grep -r "docker restart" .` e `echo` seriam negados |

## Trade-offs

- **Defeito do hook bloqueia o Bash** (U4, W2): troca um allow silencioso por uma negação visível. Mitigação: válvula do item 6.6 e testes de fuzz já existentes sem exceção.
- **1,8 ms por chamada auditada** pelo `fork` (Open questions 2).
- **Corpos mantidos a mais** (H1-H3): `x=$(true) cat <<EOF`, `git $X commit -F -`, `gh ... --title "$T" -F -` passam a ter o corpo classificado; um corpo que cite `docker compose up` é negado. Raro nas métricas (um heredoc com `$(` em 374); o motivo `heredoc_unclean_prefix` mostra cada caso.
- **Canário barulhento**: `echo "docker restart x"` e `grep` geram `deny_token_unmatched`. Só registro; a lista de candidatos é para revisão humana.
- **Limite de 16 leituras de run state**: um run ativo mais velho que 16 runs terminados não é visto (documentado e fixado por teste).
- **Suite**: a meta de menos de 5 s não volta nesta spec (Open questions 5).
- **Cobertura não muda**: `true & docker restart x`, `(docker restart x)`, `sudo -u u docker restart x` e afins continuam `other`; passam a ser registrados pelo canário. A correção é a spec do lexer.

## Testing

Suite: `claude-hooks` (tabela `Test suites` do `CLAUDE.md` da raiz; hoje 317 testes em 8,5 s). Comandos com `docker` e `git` aparecem só como strings. "pre"/"post" = saída e registro de `call_main` com `TEST_CONFIG`; "proc" = `HookProcess` (cópia privada do hook, `TIMEOUT = 10`, o mesmo do `settings.json`); todo caso "proc" também verifica exit 0 e stderr vazio. Classes e testes novos citam esta spec na docstring. Testes de processo com prazo usam `AGENT_AUDIT_ANALYSIS_TIMEOUT=0.3`.

Para os casos "proc" que precisam de uma falha dentro da análise (exceção, crash, chamada C longa), `HookProcess` ganha `patch_source(old, new)`: troca um trecho que aparece exatamente uma vez na **cópia privada** do hook (falha se aparecer zero ou várias vezes). O hook versionado nunca muda.

### Testes que mudam

| Teste | Mudança |
|---|---|
| `test_classify.py` `test_nesting_deeper_than_the_cap_fails_closed` (LR12) | espera `unclassified_command` em flags, `unclassified` em categorias, e **nem** `docker_lifecycle` **nem** `nested_shell_unclassified`; `analyze_command(...).uncertainty == ["nested_shell_depth"]` |
| `test_hook_main.py` `DecisionBeforeRecording.test_slow_recording_cannot_delay_or_lose_the_decision` | o registro deixa de se perder: um registro com `in_run: false` e `run_tags: "timeout"` (R1) |
| `DecisionBeforeRecording.test_decision_is_already_on_stdout_when_the_recording_starts` | roda com `_fork_available` falso (o espião de `git_root` vive no processo); caso equivalente do caminho com `fork` em WD7 |
| `AnalysisLimitAndArming` (3 testes) | rodam com `_fork_available` falso (o `setitimer` só arma a análise no fallback) |
| `test_config_contract.py` F2 | piso inclui `unclassified_command` |
| `_support.py` `TEST_CONFIG` | `unclassified_command: block`, `parse_uncertain: audit` |

Nenhuma outra expectativa de tabela muda: `classify_command` mantém o formato e não inclui `parse_uncertain`.

### `test_bounded_io.py` (novo, Task 1)

| # | Caso | Esperado |
|---|---|---|
| BIO1 | `_read_bounded`: arquivo regular abaixo do limite; acima (estrito e `truncate=True`); FIFO sem escritor; diretório; ausente; link para regular; link para FIFO; `os.devnull` | bytes; `None` e os primeiros `limit`; `None` em menos de 0,5 s; `None`; `None`; bytes; `None`; `None`. Nunca levanta |
| BIO2 | `load_config` com `CONFIG_PATH` (patch) num FIFO, num arquivo de 64 KiB + 1, num JSON válido | `{"mode": "audit"}` em menos de 0,5 s; `{"mode": "audit"}`; o config |
| BIO3 | `active_run` com `[]`, `"x"`, `3`, `null` (mais novos) e um run válido; só os não objetos; e `evaluate_write` de `backend-node` em `README.md` com um `[]` ao lado do run válido | o válido; `None`; flags com `docs_write_by_implementer`, `area: code` (bug: hoje cai no fallback, `area: outside`) |
| BIO4 | `active_run` com um `.json` esparso de 50 MB (`os.truncate`) mais novo e um válido | o válido, em menos de 0,5 s |
| BIO5 | `active_run` com um FIFO `x.json` e um diretório `y.json` | ignorados, em menos de 0,5 s |
| BIO6 | `active_run` com 300 arquivos (`MAX_RUN_ENTRIES` + 44), espião em `_read_bounded`; e 16 estados `done` mais novos que um ativo | retorna, com no máximo 16 leituras; `None` (limite documentado) |
| BIO7 | `_append_line`: arquivo novo; arquivo existente; FIFO sem leitor no lugar; link simbólico para outro arquivo; diretório | linha gravada, modo `0600`; acrescentada; `False` em menos de 0,5 s; `False` e o alvo do link intacto; `False` |
| BIO8 | `call_main`, caminho no processo: `git_root` dorme 30 s, `ANALYSIS_TIMEOUT_S = 0.05`; post de Bash; pre de `docker compose up` | registro com `in_run: false`, `run_tags: "timeout"`; deny impresso e o mesmo registro; menos de 2 s |
| BIO9 | estrutural (B5): AST de `agent-audit.py` | nenhuma chamada de arquivo fora de `_read_bounded`, `_append_line` e do stdin de `main` |
| BIO10 | `project_docs_root` | os casos R10 atuais passam sem mudança (inalterado) |

### `test_uncertainty.py` (novo, Task 2; casos HS8 na Task 3)

| # | Caso | Esperado |
|---|---|---|
| UN1 | `command_readings`: `timeout 5 x`; `timeout "$T" x`; `timeout -s KILL "$T" docker restart x`; `rtk proxy sudo x` | uma leitura, sem motivo; `["$T x", "x"]`, `prefix_readings`; inclui `docker restart x`; `["x"]` |
| UN2 | `"timeout a " * k + "docker restart x"` para k = 4, 5, 7; o mesmo com `git push` | `docker_lifecycle` (hoje `other` para k >= 4); `git_push` |
| UN3 | k = 8, 20, 2000 (abaixo de `MAX_COMMAND_LEN`) | `(["unclassified"], ["unclassified_command"])`, motivo `readings_cap`; k = 2000 em menos de 1 s |
| UN4 | `"timeout zz " * 1450` (cerca de 16 KB); `"timeout 5 " * 1600 + "docker restart x"` | menos de 1 s cada; o segundo com uma leitura e `docker_lifecycle` |
| UN5 | `timeout x busted`; `timeout -k 2 "$T" npm run lint` | `["other", "test-full"]`; `["lint", "other"]` (a primária é dona do `other`, inalterado) |
| UN6 | nvim com 3 e 4 níveis | 3: `["docker_lifecycle"]` (inalterado); 4: ver LR12 |
| UN7 | `_classify_segment` levanta `RecursionError` (mock): pre como `backend-python` e `main`; post | deny `unclassified_command` para os dois; registro com `uncertainty: ["classifier_error"]`, `error: "RecursionError"`; post grava, sem saída |
| UN8 | `"docker" restart x '` (aspa sem par); `echo "a; b"` | `docker_lifecycle`, motivo `shlex_fallback`; `(["other"], [])` com `shlex_fallback` (guarda de falso positivo) |
| UN9 | canário: `sudo -u x docker restart x`, `true & docker restart x`, `bash -c "git push"`; e `docker ps`, `git log --grep commit`, `docker restart x` | os três primeiros sem flag de negação e com `deny_token_unmatched`; os três últimos sem o motivo |
| UN10 | `classify_command` x `analyze_command` em todas as tabelas de `test_classify.py` (`COMMAND_TABLE`, `PREFIX_TABLE`, `LUA_TABLE`, `TIMEOUT_*`) | mesmas categorias e flags; `parse_uncertain` nunca em `classify_command` |
| UN11 | post de `timeout "$T" pytest tests/a_test.py`; post de `pytest`; pre de `timeout "$T" docker restart x` | flags com `parse_uncertain` e `uncertainty: ["prefix_readings"]`; sem campo `uncertainty`; deny `docker_lifecycle`, registro com `parse_uncertain` |
| UN12 | `decide` com `unclassified_command` para `main` e `subagent` | deny; motivo com o `WHY` e o `what_to_do` da seção 3.5 |
| UN13 | `timeout 0,5 docker restart x` | `docker_lifecycle` (locale coberto pela união) |

### `test_heredoc.py` - `HeredocCleanPrefix` (nova, Task 3)

| # | Caso | Esperado |
|---|---|---|
| HS1 | `sh -s $(true) cat <<'EOF'`, `bash -s "$(true)" cat <<EOF`, `sh -s $(echo) tee x <<EOF`, `x=$(true) cat <<EOF` com corpo `docker compose up` | `docker_lifecycle` em todos (bug) |
| HS2 | `(sh -s) cat <<EOF`; `git commit -m "$(cat <<'EOF' ... EOF\n)" && cat <<X ... X` (corpo de X com `docker compose up`) | primeiro classificado; segundo só `["git_commit"]` (restaurar o `seg_start` não apaga o separador) |
| HS3 | `timeout -s KILL "$T" cat <<EOF`; `timeout 5 cat <<EOF` | classificado; removido |
| HS4 | `$X cat <<EOF`, `A=$B cat <<EOF`, `"$C" <<EOF`; e `cat > $SP/x.sh <<EOF`, `tee "$F" <<EOF` | os três primeiros classificados; os dois últimos removidos (forma das métricas) |
| HS5 | `git $X commit -F - <<EOF`, `gh pr create --title "$T" -F - <<EOF` | classificados (`docker_lifecycle`) |
| HS6 | `_sub("git commit -m ")`, `_sub("gh pr create --title t --body ")`; `git commit -m "$X$(cat <<'EOF' ...)"` | removidos (H3 tira a aspa final); o último classificado |
| HS7 | `_clean_sink_tokens("cat 'x")`, `_clean_sink_tokens("timeout zz cat")`, `_clean_sink_tokens("FOO=1 cat > $F")` | `None`; `None`; `["cat", ">", "$F"]` |
| HS8 (`test_uncertainty.py`) | motivo de HS1, HS3 e HS4 (mantidos) por `analyze_command`; `python3 - <<EOF`, `bash <<EOF` | `heredoc_unclean_prefix`; sem motivo |

As classes atuais de `test_heredoc.py` passam sem mudança.

### `test_watchdog.py` (novo, Task 4, por `call_main`)

| # | Caso | Esperado |
|---|---|---|
| WD1 | espião em `os.fork`: pre/post de Bash e Write; Read; modo `off`; pre em modo `audit` | um `fork` por ferramenta auditada; nenhum nos outros |
| WD2 | `classify_command` dorme 30 s, `ANALYSIS_TIMEOUT_S = 0.05`; pre e post | deny `analysis_timeout`; post grava; menos de 2 s; `os.kill(pid, SIGKILL)` chamado |
| WD3 | chamada C longa: `classify_command` faz `sum(range(10**12))` | deny `analysis_timeout` em menos de 2 s (o `SIGALRM` sozinho não interromperia) |
| WD4 | filho termina sem mensagem: `os._exit(3)`; `os.kill(os.getpid(), SIGKILL)` | deny `unclassified_command`, `uncertainty: ["analysis_crash"]` |
| WD5 | exceção no filho, com `fork` e com `_fork_available` falso | deny `unclassified_command`, `classifier_error`, mesmo registro nos dois caminhos |
| WD6 | linha 1 inválida (`_send` escreve `xx\n`); linha 1 acima de `MAX_CHILD_MESSAGE` | `analysis_crash` |
| WD7 | marcação lenta no filho (`git_root` dorme 30 s), `ANALYSIS_TIMEOUT_S = 0.3`; pre de `docker compose up` | saída com o deny; registro com `run_tags: "timeout"`; menos de 2 s |
| WD8 | `classify_command` imprime `noise` no stdout | saída do hook é só o JSON da decisão |
| WD9 | `os.fork` levanta `OSError`; `_fork_available` falso | caminho no processo: deny `docker_lifecycle`; `analysis_timeout` com o classificador lento |
| WD10 | pre sem decisão (`echo hi`) | silencioso; o filho é morto sem esperar a marcação |

### `test_hook_process.py` - `HardeningProcess` (nova, distribuída pelas tasks)

| # | Task | Caso | Esperado |
|---|---|---|---|
| P-HH1 | 1 | `metrics_dir/t.jsonl` é um FIFO: pre `docker compose restart api`; post `pytest tests/test_a.py` | deny impresso; os dois terminam em menos de 2 s; nenhum registro |
| P-HH2 | 1 | repo com `.claude/runs/a.json` = `[]`, `b.json` esparso de 50 MB e um run válido (`services/web/src/**`): pre e post de Write de `frontend-react` em `README.md` | registro post com `docs_write_by_implementer` e `out_of_scope_write`, `area: code` e `run` do estado válido (hoje o `AttributeError` cai no fallback, que perde `docs_write_by_implementer` e grava `area: outside`); menos de 2 s |
| P-HH3 | 2 | `"timeout a " * 9 + "docker restart x"` | deny `unclassified_command`; registro com `readings_cap` |
| P-HH4 | 2 | nvim com 4 níveis | deny `unclassified_command`, motivo `nested_shell_depth` |
| P-HH5 | 2 | `patch_source`: `_classify_segment` levanta | deny `unclassified_command`, `classifier_error` |
| P-HH6 | 2 | `"timeout a " * 4 + "docker restart x"` | deny `docker_lifecycle` (teto antigo removido) |
| P-HH7 | 3 | `sh -s $(true) cat <<'EOF'` + corpo `docker restart x` | deny `docker_lifecycle` |
| P-HH8 | 4 | `patch_source`: `sum(range(10**12))` no classificador | deny `analysis_timeout` em menos de 2 s |
| P-HH9 | 4 | `patch_source`: `os._exit(3)` no classificador | deny `unclassified_command`, `analysis_crash` |
| P-HH10 | 4 | `PATH` com um `git` falso que dorme 30 s; post de `pytest tests/test_a.py` | registro com `run_tags: "timeout"`; menos de 2 s |
| P-HH11 | 4 | pre `pytest tests/test_a.py` e `docker compose restart api` no caminho normal | silencioso; deny `docker_lifecycle` (o `fork` não muda o contrato) |

Os casos independentes de uma mesma classe rodam juntos por `HookProcess.run_many` (Task 6).

### `test_agent_metrics.py` (Task 5)

| # | Caso | Esperado |
|---|---|---|
| MR1 | JSONL sintético com cada motivo | tabela por motivo com contagens e exemplos; registro PreToolUse warn não conta duas vezes |
| MR2 | pre block com `prefix_readings`; pre block `unclassified_command`; pre block sem motivo | os dois primeiros em False-positive candidates; o terceiro não |
| MR3 | post com `deny_token_unmatched` sem decisão; pre block com o mesmo motivo | o primeiro em False-negative candidates; o segundo não |
| MR4 | registros `analysis_timeout`, `run_tags: "timeout"` | contados em Hook health |
| MR5 | nenhum motivo no período | a seção diz "None." |

### Regras -> testes

| Regra | Testes |
|---|---|
| U1 união, primária dona do `other` | UN1, UN5, UN10, UN13, LR13 e tabelas atuais |
| U2 sem profundidade; teto de leituras | UN2, UN3, UN4, P-HH3, P-HH6 |
| U3 profundidade do nvim | UN6, LR12, P-HH4 |
| U4 exceção | UN7, WD5, P-HH5 |
| U5 `shlex` | UN8 |
| U6 campo e flag | UN11, MR1 |
| U7 canário | UN9, MR3 |
| H1 `seg_start` restaurado | HS1, HS2, P-HH7 |
| H2 prefixo limpo | HS3, HS4, HS5, HS7 |
| H3 texto de fora | HS6, `SubstitutionOnlyDataAsMessageValue` sem mudança |
| H4 motivo | HS8 |
| W1 prazo duro | WD2, WD3, P-HH8 |
| W2 crash | WD4, WD6, P-HH9 |
| W3 exceção no filho | WD5 |
| W4 decisão antes da marcação | WD7, WD10, P-HH10 |
| W5 fallback | WD9, `AnalysisLimitAndArming`, `DecisionBeforeRecording` |
| W6 saída isolada | WD8, P-HH11 |
| B1 config | BIO2 |
| B2 run states | BIO3-BIO6, P-HH2 |
| B3 métricas | BIO7, P-HH1 |
| B4 CLAUDE.md | BIO10 |
| B5 invariante | BIO9 |
| R1 registro | BIO8, WD7, P-HH10 |
| C1, C2 categorias | UN12, F2, F3, F6 |
| M1 relatório | MR1-MR5 |

## Implementation order

### Task 1 - I/O limitado e registro que não se perde

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/tests/test_bounded_io.py`, `.claude/hooks/tests/test_hook_main.py`, `.claude/hooks/tests/test_hook_process.py`, `.claude/hooks/tests/_support.py`
- **Depends on:** -
- **Done when:** `_read_bounded`, `_append_line`, `load_config`, `active_run`, `project_docs_root`, `_run_tags` e `_write_record` seguem a Design, seção 2 (B1-B5, R1, constantes nomeadas); BIO1-BIO10, P-HH1 e P-HH2 passam; `DecisionBeforeRecording.test_slow_recording_cannot_delay_or_lose_the_decision` espera o registro com `run_tags: "timeout"`; `python3 -I -B -m unittest discover -s .claude/hooks/tests -t .claude/hooks` verde; `agent-audit.json` e `settings.json` intactos
- **Status:** done

### Task 2 - Leituras por posição, incerteza e unclassified_command

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/agent-audit.json`, `.claude/hooks/agent-metrics.py`, `.claude/hooks/tests/_support.py`, `.claude/hooks/tests/test_uncertainty.py`, `.claude/hooks/tests/test_classify.py`, `.claude/hooks/tests/test_config_contract.py`, `.claude/hooks/tests/test_decide.py`, `.claude/hooks/tests/test_hook_main.py`, `.claude/hooks/tests/test_hook_process.py`
- **Depends on:** Task 1
- **Done when:** `command_readings`, `_command_starts`, `_prefix_steps`, `analyze_command`, o envoltório `classify_command`, `_nvim_nested` e o `except Exception` de `main()` seguem a Design, seção 3 (U1-U7, C1, C2); `strip_prefixes` e `strip_prefix_variants` removidos; `agent-audit.json` ganha só `unclassified_command: block` e `parse_uncertain: audit`; `WHY`, `what_to_do`, `FLAG_LABELS`, `TEST_CONFIG` e o piso F2 atualizados; LR12 alterado; UN1-UN13 (exceto HS8) e P-HH3-P-HH6 passam; `git grep -n "nested_shell_unclassified\|strip_prefix_variants" -- .claude/hooks` sem ocorrências; suite verde; `settings.json` intacto
- **Status:** done

### Task 3 - Heredoc só é dado com prefixo limpo

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/tests/test_heredoc.py`, `.claude/hooks/tests/test_uncertainty.py`, `.claude/hooks/tests/test_hook_process.py`
- **Depends on:** Task 2
- **Done when:** `_scan_heredocs` restaura o `seg_start` (H1) e `_is_data_sink` usa `_clean_sink_tokens` (H2-H4), conforme a Design, seção 4; a tabela "Comportamento resultante" vale; HS1-HS8 e P-HH7 passam; as classes atuais de `test_heredoc.py` e `HeredocOpenerBound` passam sem mudança; suite verde
- **Status:** done

### Task 4 - Watchdog de análise por fork

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/tests/test_watchdog.py`, `.claude/hooks/tests/test_hook_main.py`, `.claude/hooks/tests/test_hook_process.py`, `.claude/hooks/tests/_support.py`
- **Depends on:** Task 3
- **Done when:** `_analysis`, `_fork_available`, o protocolo de duas linhas, `MAX_CHILD_MESSAGE` e o fallback seguem a Design, seção 5 (W1-W6); `HookProcess.patch_source` existe e falha quando o trecho não aparece exatamente uma vez; os testes de `AnalysisLimitAndArming` e `DecisionBeforeRecording` listados em "Testes que mudam" rodam com `_fork_available` falso; WD1-WD10 e P-HH8-P-HH11 passam; latência do processo do hook medida antes e depois (mediana de 15 execuções de `pytest tests/test_a.py`, como na seção 5) e registrada no relatório da task, com aumento de até 5 ms; suite verde
- **Status:** done

### Task 5 - Seção de incerteza no relatório de métricas

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-metrics.py`, `.claude/hooks/tests/test_agent_metrics.py`
- **Depends on:** Task 2
- **Done when:** `report()` tem a seção "Parser uncertainty and hook health" da Design, seção 6 (M1); MR1-MR5 passam; as seções atuais do relatório não mudam; suite verde
- **Status:** done

### Task 6 - Tempo da suite claude-hooks dentro do orçamento

- **Stack:** backend-python
- **Files:** `.claude/hooks/tests/*.py`
- **Depends on:** Task 4, Task 5
- **Done when:** perfil por teste antes e depois (o mesmo método do Background da entrada: tempo por `id()` de teste, os 30 mais lentos e o total por módulo) registrado no relatório da task; `HookProcess.run_many(items)` roda processos independentes em paralelo (`ThreadPoolExecutor`, no máximo `min(8, os.cpu_count())`, cada item com o próprio `HookProcess` ou a própria sessão, para não misturar a ordem dos registros) e é usado nos laços de `subTest` de processo independentes (pelo menos `test_huge_or_non_finite_overrides_are_clamped_never_a_silent_allow`, `test_an_invalid_override_falls_back_to_the_default_limit`, `test_p6_design_system_rules_match_the_h_table` e `HardeningProcess`); limites de 0,2-0,3 s dos testes no processo cujo mock nunca termina baixam para 0,05 s; nenhuma asserção enfraquecida; a suite inteira, com os testes novos, roda em no máximo 8,5 s de parede na mesma máquina, nenhum teste isolado passa de 0,5 s, e três execuções seguidas ficam verdes (sem flakiness); o hook não muda
- **Status:** done

## Verification

No fim do run, pelo `test-runner`:

1. Suite `claude-hooks` inteira, verde, três vezes seguidas, com o tempo de parede de cada uma (orçamento da Task 6: até 8,5 s), normal e com `TMPDIR` dentro de um diretório `claude-*` do scratchpad (como nos runs anteriores).
2. `git grep -n "nested_shell_unclassified\|strip_prefix_variants" -- .claude/hooks` sem ocorrências.
3. `git diff --stat main -- .claude/settings.json` vazio; `git diff main -- .claude/hooks/agent-audit.json` mostra só as duas chaves novas.

Sem runtime local nem UI: não há request a uma instância nem check visual. Pela sessão principal, só leitura, scripts no scratchpad:

4. **Replay das métricas**: cada `cmd` de Bash em `~/.claude/metrics/*.jsonl` (nas duas máquinas) classificado pela versão de `main` e pela nova (`classify_command`); listar as diferenças. Esperado: só as mudanças pretendidas (heredoc com prefixo não limpo, cadeias de `timeout`, nvim profundo). Lembrar que o `cmd` é truncado em 300 caracteres.
5. **Sondas do revisor** (`e2e.py`, `cap.py`, `fuzz.py`, `fo.py`, `variants.py` do scratchpad da lua-agent, sem editá-las): `fo.py` com `sh -s $(true) cat` negado; `cap.py` com todos os casos em menos de 2 s; `fuzz.py` sem exceção; `variants.py` sem leitura truncada (nenhum `other` silencioso numa cadeia que contém comando bloqueado).

Checks manuais do usuário, depois do merge (o hook vivo muda na hora):

- Uma sessão normal de trabalho (commits, testes, heredocs `cat > arquivo <<EOF`, `python3 - <<EOF`) sem negação `unclassified_command` nem `analysis_timeout`, e sem diferença perceptível de latência.
- Depois de cerca de uma semana nas duas máquinas: `python3 ~/.claude/hooks/agent-metrics.py --since <data do merge> --merge`, seção "Parser uncertainty and hook health": nenhum falso positivo; cada candidato a falso negativo vira entrada para a spec do lexer (Design, seção 6).

**needs_docs** (para o `docs-writer`, no fim):

- `.claude/README.md`, seção dos hooks: princípio de incerteza em dois níveis, `unclassified_command` (block) e `parse_uncertain` (audit) com os motivos, watchdog por `fork` e fallback, limites de I/O (config, run states, métricas), campo `uncertainty`, `run_tags`.
- `.claude/agent-workflow.md`: 13.1 (o hook analisa num processo filho com prazo duro; o pai decide); 13.6 (heredoc só é dado com prefixo limpo, regras H1-H3); 13.8 nova "Incerteza do parser: fail closed" (níveis A e B, motivos, válvula de emergência); 14.2 (seção nova do relatório e o procedimento de medição e ajuste da Design, seção 6).

## Open questions

1. **Categoria nova `unclassified_command`** (decidir na aprovação). Opções: (a) categoria `block` própria, com o motivo no campo `uncertainty`; (b) reusar `analysis_timeout` ("too complex to analyze"); (c) manter `docker_lifecycle` no nvim e não bloquear nos outros tetos. Recomendação: (a). Separa "lento" de "estruturalmente incerto" nas métricas, dá uma mensagem que diz ao agent o que fazer e resolve a entrada nvim-depth-cap. (b) mistura causas no ajuste de falsos positivos; (c) deixa F3 aberta.
2. **Watchdog por `fork`** (Task 4; decidir na aprovação). Opções: (a) `fork` com prazo duro, +1,8 ms medidos por chamada auditada (cerca de 2,4% dos 74 ms do hook); (b) só `SIGALRM` + I/O limitado (Tasks 1-3), latência zero, residual: syscall presa em estado D, chamada C futura sobre entrada não limitada, crash do interpretador. Recomendação: (a). É o único mecanismo que fecha a classe de tempo e de crash sem depender de toda entrada futura ser limitada, por um custo que não se percebe. Com (b), a Task 4 sai inteira e o resto da spec não muda (W5 já é o caminho atual).
3. **Canário `deny_token_unmatched`** (U7). Opções: (a) incluir, só registro; (b) tirar. Recomendação: (a). É o que torna visível a próxima forma que escapa, sem negar nada; o ruído (`echo`, `grep`) fica restrito à lista de revisão.
4. **Próxima spec de cobertura: lexer de shell.** Fica fora daqui, mas é o maior buraco restante: `true & docker restart x`, `(docker restart x)`, `{ docker restart x; }`, `if ...; then docker restart x; fi`, `for ...; do docker restart x; done`, `! docker restart x`, `$(docker restart x)`, crases, `sudo -u u docker restart x`, `nohup`, `xargs`, `watch`, `bash -c "..."` e `eval` dão `other` hoje (conferido). Opções: (a) uma spec "audit-shell-lexer" que troca o `SEGMENT_SPLIT` por um lexer com aspas, `&`, grupos, palavras reservadas e substituições, e acrescenta os wrappers como passos de `_prefix_steps`, juntando segment-split-quote-blind, strip-prefixes-wrappers e nvim-shell-exec-unclassified; (b) specs separadas por entrada. Recomendação: (a), logo depois da spec da declaração da raiz de docs (que o usuário já marcou como a próxima).
5. **Meta de tempo da suite.** Opções: (a) manter no máximo 8,5 s com os testes novos (Task 6) e deixar a meta de menos de 5 s aberta na entrada; (b) voltar a menos de 5 s agora, o que exige mudar o contrato da suite (marcar testes de processo lentos como on-demand) ou o modo como o hook roda (ver `out_of_scope_issues`: lançador com bytecode em cache). Recomendação: (a); (b) pede uma decisão de contrato que não cabe aqui.
6. **Entradas do backlog.** Opções: (a) o `backlog-keeper` acrescenta o link desta spec às entradas cobertas e mantém o status (`Proposed`/`Open`) até o `/implement` começar, quando vão a `In progress`; a entrada da suite lenta recebe o link com "coberta em parte (Task 6)"; (b) `In progress` já agora. Recomendação: (a), como nas specs anteriores.
