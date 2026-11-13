# skills-docs-root - raiz de docs por projeto, declarada uma vez e lida pelo hook e pelas skills

- **Date:** 2026-11-12
- **Status:** Implemented
- **Source:** [docs/backlog/refactor/2026-11-11-skills-configurable-docs-root.md](../../backlog/refactor/2026-11-11-skills-configurable-docs-root.md) (refactor sem plan; não há `plan.md` nesta pasta)
- **Implementation log:** [log.md](log.md) (criado pelo `/implement` na primeira task)

## Summary

A raiz de docs de um projeto (`docs/` por padrão) passa a ser declarada num único lugar: a linha `- docs root: <caminho>/` na seção `## Workflow` do `CLAUDE.md` da raiz git, ao lado da `- docs layout:` que já existe ali. O hook `agent-audit` lê essa linha por raiz git (sai o `docs_roots` global do `agent-audit.json`), e a skill `project-docs` resolve todos os caminhos (plan, spec, log, backlog, Index, requests, quality) a partir dela. As skills, os agents e o `CLAUDE.md` global trocam o `docs/` fixo pelo marcador `<docs>/`, que a `project-docs` define. Este repo declara `- docs root: .claude/docs/`, e um teste do `claude-hooks` prende essa declaração.

| Camada | Arquivos | Mudança |
|---|---|---|
| Hook | `.claude/hooks/agent-audit.py`, `.claude/hooks/agent-audit.json` | `normalize_docs_root()` e `project_docs_root()` (novos) substituem `docs_roots()`; cada raiz git julgada usa a própria declaração; sai a chave `docs_roots`; textos de `WHY` |
| Métricas | `.claude/hooks/agent-metrics.py` | rótulos de `md_outside_docs` e `docs_write_by_implementer` falam em "docs root" |
| Declaração deste repo | `CLAUDE.md` (raiz do repo) | `- docs root: .claude/docs/` e o parágrafo da `## Workflow` reescrito |
| Testes | `hooks/tests/_support.py`, `test_write_areas.py`, `test_config_contract.py`, `test_hook_process.py` | sai `docs_roots` do `TEST_CONFIG`; D1-D11 substituídos por DR1-DR17; F4 reescrito; P-DR novo |
| Skill fonte | `.claude/skills/project-docs/SKILL.md` | subseção **Docs root** em **Layouts and path resolution**; todo caminho passa a `<docs>/...` |
| Outras skills e global | `implement`, `fix-bug`, `onboard`, `implementer-contract`, `docs`, `.claude/CLAUDE.md` | `<docs>/...` no lugar de `docs/...`; `onboard` grava a declaração |
| Agents | `planner`, `specker`, `backlog-keeper`, `docs-writer`, `code-reviewer`, `test-writer`, `quality-fixer`, 5 backends | `<docs>/...`; `planner` e `specker` podem gravar a linha `docs root` após o sim do usuário |
| Templates | `templates/docs-structure/features/_template/spec.md`, `templates/project-root/CLAUDE.md` | **Source** como link relativo; dica comentada da declaração |
| Docs (fim, `docs-writer`) | `.claude/README.md`, `.claude/agent-workflow.md` (6.1.1, 13.5) | needs_docs |

Sem serviço, API, banco nem flag. Projetos sem declaração continuam em `docs/` sem mudança de comportamento.

## Background

**O problema.** Este repo guarda os docs em `.claude/docs/` (a pasta não é linkada em `~/.claude`). O hook já aceita raízes configuráveis, mas as skills só conhecem `docs/` na raiz do repo, então todo caminho de feature teve de ser passado à mão para `/implement`, `specker` e os demais (`agent-workflow.md` 13.5, último item; `.claude/README.md`, item `docs_roots`; os run states em `.claude/runs/*.json` gravam `"feature": ".claude/docs/features/<slug>/"` só porque o caminho veio explícito).

**Como o hook faz hoje.** `docs_roots(config)` (`agent-audit.py`, linhas 125-149) lê a lista `docs_roots` do `agent-audit.json`, normaliza cada item e cai em `["docs/"]` se faltar ou for inválida. `main()` passa a lista a `evaluate_write(..., roots)`, e `_assess_root` a usa para `area == "docs"` (isenção de `md_outside_docs`, gatilho de `docs_write_by_implementer`) e para `<raiz>backlog/` (`backlog_write_by_other`). O valor vivo é `["docs/", ".claude/docs/"]`.

**Por que o `docs_roots` global não serve de fonte para as skills.** `~/.claude` é symlink para este `.claude/`, então o `agent-audit.json` vale para **todos** os projetos das duas máquinas: hoje `.claude/docs/` conta como área de docs em qualquer repo, e `docs/` conta neste repo, onde a pasta nem existe. É uma lista de candidatos, não "a raiz deste projeto"; uma skill que a lesse teria de adivinhar qual entrada vale (e este próprio repo tem um falso candidato: `.claude/templates/docs-structure/features/README.md`). A raiz é um fato do projeto, e o lugar dos fatos do projeto que o workflow lê é a `## Workflow` do `CLAUDE.md` da raiz, onde já mora `- docs layout:` (e onde este repo já escreve, em prosa, "This repo's docs root is `.claude/docs/`").

**Qual `CLAUDE.md`.** O da raiz git (`git rev-parse --show-toplevel`), o mesmo que o hook usa para achar o run (`<raiz>/.claude/runs/`). Neste repo isso importa: a sessão costuma começar em `.claude/`, e `.claude/CLAUDE.md` é o **global** (também tem `## Workflow`, sem declaração de projeto). Ler o `CLAUDE.md` do diretório de trabalho daria a resposta errada.

**Skills e symlink.** `~/.claude/skills`, `~/.claude/agents`, `~/.claude/templates` e `~/.claude/hooks` são symlinks para as pastas deste repo (conferido com `ls -la ~/.claude`): editar `.claude/skills/...` aqui muda o que todas as sessões carregam. Não há cópia a sincronizar.

**Inventário de `docs/` fixo** (`grep -rnE '(^|[^a-zA-Z_./-])docs/'` em `.claude/agents`, `.claude/skills`, `.claude/templates`, `.claude/CLAUDE.md`):

