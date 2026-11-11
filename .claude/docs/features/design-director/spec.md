# design-director - criação da direção visual (etapa H)

- **Date:** 2026-11-11
- **Status:** Implemented
- **Plan:** [agent-workflow.md, seção 15.1 "Etapa H - `design-director`"](../../../agent-workflow.md#151-etapa-h---design-director-adendo-2026-11-11) (Status: Approved, 2026-11-11; decisão D22 a-j, regras 1-34). Não há `plan.md` nesta pasta: o plan não é copiado para cá.
- **Implementation log:** [log.md](log.md) (criado pelo `/implement` na primeira task)

## Summary

A etapa H dá um dono à **criação** do `DESIGN_SYSTEM.md` e tira da config a dependência do plugin `frontend-design`, que está desligado. Tudo muda dentro de `~/dotfiles/.claude/` (a config global, ligada a `~/.claude` por symlink peça a peça). Não há serviço, API nem banco. As camadas que mudam:

| Camada | Arquivos | Mudança |
|---|---|---|
| Hook (Python) | `hooks/agent-audit.py`, `hooks/agent-audit.json`, `hooks/agent-metrics.py` | proteção de todo `DESIGN_SYSTEM.md` pelo nome; isenção de `md_outside_docs` para o `design-director` nesse arquivo; categorias novas `design_system_write_by_other` (`warn`) e `design_director_write_outside` (`block`); alvos de `approved_scope` que são um `DESIGN_SYSTEM.md` fora dos caminhos permitidos; linha calculada de escritas do `design-director` fora desse arquivo |
| Template | `templates/project-root/DESIGN_SYSTEM.md` | comentário do topo (criação x manutenção); seção nova `Layout concept`; tabela `Font family` com origem e licença; light e dark sempre |
| Agent | `agents/design-director.md` (novo) | ciclo de rodadas via `needs_input`, regras de direção, contraste, tipografia, escrita restrita e report YAML |
| Skills | `skills/design-system/SKILL.md`, `skills/new-project/SKILL.md`, `skills/implement/SKILL.md` | `design-system` só com a manutenção e a oferta do agent; pergunta no `new-project`; `scope_requests` sobre o `DESIGN_SYSTEM.md` tratados pela sessão principal no `implement` |
| Instruções | `CLAUDE.md` (global), `templates/node-ts-react/CLAUDE.md`, `templates/react-native/CLAUDE.md` | linha nova no Workflow e bullet de `scope_requests`; referências ao `frontend-design` trocadas pela divisão criação x manutenção |
| Settings | `settings.json` | sai `frontend-design@claude-plugins-official` de `enabledPlugins` |

`README.md` e `agent-workflow.md` ficam com o `docs-writer`, no fim (Design, seção 11).

## Background

**Decisões do plan que esta spec implementa** (15.1): D22 a-j e as regras 1-34. As que pesam no desenho técnico:

- D22 (e) e regras 28-30: o agent escreve só `<raiz>/DESIGN_SYSTEM.md`; tools `Read, Grep, Glob, Write, Edit`, sem `Bash`; no hook, isenção de `md_outside_docs` só para esse caminho e categoria nova `design_system_write_by_other` em `warn`.
- D22 (f): `model: opus`, `effort: high`, `skills: [design-system]`, description fixa.
- Regras 7, 8 e 29: `scope_requests` sobre o `DESIGN_SYSTEM.md` da raiz são uma exceção ao passo 5 de 13.4.
- D22 (h), (i), (j): seção `Layout concept`, só fontes com licença aberta ou do sistema, com a origem registrada, e light e dark sempre.

**Decisões tomadas com o usuário em 2026-11-11, depois do plan** (respostas às perguntas da primeira rodada desta spec):

| # | Decisão |
|---|---|
| S1 | O tratamento dos `scope_requests` sobre o `DESIGN_SYSTEM.md` da raiz (regras 7, 8 e 29) vai numa linha do passo 2 de `skills/implement/SKILL.md` e, para trabalho fora de um run, na seção Workflow do `CLAUDE.md` global. Isso **acrescenta `skills/implement/SKILL.md` aos arquivos da etapa H** (a tabela de arquivos da 15.1 é atualizada pelo `docs-writer`) |
| S2 | Stacks: `frontend-react` para as tasks de markdown do domínio de design (template, agent, skills, CLAUDE.md, pontos de entrada), porque ele já pré-carrega a `design-system`; `backend-python` para o hook, o `agent-metrics.py` e o `settings.json` |
| S3 | `Files` com caminhos relativos à raiz do git (`/home/phrb/dotfiles`), como `.claude/hooks/agent-audit.py`. O hook compara `allowed_paths` com o caminho relativo à raiz do git (`matches(rel, ...)`), então um caminho absoluto nunca casaria e toda escrita daria `out_of_scope_write` |
| S4 | A métrica "escrita restrita" (critério de sucesso da 15.1) sai de uma linha calculada no `agent-metrics.py` a partir dos registros de escrita, sem categoria nova no hook. **Revista no review** (Review changes): a linha calculada fica, e a categoria `design_director_write_outside` (`block`) passa a negar a escrita na hora |
| S5 | `md_outside_docs` continua avisando quando a **sessão principal** cria o `DESIGN_SYSTEM.md` da raiz (cópia do `new-project`, extração da regra 33), como já acontece com `PRD.md` e `CONSTRAINTS.md`. Esse falso positivo, que já existia, fica para a análise de promoção a `block`, fora da etapa H |
| S6 | Regressão do hook: os 31 casos de classificação da etapa D e os 10 da etapa G nunca foram salvos. Esta spec os troca por uma tabela de base conferida no código atual em 2026-11-11 (37 comandos de classificação e 11 casos pelo stdin da etapa G), rodada de forma avulsa pelo stdin. Uma suite pytest versionada fica para depois |

**Código existente que o desenho reaproveita:**

- `hooks/agent-audit.py`: `evaluate_write()` calcula `rel` (caminho relativo à raiz do git), `area` e os flags de escrita; `decide()` escolhe a categoria mais grave e, entre categorias de mesma gravidade, a primeira em ordem alfabética (os flags chegam ordenados e a comparação usa `>`); `WHY` guarda o texto do motivo; o `warn` devolve `additionalContext` no `PreToolUse`. Os flags de escrita fora de run (`md_outside_docs`, `backlog_write_by_other`) valem com ou sem run ativo; o mesmo vale para a categoria nova.
- `hooks/agent-metrics.py`: `FLAG_LABELS` e a seção `## Flags`; os registros de escrita já trazem `actor` e `rel`.
- Protocolo `needs_input` + retomada com `SendMessage` (etapa C), `scope_requests` (13.4), modo `enforce` (etapa G).
- Comportamento atual conferido pelo stdin, com uma cópia do hook num repo git temporário: hoje o `design-director` gravando o `DESIGN_SYSTEM.md` da raiz recebe `md_outside_docs`; o `frontend-react` editando esse arquivo durante um run recebe `out_of_scope_write`; o `docs-writer` e a sessão principal passam em silêncio. Os 37 comandos e os 11 casos da etapa G (Testing) dão o resultado esperado no código atual.
- `frontend-design` não está em `~/.claude/plugins/installed_plugins.json` (só no cache do marketplace). Tirar a entrada `false` de `enabledPlugins` não liga nada.

## Design

### 1. Convenções de execução neste repo

- **Caminhos.** O repo é `/home/phrb/dotfiles`; a config fica em `.claude/`. Os agents escrevem sempre pelo caminho real (`/home/phrb/dotfiles/.claude/...`), nunca por `~/.claude/...` (symlink). O hook resolve os dois para o mesmo `rel`, mas o caminho real evita ambiguidade no log e no review.
- **Sem `CLAUDE.md` na raiz do repo**, então não há `Local runtime` nem `Test suites`. Não há serviço para validar em runtime (nada de `local_checks`) e não há suite para o `test-runner`: o gate de task e o `full` não têm suite declarada, e o `test-runner` reporta isso em vez de inventar uma. Os checks reais são os da seção Testing, rodados como checks estreitos pelo agent da task e repetidos na Verification.
- **Estado do run**: `/home/phrb/dotfiles/.claude/runs/design-director.json`. `.claude/runs/` não está no `.gitignore` do repo; o `/implement` pergunta uma vez (pré-condição 5).
- **Hook ativo durante o run** (`enforce`). Efeitos esperados:
  - o `Write` que cria `.claude/agents/design-director.md` gera um `md_outside_docs` (`warn`): é um falso positivo conhecido, que entra no log da task 4;
  - arquivos que já existem são alterados com `Edit`, nunca reescritos com `Write`, para não gerar `md_outside_docs`;
  - editar `.claude/CLAUDE.md` e `.claude/templates/*/CLAUDE.md` não gera flag (`CLAUDE.md` é exceção do `md_outside_docs` e não está em `DOC_FILES`);
  - editar `.claude/templates/project-root/DESIGN_SYSTEM.md` com um stack agent gera `design_system_write_by_other` (`warn`), porque a proteção é pelo nome do arquivo (Design 2.1, caso H10); a task 3 rodou antes dessa regra, que veio do review.
- **Docs**: a pasta de docs deste repo foi movida de `docs/` para `.claude/docs/` a pedido do usuário, depois do Review fix r1. Spec e log ficam em `.claude/docs/features/design-director/`. O hook trata `.claude/docs/` como área de docs pela chave `docs_roots` do `agent-audit.json` (Design 2.2); o `project-docs` e o `/implement` continuam resolvendo `docs/` na raiz, então neste repo o caminho da feature é passado explicitamente.
- **`settings.json`** tem regra `ask`: o usuário confirma a edição no prompt do Claude Code (task 7).
- **Idioma**: os arquivos da config ficam em inglês, como todos os agents e skills existentes. Ficam em português só as frases-gatilho ("cria a identidade visual"...). Esta spec está em pt-BR, como o `agent-workflow.md`.
- **Hook com erro**: um erro de sintaxe no `agent-audit.py` faz o Python sair com código 1, que o Claude Code trata como erro que não bloqueia. Mesmo assim, a task 1 só termina com `py_compile` passando e os casos H e G verdes, porque um hook quebrado deixa de registrar tudo.

### 2. Hook

#### 2.1 `hooks/agent-audit.py`

Constantes novas, junto das existentes:

```python
# A project's DESIGN_SYSTEM.md: created by design-director, maintained by the main session following
# the design-system skill. Protected by file name (case-insensitive) anywhere in the repo, so a
# project root that is a subfolder of the git root (monorepo) is covered too.
DESIGN_SYSTEM_NAME = "design_system.md"
DESIGN_SYSTEM_WRITERS = {"design-director", "main"}


def is_design_system(path: str) -> bool:
    return PurePosixPath(str(path).replace("\\", "/")).name.casefold() == DESIGN_SYSTEM_NAME
```

Em `evaluate_write()`, no ramo sem raiz git e depois de calcular `rel` e `area`:

```python
if not root:
    out["in_run"] = False
    if actor == "design-director" and not is_design_system(path_str):
        out["flags"] = ["design_director_write_outside"]
    return out
...
is_ds = is_design_system(rel)
if (rel.endswith(".md") and out["area"] != "docs" and (created or tool == "Write")
        and not rel.endswith(("README.md", "CLAUDE.md", "CHANGELOG.md"))
        and not (is_ds and actor == "design-director")):
    flags.append("md_outside_docs")
if is_ds and actor not in DESIGN_SYSTEM_WRITERS:
    flags.append("design_system_write_by_other")
if actor == "design-director" and not is_ds:
    flags.append("design_director_write_outside")
...
# run ativo, caminhos permitidos do implementer:
allowed += [
    s.get("target", "") for s in run.get("approved_scope", [])
    if str(s.get("task")) == task and s.get("decision", "approved") == "approved"
    and not is_design_system(s.get("target", ""))  # never enters allowed paths
]
```

| Regra | Comportamento |
|---|---|
| Caminho | todo arquivo cujo nome é `design_system.md`, sem diferenciar maiúsculas (`name.casefold() == "design_system.md"`), em qualquer pasta do repo: o da raiz, `apps/web/DESIGN_SYSTEM.md` num monorepo em que a raiz do projeto é subpasta da raiz do git, e `design_system.md` num sistema de arquivos que não diferencia caixa. `ROOT_DESIGN_SYSTEM` (comparação exata com o da raiz) saiu |
| Templates | consequência aceita da regra pelo nome, sem caso especial para `.claude/templates/`: `.claude/templates/project-root/DESIGN_SYSTEM.md` também é protegido (stack agents recebem `design_system_write_by_other`, o `design-director` pode escrever, a sessão principal passa livre) (H10) |
| Isenção | só `actor == "design-director"`, só para `md_outside_docs` e só num `DESIGN_SYSTEM.md` |
| `design_system_write_by_other` (`warn`) | todo ator fora de `{"design-director", "main"}` escrevendo um `DESIGN_SYSTEM.md`: stack agents, `docs-writer`, `quality-fixer`, `test-writer` e `subagent` (agent sem `agent_type`) |
| `design_director_write_outside` (`block`) | toda escrita do `design-director` num arquivo que não é um `DESIGN_SYSTEM.md`: o `PreToolUse` nega (H3, H15, H16). Vale também sem raiz git, pelo nome do caminho recebido (H23-H25) |
| `approved_scope` | alvos aprovados que são um `DESIGN_SYSTEM.md` não entram nos caminhos permitidos derivados: com run ativo, o stack agent que escreve o arquivo continua recebendo `out_of_scope_write` (H26, H27); os outros alvos aprovados valem como antes (H28). Espelha o `implement` 5.2: a decisão fica em `approved_scope`, mas o caminho nunca entra em `allowed_paths` |
| Run | as duas categorias valem com ou sem run ativo, como `backlog_write_by_other` |
| Empate | com run ativo e o caminho fora de `allowed_paths`, o implementer recebe `design_system_write_by_other` e `out_of_scope_write` (os dois `warn`); `decide()` escolhe `design_system_write_by_other`, que vem primeiro em ordem alfabética (caso H5). O registro do `PostToolUse` guarda os dois flags. Com `md_outside_docs` (`warn`) e `design_director_write_outside` (`block`), vence o `block` pela gravidade (H3) |
| Fora de um repo git | `evaluate_write()` retorna antes dos outros flags: só `design_director_write_outside` é avaliado. Logo depois do `new-project`, que não roda `git init`, o hook não grava `rel` nem os outros flags, mas uma escrita do `design-director` fora de um `DESIGN_SYSTEM.md` continua negada (Trade-offs) |

Entradas novas em `WHY`:

```python
"design_director_write_outside": "design-director writes only the project's DESIGN_SYSTEM.md; for anything else finish with result: blocked and a scope_requests entry saying what and why, the caller will ask the user",
"design_system_write_by_other": "a project's DESIGN_SYSTEM.md (any directory) is created only by design-director and maintained only by the main session following the design-system skill; propose the value (token, light and dark, usage) in scope_requests instead",
```

`what_to_do()` não muda: com `warn`, o texto que chega ao agent é o `WHY` mais o lembrete padrão; com `block`, o texto de subagent já manda abrir um pedido de escopo. O docstring do módulo cita o `DESIGN_SYSTEM.md` do projeto (escrito só pelo `design-director` e pela sessão principal) na lista de "file writes".

#### 2.2 `hooks/agent-audit.json`

```json
"design_system_write_by_other": "warn",
"design_director_write_outside": "block"
```

Vão em `categories`, nessa ordem, depois de `backlog_write_by_other`. `mode` continua `enforce`.

Chave nova no topo (escopo acrescentado, log "Added scope r3"), com um comentário em `_docs_roots`:

```json
"docs_roots": ["docs/", ".claude/docs/"]
```

| Regra | Comportamento |
|---|---|
| Uso | pastas, relativas à raiz do git, que contam como área de docs: um `.md` nelas não é `md_outside_docs`, e `<root>backlog/` é escrito só pelo `backlog-keeper`. O teste é por prefixo; um `services/x/docs/` aninhado não é raiz |
| Normalização | `docs_roots()` tira espaços, troca `\` por `/`, tira `./` e `/` do começo, põe `/` no fim e remove duplicatas; ignora entradas que não são texto, vazias, `.` e `..` |
| Fallback | chave ausente, valor que não é lista ou nenhuma entrada válida: `["docs/"]` (o comportamento de antes). `evaluate_write()` recebe as raízes, com `["docs/"]` como padrão |
| Lista | global, para todos os projetos (escolha do usuário); `agent-metrics.py` não muda |

#### 2.3 `hooks/agent-metrics.py`

- `FLAG_LABELS["design_system_write_by_other"] = "a DESIGN_SYSTEM.md written by someone other than design-director or the main session - propose values in scope_requests (target 0)"`.
- `FLAG_LABELS["design_director_write_outside"] = "design-director write outside DESIGN_SYSTEM.md, blocked by the hook (target 0)"`.
- Seção nova `## design-director`, depois de `## Writes`, só quando há eventos do agent (`actor == "design-director"` ou `SubagentStart` com `agent_type == "design-director"`):
  - `- calls: N` (`SubagentStart` do agent);
  - `- writes other than to a DESIGN_SYSTEM.md: N (target 0)`, contando os registros de escrita (`categories == ["write"]`, evento diferente de `PreToolUse`) com `actor == "design-director"` cujo arquivo não é um `DESIGN_SYSTEM.md` pela mesma regra do nome (`Path(rel or path).name.casefold() != "design_system.md"`: um `DESIGN_SYSTEM.md` em subpasta não conta, M1 e M4; um registro sem `rel`, de fora de um repo git, conta pelo `path`, M5); até 5 exemplos (`ts` e o `rel`, ou o `path` quando não há `rel`), como na seção `## Flags`;
  - `- calls without a prior yes from the user: check by hand in the transcript (the hook does not see the conversation; target 0)`.
- O docstring do módulo continua apontando para a 14.2.

### 3. Template `templates/project-root/DESIGN_SYSTEM.md`

| Ponto | Hoje | Depois |
|---|---|---|
| Comentário do topo | "The `design-system` skill reads and extends this file directly" | "Source of truth for every UI-facing service (web, mobile). Created once by the `design-director` agent, from a visual direction the user chose; maintained afterwards by the main session following the `design-system` skill. Subagents never edit it: they propose values in `scope_requests`." |
| Comentário de `Color` | "Provide both light and dark values if the product supports dark mode" | "Always provide both light and dark values, even when the product ships one theme" (regra 20, D22 j; sem isso, a manutenção contradiria o arquivo criado) |
| `Layout concept` | não existe | seção nova logo depois de `Principles` (abaixo) |
| `Font family` | linha `Font family: <family, with fallback stack>` | subseção `### Font family`, com uma tabela por papel (abaixo) |

Seção nova (o template usa uma cerca de código para o wireframe):

````markdown
## Layout concept

<!-- Filled by design-director from the chosen direction. Concept: how screens are organized and why (navigation model, density, where the primary action lives). Wireframe: ASCII sketch of the main-task screen - one block per platform in a monorepo (web, mobile). Avoided patterns: each generic pattern this direction could fall into and how it avoids it; elements taken from the brief or CONSTRAINTS.md that match a pattern are listed with source "brief". -->

**Concept:**

**Wireframe - <platform>:**

```text
```

**Avoided patterns:**

| Pattern | How this direction avoids it (or why it is kept) | Source |
|---|---|---|
| | | list / brief / CONSTRAINTS.md |
````

`Font family` (no fim de `Type scale`, no lugar da linha atual):

```markdown
### Font family

<!-- Open-license (e.g. SIL OFL) or system families only. Record where each family comes from and its license. In a monorepo the family must work on web and mobile (expo-font). -->

| Role | Family | Weights | Fallback stack | Source | License |
|---|---|---|---|---|---|
| Display | | | | | |
| Text | | | | | |
| Mono | | | | | |
```

Projetos existentes não são migrados. Uma seção vazia ou ausente não quebra quem lê o arquivo hoje (`frontend-react`, `mobile-react-native`, `code-reviewer`, `design-system`), porque eles leem os tokens por nome, e não por posição.

### 4. Agent `agents/design-director.md` (novo)

#### 4.1 Frontmatter

```yaml
---
name: design-director
description: Defines a project's visual direction from scratch and writes DESIGN_SYSTEM.md. Use only when the project has no DESIGN_SYSTEM.md (or its Principles are empty) and the user wants a visual identity created ("cria a identidade visual", "define o design do zero"), or when new-project or design-system hands off to it.
tools: Read, Grep, Glob, Write, Edit
model: opus
effort: high
skills:
  - design-system
color: pink
---
```

A description é a de D22 (f), palavra por palavra. `pink` não é usado por nenhum outro agent.

#### 4.2 Estrutura do corpo

Em inglês, nesta ordem. Cada seção cita as regras do plan que cobre, para o review conferir.

| Seção | Conteúdo | Regras |
|---|---|---|
| Role | cria a direção visual de um projeto sem frontend definido e escreve só `<project_root>/DESIGN_SYSTEM.md`; não mantém, não faz redesign e não escreve código; nota de que o passo 1 da `design-system` pré-carregada (oferecer o `design-director`) não vale para ele: a pré-condição é a da seção 4.4 | b, 1-2, 28 |
| Inputs | contrato da seção 4.3 | 32 |
| Preconditions | seção 4.4 | 1-3, 33 |
| Round 1 - brief | seção 4.5 | 9-11 |
| Round 2 - two directions | seção 4.6 | 12-18 |
| Round 3 - the file | seção 4.7 | 19-27, 34 |
| Contrast | fórmula e pares (seção 4.8) | 21, 26 |
| Write scope and tools | seção 4.9 | 28-30 |
| Report | seção 4.10 | 31 |
| Rules | sem prints, browser nem simulador; não mexe no estado do run (`.claude/runs/`); nunca o em dash | 28; casos de borda |

O corpo não cita o plugin `frontend-design`: as ideias de D22 (a) entram reescritas, como "compact token plan reviewed against the brief" e "generic AI-default patterns".

#### 4.3 Contrato de entrada (regra 32)

O prompt se basta sozinho, sem depender da conversa principal:

```yaml
phase: design-direction
project_root: /abs/path/to/project       # obrigatório
entry: new-project | workflow | design-system | implement
brief: "<o que o usuário pediu e o que a sessão principal já sabe>"
answers: "<respostas da rodada 1>"        # opcional
choice: "<direção escolhida, mistura ou mudanças, em texto>"   # opcional
rejected: "<o que foi recusado e por quê>" # opcional
```

Qual rodada roda:

| Entrada | Rodada |
|---|---|
| pré-condição falha | nenhuma: `blocked` |
| `choice` com uma direção ou uma mistura | 3 (depois de rechecar a pré-condição; cobre a sessão reiniciada sem `SendMessage`) |
| `choice` pedindo mudanças, ou `rejected` | 2, com duas direções novas |
| falta assunto, público ou tarefa principal (em `brief`, `answers`, `PRD.md`) | 1 |
| senão | 2 |

Na retomada com `SendMessage`, o agent já tem as direções no contexto; numa chamada nova, ele usa só o texto de `choice`.

#### 4.4 Pré-condição (regras 1-3, 33)

Checada no início de **toda** chamada, inclusive na retomada para a rodada 3. Só com `Read`, `Grep` e `Glob`:

1. **Arquivo.** Sem `<project_root>/DESIGN_SYSTEM.md`: segue. Com o arquivo, `Principles` está vazia quando o trecho entre `## Principles` e o próximo `## ` não tem nada além de comentários HTML e espaço em branco. Com texto: `blocked`, sem tocar no arquivo; o motivo aponta a `design-system` (manutenção) e diz que redesign está fora do escopo.
2. **Serviço de UI.** Lê a tabela `Services` do `<project_root>/CLAUDE.md`. Um serviço é de UI só pela `Stack`, como no `new-project`: `react` (incluindo Next.js e Vite com React) ou `react-native` (incluindo Expo). O nome do serviço (`web`, `frontend`, `mobile`) não conta, e uma stack Vite que não é React também não. Sem nenhum serviço de UI: `blocked` (`no-ui-service`), com o motivo. Sem `CLAUDE.md` ou sem a tabela, ele procura `package.json` com `react`, `react-dom` ou `react-native` em `services/*/`; sem achar nada, `blocked`, pedindo a lista de serviços.
3. **Tokens já em código** (só nos caminhos dos serviços de UI, ignorando `node_modules`, `dist`, `build`, `.next` e `.expo`). Conta como identidade própria:
   - `tailwind.config.*` com cores ou fontes próprias em `theme` / `theme.extend`, ou um bloco `@theme` (Tailwind v4) com `--color-*` ou `--font-*`;
   - CSS/SCSS que define propriedades `--color-*`, `--font-*` ou `--space-*`;
   - módulos de tema ou tokens (`**/theme.{ts,tsx,js}`, `**/tokens.{ts,js,json}`, `**/colors.{ts,js}`) que exportam valores hex, rgb ou hsl;
   - `useFonts` / `Font.loadAsync` do `expo-font` com famílias próprias.

   Achou: `blocked` com os arquivos como evidência e o caminho certo, que é a extração dos tokens existentes pela sessão principal seguindo a `design-system` (regra 33). A tela de exemplo do `new-project`, sem tokens, não conta.

`Principles` vazia com algumas tabelas já preenchidas não bloqueia: os valores existentes entram no brief como restrição (caso de borda).

#### 4.5 Rodada 1 - briefing (regras 9-11)

- Lê `PRD.md`, `CONSTRAINTS.md`, `CLAUDE.md` (`Services`, `Documentation language`) e o `brief`. Arquivo ausente não é erro: o básico pode vir só do brief.
- O básico são três itens: **assunto** (o que o produto é), **público** (quem usa) e **tarefa principal** (o que o usuário mais faz). Faltando algum: `needs_input` só com as perguntas do que falta (até 3), sem propor direção.
- Com os três: segue para a rodada 2 na mesma chamada.

#### 4.6 Rodada 2 - duas direções (regras 12-18)

Para cada direção, antes de apresentar:

1. **Plano compacto de tokens**: paleta base de 4 a 6 hex, cada uma com seu papel; tipografias por papel (display, texto e, quando houver, mono); conceito de layout; 2 a 4 princípios.
2. **Revisão contra o brief** (público, tarefa principal, restrições de `CONSTRAINTS.md` e valores já existentes no arquivo). Uma direção que não se sustenta é refeita, não apresentada.
3. **Revisão contra os padrões genéricos**, só nos eixos que o brief deixa livres. A lista (regra 16): fundo creme + serifa + acento terracota; quase preto + um único acento ácido; kit de cards SaaS (cards idênticos arredondados com sombra cinza suave); eyebrow labels em caixa alta; acento numa única palavra do título; entradas com fade-and-slide em tudo. Para cada direção, diz qual padrão ela poderia repetir e como evita, ou "nenhum". Um elemento pedido no brief ou em `CONSTRAINTS.md` vence a lista e fica marcado `from_brief` (regra 15).
4. **Licença**: só famílias com licença aberta (ex.: SIL OFL) ou do sistema. Uma fonte paga pedida no brief não entra: a direção propõe a alternativa aberta mais próxima e diz por quê (regra 22). Em monorepo, a família serve para web e para `expo-font`.
5. **Pré-checagem de contraste** dos pares principais (texto primário e acento sobre o fundo, nos dois temas), para não apresentar uma direção que a rodada 3 teria de recusar.

As duas direções diferem em pelo menos dois dos três eixos (paleta, tipografia, conceito de layout); o agent confere isso antes de responder (regra 14). Wireframe ASCII da tela da tarefa principal, um por plataforma em monorepo. Cor de marca vinda de `CONSTRAINTS.md` entra nas duas direções; os tokens semânticos garantem AA (a marca vira `accent` só onde o contraste passa).

Com `Principles` vazia e tabelas já preenchidas, cada direção lista em `changes_to_existing` o que mudaria.

O formato de cada direção é o exemplo ilustrativo da 15.1 ("Direção A - Arquivo técnico"). O report termina com `result: needs_input`, as duas direções no YAML e a pergunta "qual direção, uma mistura (ex.: paleta da A com tipografia da B) ou mudanças?". Com mudanças pedidas ou as duas recusadas, vem uma nova rodada 2 com duas direções novas que levam em conta `rejected`; nada é escrito enquanto não há escolha (regras 17-18).

#### 4.7 Rodada 3 - o arquivo (regras 19-27, 34)

1. Recheca a pré-condição (seção 4.4).
2. Com uma mistura, confere o contraste dela antes de escrever. Se quebra AA: `needs_input` com o ajuste mais próximo (o par que falha, o valor proposto e as razões antes e depois), sem escrever nada (regra 26).
3. **Arquivo ausente**: lê `~/.claude/templates/project-root/DESIGN_SYSTEM.md`, troca `<project name>` e grava com `Write` em `<project_root>/DESIGN_SYSTEM.md`. **Arquivo existente**: preenche com `Edit`, seção por seção. Os comentários do template ficam.
4. O que é preenchido:

| Seção | Conteúdo |
|---|---|
| `Principles` | 2-4 frases da direção, com as regras duras (ex.: densidade, uma cor de ação só) (regra 24) |
| `Layout concept` | conceito, wireframe por plataforma, padrões evitados com a origem (lista / brief / `CONSTRAINTS.md`) (regra 34) |
| `Color` | todos os tokens com light **e** dark, sempre (regra 20). O agent acrescenta só linhas por papel que a direção precisa para o contraste, como `color.text.on-accent` quando há botão com fundo de acento |
| `Type scale` | 5-7 passos com tamanho, line height e peso; um token que a escala não usa diz "não se aplica" |
| `Font family` | uma linha por papel, com pesos, stack de fallback, origem (ex.: Google Fonts, fonte do sistema) e licença; `Mono` sem uso diz "não se aplica" |
| `Spacing scale`, `Breakpoints`, `Radius and elevation` | valores coerentes com a direção (ex.: sem sombra quando a direção evita o kit de cards SaaS; nesse caso, `shadow.*` diz "não se aplica: elevação por borda") |
| `Component conventions` | 2+ regras vindas da direção |
| `Accessibility baseline` | mantém as linhas do template |

   Nenhuma célula fica vazia nem com placeholder (regra 23). A prosa segue o `Documentation language`; nomes de token e cabeçalhos ficam como no template (regra 25).
5. O report final traz os pares de contraste e o próximo passo: levar os tokens ao código é um plan/spec normal (`planner` -> `specker` -> `frontend-react` / `mobile-react-native`), que o agent não faz (regra 27).

#### 4.8 Contraste (regra 21)

O agent não tem `Bash`, então calcula à mão, pela definição do WCAG 2.2, e escreve as contas no corpo do agent:

- canal sRGB `c = valor/255`; linear `c <= 0.04045 ? c/12.92 : ((c + 0.055)/1.055)^2.4`;
- luminância relativa `L = 0.2126 R + 0.7152 G + 0.0722 B`;
- razão `(L_clara + 0.05) / (L_escura + 0.05)`, com 2 casas, arredondada para baixo.

Mínimos: 4.5:1 para texto normal; 3:1 para texto grande (24px, ou 18.66px em negrito), ícones e bordas de componentes. Um par a menos de 0.2 do mínimo é refeito passo a passo; o agent prefere valores com folga.

Pares obrigatórios, em light e em dark:

| Frente | Fundo | Mínimo |
|---|---|---|
| `color.text.primary`, `color.text.secondary` | `color.background`, `color.surface` | 4.5 |
| `color.accent` como texto ou link | `color.background`, `color.surface` | 4.5 |
| `color.text.on-accent` (quando existe) | `color.accent` | 4.5 |
| `color.success`, `color.warning`, `color.danger` | `color.background` | 4.5 como texto; 3 quando a direção os usa só como ícone ou preenchimento |
| `color.border` (borda de input ou componente) | `color.background`, `color.surface` | 3 |

As razões vão no report e, como o risco da 15.1 pede, também na coluna `Usage` do token de frente (ex.: "Default text - 15.30:1 on background, 14.10:1 on surface"), para o usuário conferir num verificador qualquer.

#### 4.9 Escrita, ferramentas e erros (regras 28-30)

- Escreve só `<project_root>/DESIGN_SYSTEM.md`. Nada de código (`theme.ts`, config do Tailwind, carga de fontes, `expo-font`), config, asset, estado de run nem outro doc.
- O hook nega toda escrita fora de um `DESIGN_SYSTEM.md` (`design_director_write_outside`, Design 2.1). **Deny**: a chamada negada ("Agent workflow (<category>): ...") nunca é repetida; o agent termina `blocked` (`blocked_reason: hook-denied`), cita a categoria e diz o estado do arquivo (não gravado, ou o que já tinha sido salvo). **Warn**: um aviso numa escrita do `DESIGN_SYSTEM.md` que deu certo não é parada; vai no report final e a rodada continua.
- Se o `Write` ou o `Edit` falhar, termina `blocked` com o erro e lista em `files_written` só o que de fato foi gravado; uma escrita parcial nunca vira `done`.

#### 4.10 Report (regra 31)

Até 5 linhas de prosa (na rodada 2, as duas direções lado a lado no formato da 15.1) e o bloco final:

```yaml
result: done | needs_input | blocked
round: precheck | 1 | 2 | 3
files_written: []          # só <project_root>/DESIGN_SYSTEM.md, e só quando gravado
question: ""               # rodadas 1 e 2, e o ajuste de mistura (regra 26)
directions:                # rodada 2
  - id: A
    name: ""
    palette: []            # "#hex - papel"
    typography: []         # "papel: Família peso (licença, origem)"
    layout: ""
    wireframes: []         # um por plataforma
    principles: []
    patterns_review: ""    # padrão que poderia repetir e como evita, ou "none"
    from_brief: []         # elementos vindos do brief / CONSTRAINTS.md (regra 15)
    changes_to_existing: []
contrast_pairs:            # rodada 3 e ajuste da regra 26
  - pair: "color.text.primary / color.background"
    theme: light | dark
    ratio: "15.30:1"
    min: "4.5:1"
    result: pass | fail
blocked_reason: ""         # principles-filled | no-ui-service | ui-tokens-in-code | hook-denied | write-error, com o detalhe
next_step: ""
needs_docs: []
```

### 5. Manutenção: `skills/design-system/SKILL.md` e os CLAUDE.md dos templates

**`skills/design-system/SKILL.md`**

- `description`: "...and maintain the project's DESIGN_SYSTEM.md as the single source of those values. Preloaded by frontend-react, mobile-react-native and design-director. Creating the visual direction from scratch belongs to the design-director agent." (os gatilhos continuam os mesmos).
- Passo 1, trocado por (no arquivo, quatro bullets em vez de tabela, para a skill pré-carregada ficar curta):

| Situação | Sessão principal | Subagent |
|---|---|---|
| Arquivo ausente ou `Principles` vazia, sem tokens próprios em código | oferece o `design-director` ao usuário (nunca o chama sem um sim e nunca define a direção na conversa); com a recusa, segue sem inventar tokens, e o trabalho que precisa deles fica parado ou parcial | `result: blocked` com um `scope_requests` (`action: create`, `target: DESIGN_SYSTEM.md`, `reason: no visual direction yet; the design-director agent creates it`); recusa = pedido negado (13.4): conclui `partial` ou declara blocker, sem token inventado |
| Arquivo ausente ou `Principles` vazia, com tokens próprios em código nos serviços de UI | documenta os tokens existentes (**extração**): copia o template e preenche com os valores do código, citando o arquivo de origem de cada um, sem direção nova e sem o agent (regra 33) | `result: blocked` com um `scope_requests` de forma fixa: `action: create`, `target: DESIGN_SYSTEM.md`, `reason: extraction of tokens in <files>`. O `reason` começando com "extraction" é o que separa este pedido do de direção ausente |
| Arquivo existe, falta um valor | propõe o valor ao usuário e, com o sim, grava | propõe em `scope_requests` (`action: edit`, `target: DESIGN_SYSTEM.md`, o token, light e dark, e o uso); nunca edita o arquivo, mesmo com o caminho em `allowed_paths`; com o sim, a sessão principal grava e retoma o agent, que passa a usar o token (regra 29) |
| Você é o `design-director` | este passo não vale; a pré-condição é a do agent | - |

- Sai a referência ao `frontend-design`. Os passos 2-5 e o passe de pixel não mudam.

**`templates/node-ts-react/CLAUDE.md` e `templates/react-native/CLAUDE.md`, linha 25:**

> Root `DESIGN_SYSTEM.md` for tokens · Root `PRD.md` for product context · `design-director` agent to create the visual direction when `DESIGN_SYSTEM.md` is missing or its `Principles` are empty · `design-system` skill to maintain tokens, consistency and accessibility on any layout

(no `react-native`, "on any screen").

### 6. Pontos de entrada

**`skills/new-project/SKILL.md`, passo 3, item 1** (linha 45 atual, "Leave the `DESIGN_SYSTEM.md` tables blank..."), trocado por:

- Sem serviço de UI no perfil (nenhum `react` nem `react-native`): descarta o `DESIGN_SYSTEM.md`, como hoje.
- Com serviço de UI: pergunta uma vez, nesse passo: "Define the visual direction now? (`design-director`: two contrasting proposals, you choose)".
  - **Sim**: depois de preencher `PRD.md`, `CONSTRAINTS.md` e a tabela `Services`, chama o `design-director` com `phase: design-direction`, `project_root`, `entry: new-project` e o brief (a descrição do usuário). Repassa cada `needs_input` com `AskUserQuestion` e retoma o mesmo agent com `SendMessage` até `done` ou `blocked`; aí segue o scaffold.
  - **Não**: tabelas em branco; a direção pode ser criada depois pela frase do Workflow ou pela oferta da `design-system`. A pergunta não se repete no run.
- O relatório do passo 8 diz se a direção foi criada.

**`CLAUDE.md` global, seção Workflow:**

- Linha nova na tabela, logo depois da linha `Discover`:

  | The user says (examples) | Phase -> owner | Precondition |
  |---|---|---|
  | "cria a identidade visual", "define o design do zero", "vamos criar o frontend do zero" | Visual direction -> `design-director`, in rounds (`needs_input`: brief if missing, two contrasting directions, the user's choice), writes only the root `DESIGN_SYSTEM.md`; tokens reach the code later through a normal plan and spec | root `DESIGN_SYSTEM.md` missing or its `Principles` empty, and no UI service with its own tokens in code; the phrase is the user's yes. Otherwise say the direction exists and follow `design-system` (maintenance), or document the tokens already in code following `design-system` (extraction), without the agent |

- Bullet novo, depois do bullet "Subagents cannot ask the user...":

  > A subagent's `scope_requests` on the root `DESIGN_SYSTEM.md` never adds the path to its `allowed_paths`: a missing file (or empty `Principles`) becomes the offer of `design-director` to the user; an extraction request (`reason: extraction of tokens in <files>`, the UI service already has tokens in code) is asked as extraction, and on yes the main session documents the existing tokens following `design-system`; a proposed value is written by the main session itself, following `design-system`, after the user's yes. Then the agent is resumed. A refusal is a denied request.

**`skills/implement/SKILL.md`, passo 5.2 ("Scope requests"):** frase nova no fim:

> Exception - the root `DESIGN_SYSTEM.md`: never add it to `allowed_paths`. A request because the file is missing (or its `Principles` are empty) is asked as "create the visual direction with `design-director`?"; on yes, run `design-director` (relay its `needs_input` rounds), then resume the stack agent. A request whose `reason` starts with "extraction of tokens" (the UI service already has tokens in code) is asked as "document the existing tokens in `DESIGN_SYSTEM.md`?"; on yes, write the file yourself following the `design-system` skill (extraction, no agent), then resume the stack agent. A proposed value is asked as that value; on yes, write it yourself following the `design-system` skill, then resume the agent. A no is a denied request. Record the decision in `approved_scope` and the log as usual, but the path never enters `allowed_paths`: the main session is the one that writes `DESIGN_SYSTEM.md`.

Os três ramos, iguais nos dois textos (o do `implement` vale dentro de um run; o do `CLAUDE.md`, fora dele):

| Pedido do subagent (`scope_requests`) | Pergunta ao usuário | Com o sim |
|---|---|---|
| `action: create`, `reason: no visual direction yet; ...` (arquivo ausente ou `Principles` vazia) | criar a direção com o `design-director`? | roda o `design-director` (repassando as rodadas `needs_input`) e retoma o stack agent |
| `action: create`, `reason: extraction of tokens in <files>` | documentar os tokens existentes no `DESIGN_SYSTEM.md`? | a sessão principal faz a extração seguindo a `design-system`, sem o agent, e retoma o stack agent |
| `action: edit`, o valor proposto (token, light e dark, uso) | o próprio valor | a sessão principal grava seguindo a `design-system` e retoma o stack agent |

Nos três casos a decisão vai em `approved_scope` e no log, mas o caminho nunca entra em `allowed_paths`; o hook garante isso tirando dos caminhos permitidos todo alvo aprovado que é um `DESIGN_SYSTEM.md` (Design 2.1).

O `design-director` não mexe no estado do run; a task que pediu fica parada até o `implement` retomar o stack agent (caso de borda).

### 7. `settings.json`

Sai a linha `"frontend-design@claude-plugins-official": false,` de `enabledPlugins`. Mais nada muda: `permissions` (allow, deny, ask), `hooks`, as outras entradas de plugins e o resto das chaves ficam iguais. O plugin não está instalado (Background), então a mudança não muda o comportamento.

### 8. Segurança e privacidade

- O `design-director` não tem `Bash` nem ferramenta de rede: não roda comando, não busca fontes, não chama serviço. As origens das fontes são registradas, nunca baixadas.
- O hook continua sem guardar conteúdo de arquivo: só `rel`, ator e flags.
- `settings.json` passa pela regra `ask`: o usuário vê e confirma a edição.
- Nenhuma credencial é envolvida.

### 9. Observabilidade

| Sinal | Onde | Alvo (14.2) |
|---|---|---|
| `design_system_write_by_other` | JSONL do hook; `## Flags` e `## Enforcement decisions` do `agent-metrics.py` | 0 |
| `design_director_write_outside` (negada) | JSONL do hook; `## Flags` e `## Enforcement decisions` do `agent-metrics.py` | 0 |
| Escritas do `design-director` fora de um `DESIGN_SYSTEM.md` | `## design-director` do `agent-metrics.py` (linha calculada) | 0 |
| Chamadas do `design-director` | `## Agent calls` e `## design-director` | raras (uma por projeto) |
| Chamadas sem um sim antes | conferência à mão no transcript, nos cenários 41-42 | 0 |

### 10. Rollout e reversão

- **Ordem**: hook -> métricas -> template -> agent -> manutenção -> pontos de entrada -> settings. O hook vem primeiro para que qualquer uso real do agent já saia com os sinais certos.
- **Ativação**: agents novos só aparecem numa sessão nova do Claude Code; hook e settings valem na hora (o Claude Code recarrega o `settings.json`, e o hook é lido a cada chamada).
- **Desligar sem reverter**: `"design_system_write_by_other": "audit"` em `agent-audit.json` deixa de avisar e continua registrando; `"design_director_write_outside": "warn"` (ou `"audit"`) troca a negação por aviso (ou só registro); `"mode": "audit"` desliga todas as decisões.
- **Reverter**: cada task é um commit do usuário; reverter a do hook volta ao comportamento atual. Projetos que já ganharam um `DESIGN_SYSTEM.md` com `Layout concept` continuam válidos.
- **Promoção a `block`**: segue a regra de 13.3, com os dados da rodada de testes.

### 11. Documentação (pelo `docs-writer`, no fim)

Não é task; vai no passe de documentação:

- `.claude/README.md`: linha do `design-director` na tabela de agents (opus, effort alto, tools, `design-system`); `design-system` pré-carregada também pelo `design-director`; o parágrafo do `frontend-design` (linha 69) vira a divisão criação x manutenção; categoria nova na política do hook; a seção `## design-director` do `agent-metrics.py`. Sem isso, o `grep frontend-design` (V4) não zera.
- `.claude/agent-workflow.md`:
  - Registro de execução da etapa H;
  - na tabela de arquivos da 15.1, a linha nova de `skills/implement/SKILL.md` (decisão S1) e o bullet novo no `CLAUDE.md` global;
  - na 15.1 Verificação, a troca da regressão "31 + 10" pela tabela de base desta spec (S6);
  - os rótulos "Draft" que ficaram para trás nas linhas 412, 734, 857, 868 e 1125, enquanto a 15.1 diz Approved.

## Alternatives considered

| Tema | Alternativa | Por que não |
|---|---|---|
| Onde tratar os `scope_requests` do `DESIGN_SYSTEM.md` | só um bullet no `CLAUDE.md` global | deixaria o passo 2 do `implement` dizendo o contrário ("approved targets join allowed_paths"); duas instruções em conflito dependem do julgamento do modelo. Escolhido: `implement` + `CLAUDE.md` (S1) |
| | deixar como está | os cenários 42-43 dependeriam do julgamento da sessão principal |
| Escrita restrita do `design-director` | só a linha calculada no `agent-metrics.py` (S4, escolha original) | mede depois do fato e deixa a escrita acontecer; o review mostrou que a regra 28 precisa de garantia, não só de medida. Escolhido no review: categoria `design_director_write_outside` em `block`, mais a linha calculada |
| | categoria em `warn` | o agent poderia seguir depois do aviso; uma escrita fora do arquivo nunca é legítima para ele, então não há falso positivo que justifique só avisar |
| Testes do hook | suite pytest versionada em `.claude/hooks/` | o repo não tem suite nem tabela `Test suites`, e o plan não lista o arquivo; fica como próximo passo (S6) |
| Regra de proteção | só o `DESIGN_SYSTEM.md` da raiz do git, comparação exata (escolha original) | falha num monorepo em que a raiz do projeto é subpasta do git (`apps/web/DESIGN_SYSTEM.md`) e num sistema de arquivos que não diferencia caixa; o `design-director` seria negado no arquivo certo e um stack agent escreveria nele sem aviso. Escolhido no review: o nome, sem caixa, em qualquer pasta |
| | nome, com exceção para `.claude/templates/` | um caso especial a mais para um repo só (o dotfiles); proteger o template também é aceitável (só a sessão principal o mantém) |
| | isentar também a sessão principal de `md_outside_docs` | não resolve o falso positivo maior (`PRD.md`, `CONSTRAINTS.md` do `new-project`); fica para a análise de promoção (S5) |
| `approved_scope` sobre o `DESIGN_SYSTEM.md` | confiar só no texto do `implement` 5.2 | um alvo registrado como aprovado entraria nos caminhos permitidos derivados pelo hook e calaria o `out_of_scope_write`; o hook tirar esses alvos deixa as duas regras iguais |
| Contraste | o agent ganha `Bash` para calcular | quebra D22 (e); a conta à mão com as razões registradas no arquivo, para o usuário conferir, é a mitigação aprovada |
| `Font family` | manter uma linha só com origem e licença | com display, texto e mono, a linha fica ilegível e não dá para marcar "não se aplica" por papel; a tabela segue a regra 23 |
| Stack das tasks de markdown | `backend-python` para tudo | não pré-carrega a `design-system`, e o corpo do agent e do template exige o domínio (tokens, contraste, escala) (S2) |
| Rodadas | um único run longo que pergunta no meio | subagents não perguntam ao usuário; `needs_input` + `SendMessage` é o protocolo da config e funciona igual no Briareu |

## Trade-offs

- **Desempate alfabético no `decide()`**: o caso H5 depende de `design_system_write_by_other` vir antes de `out_of_scope_write`. É o comportamento atual para todos os empates, então não muda; o caso H5 fixa isso e quebra se alguém mudar a ordem.
- **Hook parcial fora de um repo git**: logo depois do `new-project` (sem `git init`), o hook não calcula `rel` nem os flags de escrita, com uma exceção: o `design-director` fora de um `DESIGN_SYSTEM.md` continua negado, pelo nome do caminho. `design_system_write_by_other` não vale aí. Aceito: o agent não tem `Bash`, e o próximo passo do `new-project` é o `git init`.
- **Proteção pelo nome**: todo arquivo chamado `DESIGN_SYSTEM.md` (sem caixa) é protegido, inclusive o template em `.claude/templates/project-root/` e qualquer arquivo de mesmo nome que não seja o design system do projeto. Aceito: o nome é reservado na config, e o custo é um `warn` para stack agents.
- **Contraste sem ferramenta**: arredondar para baixo e refazer pares perto do limite reduz o erro aritmético, mas não o elimina; as razões ficam no arquivo para conferir.
- **Detecção de tokens em código por heurística**: pode deixar passar um tema fora dos padrões listados; nesse caso o pior resultado é uma direção nova para um projeto que já tinha uma, e o usuário vê as duas direções antes de qualquer escrita.
- **Exceção ao 13.4 em dois lugares** (`implement` e `CLAUDE.md`): é texto duplicado, mas um vale dentro de um run e o outro fora dele; os dois citam a `design-system` como fonte.
- **Um falso positivo conhecido no run** (`md_outside_docs` ao criar `agents/design-director.md`): fica registrado no log da task 4 e não conta contra a promoção.

## Testing

Não há suite no repo (sem `Test suites`). Os testes são checks avulsos, com o harness abaixo; o agent da task roda os da sua task como checks estreitos, e a sessão principal repete todos na Verification.

### Harness pelo stdin (tasks 1 e 2)

Fica no scratchpad da sessão, nunca no repo. Usa uma cópia do hook, para que o `agent-audit.json` e as métricas fiquem isolados:

```bash
T=<scratchpad>/hook-h                       # fora do repo
mkdir -p $T/hook $T/repo/.claude/runs $T/metrics
cp /home/phrb/dotfiles/.claude/hooks/agent-audit.{py,json} /home/phrb/dotfiles/.claude/hooks/agent-metrics.py $T/hook/
git -C $T/repo init -q
# run ativo (só nos casos marcados "run"):
echo '{"phase":"implement","current_task":1,"allowed_paths":{"1":["services/web/src/**"]},"approved_scope":[]}' > $T/repo/.claude/runs/demo.json
# um caso: evento, ator ("main" = sem agent_type/agent_id), tool, caminho
payload='{"hook_event_name":"PreToolUse","session_id":"h","agent_type":"frontend-react","agent_id":"a1","cwd":"'$T/repo'","tool_name":"Edit","tool_input":{"file_path":"'$T/repo'/DESIGN_SYSTEM.md"}}'
echo "$payload" | AGENT_AUDIT_DIR=$T/metrics python3 -I $T/hook/agent-audit.py
# sem raiz git (H23-H25): cwd e file_path em $T/norepo, fora de qualquer repo
mkdir -p $T/norepo
# run com approved_scope (H26-H28):
echo '{"phase":"implement","current_task":1,"allowed_paths":{"1":["services/web/src/**"]},"approved_scope":[{"task":1,"target":"DESIGN_SYSTEM.md","decision":"approved"},{"task":1,"target":"services/api/**","decision":"approved"}]}' > $T/repo/.claude/runs/demo.json
```

- O harness da implementação, escrito com a ferramenta `Write` (um heredoc no Bash é negado como `docker_lifecycle`) e rodado com `python3 -I <arquivo>`: `<scratchpad>/harness.py` (H, G, C e os casos D1-D10 de `docs_roots` do "Added scope r3", 119 checks) e `<scratchpad>/m/harness_m.py` (M, 9 checks, com diff contra `agent-metrics.orig.py`).

- **Silencioso** = nenhuma saída no `PreToolUse`. **warn `<cat>`** = `additionalContext` com `Reminder from the agent workflow (<cat>)`. **deny / ask** = `permissionDecision`.
- Os flags gravados vêm de um `PostToolUse` com o mesmo payload (mais `"tool_response":{"type":"create"}` quando é criação), lidos do último registro em `$T/metrics/h.jsonl`.
- Modo `audit`: trocar `"mode"` na **cópia** do `agent-audit.json`.
- Casos sem run: apagar `$T/repo/.claude/runs/demo.json`.

### Casos H - categorias novas, regra do nome e isenção (`agent-audit.py`, `agent-audit.json`)

| # | Ator | Tool | Caminho (rel) | Run | Esperado no `PreToolUse` | Flags no `PostToolUse` |
|---|---|---|---|---|---|---|
| H1 | `design-director` | Write | `DESIGN_SYSTEM.md` | não | silencioso | `[]` |
| H2 | `design-director` | Write | `services/web/DESIGN_SYSTEM.md` | não | silencioso (regra do nome) | `[]` |
| H3 | `design-director` | Write | `NOTES.md` | não | deny `design_director_write_outside` | `[design_director_write_outside, md_outside_docs]` |
| H4 | `frontend-react` | Edit | `DESIGN_SYSTEM.md` | não | warn `design_system_write_by_other` | `[design_system_write_by_other]` |
| H5 | `frontend-react` | Edit | `DESIGN_SYSTEM.md` | sim | warn `design_system_write_by_other` | `[design_system_write_by_other, out_of_scope_write]` |
| H6 | `docs-writer` | Edit | `DESIGN_SYSTEM.md` | não | warn `design_system_write_by_other` | `[design_system_write_by_other]` |
| H7 | main | Edit | `DESIGN_SYSTEM.md` | não | silencioso | `[]` |
| H8 | `frontend-react` (H4), modo `audit` | Edit | `DESIGN_SYSTEM.md` | não | silencioso | `[design_system_write_by_other]` |
| H9 | `subagent` (só `agent_id`) | Edit | `DESIGN_SYSTEM.md` | não | warn `design_system_write_by_other` | `[design_system_write_by_other]` |
| H10 | `frontend-react` | Edit | `.claude/templates/project-root/DESIGN_SYSTEM.md` | não | warn `design_system_write_by_other` (template protegido pelo nome) | `[design_system_write_by_other]` |
| H11 | `design-director` | Edit | `DESIGN_SYSTEM.md` (existente) | não | silencioso | `[]` |
| H12 | `design-director` | Write, `tool_response.type: create` | `DESIGN_SYSTEM.md` | não | - | `[]` |
| H13 | `backend-node` | Write, `tool_response.type: create` | `DESIGN_SYSTEM.md` | não | warn `design_system_write_by_other` | `[design_system_write_by_other, md_outside_docs]` |
| H14 | main | Write, `tool_response.type: create` | `DESIGN_SYSTEM.md` | não | warn `md_outside_docs` (S5, sem mudança) | `[md_outside_docs]` |
| H15 | `design-director` | Edit | `src/a.ts` | não | deny `design_director_write_outside` | `[design_director_write_outside]` |
| H16 | `design-director` | Write, `tool_response.type: create` | `src/a.ts` | não | deny `design_director_write_outside` | `[design_director_write_outside]` |
| H17 | `design-director` | Edit | `apps/web/DESIGN_SYSTEM.md` | não | silencioso | `[]` |
| H18 | `design-director` | Write, `tool_response.type: create` | `apps/web/DESIGN_SYSTEM.md` | não | - | `[]` |
| H19 | `frontend-react` | Edit | `design_system.md` | não | warn `design_system_write_by_other` | `[design_system_write_by_other]` |
| H20 | `design-director` | Write, `tool_response.type: create` | `design_system.md` | não | - | `[]` |
| H21 | `frontend-react` | Edit | `apps/web/DESIGN_SYSTEM.md` | não | warn `design_system_write_by_other` | `[design_system_write_by_other]` |
| H22 | main | Edit | `apps/web/Design_System.md` | não | silencioso | `[]` |
| H23 | `design-director` | Edit | `x.ts`, sem raiz git (`$T/norepo`) | não | deny `design_director_write_outside` | - |
| H24 | `design-director` | Edit | `DESIGN_SYSTEM.md`, sem raiz git | não | silencioso | - |
| H25 | `design-director` | Edit | `app/design_system.MD`, sem raiz git | não | silencioso | - |
| H26 | `frontend-react` | Edit | `DESIGN_SYSTEM.md` | sim, `approved_scope` com `DESIGN_SYSTEM.md` e `services/api/**` aprovados | - | `[design_system_write_by_other, out_of_scope_write]` |
| H27 | `frontend-react` | Edit | `apps/web/design_system.md` | sim, o mesmo de H26 | - | `[design_system_write_by_other, out_of_scope_write]` |
| H28 | `frontend-react` | Edit | `services/api/x.ts` | sim, o mesmo de H26 | - | `[]` |

H1-H8 são os sete casos da 15.1 (H5 é o mesmo caso que H4, com run ativo, e fixa o desempate); H9-H14 cobrem a isenção nas duas fases e o caso S5. Os casos que vieram do review: H15-H16 a negação do `design-director` fora do arquivo; H17-H22 a regra do nome (subpasta de monorepo e caixa) para os três tipos de ator; H23-H25 a negação sem raiz git; H26-H28 os alvos de `approved_scope` que são um `DESIGN_SYSTEM.md` fora dos caminhos permitidos, sem afetar os outros alvos. H2, H3 e H10 mudaram de esperado no review.

### Casos M - métricas (`agent-metrics.py`)

| # | Entrada | Esperado |
|---|---|---|
| M1 | JSONL com os `PostToolUse` de H2, H3, H4 e um `SubagentStart` do `design-director` | `## Flags` lista `design_system_write_by_other` com o rótulo novo; `## design-director` mostra `calls: 1` e `writes other than to a DESIGN_SYSTEM.md: 1`, só com `NOTES.md` (`services/web/DESIGN_SYSTEM.md` é um `DESIGN_SYSTEM.md` pela regra do nome) |
| M2 | JSONL só com H1 e H11 | `writes other than to a DESIGN_SYSTEM.md: 0` |
| M3 | JSONL sem evento do `design-director` | a seção `## design-director` não aparece; o resto do relatório não muda |
| M4 | `SubagentStart` e uma escrita do `design-director` em `apps/web/Design_System.md` | `writes other than to a DESIGN_SYSTEM.md: 0` (subpasta e caixa não contam) |
| M5 | `SubagentStart` e um registro do `design-director` sem `rel` (fora de um repo git), `path` `/x/y.ts`, flag `design_director_write_outside` | `writes other than to a DESIGN_SYSTEM.md: 1` (conta pelo `path`, e o exemplo mostra `/x/y.ts`); `## Flags` lista `design_director_write_outside` com o rótulo novo |

Comando: `AGENT_AUDIT_DIR=$T/metrics python3 -I $T/hook/agent-metrics.py --session h`.

### Casos G - regressão da etapa G (11, pelo stdin)

| # | Caso | Esperado |
|---|---|---|
| G1 | `backend-node`, Bash `docker compose -f x.yml restart api` | deny `docker_lifecycle` |
| G2 | main, Bash `rtk docker compose restart api` | deny `docker_lifecycle` |
| G3 | main, Bash `git commit -m x` | ask `git_commit` |
| G4 | `ui-verifier`, Write `services/web/src/a.tsx` | deny `write_by_readonly_agent` |
| G5 | `frontend-react`, tool `mcp__playwright__browser_take_screenshot` | deny `visual_tool` |
| G6 | `ui-verifier`, mesma tool | silencioso |
| G7 | `frontend-react`, Edit `services/api/x.ts`, run ativo | warn `out_of_scope_write` |
| G8 | `frontend-react`, Edit `services/web/src/a.tsx`, run ativo | silencioso |
| G9 | `backend-python`, Bash `pytest tests/test_a.py` | silencioso |
| G10 | stdin `not json` | exit 0, nenhuma saída, nada gravado |
| G11 | G1 com a cópia do config em modo `audit` | silencioso |

### Casos C - classificação (37 comandos, `classify_command`)

Chamados importando o módulo da cópia (`importlib.util.spec_from_file_location`) e comparando `classify_command(cmd)` com a tabela. Base conferida no código atual em 2026-11-11:

| Comando | Categorias | Flags |
|---|---|---|
| `pytest tests/test_orders.py` | test-narrow | - |
| `pytest -k export` | test-narrow | - |
| `pytest` | test-full | - |
| `go test ./internal/orders/` | test-package | - |
| `go test ./...` | test-full | - |
| `go test -run TestExport ./internal/orders` | test-narrow | - |
| `cargo test` | test-full | - |
| `cargo test -p orders` | test-package | - |
| `npx vitest run src/a.test.ts` | test-narrow | - |
| `pnpm exec vitest run src/a.test.ts` | test-narrow | - |
| `pnpm vitest run` | test-full | - |
| `pnpm --filter api test` | test-package | - |
| `pnpm -r test` | test-full | - |
| `npm test` | test-full | - |
| `rtk pnpm test` | test-full | - |
| `./mvnw test -Dtest=OrderTest` | test-narrow | - |
| `./gradlew :api:test` | test-package | - |
| `uv run pytest tests/test_x.py::test_y` | test-narrow | - |
| `k6 run load.js` | test-load | - |
| `eslint src/a.ts` | lint | - |
| `pnpm lint` | lint | - |
| `ruff check .` | lint | - |
| `tsc --noEmit` | typecheck | - |
| `pnpm typecheck` | typecheck | - |
| `uv run mypy src` | typecheck | - |
| `docker compose ps` | docker-read | - |
| `docker compose -f x.yml up -d` | docker-lifecycle | docker_lifecycle |
| `rtk docker compose restart api` | docker-lifecycle | docker_lifecycle |
| `docker build -t x .` | docker-build | docker_build |
| `docker logs api --since 2m` | docker-read | - |
| `git status` | git-other | - |
| `git commit -m x` | git-commit | git_commit |
| `git push origin main` | git-push | git_push |
| `curl -s http://localhost:3000/health` | request-local | - |
| `curl -s http://api:3000/orders` | request-local | - |
| `curl https://example.com/x` | request-external | external_request |
| `cd /tmp && ls` | other | - |

### Checks estáticos (V)

| # | Check | Como rodar | Task |
|---|---|---|---|
| V1 | Hook compila | `python3 -I -m py_compile /home/phrb/dotfiles/.claude/hooks/agent-audit.py /home/phrb/dotfiles/.claude/hooks/agent-metrics.py` | 1, 2 |
| V2 | `agent-audit.json` válido e com as duas categorias | `python3 -I -c "import json;d=json.load(open('/home/phrb/dotfiles/.claude/hooks/agent-audit.json'));c=d['categories'];assert d['mode']=='enforce' and c['design_system_write_by_other']=='warn' and c['design_director_write_outside']=='block'"` | 1 |
| V3 | `settings.json` válido, sem o plugin, com hooks e `ask` intactos | `python3 -I -c "import json;d=json.load(open('/home/phrb/dotfiles/.claude/settings.json'));assert 'frontend-design@claude-plugins-official' not in d['enabledPlugins'];assert set(d['hooks'])=={'PreToolUse','PostToolUse','PostToolUseFailure','SubagentStart','SubagentStop'};assert len(d['permissions']['ask'])==2"` mais `git diff .claude/settings.json` mostrando só uma linha removida | 7 |
| V4 | Sem `frontend-design` na config | `grep -rn frontend-design /home/phrb/dotfiles/.claude --exclude=agent-workflow.md \| grep -v '^/home/phrb/dotfiles/.claude/docs/'` (a spec e o log em `.claude/docs/` citam o plugin de propósito; `--exclude-dir=docs` não serve, porque também tiraria `skills/docs/`): depois da task 7, só `README.md:69` (do `docs-writer`); depois do passe de docs, nada | 5, 7, fim |
| V5 | Frontmatter do agent | script stdlib: o bloco entre os dois `---` tem `name: design-director`, `tools: Read, Grep, Glob, Write, Edit`, `model: opus`, `effort: high`, `skills:` com só `- design-system`, e a description de D22 (f) palavra por palavra | 4 |
| V6 | Template | `grep -n '^## ' .../templates/project-root/DESIGN_SYSTEM.md` mostra `## Layout concept` logo depois de `## Principles`; `grep -n '| Role | Family | Weights | Fallback stack | Source | License |'` acha a tabela; `grep -c 'if the product supports dark mode'` = 0 | 3 |
| V7 | Sem em dash nos arquivos tocados | `grep -nP '\x{2014}' <arquivos da task>` sem saída | todas |
| V8 | Texto dos pontos de entrada | `grep -n design-director` em `skills/design-system/SKILL.md`, `skills/new-project/SKILL.md`, `skills/implement/SKILL.md`, `CLAUDE.md`, `templates/node-ts-react/CLAUDE.md` e `templates/react-native/CLAUDE.md` acha cada mudança da Design, seções 5 e 6 | 5, 6 |
| V9 | Agent cobre as regras | checklist do review: cada seção do corpo cita as regras da tabela da Design 4.2; a lista de padrões tem os 6 itens da regra 16; a fórmula e os mínimos de contraste estão escritos; sem `frontend-design` | 4 |

### Regras do plan -> testes

| Regras | Testes |
|---|---|
| 1, 2 (pré-condição, `Principles` preenchida) | cenários 37, 39; V9 |
| 3 (sem serviço de UI) | U1 |
| 4 (nada automático) | cenários 41, 42; Observabilidade (conferência à mão) |
| 5 (`new-project`) | cenário 41; V8 |
| 6 (frases do Workflow) | cenários 37, 39, 45; V8 |
| 7, 8 (`design-system` e recusa) | cenário 42; V8 |
| 9-11 (rodada 1) | cenários 37, 38 |
| 12-16 (direções, revisão, contraste de eixos, padrões) | cenário 37; U3 |
| 17, 18 (escolha, recusa) | cenários 37, 40 |
| 19-25 (arquivo, cor, contraste, tipografia, tabelas, princípios, idioma) | cenários 37, 44; U4; V6 |
| 26 (mistura que quebra AA) | U2 |
| 27 (próximo passo) | cenário 37 |
| 28 (escrita restrita, tools) | H2, H3, H15-H18, H20, H23-H25; M1, M4, M5; V5; cenário 37 ("nenhum outro arquivo escrito") |
| 29 (manutenção pela sessão principal) | H4-H6, H9, H10, H13, H19, H21, H22, H26-H28; cenário 43; V8 |
| 30 (hook) | H1-H28; G1-G11 |
| 31 (report) | cenários 37-40 (bloco YAML com as chaves da Design 4.10) |
| 32 (entrada autossuficiente) | U5 |
| 33 (UI já em código) | cenário 45 |
| 34 (`Layout concept`) | cenários 37, 44; V6 |

Checks extras de uso real, para regras sem cenário em 14.3 (mesmo ambiente dos cenários; Verification):

| # | Situação | Esperado |
|---|---|---|
| U1 | projeto cuja tabela `Services` só tem backend | `blocked`, `blocked_reason: no-ui-service`, nada escrito |
| U2 | na escolha, mistura com texto claro sobre acento claro | `needs_input` com o par que falha e o ajuste proposto, com as razões; nada escrito |
| U3 | `CONSTRAINTS.md` com cor de marca e uma fonte paga pedida | a marca nas duas direções (`from_brief`); a fonte paga trocada pela alternativa aberta mais próxima, com o motivo |
| U4 | `PRD.md` diz "sem tema escuro" | light e dark preenchidos em todos os tokens |
| U5 | sessão nova, chamada com `choice` em texto e sem `SendMessage` | recheca a pré-condição e vai direto para a rodada 3 |
| U6 | `Principles` vazia e `Color` já com valores | os valores entram como restrição; `changes_to_existing` lista o que mudaria |

## Implementation order

### Task 1 - Hook: isenção de md_outside_docs e categoria design_system_write_by_other

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/agent-audit.json`
- **Depends on:** -
- **Done when:** V1 e V2 passam; os casos H1-H14 dão o esperado da tabela, com o harness pelo stdin (no scratchpad, nunca no repo); G1-G11 e os 37 comandos C continuam iguais à tabela de base; `WHY` tem o texto de `design_system_write_by_other`; o docstring cita o `DESIGN_SYSTEM.md` da raiz; V7 sem saída
- **Status:** done

### Task 2 - Métricas: rótulo da categoria nova e seção design-director

- **Stack:** backend-python
- **Files:** `.claude/hooks/agent-metrics.py`
- **Depends on:** Task 1
- **Done when:** V1 passa; M1-M3 dão o esperado; o relatório de uma sessão sem eventos do `design-director` é igual ao de antes (M3); V7 sem saída
- **Status:** done

### Task 3 - Template DESIGN_SYSTEM.md: criação x manutenção, Layout concept e Font family

- **Stack:** frontend-react
- **Files:** `.claude/templates/project-root/DESIGN_SYSTEM.md`
- **Depends on:** -
- **Done when:** V6 passa; o comentário do topo diz criação pelo `design-director` e manutenção pela sessão principal com a `design-system`; o comentário de `Color` pede light e dark sempre; `Layout concept` tem conceito, wireframe por plataforma e a tabela de padrões evitados com `Source`; `Font family` é a tabela da Design 3; o resto do template não muda; V7 sem saída
- **Status:** done

### Task 4 - Agent design-director

- **Stack:** frontend-react
- **Files:** `.claude/agents/design-director.md`
- **Depends on:** Task 3
- **Done when:** V5 e V9 passam; o corpo tem as seções da Design 4.2, na ordem, com o contrato de entrada (4.3), a pré-condição (4.4), as três rodadas (4.5-4.7), a fórmula e os pares de contraste (4.8), escrita e erros (4.9) e o report YAML (4.10); `grep -c frontend-design` = 0; V7 sem saída. O `md_outside_docs` (`warn`) ao criar o arquivo é o falso positivo esperado e vai em `decisions`
- **Status:** done

### Task 5 - Manutenção: design-system e os CLAUDE.md dos templates

- **Stack:** frontend-react
- **Files:** `.claude/skills/design-system/SKILL.md`, `.claude/templates/node-ts-react/CLAUDE.md`, `.claude/templates/react-native/CLAUDE.md`
- **Depends on:** Task 4
- **Done when:** a description cita o `design-director` e a manutenção; o passo 1 tem as quatro situações da tabela da Design 5 (oferta, extração, valor proposto e a nota para o próprio `design-director`); a linha 25 dos dois templates fica como na Design 5; `grep -n frontend-design` nos três arquivos sem saída; V8 (parte desses arquivos) e V7 sem saída
- **Status:** done

### Task 6 - Pontos de entrada: new-project, Workflow global e exceção no implement

- **Stack:** frontend-react
- **Files:** `.claude/skills/new-project/SKILL.md`, `.claude/CLAUDE.md`, `.claude/skills/implement/SKILL.md`
- **Depends on:** Task 4, Task 5
- **Done when:** o item do `DESIGN_SYSTEM.md` no passo 3.1 do `new-project` pergunta só com serviço de UI, chama o `design-director` só depois do sim e de `PRD.md`, `CONSTRAINTS.md` e `Services` preenchidos, e no "não" deixa as tabelas em branco sem repetir a pergunta; o passo 8 relata a direção; o `CLAUDE.md` global tem a linha nova logo depois de `Discover` e o bullet de `scope_requests` sobre o `DESIGN_SYSTEM.md`; o passo 5.2 do `implement` tem a exceção da Design 6 (o caminho nunca entra em `allowed_paths`); V8 e V7 sem saída
- **Status:** done

### Task 7 - settings.json: remover o plugin frontend-design

- **Stack:** backend-python
- **Files:** `.claude/settings.json`
- **Depends on:** Task 5
- **Done when:** V3 passa; `git diff` do arquivo mostra só a linha do plugin removida; V4 mostra só `README.md:69`. A edição passa pela confirmação do usuário (regra `ask`)
- **Status:** done

## Verification

O repo não tem `CLAUDE.md` na raiz nem tabela `Test suites`: não há suite com nome para o `test-runner` (nem `on-demand`). No fim do run, a sessão principal roda os checks abaixo, todos de leitura, com o harness no scratchpad:

1. **Estáticos**: V1-V9 (Testing), incluindo `settings.json` e `agent-audit.json` válidos (V2, V3). V4 é rodado de novo depois do passe do `docs-writer` e deve voltar vazio.
2. **Hook pelo stdin**: H1-H28, M1-M5, G1-G11, os 37 comandos C e D1-D10 (`harness.py`, 119 checks, e `m/harness_m.py`, 9 checks, no scratchpad), contra uma cópia de `.claude/hooks/` atualizada, com `AGENT_AUDIT_DIR` no scratchpad (as métricas reais em `~/.claude/metrics/` não são tocadas).
3. **Hook ao vivo** (sessão atual, sem projeto): nada a rodar, porque nenhum dos casos acima depende do Claude Code. O `warn` chegando ao contexto do agent continua como pendência da etapa G.

**Uso real, pelo usuário, numa sessão nova do Claude Code** (agents novos só aparecem nela), em projetos descartáveis fora do dotfiles (ex.: `~/sandbox/ds-*`, cada um com `git init`, um `CLAUDE.md` com a tabela `Services` e um `PRD.md`):

| Cenário (14.3) | Montagem | O que conferir |
|---|---|---|
| 37 | projeto web sem `DESIGN_SYSTEM.md`, `PRD.md` completo; dizer "cria a identidade visual" | rodada 2 com duas direções que diferem em 2 de 3 eixos e trazem `patterns_review`; depois da escolha, o arquivo tem todas as tabelas, light e dark, `Layout concept`, `Font family` com origem e licença, e as razões no report e em `Usage`; `git status` mostra só o `DESIGN_SYSTEM.md` |
| 38 | `PRD.md` sem público | só as perguntas do que falta, nenhuma direção |
| 39 | `DESIGN_SYSTEM.md` com `Principles` preenchida | `blocked` (`principles-filled`), arquivo intocado (`git diff` vazio), aponta a `design-system` |
| 40 | recusar as duas direções | nova rodada 2 com duas direções novas que citam a recusa; nada escrito |
| 41 | `/new-project` com `frontend=react`, uma vez "sim" e outra "não" | sim: o agent roda depois do `PRD.md`; não: tabelas em branco e nenhuma pergunta repetida; nenhuma chamada antes da resposta |
| 42 | `/implement` de uma spec com task `frontend-react` num projeto sem `DESIGN_SYSTEM.md` | `frontend-react` `blocked` com `scope_requests`; a pergunta é "criar a direção com o `design-director`?"; o agent só roda depois do sim; no não, a task fica `partial` sem token inventado; `approved_scope` registra a decisão |
| 43 | pedir ao `frontend-react` que acrescente um token ao `DESIGN_SYSTEM.md` | o hook avisa `design_system_write_by_other`; o agent reporta o valor em `scope_requests`; a sessão principal grava depois do sim |
| 44 | monorepo com `web` (react) e `mobile` (react-native) | um só `DESIGN_SYSTEM.md` na raiz; um wireframe por plataforma na rodada 2 e em `Layout concept`; famílias que servem para web e `expo-font` |
| 45 | projeto com `tailwind.config.ts` com cores próprias, sem `DESIGN_SYSTEM.md`; dizer "cria a identidade visual" | a sessão principal segue para a extração com a `design-system` (ou o agent termina `blocked` com `ui-tokens-in-code`); os tokens documentados são os do código |

Mais U1-U6 (Testing) no mesmo ambiente. No fim: `python3 ~/.claude/hooks/agent-metrics.py --since 2026-11-11 --merge`, conferindo `design_system_write_by_other` = 0 fora do cenário 43, `design_director_write_outside` = 0, `writes other than to a DESIGN_SYSTEM.md` = 0 e, no transcript, que cada chamada do `design-director` teve um sim antes.

**Para o usuário conferir na leitura** (sem prints): a direção do cenário 37 lida no `DESIGN_SYSTEM.md` (paleta, pares de contraste num verificador WCAG, wireframes legíveis em fonte monoespaçada) e o texto das perguntas que aparecem nos cenários 41 e 42.

## Open questions

Nenhuma que bloqueie as tasks. As da primeira rodada desta spec foram respondidas em 2026-11-11 (Background, S1-S6). Fica para depois, fora da etapa H:

1. Suite pytest versionada para o hook (H, G, C e M como testes), com a linha correspondente numa futura tabela `Test suites` do repo (S6).
2. O falso positivo de `md_outside_docs` quando a sessão principal cria arquivos da raiz (`new-project`, extração) entra na análise de promoção a `block` (S5).

## Review changes (2026-11-11)

Depois das tasks 1-7, os achados do `code-reviewer` e do `security-reviewer` viraram dois passes de correção (log: "Review fix r1" e "Review fix r2"), aprovados pelo usuário, e o usuário aprovou um escopo acrescentado (log: "Added scope r3"); os textos do hook e das métricas foram alinhados à regra do nome em "Review fix r4". Esta spec foi atualizada no lugar para refletir o que foi implementado; as tasks continuam `done`.

| # | Mudança | Seções |
|---|---|---|
| R1 | Categoria nova `design_director_write_outside` (`block`): o hook nega toda escrita do `design-director` fora de um `DESIGN_SYSTEM.md`, também sem raiz git; entradas em `WHY` e `FLAG_LABELS`. Substitui a escolha S4 de só medir | Summary, Background S4, Design 2.1-2.3, 9, 10, Alternatives |
| R2 | Proteção pelo nome (`name.casefold() == "design_system.md"`, em qualquer pasta do repo) no lugar da comparação exata com o da raiz; `ROOT_DESIGN_SYSTEM` saiu. Cobre monorepo e sistemas de arquivos sem caixa | Design 1, 2.1, 2.3, Alternatives, Trade-offs |
| R3 | Consequência aceita de R2: o template `.claude/templates/project-root/DESIGN_SYSTEM.md` também é protegido, sem caso especial | Design 1, 2.1, Trade-offs |
| R4 | Alvos de `approved_scope` que são um `DESIGN_SYSTEM.md` saem dos caminhos permitidos derivados pelo hook | Design 2.1, 6, Alternatives |
| R5 | `design-director`: deny nunca repetido, termina `blocked` (`hook-denied`) com o estado do arquivo; warn numa escrita que deu certo vai no report e a rodada continua | Design 4.9 |
| R6 | `design-director`: serviço de UI só pela stack (`react`, com Next.js e Vite com React; `react-native`, com Expo), como no `new-project`; o nome do serviço não conta | Design 4.4 |
| R7 | Pedido de extração com forma fixa (`action: create`, `target: DESIGN_SYSTEM.md`, `reason: extraction of tokens in <files>`) e os três ramos no `implement` 5.2 e no bullet do `CLAUDE.md` global | Design 5, 6 |
| R8 | Testes: H2 agora silencioso, H3 agora deny `design_director_write_outside`, H10 agora warn `design_system_write_by_other`, M1 com 1 escrita fora; casos novos H15-H28 e M4-M5; V2 com as duas categorias; V4 sem `.claude/docs/` | Testing, Verification |
| R9 | Pasta de docs movida de `docs/` para `.claude/docs/` a pedido do usuário | Design 1, Testing (V4) |
| R10 | Escopo acrescentado (log "Added scope r3"): `"docs_roots": ["docs/", ".claude/docs/"]` no `agent-audit.json`, usada pelo hook para a área de docs e para o dono de `<root>backlog/`, com normalização e fallback `["docs/"]` | Design 1, 2.2 |
| R11 | Textos das mensagens e das métricas sem "root" (log "Review fix r4"): o `WHY` de `design_system_write_by_other` diz "a project's DESIGN_SYSTEM.md (any directory)", o rótulo começa com "a DESIGN_SYSTEM.md written by", e a linha passa a ser `writes other than to a DESIGN_SYSTEM.md: N (target 0)`; o exemplo mostra o `rel`, ou o `path` quando não há `rel` | Design 2.1, 2.3, 9; Testing (M1-M5); Verification |
