# audit-md-outside-docs - `md_outside_docs` só para agents, por nome exato e só para arquivo novo

- **Date:** 2026-11-12
- **Status:** Implemented
- **Source:** [docs/backlog/refactor/2026-11-11-audit-md-outside-docs-false-positive.md](../../backlog/refactor/2026-11-11-audit-md-outside-docs-false-positive.md) (refactor sem plan; não há `plan.md` nesta pasta). Junta também [2026-11-12-audit-md-exemption-basename.md](../../backlog/refactor/2026-11-12-audit-md-exemption-basename.md) (mesma regra, ver Background)
- **Implementation log:** [log.md](log.md) (criado pelo `/implement` na primeira task)

## Summary

A flag `md_outside_docs` do hook `agent-audit` passa a julgar só o que ela quer pegar: um **agent** que **cria** um `.md` solto (nota, resumo, relatório) fora da raiz de docs. Hoje ela avisa também a sessão principal quando ela cria os arquivos de raiz do projeto (`PRD.md`, `CONSTRAINTS.md`, `OPEN_QUESTIONS.md`, `DESIGN_SYSTEM.md`, `BACKEND.md`...), avisa um implementer que cria um `.md` listado no **Files** da própria task, avisa quem reescreve com `Write` um `.md` que já existe, e deixa passar `MY_README.md` e `NOTES.MD`. Com esses falsos positivos fora, a categoria fica pronta para a análise de promoção `warn` -> `block` (`agent-workflow.md` 13.3); a promoção em si não faz parte desta spec.

| Camada | Arquivos | Mudança |
|---|---|---|
| Hook | `.claude/hooks/agent-audit.py` | predicado novo de `md_outside_docs` em `_assess_root` (sessão principal fora; nomes de doc por nome exato, sem diferenciar caixa; extensão `.md` sem diferenciar caixa; só arquivo novo; `.md` declarado no Files da task); `docs_write_by_implementer` usa a mesma regra de nome; helpers `file_name()`, `write_creates()`; textos de `WHY` e da docstring |
| Métricas | `.claude/hooks/agent-metrics.py` | rótulo de `md_outside_docs` em `FLAG_LABELS` |
| Testes | `hooks/tests/test_write_areas.py`, `test_design_system.py`, `test_hook_main.py`, `test_hook_process.py` | A1, A2, A3 e H14 (que fixam o comportamento desta entrada) mudam; DR10, DR13, DR16 e P-DR trocam a sessão principal por `specker`; casos MD1-MD16 |
| Agent | `.claude/agents/specker.md` | uma frase no item **Files**: um `.md` que a task cria é listado pelo caminho ou por um glob que termina em `.md` |
| Docs (fim, `docs-writer`) | `.claude/README.md`, `.claude/agent-workflow.md` (13.3, 13.5, 13.7) | needs_docs |

O config (`agent-audit.json`) não muda: nenhuma categoria nova, `md_outside_docs` continua `warn`. Sem serviço, API, banco, flag nem migração.

## Background

### O que o hook faz hoje

`_assess_root` (`agent-audit.py`, linhas 607-612):

```python
if (inside and rel.endswith(".md") and area != "docs" and (created or tool == "Write")
        and not rel.endswith(("README.md", "CLAUDE.md", "CHANGELOG.md"))
        and not (is_ds and actor == "design-director")):
    found.append("md_outside_docs")
if inside and actor in IMPLEMENTERS and (area == "docs" or Path(rel).name in DOC_FILES):
    found.append("docs_write_by_implementer")
```

`created` é `tool_response.type == "create"`; no `PreToolUse` não há `tool_response`, então o gatilho real é `tool == "Write"`, criando ou sobrescrevendo. Não há filtro de ator: a sessão principal (`actor == "main"`, payload sem `agent_id`) recebe a flag como qualquer agent.

**Comportamento conferido** (hook atual, repo git temporário no scratchpad, `evaluate_write` com `Write` e sem `tool_response`; "todos" = `main`, `subagent`, `docs-writer`, `backend-node`, `planner`):

| Alvo | Resultado | Problema |
|---|---|---|
| `PRD.md`, `CONSTRAINTS.md`, `BACKEND.md`, `.github/pull_request_template.md` | `md_outside_docs` para todos | a sessão principal cria esses arquivos legitimamente (`new-project`, `onboard`, `grill-me`) |
| `DESIGN_SYSTEM.md` | `md_outside_docs` para `main` | S5 da spec design-director: cópia do `new-project`, extração da `design-system` |
| `DEPLOY.md` | `md_outside_docs` para todos, inclusive `docs-writer` | é um `DOC_FILES`: o dono dele recebe a flag |
| `PRD.md` com `tool_response.type: update` | `md_outside_docs` | reescrever um arquivo existente não cria `.md` solto; o rótulo das métricas já diz "new .md files" |
| `MY_README.md`, `NOTCLAUDE.md`, `xCHANGELOG.md` | sem flag para todos | isenção por sufixo (entrada basename) |
| `NOTES.MD` | sem flag para todos | `endswith(".md")` diferencia caixa |
| `PRD.md` com `Edit` | sem flag | correto (Edit nunca cria) |

**Evidência nas métricas** (`~/.claude/metrics/*.jsonl`, só leitura): nesta máquina há 4 sessões, todas de 2026-11-12, 1405 registros e **nenhum** `md_outside_docs`. As escritas da sessão principal em `.md` fora da raiz de docs foram `Edit` (`DESIGN_SYSTEM.md` 5 vezes, `TASKS.md` 6 vezes), por isso sem flag; as outras foram fora do repo (memória do projeto, scratchpad), onde flags de área não valem. As sessões em que os falsos positivos aconteceram (stage H) rodaram na outra máquina e não estão aqui; o registro deles está na spec e no log da design-director:

| Fonte | Falso positivo | Ator | Classe |
|---|---|---|---|
| design-director spec, S5 e caso H14 | criar `DESIGN_SYSTEM.md` na raiz | sessão principal | arquivo de raiz do projeto |
| design-director log, Task 4 | criar `.claude/agents/design-director.md`, listado no **Files** da task | implementer (`frontend-react`, convenção S2) | `.md` declarado na spec |
| design-director spec, Design 1 | "arquivos que já existem são alterados com `Edit`, nunca reescritos com `Write`, para não gerar `md_outside_docs`" | qualquer | sobrescrita |

Os dados são poucos; o desenho sai do código e do inventário de quem cria `.md` fora da raiz de docs:

| Quem | Arquivos | Por quê |
|---|---|---|
| sessão principal, `new-project` (passo 3.1) | `CLAUDE.md`, `PRD.md`, `CONSTRAINTS.md`, `OPEN_QUESTIONS.md`, `DEPLOY.md`, `DESIGN_SYSTEM.md`; `README.md`/`CLAUDE.md` por serviço | cópia dos templates de `templates/project-root/` |
| sessão principal, `onboard` | `BACKEND.md`, `FRONTEND.md`, `MOBILE.md`, `CLAUDE.md` | passo 5 |
| sessão principal, `grill-me` | `PRD.md`, `OPEN_QUESTIONS.md` | decisões de produto confirmadas pelo usuário |
| sessão principal, `design-system` (extração) | `DESIGN_SYSTEM.md` | regra 33; subagents só pedem em `scope_requests` |
| sessão principal neste repo | `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `.claude/agent-workflow.md` | aqui `.md` é código da config |
| implementer num run | `.md` listado no **Files** da task (prompts de agent, conteúdo, templates, fixtures) | a spec declarou o arquivo |
| `docs-writer` | `README.md`, `CHANGELOG.md`, `DEPLOY.md` | `DOC_FILES`, dono declarado |
| `design-director` | `DESIGN_SYSTEM.md` | já isento (stage H) |

O texto da flag (`WHY`) fala com quem tem `needs_docs` ("documentation needs go to needs_docs"): subagents. A sessão principal não reporta `needs_docs`, roda as skills que criam esses arquivos com o usuário acompanhando, e um `block` nela seria um beco sem saída (o `what_to_do` manda pedir autorização, mas a nova tentativa seria negada de novo). Enquanto a sessão principal receber a flag, a promoção a `block` é impossível.

### Análise de promoção (13.3)

`agent-workflow.md` 13.3, item 3, e a pendência da etapa G: promover a `block`, categoria por categoria, as que os dados mostrarem sem falso positivo; candidatas `md_outside_docs`, `docs_write_by_implementer`, `backlog_write_by_other`. A entrada diz "handle in the warn->block promotion analysis": esta spec **remove as classes conhecidas de falso positivo** e deixa a categoria em `warn`. A promoção é uma decisão do usuário, com dados de uso real depois do merge (Open questions 1 e Verification), e tem uma pré-condição de segurança que esta spec não resolve (Open questions 2).

### O que entra e o que fica fora

| Entrada | Decisão | Motivo |
|---|---|---|
| [md-outside-docs-false-positive](../../backlog/refactor/2026-11-11-audit-md-outside-docs-false-positive.md) | **entra** (fonte) | - |
| [md-exemption-basename](../../backlog/refactor/2026-11-12-audit-md-exemption-basename.md) | **entra** | mesma causa raiz: o predicado de `md_outside_docs` identifica o arquivo errado. É a mesma linha, reescrita aqui; a caixa da extensão (`NOTES.MD`) é o mesmo defeito, achado nesta análise |
| `docs_write_by_implementer`: só a regra de nome | **entra** | a isenção nova compara o nome sem diferenciar caixa; se `DOC_FILES` continuasse diferenciando, um implementer criaria `readme.md` sem flag nenhuma. Uma regra de nome para as duas flags. O conjunto de atores não muda |
| [docs-write-flag-implementers-only](../../backlog/refactor/2026-11-12-audit-docs-write-flag-implementers-only.md) | fica fora | outra causa raiz (o conjunto de atores donos de `DOC_FILES` e da área de docs); estender a flag a todos menos `docs-writer` dispararia em `planner`, `specker`, `backlog-keeper` e no log do `/implement` dentro da área de docs, e a entrada pede confirmação do conjunto (Open questions 4) |
| [docs-root-declaration-unprotected](../../backlog/refactor/2026-11-13-audit-docs-root-declaration-unprotected.md) | fica fora | outra causa raiz (confiança numa entrada de política gravável por agents), sem relação com quem cria `.md`; precisa de uma escolha do usuário entre mecanismos (Open questions 2) |

## Design

### 1. Regras

| # | Regra |
|---|---|
| M1 | A sessão principal (`actor == "main"`) nunca recebe `md_outside_docs`. As outras flags dela não mudam (`backlog_write_by_other` continua) |
| M2 | Para os demais atores (agents nomeados, `subagent`), `md_outside_docs` vale para um arquivo **dentro** de uma raiz git, **fora** da raiz de docs, cujo nome termina em `.md` sem diferenciar caixa, e que a escrita **cria** |
| M3 | "Cria": `tool_response.type == "create"` (`"update"` não cria); sem `tool_response` (`PreToolUse`), um `Write` cria quando o alvo não existe; um `Write` com `tool_response` sem `type` conta como criação (conservador, igual a hoje); `Edit`, `MultiEdit` e `NotebookEdit` sem `type: create` não criam. Erro ao checar a existência conta como criação |
| M4 | Nomes de documentação isentos por nome **exato** do arquivo, sem diferenciar caixa: `README.md`, `CHANGELOG.md`, `DEPLOY.md` (os `.md` de `DOC_FILES`) e `CLAUDE.md`. `MY_README.md`, `NOTCLAUDE.md`, `README.md.md` não são isentos |
| M5 | O `design-director` continua isento só num `DESIGN_SYSTEM.md` (inalterado) |
| M6 | Ator de escopo fixo (implementers, `quality-fixer`, `test-writer`) com run ativo: isento quando o caminho casa com um padrão **markdown** das tasks em execução, isto é, uma entrada de `allowed_paths` ou um alvo de `approved_scope` aprovado cujo nome termina em `.md` sem diferenciar caixa (`.claude/agents/x.md`, `content/*.md`, `**/*.MD`). Um glob amplo (`services/api/**`) não isenta; `ALWAYS_ALLOWED` não conta; alvos que são `DESIGN_SYSTEM.md` continuam descartados |
| M7 | `docs_write_by_implementer` identifica `DOC_FILES` pelo mesmo nome exato sem diferenciar caixa (`Readme.md`, `.ENV.EXAMPLE` passam a contar). Conjunto de atores inalterado (`IMPLEMENTERS`) |
| M8 | Fora de toda raiz git, flags de área continuam sem valer; registro, ações do config, demais flags e o comportamento das outras categorias não mudam |

*Adendo 2026-11-13:* M2 deixa de valer para o `docs-writer`, que fica isento de `md_outside_docs` em qualquer `.md` (regra M9). Ver [Adendo 2026-11-13](#adendo-2026-11-13---decisões-do-usuário-na-aprovação).

### 2. `.claude/hooks/agent-audit.py`

**Constantes e helpers**, ao lado de `DOC_FILES` e `is_design_system`:

```python
DOC_FILE_NAMES = frozenset(n.casefold() for n in DOC_FILES)
# md_outside_docs: known documentation names, exempt by exact file name (any case); their ownership
# is judged by other flags (docs_write_by_implementer; CLAUDE.md has none yet).
MD_DOC_NAMES = frozenset(n for n in DOC_FILE_NAMES if n.endswith(".md")) | {"claude.md"}
# The main session creates root project files (PRD.md, DESIGN_SYSTEM.md...) with the user: never md_outside_docs.
MD_FREE_ACTORS = frozenset({"main"})


def file_name(path: str) -> str:
    """Case-folded last component of a path or glob (`\\` read as `/`)."""
    return PurePosixPath(str(path).replace("\\", "/")).name.casefold()


def write_creates(tool: str, response) -> bool | None:
    """Whether the write creates the file: True/False when the payload says so, None when only the
    target's existence can tell (a Write without tool_response, that is PreToolUse)."""
    if isinstance(response, dict) and response.get("type") in ("create", "update"):
        return response["type"] == "create"
    if tool != "Write":
        return False
    return None if response is None else True
```

`is_design_system` passa a usar `file_name(path) == DESIGN_SYSTEM_NAME` (mesmo resultado).

**`evaluate_write`**: `created = write_creates(tool, response)` no lugar de `isinstance(response, dict) and response.get("type") == "create"`; o valor (agora `bool | None`) vai para `_assess_root`. A docstring ganha uma frase: "`md_outside_docs` is for agents creating a stray .md (see `_assess_root`)".

**`_assess_root(..., created: bool | None, ...)`**: o cálculo do escopo do run sobe para antes das flags, para que o mesmo `allowed` sirva às duas coisas:

```python
scoped_run = bool(run) and (actor in IMPLEMENTERS or actor in {"quality-fixer", "test-writer"})
allowed: list[str] = []
if scoped_run:
    by_task = run.get("allowed_paths") or {}
    allowed = [p for k in keys for p in by_task.get(k, [])]
    allowed += [ ... approved_scope, como hoje, sem DESIGN_SYSTEM.md ... ]
declared_md = [p for p in allowed if file_name(str(p).strip().strip("`")).endswith(".md")]
```

e, por forma julgada:

```python
name = file_name(rel)
if (inside and actor not in MD_FREE_ACTORS and area != "docs" and name.endswith(".md")
        and name not in MD_DOC_NAMES
        and not (is_ds and actor == "design-director")
        and not (declared_md and matches(rel, declared_md))
        and _creates(form, created)):
    found.append("md_outside_docs")
if inside and actor in IMPLEMENTERS and (area == "docs" or name in DOC_FILE_NAMES):
    found.append("docs_write_by_implementer")
```

com

```python
def _creates(form: Path, created: bool | None) -> bool:
    if created is not None:
        return created
    try:
        return not form.exists()
    except Exception:
        return True  # cannot tell: judge as a new file
```

`_creates` é o último termo: o `stat` só roda quando todo o resto já sinalizaria. O bloco de `out_of_scope_write` usa o `allowed` já calculado (comportamento igual; `in_scope`, `scratch` e o registro não mudam). Com `..` no caminho, as formas resolvida e léxica são julgadas como hoje e cada uma faz o próprio `exists()`.

**`WHY["md_outside_docs"]`** (o lembrete só chega a agents agora):

> agents do not create new .md files (notes, summaries, reports) outside the project's docs root (docs/, or the "- docs root:" line of the root CLAUDE.md ## Workflow); documentation needs go to needs_docs, and a markdown file the task really needs must be in its Files or come through a scope_requests entry

**Docstring do módulo**: no item das escritas, "new .md files created by agents outside the docs root (not by the main session, not the known doc names, not a markdown path in the task's Files)".

**Comportamento resultante** (sem run, salvo indicação; `Write` sem `tool_response`, alvo inexistente):

| Ator | Alvo | Hoje | Depois |
|---|---|---|---|
| `main` | `PRD.md`, `DESIGN_SYSTEM.md`, `BACKEND.md`, `.claude/agents/x.md`, `NOTES.md` | `md_outside_docs` | sem flag (M1) |
| `main` | `docs/backlog/x.md` | `backlog_write_by_other` | igual |
| `backend-node`, `planner`, `subagent` | `NOTES.md`, `PRD.md` | `md_outside_docs` | igual |
| `backend-node` | `NOTES.MD`, `MY_README.md` | sem flag | `md_outside_docs` (M2, M4) |
| `docs-writer` | `DEPLOY.md` | `md_outside_docs` | sem flag (M4) |
| `backend-node` | `Readme.md` | sem flag | `docs_write_by_implementer` (M7) |
| `planner` | `NOTES.md` que já existe; ou `tool_response.type: update` | `md_outside_docs` | sem flag (M3) |
| `frontend-react`, run com Files `.claude/agents/x.md` | `.claude/agents/x.md` | `md_outside_docs` | sem flag (M6) |
| `frontend-react`, run com Files `services/web/**` | `services/web/NOTES.md` | `md_outside_docs` | igual (glob amplo) |
| `backend-node` | `DESIGN_SYSTEM.md` (`type: create`) | `design_system_write_by_other`, `md_outside_docs` | igual |
| `design-director` | `NOTES.md` | deny `design_director_write_outside` + `md_outside_docs` | igual |

### 3. `.claude/hooks/agent-metrics.py`

`FLAG_LABELS["md_outside_docs"]` = `"new .md files created by agents outside the docs root, not in the task's Files (target 0)"`. Nada mais muda no relatório.

### 4. `.claude/agents/specker.md`

No item **Files** da seção **The spec** (Implementation order), depois de "Cover the task's own folders, not the whole service;", uma frase:

> A markdown file outside the docs root that the task creates is listed by its path or by a glob ending in `.md` (`content/*.md`); a broader glob does not cover it for the hook's `md_outside_docs`.

### 5. Segurança, privacidade e observabilidade

- **Sessão principal sem lembrete**: ela já é livre em `DESIGN_SYSTEM.md` e não tem `allowed_paths`; age com o usuário acompanhando. M1 não concede capacidade nova (a flag é `warn`), e toda escrita dela continua registrada com `actor`, `rel`, `area` e `tool`: uma análise posterior acha qualquer `.md` criado por ela sem precisar da flag.
- **Isenção por Files (M6)**: depende do run state (`.claude/runs/<slug>.json`), a mesma confiança que `out_of_scope_write` já tem; não amplia nada além do que a task já pode escrever. Um agent que reescreva o run state é o bug aberto [audit-hook-self-protection](../../backlog/bugs/2026-11-11-audit-hook-self-protection.md), fora do escopo.
- **Declaração da raiz de docs**: M2 depende de `area`, que depende da linha `docs root`. A fraqueza dessa linha (entrada declaration-unprotected) não muda aqui, e precisa ser resolvida antes de promover qualquer flag de área a `block` (Open questions 2).
- **Privacidade**: nenhum campo novo no registro; o `exists()` não lê conteúdo.
- **Fail-open**: `write_creates` e `file_name` não levantam com entradas do payload; `_creates` captura qualquer erro; qualquer outra exceção cai no `except` atual de `evaluate_write`.
- **Latência**: no máximo um `stat` por forma, só em `PreToolUse` de `Write` de um agent num `.md` que já seria sinalizado.

### 6. Rollout e reversão

Sem flag: `~/.claude/hooks` aponta para `.claude/hooks/`, então a regra vale na próxima chamada depois do merge. Como `md_outside_docs` e `docs_write_by_implementer` são `warn`, o pior efeito de um erro é um lembrete a mais ou a menos e uma linha nas métricas. Reversão: `git revert` dos commits das tasks; não há estado nem config.

## Alternatives considered

### Sessão principal

| Opção | Corretude e robustez | Simplicidade e manutenção | Decisão |
|---|---|---|---|
| **Fora da flag (M1)** | cobre todas as classes (raiz do projeto, monorepo, `.md` de config neste repo, skills futuras); a flag fica com o público do texto dela | uma condição; mesmo tratamento que `design_system_write_by_other` já dá à sessão principal | **escolhida** |
| Lista de nomes de raiz liberados para a sessão principal (`PRD.md`, `CONSTRAINTS.md`, `OPEN_QUESTIONS.md`, `DESIGN_SYSTEM.md`, `BACKEND.md`...) | não cobre `.claude/agents/*.md` neste repo, `apps/web/PRD.md` num monorepo nem nomes novos de skills; continua avisando em trabalho legítimo | acopla o hook aos templates; deriva a cada template novo | rejeitada |
| Ler a lista em tempo de execução de `~/.claude/templates/project-root/*.md` | mesmo buraco da lista, e um hook que depende de arquivos fora do repo julgado | frágil | rejeitada |
| Categoria própria em `audit` para a sessão principal (`md_outside_docs_main`) | guarda o dado, mas o registro de toda escrita já guarda | categoria, rótulo e config a mais por zero informação nova | rejeitada |
| Manter a flag na sessão principal | impede a promoção (um `block` nela não tem saída) | - | rejeitada |

### `.md` que a task declara

| Opção | Por que |
|---|---|
| **Padrão markdown de `allowed_paths`/`approved_scope` (M6)** (escolhida) | a spec declarou o arquivo; um glob amplo não vira licença para `NOTES.md`; reaproveita `matches()` |
| Qualquer caminho em escopo isenta | `services/api/**` liberaria `services/api/NOTES.md`, exatamente o que a flag quer pegar |
| Só `approved_scope` | obrigaria um pedido de escopo para todo `.md` que a spec já listou |
| Nada (falso positivo aceito) | foi o caso da Task 4 da design-director; com `block`, a task seria negada |

### Sobrescrita

| Opção | Por que |
|---|---|
| **Só arquivo novo (M3)** (escolhida) | é o que o rótulo das métricas já promete; tira a regra "nunca reescreva com `Write`" dos agents; o `Edit` nunca foi sinalizado |
| `Write` sempre sinaliza (hoje) | falso positivo em toda reescrita completa de um `.md` legítimo; com `block`, negaria trabalho correto |
| Existência também no `PostToolUse` | no `PostToolUse` o arquivo sempre existe; o `type` do `tool_response` é a fonte certa (conferido no Claude Code 2.1.323: o resultado do `Write` traz `type: "update"`/`"create"` e `filePath`) |

### Escopo do pacote

| Opção | Por que |
|---|---|
| **Fonte + basename + regra de nome de `DOC_FILES`** (escolhido) | uma causa raiz: o predicado identifica o arquivo e o ator errados; tudo na mesma linha de `_assess_root` |
| Juntar `docs-write-flag-implementers-only` | outra decisão (quem é dono de doc), com risco próprio de falso positivo na área de docs; a regra de nome feita aqui deixa aquela spec só com o conjunto de atores |
| Juntar `docs-root-declaration-unprotected` | outro mecanismo (de onde vem a política, HEAD x árvore de trabalho, flag de ator no `CLAUDE.md`), com escolha do usuário pendente; misturaria segurança de política com classificação de escrita |

## Trade-offs

- **`DEPLOY.md` isento para todos**: `quality-fixer`, `test-writer`, `planner`, `specker` e `subagent` que criem um `DEPLOY.md` deixam de receber `md_outside_docs`. É a mesma lacuna que `README.md` e `CHANGELOG.md` já têm (nenhuma flag para esses atores); a entrada docs-write-flag-implementers-only a fecha para os três nomes de uma vez.
- **Sessão principal sem lembrete**: um `NOTES.md` criado por ela passa em silêncio. Aceito: a regra global vale por instrução, o usuário vê a escrita, e o registro existe.
- **Sobrescrita não sinalizada**: um agent que troque o conteúdo de um `.md` existente por uma nota não recebe a flag. Aceito: a escrita fora do escopo de um run já gera `out_of_scope_write`, e o `Edit` nunca foi sinalizado.
- **Corrida no `PreToolUse`**: a existência é lida antes do `Write`; um arquivo criado entre o `PreToolUse` e a escrita muda só o lembrete. O `PostToolUse` decide pelo `type`.
- **`.markdown` e `.mdx`** continuam fora (`.mdx` é código de componente em projetos React; `.markdown` não aparece em nenhum fluxo).
- **Mais flags por nome**: `Readme.md` de implementer passa a gerar `docs_write_by_implementer`, e `NOTES.MD`/`MY_README.md` de agent passam a gerar `md_outside_docs`. É o efeito pretendido.

*Adendo 2026-11-13:* o `docs-writer` também fica sem lembrete em qualquer `.md` (M9); trade-off aceito no [Adendo 2026-11-13](#adendo-2026-11-13---decisões-do-usuário-na-aprovação).

## Testing

Suite: `claude-hooks` (tabela `Test suites` do `CLAUDE.md` da raiz; hoje 237 testes). "flags" = `evaluate_write(...)["flags"]`; "pre" = saída do `PreToolUse` em `enforce` com `TEST_CONFIG`; "post" = flags do registro do `PostToolUse`. Salvo indicação: `Write`, sem `tool_response`, alvo inexistente no repo temporário, sem run. Classes e testes novos ou alterados citam esta spec na docstring (não mais a entrada do backlog).

### Testes que mudam

| Teste | Mudança |
|---|---|
| `test_write_areas.py` A1 `test_a1_main_write_of_md_at_root_is_md_outside_docs` | renomeado para `test_a1_main_write_of_md_at_root_has_no_md_flag`: `main` em `notes.md` -> sem `md_outside_docs`, `area: code` (M1) |
| A2 | ator `backend-node` (a asserção "Edit de `.md` existente sem flag" só tem sentido para quem recebe a flag) |
| A3 | ator `test-writer` e `docs-writer` (com `main` a asserção passaria à toa); nomes `README.md`, `services/api/README.md`, `CLAUDE.md`, `CHANGELOG.md`, `DEPLOY.md`, `readme.md`, `Changelog.MD`, `services/api/claude.md` -> sem `md_outside_docs` (M4) |
| DR10, DR13 (`DocsRootEffect`) | ator `specker` nas escritas que esperam `md_outside_docs`; asserções iguais (o teste é sobre a raiz declarada, não sobre o ator) |
| DR16, caso "old docs_roots key ignored" | `post_flags` com `actor="specker"` |
| `test_hook_process.py` P-DR | ator `specker` nos dois subtests |
| `test_design_system.py` H14 | `main` Write `type: create` em `DESIGN_SYSTEM.md` -> pre silencioso, post `[]` (M1); docstring da classe deixa de citar a entrada |

H3, H13, P6 (H3) e K9 não mudam: os atores deles continuam recebendo `md_outside_docs`.

### `test_write_areas.py` - `MdOutsideDocs` (nova)

| # | Caso | Esperado |
|---|---|---|
| MD1 | `subagent`, `backend-node`, `docs-writer`, `planner`, `specker`, `quality-fixer` em `notes.md`, `PRD.md`, `services/api/NOTES.md` | `md_outside_docs` em todos (M2) |
| MD2 | `main` em `PRD.md`, `CONSTRAINTS.md`, `OPEN_QUESTIONS.md`, `DESIGN_SYSTEM.md`, `BACKEND.md`, `NOTES.md`, `.claude/agents/x.md`, `apps/web/PRD.md`; e `main` em `docs/backlog/x.md` | sem `md_outside_docs`; o último com `backlog_write_by_other` (M1, M8) |
| MD3 | `backend-node` em `MY_README.md`, `NOTCLAUDE.md`, `xCHANGELOG.md`, `README.md.md`, `PREDEPLOY.md`, `services/api/MY_CLAUDE.md` | `md_outside_docs`; nenhum com `docs_write_by_implementer` (M4, entrada basename) |
| MD4 | `backend-node` em `NOTES.MD`, `notes.Md`; e em `x.mdx`, `x.markdown` | os dois primeiros com `md_outside_docs`; os dois últimos sem (M2) |
| MD5 | `planner` em `notes.md` com `tool_response` `{"type": "create"}`, `{"type": "update"}`, `{"filePath": "..."}` (sem `type`) | flag, sem flag, flag (M3) |
| MD6 | `planner` em `notes.md` sem `tool_response`: arquivo existe; arquivo não existe | sem flag; flag (M3) |
| MD7 | `planner`: `Edit` sem `tool_response`; `Edit` com `{"type": "create"}`; `MultiEdit` sem `tool_response`, em `notes.md` inexistente | sem flag; flag; sem flag (M3) |
| MD8 | `planner` em `notes.md` inexistente com `Path.exists` levantando `PermissionError` (mock) | sem exceção; `md_outside_docs` (M3, falha conservadora) |
| MD9 | `planner` em `link.md` (symlink para `real.md`, que existe no repo); e em `dangling.md` (symlink para `missing.md`, inexistente, no repo) | sem flag; flag com `rel: missing.md` (a forma resolvida decide) |
| MD10 | `frontend-react`, run com `allowed_paths` `{"1": [".claude/agents/x.md", "services/web/content/*.md", "`kb2/GUIDE.MD`", "services/api/**"]}`: alvos `.claude/agents/x.md`, `services/web/content/post.md`, `kb2/GUIDE.MD`, `services/api/NOTES.md` | os três primeiros sem `md_outside_docs` e sem `out_of_scope_write`; o último com `md_outside_docs` e sem `out_of_scope_write` (M6) |
| MD11 | `frontend-react`, run com `allowed_paths` `{"1": ["services/api/**"]}` e `approved_scope`: `services/api/NOTES.md` aprovado na task 1; `services/api/OTHER.md` com `decision: denied`; `services/api/T2.md` aprovado na task 2 (fora de `running_tasks`) | primeiro sem `md_outside_docs`; os outros dois com (M6) |
| MD12 | mesmo run de MD10: `docs-writer` e `planner` em `.claude/agents/x.md`; e `frontend-react` em `.claude/agents/x.md` sem run (`remove_run()`) | `md_outside_docs` nos três (M6 só para escopo fixo com run) |
| MD13 | `frontend-react`, run com `approved_scope` aprovado para `DESIGN_SYSTEM.md` e `allowed_paths` `["services/web/**"]`, alvo `DESIGN_SYSTEM.md` `type: create` | `design_system_write_by_other`, `md_outside_docs`, `out_of_scope_write` (alvo DS continua descartado) |
| MD14 | `backend-node` em `Readme.md`, `services/api/readme.md`, `changelog.md`, `Deploy.md`, `.ENV.EXAMPLE`; `docs-writer` e `main` nos mesmos | `docs_write_by_implementer` só para `backend-node` (M7) |
| MD15 | helpers: `file_name()` com `a\\B.MD`, `content/*.md`, `""`; `write_creates()` para cada linha da M3 | `"b.md"`, `"*.md"`, `""`; `True`/`False`/`None` conforme M3, sem exceção com `response` de tipo inesperado (`[]`, `"x"`, `{"type": 3}`) |

`test_area_flags_do_not_apply_outside` (`test_write_scope.py`) segue cobrindo M8 sem mudança.

*Adendo 2026-11-13:* MD1 e MD12 tiram o `docs-writer` dos atores sinalizados; casos novos MD17 e MD18 cobrem M9. Ver [Adendo 2026-11-13](#adendo-2026-11-13---decisões-do-usuário-na-aprovação).

### `test_hook_main.py` - `MdOutsideDocsPayload` (nova, por `call_main`)

| # | Caso | Esperado |
|---|---|---|
| MD16a | `PreToolUse` Write: `main` em `PRD.md`; `planner` em `NOTES.md` inexistente; `planner` em `NOTES.md` criado antes no disco | silencioso; warn `md_outside_docs` com o texto novo (contém "Files"); silencioso |
| MD16b | `PostToolUse` Write de `planner` em `NOTES.md` com `tool_response` `{"type": "update"}` e `{"type": "create"}` | registros com flags `[]` e `["md_outside_docs"]` |
| MD16c | `frontend-react`, run com `allowed_paths` `{"1": [".claude/agents/x.md"]}`: pre e post de Write em `.claude/agents/x.md` (`type: create`) | silencioso; flags `[]` |

### `test_hook_process.py` - `ProcessContract` (caso novo)

| # | Caso | Esperado |
|---|---|---|
| P-MD | hook como processo real: `main` Write em `PRD.md`; `backend-node` Write em `NOTES.md` | silencioso; uma linha JSON com warn `md_outside_docs`; exit 0 e stderr vazio nos dois |

### Regras -> testes

| Regra | Testes |
|---|---|
| M1 sessão principal fora | A1, H14, MD2, MD16a, P-MD |
| M2 agents, `.md` sem caixa, dentro, fora da raiz de docs | MD1, MD4, DR10, DR13, DR16, P-DR, P-MD |
| M3 só arquivo novo | A2, MD5, MD6, MD7, MD8, MD9, MD15, MD16a, MD16b |
| M4 nomes exatos | A3, MD3 |
| M5 `design-director` | H1-H28 sem mudança (H3, H12, H18, H20) |
| M6 `.md` declarado no Files | MD10, MD11, MD12, MD13, MD16c |
| M7 nome de `DOC_FILES` sem caixa | MD14, A6 sem mudança |
| M8 o resto não muda | `test_area_flags_do_not_apply_outside`, H13, K9, suite atual inteira verde |

## Implementation order

### Task 1 - md_outside_docs para agents, por nome exato e só para arquivo novo

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/agent-metrics.py`, `.claude/hooks/tests/test_write_areas.py`, `.claude/hooks/tests/test_design_system.py`, `.claude/hooks/tests/test_hook_main.py`, `.claude/hooks/tests/test_hook_process.py`
- **Depends on:** -
- **Done when:** `_assess_root` e `evaluate_write` seguem a Design, seção 2 (`DOC_FILE_NAMES`, `MD_DOC_NAMES`, `MD_FREE_ACTORS`, `file_name()`, `write_creates()`, `_creates()`, `allowed` calculado antes das flags), com `WHY` e docstring novos; `FLAG_LABELS["md_outside_docs"]` segue a seção 3; os testes da tabela "Testes que mudam" foram alterados e MD1-MD16 e P-MD passam (um `subTest` por valor onde a tabela lista vários); `git grep -n 'endswith(("README.md"\|md-outside-docs-false-positive' -- .claude/hooks` sem ocorrências; `python3 -I -B -m unittest discover -s .claude/hooks/tests -t .claude/hooks` verde; `agent-audit.json` intacto; nenhum arquivo fora da lista muda. *Adendo 2026-11-13:* vale também o **Done when** do adendo (M9, MD17, MD18, MD1 e MD12 ajustados)
- **Status:** done

### Task 2 - specker lista os .md que a task cria

- **Stack:** frontend-react
- **Files:** `.claude/agents/specker.md`
- **Depends on:** Task 1
- **Done when:** o item **Files** de `.claude/agents/specker.md` tem a frase da Design, seção 4, logo depois de "Cover the task's own folders, not the whole service;"; frontmatter e o resto do arquivo intactos (`git diff --stat` mostra uma linha alterada ou acrescentada); nenhum arquivo fora da lista muda
- **Status:** done

(Stack de markdown segue a convenção S2 da spec design-director.)

## Verification

No fim do run, pelo `test-runner`:

1. Suite `claude-hooks` inteira, verde (237 atuais, ajustados, mais os novos).
2. `git grep -n 'md-outside-docs-false-positive\|endswith(("README.md"' -- .claude/hooks` sem ocorrências.
3. `git diff --stat main -- .claude/hooks/agent-audit.json .claude/settings.json` vazio.

Sem runtime local nem UI: não há request nem check visual. Checks manuais do usuário, depois do merge (o hook vivo muda na hora):

- Na próxima vez que a sessão principal criar um arquivo de raiz (`/new-project`, `onboard`, extração da `design-system`) ou um `.md` da config neste repo, nenhum lembrete `md_outside_docs` aparece, e `python3 ~/.claude/hooks/agent-metrics.py` não lista `md_outside_docs` com ator `main`.
- No próximo `/implement` com uma task que cria um `.md` listado no **Files**, nenhum `md_outside_docs` no relatório.
- Para a análise de promoção (Open questions 1): depois de algumas sessões de uso real nas duas máquinas, `agent-metrics.py --since <data do merge> --merge`, seção `## Flags`: cada `md_outside_docs` restante deve ser uma violação real.

**needs_docs** (para o `docs-writer`, no fim):

- `.claude/README.md`, seção dos hooks: definição de `md_outside_docs` (só agents; arquivo novo; nomes isentos por nome exato sem caixa: `README.md`, `CHANGELOG.md`, `DEPLOY.md`, `CLAUDE.md`; `.md` declarado no Files da task) e a regra de nome de `DOC_FILES`.
- `.claude/agent-workflow.md`: 13.3, item 4 (ou uma nota): o falso positivo S5 foi resolvido por esta spec e `md_outside_docs` está pronta para a análise de promoção; 13.5, linha "sessão principal" da tabela: livre também de `md_outside_docs`; 13.7, lista de flags de área: `md_outside_docs` não se aplica à sessão principal.

## Open questions

*Adendo 2026-11-13:* as cinco perguntas foram respondidas pelo usuário na aprovação; a pergunta 3 mudou o desenho (M9). Ver [Adendo 2026-11-13](#adendo-2026-11-13---decisões-do-usuário-na-aprovação).

1. **Promover `md_outside_docs` a `block`** (não bloqueia esta spec). Opções: (a) promover junto com esta spec; (b) promover depois, com os dados do uso real (Verification) e depois de resolver a pergunta 2; (c) manter em `warn`. Recomendação: (b). A regra 13.3 pede dados sem falso positivo, e as sessões desta máquina não têm nenhum registro da flag para confirmar; as classes conhecidas saem com esta spec, mas só o uso real mostra se há outras.
2. **Declaração da raiz de docs sem proteção** ([entrada](../../backlog/refactor/2026-11-13-audit-docs-root-declaration-unprotected.md); review automático de segurança do commit `cc05e36`: MEDIUM; `security-reviewer` anterior: low). Fica fora desta spec porque a causa raiz é outra (a política vem de um arquivo do repo que agents podem gravar e que o hook relê a cada chamada) e porque pede uma escolha de mecanismo. Evidência nova: nas métricas de hoje, `backend-python` editou o `CLAUDE.md` da raiz de um projeto sem flag nenhuma. Opções: (a) flag nova para escrita no `CLAUDE.md` da raiz por quem não é `main`, `planner`, `specker` ou `docs-writer` (barata, mas os três agents autorizados ainda podem mover a raiz, e a flag não vê o conteúdo); (b) fixar a raiz no começo do run, no run state (só cobre runs; fora deles o hook não tem estado); (c) proteger sempre `docs/backlog/`, além da raiz declarada; (d) só aceitar a declaração de fonte confiável: ler a linha do `CLAUDE.md` commitado (`HEAD`, um `git show` por avaliação) e, sem `HEAD` ou sem declaração commitada, da árvore de trabalho; mudar a raiz passa a exigir um commit, que já exige o sim do usuário (`git_commit` em `ask`). Recomendação: **ser a próxima spec**, com (d) + (c): a área de docs (que afrouxa `md_outside_docs`) vem só do `HEAD`, e a proteção do backlog vale para a união de `HEAD`, árvore de trabalho e `docs/`, de modo que uma edição não commitada só acrescenta flags; (a) como complemento opcional. Ela é pré-condição para promover qualquer flag de área (`md_outside_docs`, `docs_write_by_implementer`, `backlog_write_by_other`) a `block`, porque aí mover a raiz contornaria uma negação.
3. **`docs-writer` e `.md` de documentação fora dos nomes conhecidos** (ex.: criar `services/api/API.md`). Opções: (a) como desenhado, isento só pelos nomes de M4; (b) isento de `md_outside_docs` em qualquer `.md`; (c) isento também em `**/docs/**` aninhado. Recomendação: (a); o `docs-writer` raramente cria arquivo novo fora dos nomes conhecidos, e (b) tiraria a guarda contra `SUMMARY.md` justo do agent que escreve prosa. Reavaliar se as métricas mostrarem o caso.
4. **`docs_write_by_implementer` só para implementers** ([entrada](../../backlog/refactor/2026-11-12-audit-docs-write-flag-implementers-only.md)). Fica fora (outra causa raiz). Com a regra de nome feita aqui, aquela spec só decide o conjunto de atores. Opções: (a) spec própria depois da pergunta 2, cobrindo `DOC_FILES` por todos menos `docs-writer` e `main` e mantendo a área de docs com seus escritores (`planner`, `specker`, `backlog-keeper`, `main`); (b) juntar aqui. Recomendação: (a).
5. **Entradas de refactor.** Opções: (a) o `backlog-keeper` mantém `Proposed` nas duas entradas que esta spec cobre (false-positive e basename), acrescenta o link desta spec e preenche "Proposed change" com o resumo de M1-M7; as duas vão a `In progress` quando o `/implement` começar; (b) `In progress` já agora. Recomendação: (a).

## Adendo 2026-11-13 - decisões do usuário na aprovação

- **Origem**: respostas do usuário às Open questions 1-5, na aprovação desta spec (2026-11-13).
- **Afeta**: Design, seção 1 (regra nova M9) e seção 2 (`MD_FREE_ACTORS`); Trade-offs; Testing (MD1, MD12, casos novos MD17 e MD18, Regras -> testes); Task 1 (**Done when**); Open questions. O texto original fica como registro; onde divergir, vale este adendo.
- **Não muda**: M1 e M3-M8, os demais casos de teste, a Task 2, o config (`md_outside_docs` continua `warn`).

### Open questions resolvidas

1. Promoção de `md_outside_docs` a `block`: depois, com dados do uso real, e só depois de resolvida a pergunta 2. Fora desta spec.
2. Declaração da raiz de docs: próxima spec, com (d) + (c) (declaração lida do `HEAD`; backlog protegido em toda árvore candidata). Fora desta spec.
3. `docs-writer` isento de `md_outside_docs` em **qualquer** `.md` (opção b, diferente da recomendação): regra M9 abaixo.
4. `docs-write-flag-implementers-only`: spec própria, depois. Fora desta spec.
5. Entradas de refactor (false-positive e basename): ficam `Proposed` com o link desta spec e vão a `In progress` quando o `/implement` começar.

### Regra M9

| # | Regra |
|---|---|
| M9 | O `docs-writer` nunca recebe `md_outside_docs`, em qualquer `.md` e em qualquer caminho, como a sessão principal (M1). As outras flags dele não mudam: `design_system_write_by_other` num `DESIGN_SYSTEM.md` e `backlog_write_by_other` em `<docs root>backlog/` continuam |

M2 passa a valer para os demais atores, exceto a sessão principal e o `docs-writer`. Com M9, a isenção de `DEPLOY.md` por nome (M4) deixa de ser necessária para o `docs-writer`, mas M4 fica igual (vale para os outros agents).

**Código** (Design, seção 2): `MD_FREE_ACTORS = frozenset({"main", "docs-writer"})`, com o comentário trocado para "Never md_outside_docs: the main session creates root project files with the user; docs-writer is where needs_docs go." Nada mais muda no predicado.

**Trade-off aceito**: um `SUMMARY.md` ou `NOTES.md` criado pelo `docs-writer` fora da raiz de docs passa sem lembrete; o contrato do agent continua proibindo, e o registro da escrita guarda `actor` e `rel`.

### Testes

| # | Mudança |
|---|---|
| MD1 | sai o `docs-writer` da lista de atores; ficam `subagent`, `backend-node`, `planner`, `specker`, `quality-fixer` com `md_outside_docs` |
| MD12 | sai o `docs-writer`; `planner` no run e `frontend-react` sem run em `.claude/agents/x.md` continuam com `md_outside_docs` |
| MD17 (novo, `test_write_areas.py`, `MdOutsideDocs`) | `docs-writer` em `NOTES.md`, `SUMMARY.MD`, `services/api/API.md`, `PRD.md` (sem run e com o run de MD10) -> sem `md_outside_docs`; `planner` e `backend-node` nos mesmos alvos, sem run -> `md_outside_docs`; `docs-writer` Write `type: create` em `DESIGN_SYSTEM.md` -> `["design_system_write_by_other"]` (sem `md_outside_docs`); `docs-writer` em `docs/backlog/x.md` -> `backlog_write_by_other` |
| MD18 (novo, `test_hook_main.py`, `MdOutsideDocsPayload`) | `PreToolUse` Write do `docs-writer` em `NOTES.md` inexistente -> silencioso; `PostToolUse` com `type: create` -> flags `[]`; o mesmo par para `planner` -> warn `md_outside_docs` e `["md_outside_docs"]` |

Regras -> testes, linha nova: **M9 `docs-writer` fora** -> MD17, MD18. A linha de M2 ganha MD1 (ajustado).

### Task 1 - Done when (complemento)

Além do **Done when** original: `MD_FREE_ACTORS` contém `main` e `docs-writer`; MD1 e MD12 seguem a tabela acima; MD17 e MD18 passam; a suite `claude-hooks` inteira verde. `Files` não muda (os testes novos ficam em `test_write_areas.py` e `test_hook_main.py`, já na lista).

### needs_docs (complementa o da Verification)

Onde o `.claude/README.md` e o `agent-workflow.md` (13.5, 13.7) descreverem `md_outside_docs`, citar que a sessão principal e o `docs-writer` não recebem a flag.