| Arquivo | Ocorrências | Decisão |
|---|---|---|
| `skills/project-docs/SKILL.md` | 25 | em escopo (fonte da resolução) |
| `skills/implement/SKILL.md` | 4 (argument-hint, passo 1.1, 1.2.3, run state) | em escopo |
| `skills/fix-bug/SKILL.md` | 2 (argument-hint, passo 1.1) | em escopo |
| `skills/onboard/SKILL.md` | 1 (`## Workflow`) | em escopo: passa a gravar a declaração |
| `skills/implementer-contract/SKILL.md` | 4 (13, 58, 84, 115) | em escopo |
| `skills/docs/SKILL.md` | 1 (10) | em escopo |
| `.claude/CLAUDE.md` (global) | 3 (28, 33, 45) | em escopo |
| `agents/specker.md`, `backlog-keeper.md`, `planner.md`, `docs-writer.md` | 6, 6, 5, 4 | em escopo |
| `agents/code-reviewer.md`, `test-writer.md`, `quality-fixer.md` | 2, 2, 1 | em escopo |
| `agents/backend-{go,node,python,rust,spring}.md` | 1 cada (`needs_docs`: `docs/requests/`) | em escopo |
| `templates/docs-structure/features/_template/spec.md` | 1 (**Source**) | em escopo: link relativo, vale para qualquer raiz |
| `templates/project-root/CLAUDE.md`, `STRUCTURE.md`, `PRD.md` | 3, 3, 2 | fora: descrevem um projeto novo, que sempre usa `docs/`; o `CLAUDE.md` ganha só uma dica comentada |
| `skills/new-project/SKILL.md` | 3 | fora: projeto novo faz scaffold em `docs/` (o padrão), sem declaração |
| `skills/pr-description`, `tdd`, `grill-me`, `bug-repro`, `design-system` | 0 | sem mudança: já resolvem pela `project-docs` ou não citam caminhos |
| `skills/archify`, `writing-guidelines` | 1 cada | fora: "docs/" com outro sentido (exemplos, prosa) |
| `.claude/README.md`, `.claude/agent-workflow.md` | 14, 53 | docs: `docs-writer` no fim (needs_docs); o `agent-workflow.md` é registro de projeto, só 6.1.1 e 13.5 mudam |
| docstrings dos testes do hook (`docs/backlog/...`) | ~15 | fora (out_of_scope_issues) |

**Stack das tasks de markdown.** Não há stack para prosa de skill e agent; segue a convenção da spec [design-director](../design-director/spec.md) (tasks 3-6 com `frontend-react`).

**Fora do escopo:** mais de uma raiz de docs por projeto (docs por serviço num monorepo), raiz de projeto diferente da raiz git, as entradas abertas sobre `md_outside_docs` ([audit-md-outside-docs-false-positive](../../backlog/refactor/2026-11-11-audit-md-outside-docs-false-positive.md), [audit-md-exemption-basename](../../backlog/refactor/2026-11-12-audit-md-exemption-basename.md), [audit-docs-write-flag-implementers-only](../../backlog/refactor/2026-11-12-audit-docs-write-flag-implementers-only.md)) e [audit-nested-repo-run-lookup](../../backlog/refactor/2026-11-11-audit-nested-repo-run-lookup.md).

## Design

### 1. Regras

| # | Regra |
|---|---|
| R1 | A raiz de docs de um projeto é declarada uma vez: `- docs root: <caminho>/` na seção `## Workflow` do `CLAUDE.md` da raiz git, relativa à raiz git. Sem declaração: `docs/` |
| R2 | Hook e skills leem a mesma linha com as mesmas regras de normalização; não existe outro lugar que defina a raiz (sai `docs_roots` do `agent-audit.json`) |
| R3 | Valor inválido (vazio, absoluto, com `..`): o hook cai em `docs/` sem quebrar a sessão; as skills param e perguntam ao usuário, nunca caem em `docs/` em silêncio |
| R4 | Um projeto tem exatamente uma raiz; com outra raiz declarada, `docs/` não é área de docs |
| R5 | Só conta a seção `## Workflow` do `CLAUDE.md` da raiz git (não o `.claude/CLAUDE.md`, não outra seção); dentro dela, a primeira linha `docs root` decide |
| R6 | No hook, cada raiz git julgada (repo aninhado incluso) usa a própria declaração |
| R7 | Skills e agents escrevem os caminhos como `<docs>/...` e resolvem `<docs>` pela `project-docs`; entre agents e no run state circula o caminho resolvido, relativo à raiz git (`.claude/docs/features/x/`), nunca o marcador |
| R8 | A declaração só é gravada quando a árvore não está em `docs/`: scaffold fora de `docs/`, `onboard`, ou o sim do usuário à oferta da `project-docs` |
| R9 | Este repo declara `.claude/docs/`, e o `claude-hooks` falha se a declaração sumir, mudar ou apontar para uma árvore inexistente |
| R10 | `CLAUDE.md` ausente, ilegível, diretório, binário ou enorme nunca levanta exceção no hook; vale como sem declaração |

*Adendo 2026-11-13:* R10 passa a cobrir também FIFO e dispositivo (direto ou por symlink), que não podem bloquear o hook; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A1.

### 2. Formato da declaração (contrato comum)

```markdown
## Workflow

- docs layout: features
- docs root: .claude/docs/
```

| Item | Regra |
|---|---|
| Arquivo | `<raiz git>/CLAUDE.md`; nenhum outro |
| Seção | começa numa linha `## Workflow` (espaços nas pontas e caixa ignorados) e termina na próxima linha que começa com `# ` ou `## `; `###` dentro dela continua na seção |
| Linha | `-` ou `*`, espaço, `docs root:` (caixa ignorada), valor; a primeira que casar decide |
| Valor | tira espaços e um par de crases nas pontas; `\` vira `/`; segmentos vazios e `.` saem; termina com uma `/` |
| Inválido | vazio depois disso, começa com `/` ou `~`, letra de drive (`C:`), segmento `..`, caractere de controle |
| Exemplos | `.claude/docs` -> `.claude/docs/`; `` `./kb/` `` -> `kb/`; `a//b/./c` -> `a/b/c/`; `/abs`, `~/x`, `C:/x`, `.`, `a/../b`, vazio -> inválido |

A `project-docs` é a definição em prosa; `normalize_docs_root()` e `project_docs_root()` no hook são a implementação, e os testes DR1-DR9 fixam a tabela acima.

### 3. `.claude/hooks/agent-audit.py`

**Sai:** `docs_roots(config)` e `DEFAULT_DOCS_ROOTS` (único uso de `config["docs_roots"]`; conferido por grep). **Entra** `DEFAULT_DOCS_ROOT = "docs/"`.

**`normalize_docs_root(raw: object) -> str | None`**: a linha "Valor"/"Inválido" da tabela da seção 2. Não é `str` -> `None`. Nunca levanta.

**`project_docs_root(root: Path) -> str`**: lê no máximo 256 KiB de `root / "CLAUDE.md"` em bytes (`open(..., "rb").read(262144)`), decodifica UTF-8 com `errors="replace"`, percorre as linhas com dois regex de módulo:

```python
WORKFLOW_HEADING = re.compile(r"^##[ \t]+workflow[ \t]*$", re.I)
SECTION_END = re.compile(r"^#{1,2}[ \t]")
DOCS_ROOT_LINE = re.compile(r"^[ \t]*[-*][ \t]+docs root:[ \t]*(.*?)[ \t]*$", re.I)
```

A primeira `DOCS_ROOT_LINE` dentro da seção decide: `normalize_docs_root(valor) or DEFAULT_DOCS_ROOT`. Sem seção, sem linha, arquivo ausente ou qualquer exceção (diretório, permissão) -> `DEFAULT_DOCS_ROOT`. Docstring cita a `project-docs` (**Layouts and path resolution**, **Docs root**) e R1, R3, R5, R10.

*Adendo 2026-11-13:* a abertura do arquivo mudou (não bloqueante, só arquivo regular); ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A1.

**`evaluate_write(path_str, cwd, actor, tool, response, roots=None, scratchpad=None)`**: `roots` continua (override explícito, usado pelos testes de área); com `None`, cada raiz julgada usa `[project_docs_root(root)]`:

```python
found, cur = _assess_root(root, forms, actor, tool, created, roots or [project_docs_root(root)], scratch=sp)
```

