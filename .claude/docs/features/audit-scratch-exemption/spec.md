# audit-scratch-exemption - isenção de scratch restrita ao scratchpad da sessão

- **Date:** 2026-11-12
- **Status:** Implemented
- **Source:** [docs/backlog/refactor/2026-11-11-audit-scratch-exemption-too-broad.md](../../backlog/refactor/2026-11-11-audit-scratch-exemption-too-broad.md) (refactor sem plan; não há `plan.md` nesta pasta)
- **Implementation log:** [log.md](log.md) (criado pelo `/implement` na primeira task)

## Summary

Troca a regra de scratch do hook `agent-audit` (qualquer `<tempdir>/claude-*` ou `/tmp/claude-*`) pelo scratchpad da sessão atual, que o Claude Code entrega ao hook no campo `scratchpad_dir` do payload. Um ator de escopo fixo num run só escreve fora do repo sem `out_of_scope_write` dentro desse diretório (ou num glob absoluto aprovado, como hoje). Sem `scratchpad_dir` válido no payload, não há isenção, e o registro diz isso.

| Camada | Arquivos | Mudança |
|---|---|---|
| Hook | `.claude/hooks/agent-audit.py` | `session_scratchpad()` (novo), `is_scratch()` com o scratchpad da sessão, campo `scratch` no registro; saem `SCRATCH_BASES`, o uso de `tempfile.gettempdir()` e os imports `tempfile` e `fnmatch` |
| Métricas | `.claude/hooks/agent-metrics.py` | linha nova em `## Writes`: escritas fora do repo durante um run, por situação de scratch |
| Testes | `hooks/tests/_support.py`, `test_write_scope.py`, `test_hook_main.py`, `test_hook_process.py`, `test_agent_metrics.py` | sai o patch de `SCRATCH_BASES`; os dois testes que fixam a regra antiga são substituídos; casos SC1-SC20 e R10 |
| Docs (fim, `docs-writer`) | `.claude/README.md`, `.claude/agent-workflow.md` (13.7) | a definição de scratch e a API do `_support` (needs_docs) |

O config (`agent-audit.json`) não muda: nenhuma categoria nova, `out_of_scope_write` continua `warn`. Sem serviço, API, banco, flag nem migração.

## Background

**O problema.** `is_scratch()` (`agent-audit.py`, linhas 505-517) aceita qualquer diretório cujo primeiro componente sob `tempfile.gettempdir()` ou `/tmp` case com `claude-*`. Isso cobre o scratchpad de outras sessões, diretórios internos do Claude Code (`/tmp/claude-1000/bash-edit-diff/`) e diretórios criados por agents. Evidência nas métricas desta máquina (sessão `e3f6c6b7`, 2026-11-12), escritas aceitas como scratch pela regra atual:

| Caminho escrito | O que é |
|---|---|
| `/tmp/claude-1000/-home-dotfiles--claude/e3f6c6b7-.../scratchpad/probe.py` | slug errado (falta `void`), criado por um agent; depois movido |
| `/tmp/claude-1000/e3f6c6b7-.../scratchpad/tmpprobe` | sem o componente do projeto, criado por `mkdir -p` de um agent (modo `755`, os do Claude Code são `700`); ainda existe |

**O que o hook recebe.** Verificado na documentação oficial e no código do Claude Code instalado (2.1.323, `~/.local/share/claude/versions/2.1.323`), não de memória:

| Fonte | Fato |
|---|---|
| [Hooks, Common input fields](https://code.claude.com/docs/en/hooks#common-input-fields) | todo evento recebe `scratchpad_dir`: "Path to the session's scratchpad directory ... Absent when the session has no scratchpad or the temp directory is unavailable. Requires Claude Code v2.1.257 or later" |
| [.claude directory, Session scratchpad directory](https://code.claude.com/docs/en/claude-directory#session-scratchpad-directory) | caminho `/tmp/claude-<uid>/<project>/<session-id>/scratchpad/` (ou sob `$TMPDIR`/`CLAUDE_CODE_TMPDIR`); `<project>` é o diretório de trabalho com tudo que não é letra ou dígito trocado por `-`; a sessão só tem scratchpad com login claude.ai, API da Anthropic e `enableArtifact` diferente de `false`; "Hooks receive the current session's path as `scratchpad_dir`" |
| binário 2.1.323, montagem do payload do hook | `session_id: e.id`, `transcript_path: Np(e.id)`, `scratchpad_dir: wx() ? XP(e.id) ?? undefined : undefined`: o mesmo objeto de sessão gera o id e o scratchpad; `wx()` é a elegibilidade do scratchpad (sem ela, campo ausente). Chamadas remotas (`served:`) não levam `scratchpad_dir` |
| binário 2.1.323, `XP()` e `CO()` | scratchpad = `join(realpath(CLAUDE_CODE_TMPDIR ou tmpdir) + "/claude-<uid>", QL(cwd de início), sessionId, "scratchpad")`; `QL` troca `[^a-zA-Z0-9]` por `-` e, acima de 200 caracteres, trunca e soma um hash JS; o diretório é criado com modo `0700` |
| métricas locais (3 sessões) | registros de subagents (`agent_id` presente) ficam no arquivo da sessão pai, com o `session_id` do pai; o ambiente deste subagent tem `CLAUDE_CODE_SESSION_ID` igual ao do pai e o scratchpad sob o id do pai: **subagents compartilham o scratchpad do pai**, e o `agent_id` próprio não entra no caminho |
| métricas locais, campo `cwd` | numa mesma sessão o `cwd` do payload variou (`.claude`, `.claude/runs`, `.claude/docs/features/...`), enquanto o slug do scratchpad é o do diretório de início (`-home-void-dotfiles--claude`): **o `cwd` do payload não serve para derivar o slug** |

Conclusão: o caminho do scratchpad da sessão não precisa ser derivado; o Claude Code o entrega pronto, canônico (raiz temporária com `realpath`), igual para a sessão principal e os subagents. Derivá-lo (de `session_id`, `transcript_path`, `CLAUDE_CODE_TMPDIR` e uid) reimplementaria detalhes internos frágeis (truncamento com hash, `realpath`, regra do Windows); ver Alternatives.

**Quem a regra afeta.** `is_scratch()` só é consultado para um alvo fora de toda raiz git, escrito por um ator de escopo fixo (`IMPLEMENTERS`, `quality-fixer`, `test-writer`) com run ativo (`_assess_root`, linhas 575-579). Escritas pelo Bash não passam por `evaluate_write` (fronteira atual do hook, inalterada). A sessão principal, os outros agents e as flags de ator (`write_by_readonly_agent`, `design_director_write_outside`, `design_system_write_by_other`) não mudam.

**Testes que fixam a regra antiga** (docstrings citam esta entrada): `OutsideRepoWrites.test_scratchpad_under_tmp_claude_dir_is_allowed` e `OutsideRepoHardening.test_literal_tmp_claude_dir_is_scratch_even_if_tempdir_differs`, em `test_write_scope.py`. Além deles, `_support.py` depende de `SCRATCH_BASES`: `TempRepoCase.setUp` faz `mock.patch.object(audit, "SCRATCH_BASES", ())` (falharia com `AttributeError` quando o atributo sair), e `assert_not_scratch()` protege as fixtures contra o defeito do `TMPDIR` (bug [audit-tests-fail-under-tmp-claude](../../backlog/bugs/2026-11-12-audit-tests-fail-under-tmp-claude.md), Fixed). Com a regra nova a causa raiz desse bug some: nenhum diretório é scratch por acaso, só o nomeado no payload.

**Fora do escopo:** [nested-repo-run-lookup](../../backlog/refactor/2026-11-11-audit-nested-repo-run-lookup.md) e os bugs abertos em `docs/backlog/bugs/` (nenhum teste desta spec os fixa).

## Design

### 1. Regras

| # | Regra |
|---|---|
| B1 | Ator de escopo fixo, run ativo, alvo fora de toda raiz git: em escopo só se o alvo estiver estritamente dentro do scratchpad da sessão atual, ou casar com um glob absoluto aprovado (inalterado) |
| B2 | Scratchpad de outra sessão, diretórios internos do Claude Code e qualquer outro `claude-*` sob o temp não são scratch, nem com o mesmo `session_id` num caminho diferente |
| B3 | Subagents usam o scratchpad da sessão pai (o que vier no payload; o `agent_id` não entra) |
| B4 | Sem `scratchpad_dir` válido no payload, não há isenção: o alvo é julgado como qualquer caminho de fora (hoje `out_of_scope_write`, ação `warn`) e o registro marca `scratch: "unavailable"` |
| B5 | Um symlink nunca amplia a isenção: o alvo é comparado na forma resolvida (e na léxica, com `..`), e o scratchpad literalmente, sem `realpath` |
| B6 | Um `scratchpad_dir` inválido nunca levanta exceção nem quebra a sessão; vale como ausente |
| B7 | Escritas fora do repo durante um run aparecem nas métricas pela situação de scratch, para monitorar o risco da entrada |
| B8 | Atores sem escopo fixo, flags de ator, flags de área e o comportamento dentro do repo não mudam; um scratchpad dentro do repo não isenta nada (dentro do repo valem os `allowed_paths`) |

### 2. `.claude/hooks/agent-audit.py`

**Sai:** `SCRATCH_BASES`, o laço sobre `tempfile.gettempdir()` e os imports `fnmatch` e `tempfile` (só `is_scratch` os usa; conferido por grep).

**Novo `session_scratchpad(raw: object) -> Path | None`**, ao lado de `is_scratch`:

| Entrada | Saída |
|---|---|
| não é `str`, vazio, contém `\0`, relativo (`not os.path.isabs`) | `None` |
| absoluto | `Path(os.path.normpath(raw))`; se for a raiz do sistema (`p == Path(p.anchor)`), `None` |
| qualquer exceção | `None` |

Sem `realpath` e sem checar existência: o valor vem do Claude Code (o agent não altera o payload), já é canônico, e o diretório pode ainda não existir (é criado sob demanda). Também sem checagem de forma (`.../<session>/scratchpad`): se o Claude Code mudar o formato, a regra continua valendo para o caminho que ele entregar.

**`is_scratch(target: Path, scratchpad: Path | None) -> bool`**: `True` só quando `scratchpad` não é `None` e `target.relative_to(scratchpad)` tem pelo menos um componente (estritamente dentro; `<sp>x/` e `<sp>-other/` não casam porque a comparação é por componente). Comparação literal, nunca contra `scratchpad.resolve()`: se um agent trocar o scratchpad por um symlink para `$HOME`, o alvo resolvido fica em `$HOME/...`, não casa, e a escrita é sinalizada. Docstring cita B1, B2 e B5.

**`evaluate_write(path_str, cwd, actor, tool, response, roots=None, scratchpad=None)`**: parâmetro novo, só por nome na chamada do `main()` e com padrão `None` (as chamadas posicionais atuais seguem válidas). Dentro do `try`, `sp = session_scratchpad(scratchpad)`, passado a `_assess_root(..., scratch=sp)`. A docstring troca "a <tempdir>|/tmp claude-* scratch path" por "a path inside the session scratchpad (`scratchpad_dir` of the payload)".

**`_assess_root`**, no ramo `else` (fora do repo) de atores de escopo fixo com run:

```python
in_scratch = is_scratch(form, scratch)
cur["scratch"] = "unavailable" if scratch is None else "match" if in_scratch else "no-match"
in_scope = in_scratch or matches(rel, [a for a in absolute if a.startswith("/")])
```

O comentário do bloco passa a citar o scratchpad da sessão. O campo `scratch` só existe quando esse ramo roda (alvo fora, ator de escopo fixo, run ativo); nos outros registros a chave não aparece. Com várias formas (resolvida e léxica), o registro segue a regra atual (o da primeira forma sinalizada).

**`main()`**: `evaluate_write(..., docs_roots(config), scratchpad=payload.get("scratchpad_dir"))`. O valor de `scratchpad_dir` não é gravado no registro (só o enum `scratch`), coerente com a regra de guardar o mínimo.

**Docstring do módulo**: na lista do que é classificado, "file writes: ... outside the repo only inside the session scratchpad (`scratchpad_dir`) or an approved absolute glob".

**Comportamento resultante** (ator `backend-node`, run ativo, `sp` = scratchpad do payload):

| Alvo | `scratchpad_dir` | `scratch` | `out_of_scope_write` |
|---|---|---|---|
| `sp/n.txt` | `sp` | `match` | não |
| `/tmp/claude-1000/<outro-slug>/<outra-sessão>/scratchpad/n.txt` | `sp` | `no-match` | sim |
| `/tmp/claude-1000/bash-edit-diff/x` | `sp` | `no-match` | sim |
| `sp/n.txt` | ausente | `unavailable` | sim |
| `sp/link/x` com `link` -> diretório de fora | `sp` | `no-match` | sim |
| `<repo>/services/web/x.ts` (fora dos `allowed_paths`) | qualquer | (sem chave) | sim, como hoje |

### 3. `.claude/hooks/agent-metrics.py`

Em `report()`, seção `## Writes`, depois da linha atual, quando houver registros com `scratch` (só eventos que não são `PreToolUse`, como em `## Flags`):

```
- outside the repo during a run: N (session scratchpad: a; elsewhere: b; no scratchpad known: c)
```

`a`, `b`, `c` contam `match`, `no-match` e `unavailable`. Sem registros com `scratch`, a linha não aparece (relatórios de sessões antigas ficam iguais). É a métrica para a análise de promoção `warn` -> `block` (seção 13.3 do `agent-workflow.md`): um `c` maior que zero numa sessão com scratchpad indicaria o risco da entrada.

*Adendo 2026-11-12:* a linha acima foi substituída; o bucket `elsewhere` foi dividido em `approved glob` e `out of scope`. Ver [Adendo 2026-11-12](#adendo-2026-11-12---linha-de-scratch-nas-métricas-separa-glob-aprovado-de-fora-do-escopo).

### 4. Testes: infraestrutura (`hooks/tests/_support.py`)

| Item | Mudança |
|---|---|
| `TempRepoCase` | saem `REAL_SCRATCH_BASES`, `use_real_scratch_bases()` e o patch de `SCRATCH_BASES` no `setUp`; a docstring deixa de falar do `TMPDIR` |
| `assert_not_scratch()` | removido, e suas chamadas em `setUp` e `make_dir`: sem scratchpad no payload nada é scratch, a premissa deixa de existir. `assert_no_git_root()` fica |
| `eval_at(target, actor, cwd=None, scratchpad=None)` | repassa `scratchpad=` a `evaluate_write` |
| `make_scratchpad(session="s1", slug="-proj")` (novo, em `TempRepoCase`) | cria `<make_dir()>/claude-<uid>/<slug>/<session>/scratchpad` (modo `0700`) e devolve o `Path`; mesma forma do Claude Code, fora de qualquer repo, removido no cleanup |
| `payload(..., scratchpad=None)` | com valor, inclui `"scratchpad_dir": str(scratchpad)` |

### 5. Segurança, privacidade e observabilidade

- **Confiança no payload**: o `scratchpad_dir` vem do processo do Claude Code; um agent não o altera. Um agent que reescreva `settings.json` (`env.CLAUDE_CODE_TMPDIR`) mudaria a raiz temporária das sessões seguintes: isso é o bug aberto [audit-hook-self-protection](../../backlog/bugs/2026-11-11-audit-hook-self-protection.md), fora do escopo.
- **Symlinks**: B5. A forma resolvida do alvo é sempre julgada; o scratchpad nunca é resolvido, como os globs absolutos aprovados (mesma defesa contra symlink plantado).
- **Privacidade**: nenhum conteúdo novo no registro; só o enum `scratch`. O caminho do scratchpad não é gravado.
- **Observabilidade**: `scratch` no registro de cada escrita fora do repo julgada por escopo, e a linha nova do `agent-metrics.py` (B7).
- **Fail-open preservado**: `session_scratchpad` não levanta; qualquer erro em `evaluate_write` cai no `except` atual (falha fechada para escopo, sem quebrar a sessão).

### 6. Rollout e reversão

Sem flag: o hook vivo é o arquivo do repo (`~/.claude` aponta para `.claude/`), então a regra vale na próxima chamada depois do merge, para todas as sessões abertas. Como `out_of_scope_write` é `warn`, o pior efeito de um falso positivo é um lembrete no contexto do agent e uma linha nas métricas, nunca uma negação. Reversão: `git revert` dos commits das tasks; não há estado nem config a desfazer. Os registros com `scratch` já gravados são ignorados pelo relatório antigo.

## Alternatives considered

### Origem do caminho do scratchpad

| Opção | Corretude e robustez | Simplicidade e manutenção | Decisão |
|---|---|---|---|
| **Campo `scratchpad_dir` do payload, comparação literal** | exato: é o caminho que o Claude Code dá aos agents; igual para pai e subagents; canônico; ausente só quando a sessão não tem scratchpad (ou versão < 2.1.257) | uma função de validação e uma comparação; contrato documentado | **escolhida** |
| Derivar de `session_id` + slug de `transcript_path` (`~/.claude/projects/<slug>/`) + `CLAUDE_CODE_TMPDIR`/tmpdir + `claude-<uid>` | correta hoje nesta máquina (os slugs batem: `-home-void-dotfiles--claude`), mas depende de detalhes internos: `realpath` da raiz, `CLAUDE_CODE_TMPDIR` lido do ambiente do hook, slug truncado com hash JS acima de 200 caracteres, regra diferente no Windows e no Desktop | reimplementa o Claude Code; quebra em silêncio a cada mudança interna | rejeitada (e como fallback, Open questions 1) |
| Derivar do `cwd` do payload | errada: o `cwd` muda durante a sessão e o slug é do diretório de início (evidência em Background) | - | rejeitada |
| Curinga por sessão: `*/claude-*/*/<session_id>/scratchpad/**` | aceita diretórios criados por agents com slug errado ou sem slug (os dois casos da evidência) | simples, mas não é "o" scratchpad | rejeitada |
| Prefixo atual restrito a `claude-<uid>` | ainda cobre outras sessões e diretórios internos | - | rejeitada |

### Comparação com o scratchpad

| Opção | Por que não |
|---|---|
| Comparar também com `scratchpad.resolve()` (como `_under` faz com a raiz git) | um symlink no lugar do scratchpad ampliaria a isenção para o destino (ex.: `$HOME`); o valor do payload já é canônico |
| Exigir a forma `.../<session_id>/scratchpad` | protege contra nada (o payload é confiável) e desligaria a isenção se o Claude Code mudar o nome |
| **Literal, por componente, estritamente dentro** (escolhida) | mesma defesa dos globs absolutos aprovados; uma mudança de formato do Claude Code continua funcionando |

### Sem `scratchpad_dir`

| Opção | Por que não |
|---|---|
| Voltar à regra de prefixo | reabre exatamente o buraco desta entrada, justamente nas sessões sem scratchpad, onde nenhum agent tem motivo legítimo para escrever ali |
| Derivar (acima) | ver acima; fica como opção do usuário (Open questions 1) |
| **Sem isenção, marcado `unavailable`** (escolhida) | coerente com a documentação: sem o campo, a sessão não tem scratchpad, e o prompt dos agents nem menciona um; a ação é `warn`, e a métrica mostra se o risco aparece |

## Trade-offs

- **Versões < 2.1.257**: a sessão tem scratchpad mas o hook não recebe o campo; escritas de agents de escopo fixo ali viram `warn`. Aceito: as duas máquinas atualizam o Claude Code sozinhas (2.1.323 instalado), e o `scratch: unavailable` torna o caso visível.
- **Promoção futura de `out_of_scope_write` para `block`**: B4 passaria a negar escritas fora do repo em sessões sem scratchpad. Aceito: sem scratchpad não há onde um agent "deva" escrever fora do repo; a análise de promoção olha a linha nova antes.
- **Escritas pelo Bash** continuam fora do alcance de `evaluate_write` (`cat > /tmp/x`, `mktemp`): fronteira atual do hook, não muda aqui.
- **Campo novo no registro**: o formato das métricas ganha uma chave opcional; leitores antigos a ignoram.
- **Isenção mais estreita para quem errava o caminho**: o agent que escrever num slug errado passa a receber o lembrete. É o efeito pretendido.

## Testing

Suite: `claude-hooks` (tabela `Test suites` do `CLAUDE.md` da raiz). "flags" = `evaluate_write(...)["flags"]`; "pre" = saída do `PreToolUse` em `enforce` com `TEST_CONFIG`. Salvo indicação: ator `backend-node`, run ativo com `ALLOWED`, `sp = self.make_scratchpad()` passado como `scratchpad=sp`. Cada classe nova cita esta spec na docstring.

### `test_write_scope.py` - substituições

| Teste antigo | Destino |
|---|---|
| `OutsideRepoWrites.test_scratchpad_under_tmp_claude_dir_is_allowed` | removido; substituído por SC1 |
| `OutsideRepoHardening.test_literal_tmp_claude_dir_is_scratch_even_if_tempdir_differs` | removido; substituído por SC4 (o mesmo diretório literal `/tmp/claude-audit-test-<uuid>` agora é sinalizado) |
| `TempRepoCase` sem patch de `SCRATCH_BASES` | todos os testes atuais de `OutsideRepo*`, `ParallelTasksScope` e `InRepoScope` passam sem mudança de asserção, também com `TMPDIR` sob um diretório `claude-*` |

### `test_write_scope.py` - `SessionScratchpad` (nova)

| # | Caso | Esperado |
|---|---|---|
| SC1 | `sp/n.txt` e `sp/a/b/c.py` (diretórios intermediários inexistentes) | sem `out_of_scope_write`; `area: outside`; `in_scope: True`; `scratch: "match"` |
| SC2 | irmãos por prefixo de string: `<sp>x/n.txt`, `<sp>-other/n.txt`; e o próprio `sp` como alvo | `out_of_scope_write`; `scratch: "no-match"` |
| SC3 | scratchpad de outra sessão: `make_scratchpad(session="s2")` / `n.txt`, com o payload em `s1` | `out_of_scope_write`; `scratch: "no-match"` |
| SC4 | outros `claude-*`: `<base>/claude-<uid>/bash-edit-diff/x`, `<base>/claude-xyz/x`; e o literal `/tmp/claude-audit-test-<uuid>/n.txt` (pula se `/tmp` não é gravável) | `out_of_scope_write` em todos |
| SC5 | mesmo `session_id`, caminho errado: `<base>/claude-<uid>/-wrong/s1/scratchpad/x` e `<base>/claude-<uid>/s1/scratchpad/x` | `out_of_scope_write` (evidência de 2026-11-12) |
| SC6 | `scratchpad=None`, alvo `sp/n.txt` | `out_of_scope_write`; `scratch: "unavailable"` |
| SC7 | `scratchpad` inválido: `""`, `"rel/scratchpad"`, `"/"`, `42`, `["/x"]`, `{"a": 1}`, `str(sp) + "\0"`; alvo `sp/n.txt` | sem exceção; `out_of_scope_write`; `scratch: "unavailable"` (um `subTest` por valor) |
| SC8 | `sp/link/x.py`, com `link` -> `make_dir()` | `out_of_scope_write` (forma resolvida) |
| SC9 | `sp` trocado por um symlink para `D = make_dir()`; alvo `D/x` e alvo `sp/x` | os dois com `out_of_scope_write` (o scratchpad não é resolvido) |
| SC10 | `..`: `sp/../fora/x` sinalizado; `sp/a/../b.txt` sem flag | como descrito (formas resolvida e léxica) |
| SC11 | `scratchpad` não normalizado: `str(sp) + "/"`, `str(sp) + "/./"`, `str(sp.parent) + "/x/../scratchpad"`; alvo `sp/n.txt` | sem `out_of_scope_write` |
| SC12 | `main`, `docs-writer`, `planner` escrevendo em `<base>/claude-xyz/x`, com e sem `scratchpad` | sem `out_of_scope_write`; sem a chave `scratch` |
| SC13 | flags de ator no scratchpad: `code-reviewer` em `sp/n.txt`; `design-director` em `sp/x.md` | `write_by_readonly_agent`; `design_director_write_outside` (inalterado, B8) |
| SC14 | sem run ativo (`remove_run()`), alvo `<base>/claude-xyz/x` | sem flag de escopo; sem a chave `scratch`; `in_run: False` |
| SC15 | scratchpad dentro do repo (`<repo>/tmp/claude-<uid>/p/s1/scratchpad`), alvo nele fora dos `allowed_paths` | `out_of_scope_write`; `area: code`; sem a chave `scratch` (B8) |
| SC16 | glob absoluto aprovado de outro diretório + `scratchpad` dado: alvo no glob; alvo em `sp` | os dois sem `out_of_scope_write` (B1, o glob segue valendo) |
| SC17 | `session_scratchpad()` direto: cada linha da tabela da Design, seção 2, mais `None`, `Path(sp)` (não é `str`) e `"//"` | `Path` normalizado ou `None`, nunca exceção |

### `test_hook_main.py` - `ScratchpadPayload` (nova, por `call_main`)

| # | Caso | Esperado |
|---|---|---|
| SC18 | `PreToolUse` Write de `backend-node` com run ativo e `scratchpad_dir = sp`: alvo `sp/n.txt`; alvo em `<base>/claude-xyz/x`; payload sem `scratchpad_dir` e alvo `sp/n.txt` | silencioso; warn `out_of_scope_write`; warn `out_of_scope_write` |
| SC19 | os mesmos três em `PostToolUse`; e um subagent (`agent_type: test-writer`, `agent_id` próprio) com o `session_id` e o `scratchpad_dir` do pai, alvo `sp/n.txt` | registros com `scratch` `match`, `no-match`, `unavailable`; o subagent sem `out_of_scope_write` e `scratch: "match"` (B3); nenhum registro contém o valor de `scratchpad_dir` |

### `test_hook_process.py` - `ProcessContract` (caso novo)

| # | Caso | Esperado |
|---|---|---|
| SC20 | hook como processo real (env sem `TMPDIR`), `frontend-react` com run ativo (`RUN_ALLOWED`), `sp` criado em `self.tmp/claude-<uid>/-proj/s1/scratchpad` (fora do repo): Write em `sp/n.txt` com `scratchpad_dir`; o mesmo sem o campo | silencioso; uma linha JSON com warn `out_of_scope_write`; exit 0 e stderr vazio nos dois |

### `test_agent_metrics.py` - `ReportSections` (caso novo)

| # | Entrada | Esperado |
|---|---|---|
| R10 | registros de escrita `PostToolUse` com `scratch` `match` (2), `no-match` (1), `unavailable` (1), mais um `PreToolUse` com `scratch: no-match`; e um conjunto sem nenhum `scratch` | `- outside the repo during a run: 4 (session scratchpad: 2; elsewhere: 1; no scratchpad known: 1)`; sem `scratch`, a linha não aparece e o restante de `## Writes` fica igual a R6 |

*Adendo 2026-11-12:* R10 foi substituído pela versão com os quatro buckets; ver [Adendo 2026-11-12](#adendo-2026-11-12---linha-de-scratch-nas-métricas-separa-glob-aprovado-de-fora-do-escopo).

### Regras -> testes

| Regra | Testes |
|---|---|
| B1 só o scratchpad da sessão (ou glob aprovado) | SC1, SC16, SC18, SC20 |
| B2 outras sessões e outros `claude-*` não são scratch | SC2, SC3, SC4, SC5, SC18 |
| B3 subagents usam o scratchpad do pai | SC19 |
| B4 sem `scratchpad_dir`, sem isenção, marcado | SC6, SC18, SC19, SC20 |
| B5 symlink não amplia | SC8, SC9, SC10 |
| B6 valor inválido não quebra | SC7, SC11, SC17 |
| B7 métricas por situação de scratch | SC19, R10 |
| B8 o resto não muda | SC12, SC13, SC14, SC15, suite atual inteira verde |

## Implementation order

### Task 1 - Isenção de scratch pelo scratchpad_dir do payload

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/tests/_support.py`, `.claude/hooks/tests/test_write_scope.py`, `.claude/hooks/tests/test_hook_main.py`, `.claude/hooks/tests/test_hook_process.py`
- **Depends on:** -
- **Done when:** `SCRATCH_BASES`, `tempfile` e `fnmatch` não existem mais em `agent-audit.py`; `session_scratchpad()`, o novo `is_scratch()`, o parâmetro `scratchpad=` de `evaluate_write` e o campo `scratch` seguem a Design (seção 2); `_support.py` segue a seção 4; os dois testes antigos foram removidos e SC1-SC20 passam (um `subTest` por valor onde a tabela lista vários); `python3 -I -B -m unittest discover -s .claude/hooks/tests -t .claude/hooks` verde, também com `TMPDIR` apontando para um diretório `claude-*` dentro do scratchpad; nenhum arquivo fora da lista muda
- **Status:** done

### Task 2 - Linha de scratch no relatório de métricas

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-metrics.py`, `.claude/hooks/tests/test_agent_metrics.py`
- **Depends on:** Task 1
- **Done when:** `report()` imprime a linha da Design (seção 3) só quando há registros com `scratch` fora de `PreToolUse`; R10 passa e R1-R9, M1-M5, L1-L7 seguem verdes; nenhum arquivo fora da lista muda
- **Status:** done

## Verification

No fim do run, pelo `test-runner`:

1. Suite `claude-hooks` inteira, verde.
2. A mesma suite com `TMPDIR` apontando para um diretório `claude-*` dentro do scratchpad da sessão (a suite não depende do `TMPDIR`; antes isso exigia o patch de `SCRATCH_BASES`).
3. `git grep -n 'SCRATCH_BASES\|gettempdir\|claude-\*' -- .claude/hooks` sem ocorrências fora de comentários de teste que citem a regra antiga.
4. `git diff --stat main -- .claude/hooks/agent-audit.json .claude/settings.json` vazio (config e registro do hook intactos).

Sem runtime local nem UI: não há request nem check visual. Checks manuais do usuário, depois do merge (o hook vivo muda na hora):

- No próximo `/implement` com subagents de escopo fixo, `python3 ~/.claude/hooks/agent-metrics.py` mostra a linha `outside the repo during a run` com escritas no scratchpad como `session scratchpad`, e nenhuma em `no scratchpad known`. É a confirmação, num payload real, de que os subagents recebem o `scratchpad_dir` do pai (a spec a verificou pela documentação e pelo código do Claude Code, não por um payload capturado).
- Um agent que escreva com Write em `/tmp/claude-<uid>/<outro>/...` durante um run recebe o lembrete `out_of_scope_write`.

**needs_docs** (para o `docs-writer`, no fim):

- `.claude/README.md`, seção dos hooks: "or the path is scratch (`<tempdir>/claude-*` or `/tmp/claude-*`)" passa a "or the path is inside the session scratchpad (`scratchpad_dir` from the hook payload; without it there is no scratch exemption)"; mencionar o campo `scratch` do registro e a linha nova do relatório. Na descrição de `tests/_support.py`, tirar `assert_not_scratch()` e citar `make_scratchpad()` e os parâmetros `scratchpad=` de `eval_at()` e `payload()`.
- `.claude/agent-workflow.md`, 13.7 (`out_of_scope_write` fora do repositório): "ou for scratch (`<tempdir>/claude-*` ou `/tmp/claude-*`)" passa a "ou estiver dentro do scratchpad da sessão (`scratchpad_dir` do payload do hook; sem ele, não há isenção)".

## Open questions

1. **Sem `scratchpad_dir` no payload** (não bloqueia; a spec segue a recomendação). Opções: (a) sem isenção, `scratch: "unavailable"`, ação `warn` atual; (b) fallback derivado (`session_id` + slug do `transcript_path` + raiz temporária + `claude-<uid>`), aceito só quando o caminho existe e é diretório com modo `0700`; (c) voltar à regra de prefixo quando o campo faltar. Recomendação: (a). A documentação diz que o campo falta só quando a sessão não tem scratchpad (ou a versão é anterior a 2.1.257), e a versão instalada é 2.1.323; (b) reimplementa detalhes internos do Claude Code, e (c) reabre o buraco. Se a linha `no scratchpad known` aparecer nas métricas, (b) entra como adendo.
2. **Entrada de refactor.** O vocabulário do backlog é `Proposed` -> `In progress` -> `Done`. Opções: (a) o `backlog-keeper` mantém `Proposed`, adiciona o link desta spec e troca "Proposed change: Not defined" pelo resumo de B1-B4; a entrada vai a `In progress` quando o `/implement` começar; (b) passar a `In progress` já agora. Recomendação: (a).

## Adendo 2026-11-12 - linha de scratch nas métricas separa glob aprovado de fora do escopo

- **Origem**: decisão do usuário no review da Task 2 (2026-11-12).
- **Afeta**: Design, seção 3; Testing, R10; Task 2 (o **Done when** passa a valer com a linha e o R10 deste adendo). O texto original dessas seções fica como registro; onde divergir, vale este adendo.
- **Não muda**: o hook (`agent-audit.py`), o campo `scratch` do registro e seus três valores, as regras B1-B8 e os casos SC1-SC20.

**Motivo.** O bucket `elsewhere` contava todo `scratch == "no-match"`, inclusive escritas em escopo por um glob absoluto aprovado (B1). Na análise de promoção `warn` -> `block` ele superestimaria o risco: uma escrita autorizada apareceria como se fosse ser negada.

**Linha nova** (substitui a da Design, seção 3), exatamente:

```
- outside the repo during a run: N (session scratchpad: a; approved glob: g; out of scope: o; no scratchpad known: c)
```

| Contador | Registros contados |
|---|---|
| `a` | `scratch == "match"` |
| `g` | `scratch == "no-match"` sem `out_of_scope_write` em `flags` (lista ausente ou vazia conta como sem a flag) |
| `o` | `scratch == "no-match"` com `out_of_scope_write` em `flags` |
| `c` | `scratch == "unavailable"`, com ou sem a flag |
| `N` | `a + g + o + c` |

Mesmas condições de antes: só registros de escrita, só eventos que não são `PreToolUse`, e a linha só aparece quando existe algum registro assim com `scratch`. Na análise de promoção, `o` é o número de escritas que um `block` negaria em sessões com scratchpad; `c` maior que zero numa sessão com scratchpad continua indicando o risco da entrada (B4).

**R10** (substitui o da Testing, `test_agent_metrics.py`):

| # | Entrada | Esperado |
|---|---|---|
| R10 | registros de escrita `PostToolUse`: `scratch: match` (2); `scratch: no-match` sem flags (1); `scratch: no-match` com `flags: ["out_of_scope_write"]` (1); `scratch: unavailable` com `flags: ["out_of_scope_write"]` (1); mais um `PreToolUse` com `scratch: no-match` e `out_of_scope_write`; e um conjunto sem nenhum `scratch` | `- outside the repo during a run: 5 (session scratchpad: 2; approved glob: 1; out of scope: 1; no scratchpad known: 1)`: o `PreToolUse` não conta e o `unavailable` com a flag fica em `c`, não em `o`; sem `scratch` (ou só com o `PreToolUse`), a linha não aparece e o restante de `## Writes` fica igual a R6 |

A linha Regras -> testes de B7 (SC19, R10) não muda.

**needs_docs** (complementa o da Verification): onde o `.claude/README.md` citar a linha nova do relatório, descrever os quatro buckets (`session scratchpad`, `approved glob`, `out of scope`, `no scratchpad known`).