Sai a linha `roots = roots or DEFAULT_DOCS_ROOTS`. A docstring ganha: "docs area = `roots` when given, else the governing root's declared docs root (`project_docs_root`)".

**`main()`**: `evaluate_write(path, cwd, actor, tool, response, scratchpad=...)`, sem `docs_roots(config)`. Uma chave `docs_roots` que sobre num config antigo é ignorada.

**`WHY`**:

| Categoria | Texto novo |
|---|---|
| `md_outside_docs` | `notes, summaries and other .md files outside the project's docs root (docs/, or the "- docs root:" line of the root CLAUDE.md ## Workflow) are not created; documentation needs go to needs_docs` |
| `backlog_write_by_other` | `<docs root>/backlog/ (docs/backlog/ unless the root CLAUDE.md declares a docs root) is written only by backlog-keeper; report it in out_of_scope_issues` |

**Docstring do módulo**: "docs and backlog files" passa a "docs and backlog files (under the project's docs root: `- docs root:` in the root CLAUDE.md `## Workflow`, default `docs/`)". O comentário de `DOC_FILES` ("outside the docs roots (agent-audit.json `docs_roots`)") passa a "outside the project's docs root".

**Comportamento resultante** (ator `main`, `Write` de arquivo novo):

| Repo | Alvo | `area` | Flags |
|---|---|---|---|
| este, declara `.claude/docs/` | `.claude/docs/features/x/spec.md` | `docs` | nenhuma |
| este | `docs/notes.md` | `code` | `md_outside_docs` (antes: `docs`) |
| este, ator `specker` | `.claude/docs/backlog/refactor/x.md` | `docs` | `backlog_write_by_other` |
| outro, sem declaração | `docs/features/x/plan.md` | `docs` | nenhuma (igual a hoje) |
| outro, sem declaração | `.claude/docs/x.md` | `code` | `md_outside_docs` (antes: `docs`) |

### 4. `.claude/hooks/agent-audit.json`

Saem `docs_roots` e `_docs_roots`. Entra só um comentário, para quem procurar a chave antiga:

```json
"_docs_root": "The docs area is per project: the \"- docs root: <path>/\" line of the root CLAUDE.md ## Workflow section (default docs/), read by the hook and by the project-docs skill. There is no docs key here."
```

`mode` e `categories` não mudam.

### 5. `.claude/hooks/agent-metrics.py`

Só `FLAG_LABELS`:

| Chave | Texto novo |
|---|---|
| `md_outside_docs` | `new .md files outside the docs root (target 0)` |
| `docs_write_by_implementer` | `docs (docs root, README, CHANGELOG, .env.example, DEPLOY.md) edited by implementers - docs-writer owns them (target 0)` |

### 6. `CLAUDE.md` da raiz deste repo

A seção `## Workflow` fica exatamente assim (o resto do arquivo não muda). Vai na Task 1, como **primeira** edição dela, porque o hook novo lê esta linha: sem ela, o `log.md` e as escritas do próprio run em `.claude/docs/` passariam a gerar `md_outside_docs`.

```markdown
## Workflow

- docs layout: features
- docs root: .claude/docs/

This repo's docs live under `.claude/docs/`, not `docs/` (the folder is not linked into `~/.claude`). The `docs root` line above is the single source: the `project-docs` skill resolves every plan, spec, log and backlog path under it, and the `agent-audit` hook reads it to define the docs area.
```

As linhas `- docs ...` da `## Workflow` são declarações lidas por máquina (como `docs layout`, que `planner` e `specker` já gravam), não prosa de documentação; por isso entram numa task de código, com o texto fixado aqui.

### 7. `.claude/skills/project-docs/SKILL.md`

**Subseção nova**, no início de **Layouts and path resolution** (antes de **Two layouts**), exatamente:

```markdown
**Docs root.** Every path in this skill is relative to the project's docs root, written `<docs>/`. Resolve it before the layout:

1. The root `CLAUDE.md` - the one at the git root (`git rev-parse --show-toplevel`), even when the session starts in a subfolder; never `.claude/CLAUDE.md` - declares it in its `## Workflow` section: `- docs root: <path>/`, relative to the git root (for instance `- docs root: .claude/docs/`). The section ends at the next `#` or `##` heading; the first `docs root` line inside it counts.
2. No declaration: `docs/`.

Normalize the value: drop surrounding spaces and backticks, turn `\` into `/`, drop empty and `.` segments, end with one `/`. A value that is empty, absolute (`/`, `~`, a drive letter) or has a `..` segment is invalid: stop and tell the user the line is invalid (subagents return it as `needs_input`); never fall back to `docs/` silently. The `agent-audit` hook reads the same line with the same rules (it falls back to `docs/`, because a hook never stops a session); nothing else defines the docs root.

`<docs>` is only a placeholder in these instructions. Agents, skills and the run state always carry the resolved path, relative to the git root (`.claude/docs/features/<slug>/`, never `<docs>/features/<slug>/`), and tool calls use absolute paths.

A project has exactly one docs root; with another one declared, `docs/` is not part of the docs tree. The line is written only when the tree is not at `docs/`: by scaffold mode when it scaffolds elsewhere, by `onboard` when it finds the tree elsewhere, and after a yes to the offer below.

**Docs root offer.** No declaration, no `docs/`, and the user points at a tree elsewhere (for instance passes `.claude/docs/features/x/`): ask once "record `- docs root: .claude/docs/` in the root `CLAUDE.md`?" (subagents return it as `needs_input`). Yes: the agent that asked writes the line in `## Workflow` (create the section if missing), next to `docs layout`. No: use the given path for this run only.
```

**Demais edições do arquivo** (regra: todo `docs/` que nomeia a árvore vira `<docs>/`; nada muda de sentido):

| Lugar | Mudança |
|---|---|
| frontmatter `description` | "a project's docs/ tree" -> "a project's docs tree (`docs/` by default, or the declared docs root)"; "migrate a legacy docs/" -> "migrate a legacy tree" |
| abertura e diagrama | "Maintains the `<docs>/` tree (`docs/` unless the project declares another docs root, see **Docs root**)"; raiz do diagrama `<docs>/` |
| **Evolving the structure**, parágrafo do `PRD.md` | `<docs>/` |
| **Two layouts** (`legacy`) e **Detection** 2-3 | `<docs>/plans/`, `<docs>/specs/`, `<docs>/features/` |
| **One-time migration offer** | "migrate `<docs>/` to `<docs>/features/` now?"; no mesmo parágrafo: `planner`/`specker` gravam a linha `docs layout` como antes |
| **Path map** | prefixo `<docs>/` em todas as células de caminho; linha "what an agent receives": `feature: <docs>/features/<slug>/` e `spec: <docs>/specs/<file>.md`, com a nota "(resolved: `feature: .claude/docs/features/<slug>/` when the docs root is `.claude/docs/`)" |
| **Scaffold mode** | abertura "Use when `<docs>/` is missing..."; passo 1: "Confirm the docs root: the resolved one (`docs/` by default). If the user wants the tree elsewhere (for instance under one service of a monorepo), scaffold there and record `- docs root: <path>/` (step 6); a project has one docs root."; passo 3: "Copy ... into `<docs>/`"; passo 6: "... says `- docs layout: features`, plus `- docs root: <path>/` when the root is not `docs/`" |
| **Add entry mode** passo 3 e 6 | `<docs>/backlog/bugs/...`, `<docs>/backlog/refactor/...`, `<docs>/quality/...` (e `<docs>/quality/README.md`), `<docs>/concepts/...`, `<docs>/requests/`; "the rest of `<docs>/`" |
| **Migrate mode** passos 1 e 5 | "`git status` for `<docs>/`"; "every reference to the old paths in `<docs>/`, `PRD.md`, ... (grep for `<docs>/plans/` and `<docs>/specs/`)" |

*Adendo 2026-11-13:* dois trechos do bloco exato acima foram substituídos (quem grava a linha na **Docs root offer**; caractere de controle na lista de inválidos); ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A2 e A3.

### 8. Outras skills e o `CLAUDE.md` global

| Arquivo | Lugar | Mudança |
|---|---|---|
| `skills/implement/SKILL.md` | `argument-hint` | `<<docs>/features/<slug>/ or <docs>/specs/file.md> ...` |
| | passo 1.1 | acrescenta: "This includes the docs root: a feature passed by slug or title is looked up under the resolved `<docs>/`; a path the user passes outside it triggers the project-docs **Docs root offer** (asked by you, the main session, which writes the line on yes)." O "Never hard-code `docs/plans`, `docs/specs` or `docs/features`" vira "Never hard-code a docs path; every path starts at the resolved docs root." |
| | passo 1.2.3 | `<docs>/features/README.md` |
| | seção 3, JSON | `"feature": "<docs>/features/<slug>/"`; frase nova abaixo do bloco: "`feature`, `spec` and `log` hold resolved paths relative to the git root (`.claude/docs/features/<slug>/` when the docs root is `.claude/docs/`)." |
| `skills/fix-bug/SKILL.md` | `argument-hint` e passo 1.1 | `<docs>/backlog/bugs/`; no 1.1: "(resolved with the project-docs skill)" |
| `skills/onboard/SKILL.md` | passo 6, item `## Workflow` | "the docs layout, detected as the `project-docs` skill describes, and `- docs root: <path>/` when the project's docs tree is not at `docs/` (when `docs/` is missing and you find a tree with `features/`, `plans/` or `backlog/` elsewhere, ask the user to confirm it; never guess between candidates). Do not migrate a legacy tree here; just record what exists." |
| `skills/implementer-contract/SKILL.md` | linhas 13, 58, 84, 115 | `<docs>/features/<slug>/`, `<docs>/requests/`, `<docs>/backlog/`, `<docs>/requests`; na 13: "the feature folder (`<docs>/features/<slug>/`, resolved: `.claude/docs/features/<slug>/` when the docs root is `.claude/docs/`)" |
| `skills/docs/SKILL.md` | linha 10 | `<docs>/requests/` |
| `.claude/CLAUDE.md` (global) | linha 28 | "of `<docs>/backlog/` (`<docs>` = the project's docs root, `docs/` unless declared; see `## Workflow`)" |
| | linha 33 | "(README, `.env.example`, `<docs>/`, notes, summaries)" |
| | linha 45 | "Plans, specs, logs and the backlog are found through the `project-docs` skill, under the project's docs root `<docs>/`: `docs/`, unless the root `CLAUDE.md` `## Workflow` declares `- docs root: <path>/` (`<docs>/features/<slug>/`, or `<docs>/plans` + `<docs>/specs` in legacy projects)." |

*Adendo 2026-11-13:* o texto do passo 1.1 do `implement` e a linha 13 do `implementer-contract` foram substituídos; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A4 e A5.

### 9. Agents

Regra geral: o mesmo `docs/` -> `<docs>/`. Onde o texto é escopo de escrita ou a frase "never hard-code", a redação é a da tabela.

| Arquivo | Linhas | Mudança |
|---|---|---|
| `agents/planner.md` | 3 | "into the project's docs tree (`<docs>/`)" |
| | 14 | "You only write inside `<docs>/`, plus the `docs layout` and `docs root` lines of the root `CLAUDE.md` `## Workflow` section when the project-docs migration decision or docs root offer requires it." |
| | 18, 19, 27 | `<docs>/`; 19: "never hard-code a docs path. If the docs tree does not exist at `<docs>/`, scaffold it first, as project-docs describes (a path the user gave elsewhere is the docs root offer first)." |
| `agents/specker.md` | 3, 14, 18, 21, 37, 76 | iguais ao `planner` (14 com as duas linhas); 21 e 76: `<docs>/backlog/refactor/` |
| `agents/backlog-keeper.md` | 3 | "Single writer of the project's backlog (`<docs>/backlog/`; `<docs>` is the docs root, `docs/` by default) - ..." |
| | 12, 24, 33, 45, 62 | `<docs>/backlog/`, "the rest of `<docs>/`"; 24: "Resolve `<docs>/backlog/` with the project-docs skill (docs root first)." |
| `agents/docs-writer.md` | 3, 30, 33, 39 | `<docs>/requests`, `<docs>/concepts`, `<docs>/features/`, `<docs>/backlog/` |
| `agents/code-reviewer.md` | 22, 47 | "(`<docs>/features/<slug>/` or `<docs>/specs/`, resolved with project-docs)"; "README, `<docs>/`, API docs" |
| `agents/test-writer.md` | 22, 70 | "the relevant plan/spec (resolved with project-docs)"; `<docs>/backlog/` |
| `agents/quality-fixer.md` | 51 | `<docs>/backlog/` |
| `agents/backend-{go,node,python,rust,spring}.md` | 1 linha cada (`needs_docs`) | `<docs>/requests/` |

*Adendo 2026-11-13:* todo agent que usa `<docs>` diz como ele é resolvido no parágrafo do primeiro uso, e o `specker` ganha a cláusula de scaffold do `planner`; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A5.

### 10. Templates

| Arquivo | Mudança |
|---|---|
| `templates/docs-structure/features/_template/spec.md`, linha 5 | comentário passa a: `<!-- for a refactor without a plan, replace with: **Source:** [<entry>](../../backlog/refactor/<entry>.md) -->` (relativo à pasta da feature: vale para qualquer raiz) |
| `templates/project-root/CLAUDE.md`, `## Workflow` | depois de `- docs layout: features`, a linha `<!-- Add "- docs root: <path>/" only when the docs tree is not at docs/ (project-docs, Layouts and path resolution). -->`; o resto fica (projeto novo usa `docs/`) |

### 11. Segurança, privacidade e observabilidade

- **Quem pode mexer na declaração**: `CLAUDE.md` da raiz é escrito pela sessão principal, pelo `onboard`, e por `planner`/`specker` só na linha `docs root`/`docs layout`. Um stack agent que o edite fora dos `allowed_paths` recebe `out_of_scope_write` como hoje. Declarar uma raiz falsa (por exemplo `services/`) só afrouxa `md_outside_docs` (`warn`) ali e **aumenta** os avisos de `docs_write_by_implementer`; `allowed_paths`, flags de ator e `backlog-keeper` não dependem de outra coisa. Valores absolutos e `..` são rejeitados (R3), então a declaração nunca aponta para fora do repo.
- **Robustez**: leitura limitada a 256 KiB, sem exceção (R10); o hook continua fail-open.
- **Privacidade**: o registro não ganha campo; o caminho do `CLAUDE.md` e a raiz não são gravados. O `area` do registro (`docs` x `code`) basta para diagnosticar uma declaração não lida.
- **Observabilidade**: após o merge, `python3 ~/.claude/hooks/agent-metrics.py` deve mostrar zero `md_outside_docs` nas escritas de `specker`/`planner`/`/implement` em `.claude/docs/` (Verification).

### 12. Rollout e reversão

Sem flag. Hook, skills e agents são os arquivos do repo (symlinks): cada task vale na próxima chamada; agents novos carregam na próxima sessão. A Task 1 grava a declaração antes de mudar o hook (seção 6), então o run desta própria spec não ganha avisos. As tasks 3 e 4 editam `implement` e `specker` enquanto o `/implement` roda: a skill já carregada no contexto não muda. Reversão: `git revert` dos commits; revertida a Task 1, a chave `docs_roots` volta junto. Não há estado nem migração.

## Alternatives considered

### Fonte da raiz de docs

| Opção | Corretude e robustez | Simplicidade e manutenção | Decisão |
|---|---|---|---|
| **`- docs root:` na `## Workflow` do `CLAUDE.md` da raiz git, lida pelo hook e pelas skills** | por projeto e por raiz git (repos aninhados corretos); versionada com o projeto; vale nas duas máquinas sem caminho absoluto | uma linha, no lugar onde já está `docs layout`; um parser pequeno no hook; um teste prende este repo | **escolhida** |
| `docs_roots` global do `agent-audit.json`, lido também pelas skills | global: vaza `.claude/docs/` para todo projeto e `docs/` para este; é lista de candidatos, a skill teria de adivinhar qual vale | skills acopladas ao config de um hook | rejeitada |
| As duas, mantidas iguais por teste | o teste só enxerga este repo; nos outros a divergência é invisível | duas fontes, duas edições a cada mudança | rejeitada |
| Override por projeto no `agent-audit.json` (chave = caminho do repo) | caminhos absolutos num config versionado e compartilhado por duas máquinas com usuários diferentes (o log da design-director mostra `/home/phrb/dotfiles`) | config global cresce com cada projeto | rejeitada |
| Arquivo próprio (`.claude/project.json`, `.claude/docs-root`) | correto | formato novo, longe de `docs layout`; mais um arquivo que skills e hook precisam conhecer | rejeitada |
| Detecção automática (procurar `features/README.md` + `backlog/`) | ambígua: este repo tem `.claude/templates/docs-structure/features/README.md`; cara no hook (varredura a cada escrita) | adivinhação | rejeitada |

### Como as skills e agents citam a raiz

| Opção | Por que |
|---|---|
| **Marcador `<docs>/` definido na `project-docs`, em todos os arquivos** (escolhida) | explícito e procurável por grep; o agent lê literalmente o que vai fazer |
| Manter `docs/` e uma frase global "docs/ significa a raiz declarada" | implícito: o modelo lê `docs/backlog/` literalmente, que é o defeito desta entrada |

### Override `roots` em `evaluate_write`

| Opção | Por que |
|---|---|
| **Manter o parâmetro como override, `None` = declaração da raiz** (escolhida) | os testes de área A1-A9 (mecanismo de área, não de declaração) continuam sem fixture de `CLAUDE.md`; o caminho real é coberto por DR10-DR16 |
| Remover e exigir `CLAUDE.md` nas fixtures | mais churn sem ganho de cobertura |

### Valor inválido

| Opção | Por que |
|---|---|
| **Hook cai em `docs/`; skills param e perguntam** (escolhida) | o hook nunca quebra a sessão; uma skill que escrevesse em `docs/` em silêncio criaria uma árvore paralela |
| Normalizar absolutos como hoje (`/z` -> `z/`) | um `/home/void/dotfiles/.claude/docs/` viraria `home/void/...`, silenciosamente errado |

## Trade-offs

- **`docs/` deixa de ser área de docs neste repo**, e `.claude/docs/` deixa de ser nos outros. Correto (R4); um projeto alheio que guarde docs em `.claude/docs/` passa a receber `md_outside_docs` (`warn`) até declarar a raiz. Não há outro conhecido nas duas máquinas.
- **Uma leitura de arquivo por raiz julgada em cada escrita** (no máximo duas, até 256 KiB): custo desprezível frente ao `git rev-parse` que o hook já faz.
- **Formato estrito em markdown**: uma linha mal escrita (`docs-root:`) é ignorada pelo hook. Mitigação: o formato está na `project-docs` e no template, e este repo é preso por teste (R9).
- **Uma raiz por projeto**: docs por serviço num monorepo não são suportados; quem quiser declara uma raiz única.
- **`<docs>` em textos lidos por modelos**: um placeholder a mais; a `project-docs` o define e o `CLAUDE.md` global o explica na primeira menção.

## Testing

Suite: `claude-hooks` (tabela `Test suites` do `CLAUDE.md` da raiz). Markdown de skills e agents não tem teste automático: verificação na seção Verification. Cada classe nova cita esta spec na docstring.

### `_support.py`

| Item | Mudança |
|---|---|
| `TEST_CONFIG` | sai `"docs_roots"` |
| `declare_docs_root(root, value, *, section="Workflow", extra="")` (nova, módulo) | escreve `<root>/CLAUDE.md` com `# p`, `## <section>`, `- docs layout: features`, `- docs root: <value>` e `extra` |
| `TempRepoCase.declare(value, **kw)` | atalho para `declare_docs_root(self.repo, value, **kw)` |

### `test_write_areas.py` - `DocsRootDeclaration` (substitui D1-D7)

| # | Caso | Esperado |
|---|---|---|
| DR1 | sem `CLAUDE.md` | `project_docs_root(repo) == "docs/"` |
| DR2 | `CLAUDE.md` sem `## Workflow`; com `## Workflow` sem a linha | `"docs/"` |
| DR3 | formas válidas: `.claude/docs/`, `.claude/docs`, `` `kb` ``, `  ./kb/  `, `* Docs Root: kb` (bullet `*`, caixa), `a//b/./c`, `x\y` | `.claude/docs/`, `.claude/docs/`, `kb/`, `kb/`, `kb/`, `a/b/c/`, `x/y/` (um `subTest` por valor) |
| DR4 | inválidos: vazio, `.`, `..`, `a/../b`, `/abs`, `~/x`, `C:/x`, `kb\tx` com controle | `"docs/"`; `normalize_docs_root()` devolve `None` |
| DR5 | linha fora da seção: em `## Test suites`; em `### Workflow` sem `## Workflow`; depois de `## Outra` que fecha a `## Workflow`; numa seção `# Workflow` (nível 1) | `"docs/"` |
| DR6 | `### Sub` dentro de `## Workflow` com a linha abaixo dela; `##   workflow  ` (espaços, caixa) | a linha conta |
| DR7 | duas linhas `docs root` (`kb/` e depois `other/`); primeira inválida e segunda válida | `kb/`; `"docs/"` (a primeira decide) |
| DR8 | `CLAUDE.md` é diretório; bytes inválidos em UTF-8 antes da seção; arquivo de 300 KiB com a linha depois dos 256 KiB; sem permissão de leitura (pula como root) | sem exceção; `"docs/"` nos casos sem linha legível; bytes inválidos não impedem a leitura da linha válida |
| DR9 | só `.claude/CLAUDE.md` declara (raiz sem `CLAUDE.md`) | `"docs/"` (R5) |
| DR17 | `normalize_docs_root()` com não-`str` (`None`, `3`, `["kb"]`, `Path("kb")`) | `None`, sem exceção |

*Adendo 2026-11-13:* `DocsRootDeclaration` ganha DR18 (FIFO) e DR19 (symlink para dispositivo de caractere); ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A1.

### `test_write_areas.py` - `DocsRootEffect` (substitui D8-D11)

| # | Caso | Esperado |
|---|---|---|
| DR10 | repo declara `kb/`, `evaluate_write` sem `roots`: `main` cria `kb/x.md`; `main` cria `docs/x.md` | `area: docs`, sem flag; `area: code`, `md_outside_docs` |
| DR11 | repo declara `kb/`: `specker` em `kb/backlog/bugs/x.md`; `backlog-keeper` no mesmo; `specker` em `docs/backlog/x.md` | `backlog_write_by_other`; nada; sem `backlog_write_by_other` (mas `md_outside_docs`) |
| DR12 | repo declara `kb/`: `backend-node` em `kb/x.md` | `docs_write_by_implementer` |
| DR13 | repo sem declaração: `.claude/docs/x.md` e `services/x/docs/a.md` criados por `main` | `area: code`, `md_outside_docs` nos dois |
| DR14 | repo aninhado: externo declara `kb/`, interno (`sub/`, `git init`) declara `notes/`; alvo `sub/notes/x.md` | registro com o `rel`/`area` do interno: `notes/x.md`, `docs` (R6); flags unidas como hoje |
| DR15 | override: repo declara `kb/`, `evaluate_write(..., roots=["docs/"])` em `kb/x.md` | `area: code` (o override vence) |
| DR16 | `main()` por `call_main`: `PostToolUse` Write de `kb/a.md` com o repo declarando `kb/`; config com `docs_roots: ["kb/"]` e repo sem declaração; `PreToolUse` (enforce) de `specker` criando `.claude/docs/features/x/spec.md` com e sem a declaração `.claude/docs/` | sem flag; `md_outside_docs` (a chave antiga é ignorada); silencioso / warn `md_outside_docs` |

`AreaFlags` (A1-A9) não muda: usa `roots=ROOTS` explícito.

### `test_hook_process.py` - `ProcessContract` (caso novo)

| # | Caso | Esperado |
|---|---|---|
| P-DR | hook como processo real, `self.repo` com `CLAUDE.md` declarando `kb/`, `PreToolUse` Write de `main` em `kb/a.md` (novo) e em `docs/a.md` (novo) | silencioso; uma linha JSON com warn `md_outside_docs`; exit 0 e stderr vazio nos dois |

### `test_config_contract.py` (F4 reescrito)

`REPO_ROOT = audit.git_root(CLAUDE_DIR)`. A docstring do módulo passa a dizer que ele também lê o `CLAUDE.md` da raiz do repo.

| # | Caso | Esperado |
|---|---|---|
| F4a | `audit.project_docs_root(REPO_ROOT)` | `".claude/docs/"`; `REPO_ROOT/.claude/docs/features/README.md` é arquivo e `REPO_ROOT/.claude/docs/backlog/` é diretório |
| F4b | `agent-audit.json` vivo | sem a chave `docs_roots` (uma fonte só, R2) |

### Regras -> testes

| Regra | Testes |
|---|---|
| R1 declaração única, padrão `docs/` | DR1, DR2, DR3, DR10, DR13 |
| R2 mesma fonte, sem `docs_roots` | DR16, F4b; para as skills, Verification V1-V3 |
| R3 inválido: hook cai em `docs/` | DR4, DR7, DR17; skills param: Verification V6 |
| R4 uma raiz, `docs/` sai | DR10, DR11, DR13 |
| R5 só `## Workflow` do `CLAUDE.md` da raiz | DR5, DR6, DR7, DR9 |
| R6 por raiz git | DR14 |
| R7 `<docs>` nas skills, caminho resolvido entre agents | Verification V1, V2, V4, V5 |
| R8 quando gravar a declaração | Verification V2 (leitura dos textos), V7 |
| R9 este repo preso por teste | F4a |
| R10 nunca quebra | DR8, DR17, P-DR |

## Implementation order

### Task 1 - Hook lê a raiz de docs do CLAUDE.md da raiz git

- **Stack:** backend-python
- **Files:** `CLAUDE.md`, `.claude/hooks/agent-audit.py`, `.claude/hooks/agent-audit.json`, `.claude/hooks/agent-metrics.py`, `.claude/hooks/tests/_support.py`, `.claude/hooks/tests/test_write_areas.py`, `.claude/hooks/tests/test_config_contract.py`, `.claude/hooks/tests/test_hook_process.py`
- **Depends on:** -
- **Done when:** a primeira edição é a `## Workflow` do `CLAUDE.md` da raiz exatamente como na Design, seção 6; `docs_roots()` e `DEFAULT_DOCS_ROOTS` não existem mais e `normalize_docs_root()`, `project_docs_root()`, o `roots=None` por raiz, `main()`, `WHY` e docstrings seguem a seção 3; o `agent-audit.json` segue a seção 4 e os `FLAG_LABELS` a seção 5; D1-D11 e o F4 antigo foram removidos e DR1-DR17, P-DR, F4a e F4b passam; `python3 -I -B -m unittest discover -s .claude/hooks/tests -t .claude/hooks` verde; nenhum arquivo fora da lista muda
- **Status:** done

### Task 2 - project-docs define a raiz de docs; templates

- **Stack:** frontend-react
- **Files:** `.claude/skills/project-docs/SKILL.md`, `.claude/templates/docs-structure/features/_template/spec.md`, `.claude/templates/project-root/CLAUDE.md`
- **Depends on:** Task 1
- **Done when:** a subseção **Docs root** está em **Layouts and path resolution** com o texto exato da Design, seção 7, e as demais edições da tabela dessa seção foram feitas; `grep -nE '(^|[^A-Za-z_./<-])docs/(features|backlog|plans|specs|requests|concepts|quality)' .claude/skills/project-docs/SKILL.md` não acha nada; os dois templates seguem a seção 10; nenhuma regra de layout, migração ou add entry mudou de sentido; nenhum arquivo fora da lista muda
- **Status:** done

### Task 3 - Skills consumidoras e CLAUDE.md global

- **Stack:** frontend-react
- **Files:** `.claude/skills/implement/SKILL.md`, `.claude/skills/fix-bug/SKILL.md`, `.claude/skills/onboard/SKILL.md`, `.claude/skills/implementer-contract/SKILL.md`, `.claude/skills/docs/SKILL.md`, `.claude/CLAUDE.md`
- **Depends on:** Task 2
- **Done when:** cada lugar da tabela da Design, seção 8, tem o texto dela; o grep da Verification V1 não acha nada nesses arquivos; o único em dash do `.claude/CLAUDE.md` continua sendo o da regra citada; nenhum arquivo fora da lista muda
- **Status:** done

### Task 4 - Agents

- **Stack:** frontend-react
- **Files:** `.claude/agents/planner.md`, `.claude/agents/specker.md`, `.claude/agents/backlog-keeper.md`, `.claude/agents/docs-writer.md`, `.claude/agents/code-reviewer.md`, `.claude/agents/test-writer.md`, `.claude/agents/quality-fixer.md`, `.claude/agents/backend-go.md`, `.claude/agents/backend-node.md`, `.claude/agents/backend-python.md`, `.claude/agents/backend-rust.md`, `.claude/agents/backend-spring.md`
- **Depends on:** Task 2
- **Done when:** cada linha da tabela da Design, seção 9, foi trocada; `planner` e `specker` declaram as duas linhas da `## Workflow` no escopo de escrita; o grep da Verification V1 não acha nada em `.claude/agents/`; frontmatter (nome, tools, modelo) intacto além do texto de `description`; nenhum arquivo fora da lista muda
- **Status:** done

## Verification

No fim do run:

1. Suite `claude-hooks` inteira, verde, pelo `test-runner`.
2. Checks de texto (read-only, pela sessão principal ou pelo `test-runner`):
   - **V1** `git grep -nE '(^|[^A-Za-z_./<-])docs/(features|backlog|plans|specs|requests|concepts|quality)' -- .claude/agents .claude/skills/project-docs .claude/skills/implement .claude/skills/fix-bug .claude/skills/onboard .claude/skills/implementer-contract .claude/skills/docs .claude/CLAUDE.md .claude/templates/docs-structure` sem ocorrências.
   - **V2** `git grep -n '<docs>' -- .claude/agents .claude/skills .claude/CLAUDE.md`: todo arquivo listado é a `project-docs` ou cita a resolução pela `project-docs` (ou o `## Workflow` global) no mesmo parágrafo da primeira ocorrência; a `project-docs` define `<docs>` antes do primeiro uso dentro de **Layouts and path resolution**.
   - **V3** `git grep -n 'docs_roots' -- .claude/hooks .claude/agents .claude/skills .claude/CLAUDE.md CLAUDE.md` sem ocorrências fora de testes que afirmem a ausência (F4b, DR16).
   - **V4** `git diff --stat main -- .claude/templates/project-root/STRUCTURE.md .claude/templates/project-root/PRD.md .claude/skills/new-project .claude/settings.json` vazio.

   *Adendo 2026-11-13:* V2 ficou mais estrito e o teste `test_a4_docs_roots_...` foi renomeado para passar no V3; ver [Adendo 2026-11-13](#adendo-2026-11-13---ajustes-do-review-de-código-e-de-segurança), A5 e A6.

Sem runtime local nem UI. Checks manuais do usuário, numa sessão nova do Claude Code depois do merge (agents carregam no início da sessão), neste repo:

- **V5** "pode especificar" uma entrada de refactor citada só pelo título: o `specker` acha a entrada em `.claude/docs/backlog/refactor/` e escreve em `.claude/docs/features/<slug>/spec.md` sem receber caminho; `python3 ~/.claude/hooks/agent-metrics.py` não mostra `md_outside_docs` nessas escritas.
- **V6** Num repo descartável com `CLAUDE.md` declarando `- docs root: ../x`, pedir "registra um refactor": o `backlog-keeper` volta com `needs_input` dizendo que a linha é inválida, e nada é escrito em `docs/`.
- **V7** `/implement <slug>` só com o slug de uma feature deste repo: o run state grava `"feature": ".claude/docs/features/<slug>/"`; e `@backlog-keeper` registra um bug em `.claude/docs/backlog/bugs/` sem caminho no pedido.

**needs_docs** (para o `docs-writer`, no fim):

- `.claude/README.md`: item `docs_roots` da seção dos hooks vira "docs root": a linha `- docs root:` da `## Workflow` do `CLAUDE.md` da raiz git (padrão `docs/`, aqui `.claude/docs/`), lida pelo hook por raiz git e pela `project-docs`, regras de normalização, inválido -> `docs/` no hook; tirar "`project-docs` and `/implement` still resolve `docs/` ... passed explicitly"; no item do `agent-audit.json`, "`.md` outside the docs roots" -> "outside the project's docs root"; a tabela de agents ("read + write `docs/`", "`docs/backlog/`") passa a `<docs>/`, com uma frase que define `<docs>`; os passos 1-3 do fluxo (`docs/features/<slug>/`) idem; a descrição de `tests/` cita `declare_docs_root()`.
- `.claude/agent-workflow.md`: adendo datado em 13.5 (o `docs_roots` do `agent-audit.json` foi substituído pela declaração `- docs root:` por projeto; a frase "`project-docs` e `/implement` ainda resolvem `docs/`..." deixa de valer) e uma linha em 6.1.1 (a detecção do layout parte da raiz de docs resolvida; mapa de caminhos relativo a `<docs>/`). O resto do documento é registro e não muda.

## Open questions

1. **Fonte única da raiz** (não bloqueia; a spec segue a recomendação). Opções: (a) linha `- docs root:` na `## Workflow` do `CLAUDE.md` da raiz git, lida pelo hook e pelas skills, sem `docs_roots` no `agent-audit.json`; (b) manter `docs_roots` no JSON como fonte e fazer as skills o lerem; (c) as duas, checadas por teste. Recomendação: (a). O JSON é global (symlink, duas máquinas) e a raiz é do projeto; (b) vaza raízes entre projetos e obriga a skill a adivinhar entre candidatos; (c) só verifica este repo.
2. **Teste automático contra `docs/` fixo em skills e agents.** Opções: (a) só o grep V1 nesta entrega; (b) um módulo novo no `claude-hooks` (`test_docs_root_contract.py`) que roda o grep V1 sobre os arquivos do workflow e falha a cada regressão. Recomendação: (a) agora. O `claude-hooks` testa o hook; lint de markdown da config pede uma suite própria, que pode vir como refactor separado se o `docs/` fixo voltar a aparecer.
3. **Entrada de refactor.** O vocabulário do backlog é `Proposed` -> `In progress` -> `Done`. Opções: (a) o `backlog-keeper` mantém `Proposed`, acrescenta o link desta spec, amplia o **Scope** (hook, `agent-audit.json`, `CLAUDE.md` da raiz, skills, agents, templates) e preenche **Proposed change** (R1-R4), **Risks** (projetos com docs em `.claude/docs/` sem declaração passam a receber `md_outside_docs`) e **Out of scope** (várias raízes por projeto); vai a `In progress` quando o `/implement` começar; (b) passar a `In progress` já. Recomendação: (a).

## Adendo 2026-11-13 - ajustes do review de código e de segurança

- **Origem**: `code-reviewer` e `security-reviewer`, review de 2026-11-13; as mudanças estão sendo aplicadas agora, dentro das tasks já feitas.
- **Afeta**: Design, seções 1 (R10), 3, 7, 8 e 9; Testing (DR18 e DR19 novos; Regras -> testes de R10); Verification, V2 e V3. O **Done when** das Tasks 1 (A1, A6), 2 (A2, A3), 3 (A4, A5) e 4 (A5) passa a valer com o texto deste adendo; o **Status** das tasks não muda. O texto original fica como registro; onde divergir, vale este adendo.
- **Não muda**: o formato da declaração (seção 2), as regras R1-R9, `normalize_docs_root()`, a precedência e a seção lida, DR1-DR17, P-DR, F4a e F4b.

### A1 - Segurança: `project_docs_root()` não bloqueia (Design 3, R10)

**Motivo.** `open(..., "rb")` num `CLAUDE.md` que é FIFO, ou symlink para um dispositivo que bloqueia na abertura ou na leitura, travava o hook até o timeout de 10 s, em cada escrita julgada naquela raiz.

**Leitura nova** (substitui "lê no máximo 256 KiB de `root / "CLAUDE.md"` em bytes (`open(..., "rb").read(262144)`)" da seção 3):

1. `os.open(root / "CLAUDE.md", os.O_RDONLY | os.O_NONBLOCK)`: abrir um FIFO sem escritor ou um dispositivo não espera.
2. `os.fstat()` no mesmo descritor (sem `stat` antes da abertura, então não há corrida entre checagem e uso); se `stat.S_ISREG()` for falso, devolve `DEFAULT_DOCS_ROOT` sem ler nada.
3. Só então lê no máximo 256 KiB do descritor; o resto (UTF-8 com `errors="replace"`, regex, primeira linha da seção) não muda. O descritor é fechado em todo caminho (`finally`).

Symlink para um `CLAUDE.md` regular continua valendo (o `fstat` é do alvo aberto). Qualquer `OSError` (ausente, diretório, permissão) segue em `DEFAULT_DOCS_ROOT`.

**R10** (substitui o da seção 1): `CLAUDE.md` ausente, ilegível, diretório, FIFO, dispositivo (direto ou por symlink), binário ou enorme nunca levanta exceção nem bloqueia o hook; vale como sem declaração.

**Testes novos** em `DocsRootDeclaration` (`.claude/hooks/tests/test_write_areas.py`). Cada um roda `project_docs_root` pelo helper `root_within()`, que usa uma thread daemon com `join` de 2 s: um travamento faz o teste falhar em vez de prender a suite.

| # | Teste | Caso | Esperado |
|---|---|---|---|
| DR18 | `test_dr18_fifo_claude_md_defaults_without_hanging` | `CLAUDE.md` é um FIFO (`os.mkfifo`) sem escritor; pulado sem `os.mkfifo` | `"docs/"` dentro de 2 s |
| DR19 | `test_dr19_symlink_to_char_device_defaults_without_hanging` | `CLAUDE.md` é symlink para `/dev/null` (dispositivo de caractere) | `"docs/"` dentro de 2 s (não é arquivo regular) |

A linha Regras -> testes de R10 passa a: DR8, DR17, DR18, DR19, P-DR. Na seção 11, **Robustez** passa a "leitura não bloqueante, só de arquivo regular, limitada a 256 KiB, sem exceção (R10)".

### A2 - Quem grava a linha na Docs root offer (Design 7)

**Motivo.** "the agent that asked writes the line" contradizia as regras de escrita: os agents read-only não escrevem nada e o `backlog-keeper` só escreve em `<docs>/backlog/`.

**Texto novo** do trecho "Yes: ..." do parágrafo **Docs root offer**, exatamente:

```markdown
Yes: the main session, `planner` or `specker` writes the line in `## Workflow` (create the section if missing), next to `docs layout`; any other subagent only relays the question with `needs_input` and never writes the line. No: use the given path for this run only.
```

A seção 11 já dizia isso ("por `planner`/`specker` só na linha `docs root`/`docs layout`"); agora a `project-docs` diz o mesmo.

### A3 - Caractere de controle na lista de inválidos (Design 7)

**Motivo.** A tabela da seção 2 e o hook rejeitam caractere de controle; a `project-docs` não o citava, e as skills aceitariam um valor que o hook recusa.

**Texto novo** da frase de inválidos do parágrafo de normalização, exatamente:

```markdown
A value that is empty, absolute (`/`, `~`, a drive letter), has a `..` segment or contains a control character is invalid: stop and tell the user the line is invalid (subagents return it as `needs_input`); never fall back to `docs/` silently.
```

### A4 - Quando o `implement` oferece a declaração (Design 8)

**Motivo.** O passo 1.1 disparava a oferta para qualquer caminho fora de `<docs>/`, inclusive com uma raiz já declarada, em que gravar a linha trocaria a raiz do projeto em silêncio.

**Texto novo** do acréscimo ao passo 1.1 de `skills/implement/SKILL.md` (substitui o da tabela da seção 8), exatamente:

```markdown
This includes the docs root: a feature passed by slug or title is looked up under the resolved `<docs>/`. When no docs root is declared and `docs/` is missing, a path the user passes elsewhere triggers the project-docs **Docs root offer** (asked by you, the main session, which writes the line on yes). When a docs root is declared and the user passes a path outside it, say so and ask which one to use; never change the declaration on your own.
```

A troca de "Never hard-code `docs/plans`..." por "Never hard-code a docs path; every path starts at the resolved docs root." fica como estava.

### A5 - `<docs>` resolvido no primeiro uso; cláusula de scaffold no `specker` (Design 8 e 9, V2)

**Motivo.** O V2 aceitava arquivos em que `<docs>` aparecia sem dizer, perto do uso, de onde vem; um agent que carrega só aquele arquivo leria o marcador literalmente.

**Regra** (vale para as seções 8 e 9): todo arquivo que usa `<docs>` diz como ele é resolvido no parágrafo do primeiro uso. Quando a primeira ocorrência é o `argument-hint` do frontmatter, conta o primeiro parágrafo do corpo que usa `<docs>`. Forma padrão, quando o parágrafo não cita a `project-docs` de outro jeito:

```markdown
(`<docs>` is the project docs root: the `- docs root:` line of the git-root `CLAUDE.md` `## Workflow`, see project-docs **Docs root**, default `docs/`)
```

| Arquivo | Mudança |
|---|---|
| `skills/implementer-contract/SKILL.md`, linha 13 | ganha a definição na forma padrão, depois de "the feature folder (`<docs>/features/<slug>/`, ...)"; é a definição em que os backends se apoiam |
| `agents/backend-{go,node,python,rust,spring}.md` | o `needs_docs` diz "(`<docs>` is the project docs root, defined in the implementer contract)" |
| `agents/specker.md`, passo 1.1 | ganha a cláusula do `planner`, como a seção 9 já pretendia ("iguais ao `planner`"): "If the docs tree does not exist at `<docs>/`, scaffold it first, as project-docs describes (a path the user gave elsewhere is the docs root offer first)." |
| demais agents e skills da seção 8 e 9 | conferidos pelo V2 novo; os que já citam a `project-docs` no parágrafo ficam como estão |

**V2** (substitui o da Verification): `git grep -n '<docs>' -- .claude/agents .claude/skills .claude/CLAUDE.md`: em todo arquivo listado, o parágrafo da primeira ocorrência (fora do `argument-hint`) diz como `<docs>` é resolvido: cita a `project-docs` (**Docs root**), o `## Workflow` global ou, nos backends, o implementer contract; a `project-docs` define `<docs>` antes do primeiro uso dentro de **Layouts and path resolution**, e o `implementer-contract` o define na linha 13.

### A6 - Nome do teste A4 (Verification V3)

**Motivo.** `AreaFlags.test_a4_docs_roots_are_area_docs_without_md_flag` cita a chave removida no nome sem afirmar a ausência dela, então o V3 o acusava.

**Mudança**: o teste passa a `test_a4_docs_root_paths_are_area_docs_without_md_flag` (testa o override `roots=ROOTS`); o corpo não muda. O V3 fica como está: as únicas ocorrências de `docs_roots` aceitas continuam sendo F4b e DR16.
