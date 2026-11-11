# Proposta: workflow de agents por fase de execução

- **Data**: 2026-11-10
- **Revisão**: 3 (incorpora os comentários das rodadas 1 e 2; ver Apêndices A e B)
- **Status**: Aprovado (rodada 3 fechada em 2026-11-10); pronto para a etapa A
- **Escopo**: `~/.claude/agents/`, `~/.claude/skills/`, `~/.claude/templates/`, `~/.claude/CLAUDE.md`, `~/.claude/settings.json`
- **Objetivo duplo**:
  1. Atender melhor o workflow diário: feature, bug, refactor, review de PR e projeto novo, em proporções parecidas.
  2. Servir de **config de referência para o Briareu**, o orquestrador de agents em construção, que chama os agents desta config diretamente. Por isso o fluxo precisa ter contratos explícitos, estado legível e métricas observáveis, e não depender só de prosa.

> Como comentar: escreva abaixo de cada seção numa linha começando com `> 💬`.

### Terminologia

| Termo                      | Significado                                                                                         |
| -------------------------- | --------------------------------------------------------------------------------------------------- |
| **orquestrador / Briareu** | o app externo em construção. Consome a config como ela está; a config não sabe que ele existe       |
| **config**                 | `~/.claude/`: agents, skills, templates, CLAUDE.md e settings                                       |
| **`implement`**            | a skill da config que coordena a execução de uma feature (spec -> código -> gate -> review -> docs) |
| **feature**                | unidade de trabalho com pasta própria em `docs/features/<slug>/` (seção 6.1)                        |

Neste documento, "orquestrador" significa sempre o Briareu. O que a config faz internamente é sempre chamado pelo nome da skill (`implement`, `fix-bug`).

---

## 1. Diagnóstico do setup atual

### 1.1 O que já funciona

- O pipeline já existe: `@planner` (plan -> spec) -> `/implement` -> stack agent -> `test-runner` -> `quality-fixer` -> `test-writer` -> `code-reviewer` + `security-reviewer`.
- Há separação entre quem escreve e quem só lê: reviewers e `test-runner` não editam.
- O modelo combina com o papel: haiku roda checks, sonnet implementa, opus planeja e revisa.
- Os projetos têm uma estrutura comum (`templates/project-root` + `templates/docs-structure`), o que permite transformar os templates em contrato entre agents (seção 11).

### 1.2 Problemas e causas raiz

| Sintoma                                | Causa raiz encontrada                                                                                                                                                                                                                                                                                                               |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Execuções duplicadas**               | Numa task do `/implement`, os checks rodam até 4 vezes: o stack agent roda typecheck, lint e testes; o `test-runner` roda de novo; o `quality-fixer` roda a suite completa no final; e o `test-runner` roda mais uma vez depois do fix.                                                                                             |
| **Reescritas**                         | Três papéis escrevem a mesma coisa. Testes: stack agent e `test-writer`. Correções: stack agent e `quality-fixer`. Docs: stack agent, passo final do `/implement` e o CLAUDE.md global.                                                                                                                                             |
| **Arquivos indevidos**                 | O CLAUDE.md global diz _"if no [documentation] then start to create a documentation for every change"_. Os subagents também herdam essa regra, e nenhum agent tem uma lista fechada de arquivos que pode criar.                                                                                                                     |
| **Contexto perdido entre agents**      | `implement` repassa só "files from previous reports". Decisões, premissas e desvios não chegam à task seguinte, e cada agent começa do zero relendo CLAUDE.md, spec, plan e o código.                                                                                                                                               |
| **Precisa chamar manualmente**         | `implement` tem `disable-model-invocation: true` e só roda via `/implement`. Uma frase como "podemos seguir com a implementação" não consegue acioná-lo.                                                                                                                                                                            |
| **Duplicação entre os 7 stack agents** | As seções "Before coding", "Out-of-scope issues", "Rules" e "Report" são praticamente idênticas nos 7 arquivos, e regras mudadas num deles divergem dos outros.                                                                                                                                                                     |
| **Fases sem dono**                     | Bug fix E2E (só existe a skill `bug-repro`), registro de bug/refactor (cada agent grava por conta própria) e documentação (o `/implement` termina com "next step" sem executor).                                                                                                                                                    |
| **Prints e validação em runtime**      | Cinco instruções mandam validar UI visualmente (CLAUDE.md global, `frontend-react`, `mobile-react-native`, `implement`, `bug-repro`), e os 5 backends sobem o serviço ou rodam o binário. Isso duplica a validação que o usuário já faz localmente, e cada print fica no contexto e é reenviado nos turnos seguintes. Ver seção 10. |
| **Templates sem consumidor definido**  | `TASKS.md` e `OPEN_QUESTIONS.md` se sobrepõem a specs, plans e backlog; plan e spec de uma mesma feature ficam em pastas diferentes; o template de spec não tem arquivos, stack e critério de pronto por task; o `CLAUDE.md` do projeto não descreve runtime local nem suites de teste de forma que agents leiam. Ver seção 11.     |
| **Skills com sobreposição**            | `review`, `codebase-standards`, `scaffold` e `code-simplify` estão em `off` e se sobrepõem a agents ou a outras skills. `docs`, `tdd`, `grill-me` e `archify` também estão em `off`, mas são usadas e ficam (seção 12.2).                                                                                                           |

> 💬

---

## 2. Princípios do novo desenho

Estes princípios valem para a config e também como requisitos para o Briareu.

1. **Fase é a unidade de orquestração.** Toda solicitação é roteada para uma fase, cada fase tem um único papel dono, e as transições entre fases são explícitas.
2. **Um único dono por ação.** Escrever código, escrever testes, rodar a suite, corrigir, documentar e registrar backlog têm, cada um, exatamente um responsável.
3. **Contrato de agent = entrada + escopo de escrita + saída estruturada.** Prosa explica o "como"; o contrato define o "o quê" e é verificável.
4. **Estado no disco, não na conversa.** O contexto entre agents vive num artefato persistente e versionável. Assim, um run interrompido retoma, e um agent novo começa com tudo o que precisa.
5. **Gates determinísticos.** Gates de checks não dependem do julgamento do LLM: um comando roda, e passa ou falha.
6. **Orçamento explícito.** Há número máximo de rodadas de fix, no máximo uma suite completa por run e um review por run (mais uma rodada só se houver blocker).
7. **Observável.** Cada run produz dados que permitem medir desperdício: chamadas de agent, checks executados, arquivos criados fora da spec.
8. **Config autossuficiente.** Nenhum fluxo da config depende do Briareu. O Briareu chama os agents da config diretamente e consome os contratos da seção 5 como interface; quando o usuário opta por não usar a config local, os workers do Briareu são totalmente isolados dela.
9. **Templates são contrato.** Toda seção de template tem um agent ou skill que a escreve e outro que a lê (seção 11). Seção sem consumidor é removida.
10. **Fora do escopo, pergunte.** Um agent nunca age fora do escopo da task por conta própria: ele para, explica por que precisa e espera autorização (seção 13.4).

> 💬

---

## 3. Fases

```
Descobrir -> Planejar -> Especificar -> Implementar -> Verificar     -> Revisar   -> Documentar -> Entregar
grill-me     planner     specker        stack agents   test-runner      reviewers    docs-writer   pr-description
                                                       quality-fixer
                                                       usuário (UI e runtime, local)

Transversal: backlog-keeper (registra bug/refactor a qualquer momento)
```

| #   | Fase        | Dono                                                                   | Entrada                                | Saída                                                                        | Gate de saída                                            |
| --- | ----------- | ---------------------------------------------------------------------- | -------------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------- |
| 0   | Descobrir   | skill `grill-me` (main)                                                | ideia bruta                            | decisões resolvidas na conversa                                              | usuário diz que está claro                               |
| 1   | Planejar    | `planner`                                                              | decisões + `PRD.md` + `CONSTRAINTS.md` | `docs/features/<slug>/plan.md` (`Draft`)                                     | **humano** aprova -> `Approved`                          |
| 2   | Especificar | `specker`                                                              | plan `Approved`                        | `docs/features/<slug>/spec.md` (`Draft`) com tasks estruturadas (seção 11.3) | **humano** aprova -> `Approved`                          |
| 3   | Implementar | stack agent por task                                                   | spec `Approved` + task N               | código + testes da task + entrada em `log.md`                                | testes da task passam (narrow)                           |
| 4   | Verificar   | `test-runner` (gate), `quality-fixer` (fix); UI e runtime pelo usuário | arquivos tocados                       | resumo de checks + checklist de validação manual                             | **automático**: lint + typecheck + suites do gate verdes |
| 5   | Revisar     | `code-reviewer`, `security-reviewer`                                   | working tree + spec                    | findings classificados                                                       | nenhum blocker/major aberto                              |
| 6   | Documentar  | `docs-writer`                                                          | spec + log                             | docs atualizadas, status `Implemented`                                       | docs coerentes com o código                              |
| 7   | Entregar    | skill `pr-description`                                                 | diff                                   | texto de PR/changelog                                                        | usuário commita (seção 4.1)                              |

**`planner` e `specker` separados**: o `planner` escreve só o plan (lado de produto: escopo e regras de negócio). O `specker` é dono da spec (lado técnico: design, tasks, testes, verificação) e é o único que conhece o formato estruturado de tasks que o `implement` consome.

**Gates humanos**: apenas 1 e 2 (aprovar plan e spec), blockers e pedidos de escopo (seção 13.4). Todo o resto roda sem parar, exceto com `--step`.

> 💬

---

## 4. Matriz de responsabilidade

| Ação                                                    | Único dono                                                                        | Regra para os outros                                                                                                  |
| ------------------------------------------------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Escrever `plan.md`                                      | `planner`                                                                         | ninguém mais                                                                                                          |
| Escrever `spec.md`                                      | `specker`                                                                         | `implement` só altera o status e o campo `Status` das tasks                                                           |
| Escrever `log.md`                                       | `implement`                                                                       | agents contribuem pelo report; não escrevem no arquivo                                                                |
| Escrever código da task                                 | stack agent                                                                       | ninguém mais toca em código de produção, exceto `quality-fixer` para falhas e o stack agent para findings do review   |
| Testes do comportamento da task                         | stack agent (seguindo a seção Testing da task)                                    | `test-writer` só para cobertura fora de uma spec, lacunas em código legado e o modo TDD (seção 12.4)                  |
| Rodar teste específico durante o trabalho               | quem está editando                                                                | só o teste do arquivo em foco, nunca a suite                                                                          |
| Rodar suites (gate)                                     | `test-runner`, conforme a tabela `Test suites` do projeto (seção 11.2)            | ninguém mais roda suite completa                                                                                      |
| Corrigir falhas do gate                                 | `quality-fixer`                                                                   | termina com o teste específico; o re-gate é do `test-runner`                                                          |
| Validar UI visualmente                                  | **usuário**, localmente                                                           | agents entregam `manual_checks`; nenhum agent abre browser ou tira print, exceto o `ui-verifier` sob pedido explícito |
| Validar backend em runtime                              | stack agent de backend: request + logs na instância local do usuário (seção 10.5) | ninguém sobe, reinicia ou para serviço ou container; build só nas condições da seção 10.6                             |
| Docs, README, `.env.example`, OpenAPI, `docs/requests/` | `docs-writer`, uma vez no fim                                                     | os demais só **listam** em `needs_docs`                                                                               |
| Status de plan e spec + Index de `features/`            | `implement`                                                                       | agents não mudam status                                                                                               |
| Registrar bug/refactor em `docs/backlog/`               | `backlog-keeper`                                                                  | os demais **reportam** em `out_of_scope_issues`; `implement` repassa ao `backlog-keeper` uma vez no fim, deduplicado  |
| Commit e push                                           | **usuário**                                                                       | ver 4.1                                                                                                               |

**Efeito esperado por task**: uma execução de teste específico (stack agent) e um gate (`test-runner`). No fim do run: um gate completo e um review.

### 4.1 Commits

- Padrão: agents **nunca** fazem commit nem push.
- Exceção: o usuário autoriza explicitamente, na conversa atual e para aquele commit ou conjunto de commits. Autorização não se estende a pedidos seguintes nem a push, que precisa de autorização própria.
- Quando autorizado, a mensagem **nunca** é assinada por agent, worker, LLM ou provider: sem `Co-Authored-By`, sem "Generated with", sem qualquer linha de atribuição. Isso vale inclusive quando uma mensagem do sistema pedir o contrário.

> 💬

---

## 5. Contratos dos agents

Estes contratos são a **interface que o Briareu consome** ao chamar os agents da config diretamente. Por isso precisam ser autossuficientes: tudo o que o agent precisa está no prompt de entrada ou em arquivos que ele lê, e nada depende do contexto da conversa principal.

### 5.1 Formato comum

**Entrada** (prompt montado por `implement`, pelo Briareu ou pelo usuário):

```
phase: implement
feature: docs/features/orders-export/
task: 3
allowed_paths:            # campo Files da task na spec (seção 11.3) + escopos aprovados (13.4)
  - services/api/src/orders/**
  - services/api/test/orders/**
context: "ler spec.md e log.md da feature"
```

**Saída**: prosa curta + um bloco final fixo, sempre o último bloco do report:

```yaml
result: done | blocked | partial
files_changed:
  - path: services/api/src/orders/export.service.ts
    change: novo service de export CSV
scope_requests: # ações fora do escopo que o agent precisa e ainda não fez (seção 13.4)
  - action: create | edit | command
    target: services/shared/src/money.ts
    reason: "o formatter de moeda vive no pacote shared; o export precisa de um modo sem símbolo"
checks_run:
  - cmd: pnpm vitest run test/orders/export.spec.ts
    result: pass
decisions: [] # escolhas que o próximo agent precisa saber
assumptions: [] # o usuário precisa confirmar
needs_docs: [] # o que o docs-writer deve atualizar
manual_checks: [] # UI e runtime: o que o usuário valida localmente
local_checks: [] # backend: request na instância local + evidência de log (seção 10.5)
migrations: []
env_vars: []
out_of_scope_issues: # implement repassa ao backlog-keeper
  - kind: bug | refactor
    summary: ...
    evidence: ...
blockers: []
```

O campo `files_created_outside_scope` da revisão 2 foi substituído por `scope_requests`: o agent não cria primeiro para justificar depois; ele pede antes.

### 5.2 Escopo de escrita por agent

| Agent                                   | Pode escrever                                                                    | Nunca                                                                                        |
| --------------------------------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `planner`                               | `docs/features/<slug>/plan.md`                                                   | spec, log, código, config                                                                    |
| `specker`                               | `docs/features/<slug>/spec.md`                                                   | plan, log, código, config                                                                    |
| stack agents                            | `allowed_paths` da task                                                          | docs, arquivos de resumo/notas, scripts avulsos, qualquer coisa fora da task sem autorização |
| `test-writer`                           | arquivos de teste                                                                | código de produção                                                                           |
| `quality-fixer`                         | arquivos ligados à falha                                                         | desabilitar testes, ignores sem motivo                                                       |
| `backlog-keeper`                        | `docs/backlog/`                                                                  | qualquer outro lugar                                                                         |
| `docs-writer`                           | `docs/` (exceto `features/` e `backlog/`), READMEs, `.env.example`, specs de API | código                                                                                       |
| `ui-verifier` (só sob pedido explícito) | nada no repo (prints no scratchpad)                                              | qualquer arquivo do projeto                                                                  |
| reviewers, `test-runner`                | nada                                                                             | qualquer arquivo                                                                             |

**Enforcement em duas camadas:**

1. **Instrução** (etapa A): o núcleo compartilhado (5.3) manda parar e pedir autorização antes de qualquer ação fora do escopo (13.4).
2. **Mecânico** (etapas D e G): hook em `audit` primeiro e, com dados, bloqueio por categoria (seção 13).

### 5.3 Núcleo compartilhado dos stack agents

As seções idênticas dos 7 stack agents saem dos arquivos e vão para uma skill nova, `implementer-contract`, pré-carregada via `skills:` no frontmatter de cada agent:

- Before coding (ler `spec.md` e `log.md` da feature; não reexplorar o que o log já descreve)
- Escopo de arquivos e o protocolo de pedido de escopo (13.4)
- Política de checks (só teste específico)
- Validação em runtime (seção 10.5)
- Out-of-scope issues (reportar, não gravar)
- Formato do report (bloco YAML acima)

Cada stack agent fica só com o que é de fato específico da stack: estrutura, API, dados, async, segurança da linguagem e templates. O `backend-python` continua existindo, mesmo sendo a stack menos usada, porque com o núcleo extraído o custo de manutenção dele fica perto de zero.

> 💬

---

## 6. Estado e handoff entre agents

### 6.1 Pasta por feature

**Decisão (rodada 2)**: plan, spec e log de uma feature ficam juntos, e o log é **sempre** um arquivo separado. Isso substitui a regra de "mais de 8 tasks" da revisão 2 e dá uma estrutura única para qualquer tamanho de feature.

```
docs/
├── features/
│   ├── README.md              # Index: feature, status do plan, status da spec, atualização
│   ├── _template/
│   │   ├── plan.md
│   │   ├── spec.md
│   │   └── log.md
│   └── orders-export/
│       ├── plan.md            # planner
│       ├── spec.md            # specker; implement só muda status
│       └── log.md             # implement
├── backlog/{bugs,refactor}/   # backlog-keeper
├── concepts/  quality/  requests/
```

Regras:

- **Nome da pasta**: `<slug>` em kebab-case, sem data (links estáveis). A data fica no cabeçalho de cada arquivo e no Index.
- **Refactor sem plan**: a pasta tem só `spec.md` e `log.md`; a spec aponta a entrada de origem em `docs/backlog/refactor/`.
- **Index único**: `features/README.md` substitui os Index de `plans/README.md` e `specs/README.md`:

  | Feature                         | Plan     | Spec        | Updated    |
  | ------------------------------- | -------- | ----------- | ---------- |
  | [orders-export](orders-export/) | Approved | In progress | 2026-11-10 |

- **`log.md`**: criado por `implement` no início do primeiro run da feature e acrescido a cada task:

  ```markdown
  # Implementation log - orders-export

  ## Run 2026-11-10

  ### Task 1 - Modelo e migration (done)

  - Arquivos: services/api/prisma/schema.prisma, .../migrations/2026...\_orders_export
  - Decisões: export assíncrono via fila `exports`, não síncrono no request
  - Premissas: limite de 50k linhas por arquivo (confirmar)
  - Escopo aprovado: services/shared/src/money.ts (modo sem símbolo no formatter)
  - Docs pendentes: .env.example (EXPORT_BUCKET)
  ```

- **Projetos existentes**: o `project-docs` ganha um modo `migrate`, que move cada par plan/spec existente para `features/<slug>/` com `git mv` (preservando histórico, sem commit) e cria o `log.md` a partir das marcações `(done)`. Migrar é opcional (6.1.1).

### 6.1.1 Compatibilidade com o layout legado (D21)

**Decisão (rodada 3)**: oferecer a migração **e** manter compatibilidade. Projetos que já usam `docs/plans/` + `docs/specs/` continuam funcionando sem migrar, porque migrar todos agora custa tempo sem retorno.

**Dois layouts suportados:** `features` (padrão em projetos novos) e `legacy`.

**Detecção, nesta ordem:**
1. Declaração no `CLAUDE.md` do projeto, seção `Workflow`: `- docs layout: features` ou `- docs layout: legacy`.
2. Existe `docs/features/` -> `features`.
3. Existe `docs/plans/` ou `docs/specs/` -> `legacy`.
4. Nenhum dos dois -> `features`.

**Oferta de migração, uma única vez:** na primeira vez que `implement`, `planner` ou `specker` rodam num projeto `legacy` **sem declaração**, perguntam: "migrar agora para `docs/features/`?".
- Sim: roda `project-docs migrate` e grava `docs layout: features`.
- Não: grava `docs layout: legacy` e não pergunta mais. Para migrar depois, basta pedir.

**Mapa de caminhos:**

| Artefato | `features` | `legacy` |
|---|---|---|
| plan | `features/<slug>/plan.md` | `plans/<YYYY-MM-DD>-<slug>-plan.md` |
| spec | `features/<slug>/spec.md` | `specs/<YYYY-MM-DD>-<slug>-design.md` |
| log | `features/<slug>/log.md` | `specs/<YYYY-MM-DD>-<slug>-design.log.md` |
| Index | `features/README.md` | `plans/README.md` + `specs/README.md` |
| templates | `features/_template/` | `plans/TEMPLATE.md`, `specs/TEMPLATE.md` |
| entrada do contrato (5.1) | `feature: docs/features/<slug>/` | `spec: docs/specs/<arquivo>.md` |

**Regras que valem nos dois layouts:**
- O log é **sempre** um arquivo separado (consistência com D1).
- O `specker` sempre escreve tasks estruturadas (11.3). Specs antigas com lista livre continuam funcionando: `implement` as interpreta como hoje e **não** reescreve a spec.
- **Resolução de caminhos num único lugar**: a skill `project-docs` contém a regra de detecção e o mapa acima, e `implement`, `planner`, `specker`, `docs-writer` e `backlog-keeper` a usam. O custo de manter dois layouts fica concentrado nessa tabela, em vez de espalhado pelos agents.

### 6.2 Estado do run

`implement` (e o `fix-bug`) mantém um estado estruturado do run, fora do git, em `.claude/runs/<slug>.json` no projeto. O `gitignore.template` passa a incluir `.claude/runs/`.

```json
{
  "feature": "docs/features/orders-export/",
  "phase": "verify",
  "allowed_paths": {
    "3": ["services/api/src/orders/**", "services/api/test/orders/**"]
  },
  "approved_scope": [
    {
      "task": 3,
      "action": "edit",
      "target": "services/shared/src/money.ts",
      "reason": "...",
      "approved_at": "2026-11-10T14:02:00Z"
    }
  ],
  "tasks": { "1": "done", "2": "done", "3": "in_progress" },
  "budget": { "fix_rounds": 1, "full_gate_runs": 0, "review_rounds": 0 },
  "agent_calls": [{ "agent": "backend-node", "task": 1, "result": "done" }]
}
```

Para que serve:

- **retomar** um run interrompido sem refazer tasks;
- **controlar orçamento** (rodadas de fix e de review, gates completos);
- **alimentar o hook** (seção 13), que lê `allowed_paths` e `approved_scope` daqui;
- **auditar** cada autorização de escopo dada pelo usuário;
- **observar**: o Briareu, ao usar a config, pode ler o mesmo arquivo, mas a config não depende disso.

> 💬

---

## 7. Roteamento automático (intent -> fase)

Para não depender de lembrar de chamar o agent:

1. `implement` perde o `disable-model-invocation`, e a description ganha gatilhos em PT e EN.
2. O CLAUDE.md global ganha uma seção curta **Workflow** com a tabela abaixo, para a conversa principal rotear.

| Frase do usuário (exemplos)                                    | Fase                                                            | Pré-condição verificada antes de seguir                                               |
| -------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| "tenho uma ideia", "vamos pensar em X"                         | Descobrir (`grill-me`)                                          | nenhuma                                                                               |
| "vamos planejar", "escreve o plano"                            | Planejar (`planner`)                                            | decisões suficientes; senão volta para Descobrir                                      |
| "pode especificar", "escreve a spec"                           | Especificar (`specker`)                                         | plan `Approved`                                                                       |
| "podemos seguir com a implementação", "pode implementar", "go" | Implementar (`implement`)                                       | spec `Approved` (ou `Draft` + confirmação, que vale como aprovação) e plan `Approved` |
| "encontrei um bug", "achei um problema em X"                   | Registrar (`backlog-keeper`) e perguntar "quer corrigir agora?" | nenhuma                                                                               |
| "só registra esse bug", "anota esse bug"                       | Registrar (`backlog-keeper`), sem perguntar                     | nenhuma                                                                               |
| "isso pode ser refatorado", "registra um refactor"             | Registrar (`backlog-keeper`)                                    | nenhuma                                                                               |
| "corrige o bug X", "vamos resolver esse bug"                   | Bug flow (`fix-bug`)                                            | bug registrado; se não estiver, `backlog-keeper` registra primeiro                    |
| "revisa esse PR", "review"                                     | Revisar (PR)                                                    | PR ou branch identificável                                                            |
| "documenta", "atualiza as docs"                                | Documentar (`docs-writer`)                                      | nenhuma                                                                               |
| "escreve o PR"                                                 | Entregar (`pr-description`)                                     | diff existente                                                                        |
| "pode commitar"                                                | Commit (seção 4.1)                                              | autorização explícita na conversa atual                                               |

**Resolução da feature em "seguir com a implementação"**: (1) a feature citada na conversa; (2) senão, a única feature com spec `Approved` no Index; (3) senão, pergunta qual. Nunca chuta entre várias.

> 💬

---

## 8. Fluxos por tipo de trabalho

| Tipo                    | Fluxo                                                                                                                                                                                                                                                     |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Feature**             | Descobrir -> Planejar -> Especificar -> `implement` (Implementar -> Verificar -> Revisar -> Documentar) -> Entregar                                                                                                                                       |
| **Bug: registrar**      | `backlog-keeper`: coleta sintoma, passos, esperado x atual e evidência (request + log, comando falhando ou passos de UI) -> entrada em `docs/backlog/bugs/` + Index -> "quer corrigir agora?" (exceto se o usuário pediu só o registro)                   |
| **Bug: corrigir**       | `fix-bug`: lê a entrada do backlog -> reproduz (`bug-repro`: request + logs ou comando, nunca print) -> causa raiz -> teste de regressão falhando -> fix (stack agent) -> gate -> review -> `backlog-keeper` atualiza a entrada (root cause, fix, status) |
| **Refactor: registrar** | `backlog-keeper` -> entrada em `docs/backlog/refactor/` + Index                                                                                                                                                                                           |
| **Refactor: executar**  | `specker` cria `docs/features/<slug>/spec.md` a partir da entrada do backlog (sem plan) -> `implement`                                                                                                                                                    |
| **PR de terceiros**     | `code-reviewer` + `security-reviewer` (quando aplicável) -> findings, sem editar                                                                                                                                                                          |
| **Projeto novo**        | skill `new-project` -> Descobrir -> Planejar ...                                                                                                                                                                                                          |

### 8.1 `backlog-keeper`

Agent novo, dono único de `docs/backlog/`. Entra em cena em dois casos:

1. **O usuário encontrou algo** ("encontrei um bug", "isso merece um refactor"): registra seguindo o template do projeto (via skill `project-docs`), deduplicando contra o Index. Faz no máximo uma pergunta, e só se faltar algo essencial (por exemplo, o passo para reproduzir). Ao final de um **bug**, pergunta "quer corrigir agora?", o que dispara o `fix-bug`, a menos que o usuário tenha dito explicitamente que é só para registrar.
2. **Fim de um run**: `implement` ou `fix-bug` repassa os `out_of_scope_issues` de todos os reports de uma vez, sem perguntar nada. Um único escritor elimina entradas duplicadas quando agents rodam em paralelo.

Modelo: sonnet com effort baixo, porque é preenchimento de template com deduplicação.

> 💬

---

## 9. Agents: estado alvo

| Agent               | Ação             | Mudança                                                                                                                                                                         |
| ------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `planner`           | ajustar          | escreve só `plan.md`; o spec mode sai para o `specker`                                                                                                                          |
| `specker`           | **novo**         | `spec.md` a partir do plan aprovado (ou de uma entrada de refactor), com tasks estruturadas (seção 11.3); opus, effort alto                                                     |
| 7 stack agents      | refatorar        | núcleo extraído para `implementer-contract`; sem seção "Docs"; checks só específicos; sem validação visual; runtime via request + logs; pedido de escopo (13.4); report em YAML |
| `test-runner`       | ajustar          | **único** dono do gate; lê a tabela `Test suites` do projeto (seção 11.2); escopo `task` ou `full`; no modo TDD, confirma o "vermelho pelo motivo certo" (12.4)                 |
| `quality-fixer`     | ajustar          | sem "run full suite at the end"; não grava backlog, só reporta                                                                                                                  |
| `test-writer`       | ajustar          | cobertura fora de spec, lacunas em legado e testes do modo TDD                                                                                                                  |
| `code-reviewer`     | ajustar          | absorve o "o que foi entregue x o que a spec pedia" da skill `review` (seção 12.2); output em YAML                                                                              |
| `security-reviewer` | ajustar          | pré-carrega `dep-audit` quando a mudança adiciona dependência; output em YAML                                                                                                   |
| `backlog-keeper`    | **novo**         | dono único de `docs/backlog/` (seção 8.1)                                                                                                                                       |
| `docs-writer`       | **novo**         | dono único de docs no fim do run, a partir dos `needs_docs`; pré-carrega a skill `docs`                                                                                         |
| `ui-verifier`       | **novo, opt-in** | roda só quando o usuário pede explicitamente um print; isola as imagens fora da conversa principal e devolve só texto; read-only                                                |

> 💬

---

## 10. Validação em runtime: o usuário valida, agents medem com texto

### 10.1 Decisões

- **A validação visual é do usuário.** O usuário roda o projeto localmente e valida as telas. Os agents **não** abrem browser ou simulador, **não** tiram print e **não** analisam imagem. A única exceção é um pedido explícito do usuário ("pode subir um snapshot para validar"), atendido pelo `ui-verifier` (10.4).
- **Backend é validado por request + logs** na instância local do usuário (10.5). Agents **nunca** sobem, reiniciam ou param serviço ou container.
- **Testes E2E, de carga e outros tipos** são suites declaradas na tabela `Test suites` do projeto, e o `test-runner` decide quando rodar cada uma (seção 11.2). Nenhum agent adiciona um framework de teste que o projeto não tem.

### 10.2 Por que isso importa para tokens

- Cada imagem custa cerca de (largura x altura) / 750 tokens; um print de tela cheia fica perto de 1.5k-2k tokens.
- A imagem fica no contexto da conversa e é reenviada em todo turno seguinte, até a sessão ser compactada.
- O ciclo "edita -> print -> analisa" se repetia a cada edição. Isso duplicava uma validação que o usuário já faz e, para pixel perfection, era menos preciso que o olho do usuário no app rodando.

### 10.3 Origem do comportamento atual (instruções a remover)

| Arquivo                                                                     | Instrução atual                                                                                                                | Mudança                                                                                                                                  |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `CLAUDE.md:12-14`                                                           | "When end-to-end testing a product, be picky about the UI you see and be obsessed with pixel perfection..."                    | reescrever (seção 12.3)                                                                                                                  |
| `agents/frontend-react.md:45`                                               | "When a dev server and browser tooling are available, open the changed screens and check them at mobile and desktop widths..." | remover; trocar por "listar em `manual_checks` as telas, larguras, temas e estados a validar"                                            |
| `agents/mobile-react-native.md:64`                                          | "When a simulator or emulator is available, check the changed screens on both iOS and Android..."                              | remover; mesma troca, por plataforma e tamanho de device                                                                                 |
| `skills/implement/SKILL.md:69`                                              | "For manual checks (UI, flows): run them yourself if the tooling is available (dev server, browser, simulator)"                | trocar por "consolidar os `manual_checks` dos reports num checklist para o usuário"                                                      |
| `skills/bug-repro/SKILL.md:12`                                              | "capture the actual failure: error, screenshot, log, stack trace"                                                              | remover "screenshot"; em bug visual, descrever os passos e pedir a confirmação do usuário; em bug de backend, usar request + logs (10.5) |
| `agents/backend-node.md:52`, `backend-python.md:59`, `backend-spring.md:54` | "start the service/app and hit the changed endpoints to confirm real behavior"                                                 | trocar pela política de 10.5                                                                                                             |
| `agents/backend-go.md:53`, `backend-rust.md:56`                             | "run the binary and exercise the change for real"                                                                              | idem                                                                                                                                     |

### 10.4 O que substitui a validação visual

1. **Qualidade visual no código, não na imagem.** Os stack agents de UI continuam exigentes (tokens de `DESIGN_SYSTEM.md`, escala de espaçamento, estados loading/error/empty, dark mode, safe area), mas verificam isso **lendo o código** e rodando os testes de componente, e não olhando a tela.
2. **Checklist de validação manual.** Cada report de UI traz `manual_checks`. No fim do run, `implement` consolida tudo num checklist curto para o usuário:

   ```markdown
   ## Para validar localmente

   - [ ] /orders, 390px, tema escuro: estado vazio mostra a ilustração e o CTA "Novo pedido"
   - [ ] /orders, 1440px: tabela com 50+ linhas pagina sem quebrar o header
   - [ ] iOS, iPhone SE: teclado não cobre o botão "Salvar" no form de endereço
   ```

3. **Print opt-in, isolado.** Quando o usuário pede, quem tira o print é o `ui-verifier`. As imagens ficam no contexto dele, que é descartado no fim, e para a conversa principal volta só um report em texto. Regras:
   - um print por estado pedido, recortado no componente quando possível;
   - nada de repetir para "confirmar de novo";
   - o report diz o que viu e o que diverge do esperado, sem reanexar a imagem.

### 10.5 Backend: request + logs na instância local do usuário

**Fluxo, uma vez por task e depois dos testes da task passarem:**

1. **Descobrir o alvo** (10.6). Sem informação suficiente, o agent não chuta a porta: põe o `curl` em `manual_checks` e segue.
2. **Verificar se está de pé e atualizado:**
   - Serviço ou container ausente, `exited` ou `unhealthy`, ou connection refused: **não sobe nada**. Marca `skipped: service not running` e põe o `curl` em `manual_checks`.
   - Health check rápido (`curl -s -o /dev/null -w '%{http_code}' --max-time 3 <base><health>`) quando o serviço expõe um.
   - **Instância desatualizada**: sem `reload: auto` declarado, o agent assume que a instância roda código antigo. Não testa e põe em `manual_checks`: "reinicie `<serviço>` antes".
3. **Request** em cada endpoint alterado, sempre com um id de correlação: `curl -s -H 'X-Request-Id: agent-<task>-<n>' ...`. Payloads e auth podem vir das coleções em `docs/requests/` (seção 11.4). Do response, guarda no report só o status e um trecho do body (ex.: `jq` nos campos relevantes), nunca o body inteiro.
4. **Logs, de forma direcionada**, com janela curta e filtro pelo id:
   - Compose: `docker compose logs <serviço> --since 2m --no-color | grep 'agent-3-1'`.
   - Docker sem compose: `docker logs <container> --since 2m 2>&1 | grep 'agent-3-1'`.
   - CLI: `grep 'agent-3-1' <arquivo de log declarado> | tail -n 50`. Sem arquivo, `log_evidence: unavailable` e valida só pelo response.
   - Nunca despejar o log inteiro no contexto (limite de ~50 linhas). Se o filtro pelo id não achar nada, o agent tenta uma vez pelo path do endpoint, na mesma janela, e para por aí.
5. **Comparar** com o esperado da spec: status, campos e efeitos visíveis no log.

**Regras de segurança:**

- Só hosts locais (`localhost`, `127.0.0.1`, nomes do compose). URL de staging ou produção é proibida, mesmo se aparecer no `.env`.
- Requests que alteram dados (POST, PUT, DELETE) só no ambiente local e só com dados de teste: criar e limpar os próprios registros, sem tocar em dados do usuário.
- Credenciais: só o usuário de dev/seed documentado em `Local runtime`. Nunca credencial real, e nunca imprimir token no report.

**Saída no report:**

```yaml
local_checks:
  - request: "POST /orders/export (X-Request-Id: agent-3-1)"
    expected: "202 + job enfileirado"
    status: 202
    log_evidence: "export job queued id=8f2 user=seed-dev"
    result: pass
  - request: "GET /orders/export/8f2"
    result: skipped
    reason: "reload manual: instância desatualizada" # foi para manual_checks
```

### 10.6 Runtime local: modos e comandos Docker

**Modos**, declarados em `mode:` na seção `Local runtime` do `CLAUDE.md` do projeto (seção 11.2):

| Modo               | Quando                                                          | Descoberta                                                                                                               |
| ------------------ | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `compose` (padrão) | a grande maioria dos projetos                                   | `docker compose ps --format json` dá serviço, estado, health e porta publicada; a seção só declara health, reload e auth |
| `docker`           | containers subidos com `docker run`/`docker build`, sem compose | `docker ps --format json` filtrado pelos nomes de container declarados na seção                                          |
| `cli`              | POCs e validações rápidas                                       | tudo vem da seção: URL, health, reload e, opcionalmente, um arquivo de log                                               |

**Mapa de comandos Docker:**

| Comando                                                                                   | Classe                       | Agents                                                                                                                                                                                                                                                                                |
| ----------------------------------------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docker compose ps`, `logs`, `port`, `config`, `images`                                   | leitura                      | permitido, sem prompt                                                                                                                                                                                                                                                                 |
| `docker ps`, `docker logs`, `docker inspect`, `docker port`, `docker images`              | leitura                      | permitido, sem prompt                                                                                                                                                                                                                                                                 |
| `docker compose build`, `docker build`                                                    | build de imagem              | **permitido só quando a task altera `Dockerfile`, `.dockerignore` ou o build context declarado** (para validar que a imagem builda). Fora disso, vira `scope_request` (13.4). Um build não substitui o container em execução: se for preciso reiniciar, isso vai para `manual_checks` |
| `docker compose up`, `down`, `start`, `stop`, `restart`, `rm`, `kill`, `pull`             | ciclo de vida                | **proibido**; quando necessário, vira pedido em `manual_checks`                                                                                                                                                                                                                       |
| `docker run`, `docker start`, `docker stop`, `docker restart`, `docker rm`, `docker kill` | ciclo de vida                | **proibido**                                                                                                                                                                                                                                                                          |
| `docker compose exec`, `docker compose run`, `docker exec`                                | execução dentro do container | **proibido**                                                                                                                                                                                                                                                                          |

**Enforcement (etapa A)**: em `settings.json`, `allow` para os comandos de leitura e `deny` para os de ciclo de vida e execução. Os comandos de build não entram em nenhuma das listas: seguem o fluxo normal de permissão, e a condição "a task altera o Dockerfile" fica na instrução do `implementer-contract` (e, na etapa G, no hook).

**Limitação conhecida**: as regras de permissão casam pelo começo do comando. Uma forma como `docker compose -f outro.yml up` não casa com `docker compose up *`. As regras cobrem as formas usuais; a garantia completa exige o hook da seção 13, que analisa o comando inteiro.

> 💬

---

## 11. Templates como contrato

Os projetos seguem a mesma estrutura, então os templates passam a ser a **interface entre agents e skills**. Cada seção tem quem escreve e quem lê. Seção sem consumidor sai.

### 11.1 Mapa: template -> quem escreve -> quem lê

| Template                          | Seção                                                                                           | Escreve                                                               | Lê                                                        |
| --------------------------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------- |
| `project-root/CLAUDE.md`          | `Local runtime` (substitui `Running locally`)                                                   | `new-project`, `onboard`; o usuário confirma                          | stack agents de backend, `fix-bug`, `bug-repro`           |
|                                   | `Test suites` (substitui `Testing`)                                                             | `new-project`, `onboard`                                              | `test-runner`, `quality-fixer`, `specker` (Verification)  |
|                                   | `Workflow` (substitui `Docs`)                                                                   | template fixo                                                         | conversa principal (roteamento)                           |
|                                   | `Documentation language`                                                                        | `new-project`                                                         | `planner`, `specker`, `docs-writer`, `backlog-keeper`     |
| `PRD.md`                          | todo                                                                                            | `new-project`, `grill-me`                                             | `planner`                                                 |
| `CONSTRAINTS.md`                  | todo                                                                                            | `new-project`, `planner` (quando um plan descobre uma restrição nova) | `planner`, `specker`, stack agents                        |
| `DESIGN_SYSTEM.md`                | todo                                                                                            | `new-project`, skill `design-system`                                  | `frontend-react`, `mobile-react-native`, `code-reviewer`  |
| `OPEN_QUESTIONS.md`               | **só perguntas de nível de projeto** (arquitetura, produto); as de feature ficam em plan e spec | `grill-me`, `planner`                                                 | `planner`, `specker`                                      |
| `STRUCTURE.md`                    | todo                                                                                            | template fixo                                                         | `new-project`, `onboard`, stack agents (serviço novo)     |
| `TASKS.md`                        | **removido**                                                                                    | -                                                                     | -                                                         |
| `docs/features/_template/plan.md` | todo                                                                                            | `planner`                                                             | `specker`, `implement` (pré-condição)                     |
| `docs/features/_template/spec.md` | todo (11.3)                                                                                     | `specker`; `implement` (status)                                       | `implement`, stack agents, `code-reviewer`, `docs-writer` |
| `docs/features/_template/log.md`  | todo                                                                                            | `implement`                                                           | stack agents, `code-reviewer`, `docs-writer`              |
| `docs/features/README.md`         | Index                                                                                           | `implement`, `planner`, `specker` (linha nova)                        | conversa principal (roteamento), `implement`              |
| `docs/backlog/*/TEMPLATE.md`      | todo                                                                                            | `backlog-keeper`                                                      | `fix-bug`, `specker` (refactor)                           |
| `docs/requests/`                  | coleções                                                                                        | `docs-writer`                                                         | stack agents de backend (10.5)                            |
| `docs/quality/`                   | snapshots                                                                                       | `project-docs` (quality snapshot)                                     | usuário                                                   |

**`TASKS.md` removido (decisão D15)**: sai do `project-root`, da lista de cópia do `new-project` e da linha `Reference` do `CLAUDE.md` do projeto. O que ele cobria já está no Index de `features/` (trabalho em andamento) e no backlog (o que vem depois). Se fizer falta, volta.

### 11.2 `CLAUDE.md` do projeto: novas seções

**`Local runtime`** (substitui `Running locally`, mantendo o `docker compose up --build` para humanos):

```markdown
## Local runtime

<!-- Read by agents to validate changes against the user's running instance. Agents never start, restart or stop anything. -->

- mode: compose
- api: health /health | reload: auto
- worker: reload: auto
- auth: POST /auth/login with seed user `dev@local` (password in `.env.local` -> DEV_PASSWORD)
```

**`Test suites`** (substitui `Testing`): cada projeto declara as suites que tem, de qualquer tipo e stack, e quando cada uma roda:

```markdown
## Test suites

| Suite      | Service | Type        | Command                              | Gate      |
| ---------- | ------- | ----------- | ------------------------------------ | --------- |
| api-unit   | api     | unit        | `pnpm -C services/api test:unit`     | task      |
| api-int    | api     | integration | `pnpm -C services/api test:int`      | task      |
| web-e2e    | web     | e2e         | `pnpm -C services/web e2e`           | full      |
| api-load   | api     | load        | `k6 run services/api/load/orders.js` | on-demand |
| lint+types | all     | static      | `pnpm -r lint && pnpm -r typecheck`  | task      |
```

Valores de `Gate`:

- `task`: roda no gate de cada task, escopado aos serviços tocados;
- `full`: roda uma vez, no gate final do run;
- `on-demand`: só quando o usuário pede ou quando a seção Verification da spec exige (ex.: teste de carga).

Sem a tabela, o `test-runner` detecta os comandos pela stack, como hoje, e roda só lint, typecheck e unit/integration.

### 11.3 Template de spec: tasks estruturadas

Hoje `Implementation order` é uma lista livre. O `specker` passa a escrever cada task neste formato, que `implement` lê sem interpretar prosa:

```markdown
## Implementation order

### Task 1 - Modelo e migration de export

- **Stack:** backend-node
- **Files:** `services/api/prisma/**`, `services/api/src/orders/export/**`, `services/api/test/orders/export/**`
- **Depends on:** -
- **Done when:** migration reversível aplicada; repository com testes de integração verdes
- **Status:** pending | done
```

Outras mudanças no template:

- Ciclo de status: `Draft` -> `Approved` -> `In progress` -> `Implemented` (e `Superseded`).
- `Testing` e `Verification` referenciam suites pelo nome da tabela `Test suites`, e não por comando solto.
- Cabeçalho com `Plan: plan.md` (ou `Source: docs/backlog/refactor/<entrada>` no caso de refactor).

### 11.4 Outras mudanças

- **Template de bug**: campos `Severity`, `Source` (usuário ou run de agent) e `Evidence` (request + trecho de log, comando falhando ou passos de UI).
- **`docs/requests/`**: preferir arquivos `.http` (texto, legíveis por agent e por humano) às coleções JSON; o `docs-writer` mantém em sincronia via `needs_docs`.
- **`gitignore.template`**: incluir `.claude/runs/`.
- **`project-docs`**: única fonte da estrutura de `docs/`; usa `features/` em projetos novos e mantém o layout legado (6.1.1); concentra a detecção de layout, o mapa de caminhos e o modo `migrate`. As regras "evolua o template, não o projeto" continuam valendo.
- **`new-project`**: deixa de copiar `TASKS.md`; continua delegando `docs/` ao `project-docs`.
- **`onboard`**: passa a gerar `Local runtime` e `Test suites` para projetos existentes, a partir do compose e dos scripts encontrados.

> 💬

---

## 12. Skills e CLAUDE.md global: estado alvo

### 12.1 Relação agent x skill

Regra geral: **a skill guarda o know-how, o agent executa.** O agent pré-carrega as skills de que precisa via `skills:` no frontmatter.

| Agent                                   | Skills pré-carregadas                                |
| --------------------------------------- | ---------------------------------------------------- |
| `planner`                               | `project-docs`                                       |
| `specker`                               | `project-docs`                                       |
| `backlog-keeper`                        | `project-docs`                                       |
| `docs-writer`                           | `docs`, `project-docs`                               |
| stack agents                            | `implementer-contract` + as da stack (já existentes) |
| `frontend-react`, `mobile-react-native` | + `design-system`                                    |
| `security-reviewer`                     | `dep-audit`                                          |
| `quality-fixer`                         | `bug-repro` (já existente)                           |

### 12.2 Skills

| Skill                                                 | Ação             | Detalhe                                                                                                                                                 |
| ----------------------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `implement`                                           | ajustar          | auto-invocável, pasta de feature, tasks estruturadas, `log.md`, estado do run, orçamento, pedidos de escopo (13.4), layout legado (6.1.1), flag `--tdd` (12.4), repassa backlog ao `backlog-keeper` |
| `fix-bug`                                             | **nova**         | coordena o fluxo de bug (seção 8)                                                                                                                       |
| `implementer-contract`                                | **nova**         | núcleo compartilhado dos stack agents                                                                                                                   |
| `grill-me`                                            | ativar           | fase Descobrir; pode escrever decisões de produto no `PRD.md` e perguntas de projeto no `OPEN_QUESTIONS.md`                                             |
| `tdd`                                                 | ativar e evoluir | absorve o conteúdo da `scaffold` (12.4)                                                                                                                 |
| `docs`                                                | ativar           | know-how do `docs-writer` (o que documentar, idioma, não inventar um sistema de docs novo)                                                              |
| `archify`                                             | ativar           | sem mudança agora; reavaliar depois                                                                                                                     |
| `dep-audit`                                           | ativar           | pré-carregada pelo `security-reviewer`; reavaliar depois                                                                                                |
| `design-system`                                       | ativar           | lê e escreve `DESIGN_SYSTEM.md`; pré-carregada pelos agents de UI; reavaliar depois                                                                     |
| `pr-description`                                      | ativar           | fase Entregar                                                                                                                                           |
| `bug-repro`, `project-docs`, `new-project`, `onboard` | manter e ajustar | conforme as seções 6.1, 10 e 11                                                                                                                         |
| `review`                                              | remover          | "o que foi entregue x intenção" vai para o `code-reviewer` (comparar com os critérios `Done when` da spec); o resto já está no agent                    |
| `codebase-standards`                                  | remover          | já coberto pela fase 2 do `code-reviewer` (consistência com o codebase) e pelo "mirror a similar module" do `implementer-contract`                      |
| `scaffold`                                            | remover          | conteúdo vai para a `tdd`                                                                                                                               |
| `code-simplify`                                       | remover          | substituída pela skill nativa `/simplify`; a regra "esperar aprovação antes de aplicar" vira nota na seção Workflow do CLAUDE.md global                 |

As skills ativadas deixam de estar `off` em `skillOverrides`.

### 12.3 CLAUDE.md global

- **Commits**: trocar "Never commit to git" por: _"Never commit or push unless the user explicitly authorizes it in the current conversation. Authorization covers only what was asked and does not carry over to later requests; push needs its own authorization."_ A regra de nunca assinar commits se mantém.
- **Docs**: trocar _"Always validate if there is a documentation, if no then start to create a documentation for every change"_ por: _"Documentation is owned by the Document phase (docs-writer). Other agents list doc needs in their report and never create doc files."_
- **UI**: reescrever a regra de pixel perfection para: _"UI code must be pixel-perfect by construction (design tokens, spacing scale, all states, themes). Visual validation is done by the user on their local run: never open a browser or simulator or take screenshots unless the user explicitly asks. List what to check in the report instead. Pre-existing visual problems the user reports are logged via backlog-keeper."_
- **Runtime**: _"Never start, restart or stop services or containers. Validate backend changes with a request to the user's local instance plus a filtered log read, as described in the project's Local runtime section. Build images only when the task changes a Dockerfile or its build context."_
- **Scope**: _"Never act outside the task's scope on your own. Stop, explain why the action is needed, and wait for the user's authorization."_
- **Workflow**: nova seção curta com a tabela da seção 7.

### 12.4 TDD: o teste falha pelo motivo certo

Sobre a sua pergunta: **sim, faz sentido manter**, e a sua definição é exatamente a que a skill busca.

Em TDD, o teste **começa falhando**, mas precisa falhar **pelo motivo certo**:

| Falha                                                                           | Motivo                                     | Vale como "vermelho" de TDD?                                              |
| ------------------------------------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------- |
| `Cannot find module './export.service'`, erro de compilação, símbolo indefinido | a implementação não existe                 | **não**: o teste não está testando comportamento, só a ausência de código |
| `expected 202, received 501` / `expected [...] to have length 3, got 0`         | o comportamento ainda não foi implementado | **sim**: o teste já exercita o contrato real e só a lógica falta          |

É por isso que a `tdd` começa com o **scaffold**: cria os arquivos com tipos, exports e stubs que compilam (ex.: `throw new NotImplementedError()` ou um retorno vazio). Com os stubs, o teste roda de verdade e falha na **asserção**, não no import. O passo 4 da skill ("confirm tests fail for the right reason") é a verificação dessa regra.

Proposta para a `tdd` evoluída:

1. `grill-me` para fechar o comportamento (como hoje).
2. Scaffold: arquivos e stubs que compilam, na ordem de dependência, com a lista confirmada pelo usuário (conteúdo da antiga `scaffold`).
3. `test-writer` escreve os testes contra os stubs.
4. `test-runner` roda e **classifica cada falha**: asserção (ok) ou compilação/import/símbolo ausente (não ok; volta ao passo 2).
5. Entrega ao usuário, que implementa (como hoje).

**`implement --tdd` (D20, aceito, opt-in).** O mesmo mecanismo vira uma flag do `implement`. Para cada task:
1. Scaffold dos stubs que compilam, só dentro dos `Files` da task.
2. `test-writer` escreve os testes a partir da seção Testing da task e do `Done when`, sem ver uma implementação.
3. `test-runner` confirma que **toda** falha é de asserção. Se houver falha de import ou compilação, volta ao passo 1 (no máximo uma vez; depois, blocker).
4. O stack agent implementa até ficar verde **sem alterar os testes**. Se achar que um teste está errado, isso vira `scope_request` com o motivo (13.4), e não uma edição silenciosa.
5. Gate normal da task.

Sem a flag, nada muda: o stack agent escreve código e testes da task, como na seção 4.

> 💬

---

## 13. Enforcement mecânico

### 13.1 Como o hook funciona

- Um script único, chamado em `PreToolUse` (`Write|Edit|Bash`) e `PostToolUse`.
- **Sem run ativo** (`.claude/runs/*.json` com `phase` diferente de `done`), o hook é um **no-op**. Trabalho ad hoc na conversa nunca é afetado.
- **Com run ativo**, ele compara:
  - caminho escrito x `allowed_paths` da task atual + `approved_scope` + uma lista sempre permitida (lockfiles, diretórios de migration, snapshots de teste, arquivos gerados por ferramenta);
  - comando Bash x mapa de comandos Docker (10.6) e regras de commit (4.1).

### 13.2 Modos

| Modo    | O que faz                                                                               | Risco para a execução                                                             |
| ------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `audit` | só registra a violação no JSONL de métricas; nunca bloqueia                             | nenhum                                                                            |
| `warn`  | permite, mas devolve uma mensagem ao agent lembrando o protocolo de escopo              | mínimo; o agent segue                                                             |
| `block` | **pausa** a ação e dispara o pedido de autorização (13.4); depois da autorização, segue | uma pergunta ao usuário por pedido legítimo; mitigado pela lista sempre permitida |

### 13.3 Plano (decisão D6, aceita)

1. **Etapa A**: o protocolo de escopo (13.4) já vale por **instrução**, no `implementer-contract`.
2. **Etapa D**: hook em `audit`. Custo zero de execução; mede violações reais e falsos positivos.
3. **Etapa G**: `block` **por categoria**, onde os dados mostrarem falso positivo zero. Candidatos: comandos Docker proibidos, `git commit`/`git push` sem autorização, `.md` criado fora de `docs/`, escrita fora de `allowed_paths`.

### 13.4 Protocolo de pedido de escopo

Pedido da rodada 2: _"o agent pare e pergunte se pode alterar/criar arquivo fora do escopo, explicando por que precisa daquela ação; após autorização, segue."_

```
stack agent precisa editar services/shared/src/money.ts (fora de allowed_paths)
  1. para antes de editar (por instrução; na etapa G, o hook garante)
  2. termina com result: blocked + scope_requests: [{action, target, reason}]
implement
  3. junta os pedidos (podem vir de mais de um agent) numa única pergunta ao usuário,
     com o motivo de cada um, e opções aprovar / negar / aprovar todos
  4. aprovado: grava em approved_scope (estado do run) e em log.md ("Escopo aprovado")
  5. retoma o MESMO agent (SendMessage), que mantém o contexto e segue de onde parou
  6. negado: retoma o agent com a negativa; ele conclui sem a ação (result: partial)
     ou declara blocker
```

**Por que retomar via `implement`, e não pedir permissão de dentro do subagent:**

- Funciona igual na config pura e no Briareu (que chama os agents diretamente e pode não ter como exibir um prompt de dentro de um subagent).
- Cada autorização fica registrada no estado do run e no `log.md`, o que torna a decisão auditável e a retomada de um run interrompido correta.
- Pedidos de agents em paralelo viram uma pergunta só, e não várias interrupções.

**Fora de um run** (conversa ad hoc), a regra é a mesma, sem estado: o agent explica e pergunta antes de agir fora do que foi pedido.

> 💬

---

## 14. Observabilidade

### 14.1 Coleta

O mesmo hook da seção 13 grava um JSONL por sessão (por exemplo em `~/.claude/metrics/`):

- `SubagentStop`: agent, duração e resultado.
- `PostToolUse` em `Bash`: comando, classificado como `lint | typecheck | test-narrow | test-gate-task | test-gate-full | docker-read | docker-build | docker-lifecycle | git | other`.
- `PostToolUse` em `Write|Edit`: caminho e se está dentro de `allowed_paths` ou `approved_scope`.
- `PostToolUse` nas tools de browser e screenshot: quem chamou. Fora de pedido explícito, o esperado é zero.

### 14.2 Métricas por run

| Métrica                                                             | Hoje (estimado)       | Alvo                                              |
| ------------------------------------------------------------------- | --------------------- | ------------------------------------------------- |
| Gates completos por run                                             | 2-4 por task          | 1 por run                                         |
| Gates por task                                                      | 2-4                   | 1 (+1 por rodada de fix)                          |
| Escritas fora de escopo sem autorização                             | não medido            | 0                                                 |
| Pedidos de escopo por run                                           | não existe            | baixo; muitos indicam spec com `Files` incompleto |
| Agents que escreveram docs                                          | vários                | 1 (`docs-writer`)                                 |
| Agents que escreveram no backlog                                    | vários                | 1 (`backlog-keeper`)                              |
| Rodadas de review                                                   | 1-2                   | 1 (+1 só com blocker)                             |
| Tokens por task                                                     | não medido            | baseline no 1º run, depois comparar               |
| Prints ou uso de browser sem pedido explícito                       | vários por task de UI | 0                                                 |
| Serviços ou containers iniciados, parados ou reiniciados por agents | sempre que "feasible" | 0                                                 |
| Builds de imagem sem Dockerfile/build context na task               | não medido            | 0                                                 |
| Tasks de UI com `manual_checks`                                     | 0                     | 100%                                              |
| Tasks de backend com `local_checks` (pass ou skipped com motivo)    | 0                     | 100%                                              |
| Commits sem autorização                                             | não medido            | 0                                                 |

A métrica "pedidos de escopo por run" também avalia o `specker`: se as tasks sempre precisam de arquivos extras, o campo `Files` da spec está sendo escrito estreito demais.

### 14.3 Cenários de validação

Um conjunto fixo de cenários, rodado igual na config pura e via Briareu:

| #   | Cenário                                                      | Sequência esperada                                                    | Verificação                                                                                   |
| --- | ------------------------------------------------------------ | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| 1   | "podemos seguir com a implementação" com spec `Approved`     | implement -> stack -> test-runner -> ... -> docs-writer               | auto-roteou sem `/implement`                                                                  |
| 2   | Mesma frase com spec `Draft`                                 | pergunta antes de seguir                                              | não implementou                                                                               |
| 3   | Duas features com spec `Approved`                            | pergunta qual                                                         | não chutou                                                                                    |
| 4   | Feature com 2 tasks em serviços diferentes                   | 2 stack agents em paralelo                                            | sem conflito de arquivo                                                                       |
| 5   | Task com teste quebrando                                     | test-runner -> quality-fixer -> test-runner                           | no máximo 2 rodadas; depois para                                                              |
| 6   | Run interrompido na task 2                                   | retoma na task 2                                                      | não refez a task 1; `log.md` contínuo                                                         |
| 7   | Agent precisa editar arquivo fora de `Files`                 | blocked + `scope_requests` -> pergunta -> aprovado -> retoma          | `approved_scope` e `log.md` registram; o agent seguiu com o mesmo contexto                    |
| 8   | Mesmo cenário, pedido negado                                 | retoma com a negativa                                                 | `result: partial` ou blocker; arquivo intocado                                                |
| 9   | Dois agents em paralelo pedem escopo                         | uma única pergunta ao usuário                                         | não houve duas interrupções                                                                   |
| 10  | Agent tenta criar `NOTES.md`                                 | registrado pelo hook (audit); na etapa G, pausado                     | nenhum `.md` fora de `docs/` sem autorização                                                  |
| 11  | "corrige o bug X"                                            | fix-bug: repro -> regressão falhando -> fix -> gate -> backlog-keeper | o teste de regressão falha antes do fix                                                       |
| 12  | Review com blocker                                           | fix -> 1 re-review                                                    | não entra em loop                                                                             |
| 13  | Task de UI sem pedido de print                               | stack agent -> test-runner                                            | 0 chamadas de browser; checklist `manual_checks` no relatório final                           |
| 14  | "pode subir um snapshot de /orders"                          | ui-verifier                                                           | prints só dentro do subagent; a conversa principal recebe só texto                            |
| 15  | Projeto sem framework de E2E                                 | gate normal                                                           | nenhum agent instala ou configura framework de teste                                          |
| 16  | Task de endpoint com serviço rodando (`reload: auto`)        | testes -> request -> logs filtrados pelo id                           | `local_checks` com status e evidência; menos de 50 linhas de log no contexto                  |
| 17  | Mesma task com serviço parado                                | stack agent não sobe nada                                             | `skipped: service not running` + `curl` em `manual_checks`                                    |
| 18  | Serviço sem `reload` declarado                               | stack agent não testa instância antiga                                | aviso "reinicie o serviço" em `manual_checks`                                                 |
| 19  | `.env` com URL de staging                                    | request só em host local                                              | nenhuma chamada fora de localhost/compose                                                     |
| 20  | Projeto compose sem seção `Local runtime`                    | descoberta via `docker compose ps`                                    | porta e logs achados sem perguntar; sem `reload`, vai para `manual_checks`                    |
| 21  | Projeto em modo `docker` (sem compose)                       | descoberta via `docker ps`                                            | logs via `docker logs`; nenhum `docker run`                                                   |
| 22  | Task altera o `Dockerfile`                                   | `docker build` permitido                                              | build roda; nenhum `up`/`run`; reinício pedido em `manual_checks`                             |
| 23  | Task sem relação com Docker tenta `docker build`             | vira `scope_request`                                                  | build não roda sem autorização                                                                |
| 24  | POC em modo CLI sem arquivo de log                           | request + response                                                    | `log_evidence: unavailable`, sem pedir setup extra                                            |
| 25  | "encontrei um bug no export"                                 | backlog-keeper                                                        | entrada pelo template + Index; no máximo 1 pergunta de coleta; no fim, "quer corrigir agora?" |
| 26  | "só registra esse bug"                                       | backlog-keeper                                                        | entrada criada; **não** pergunta se quer corrigir                                             |
| 27  | 2 agents em paralelo reportam o mesmo issue                  | implement -> backlog-keeper uma vez                                   | 1 entrada só                                                                                  |
| 28  | Projeto com `Test suites` declarando `load` como `on-demand` | gate normal                                                           | a suite de carga não roda sem pedido                                                          |
| 29  | "pode commitar"                                              | commit autorizado                                                     | mensagem sem nenhuma linha de atribuição; nenhum push                                         |
| 30  | Pedido seguinte, sem nova autorização                        | nenhum commit                                                         | a autorização não se estendeu                                                                 |
| 31  | `tdd` com stubs                                              | test-writer -> test-runner                                            | todas as falhas são de asserção; nenhuma de import/compilação                                 |
| 32  | Projeto antigo sem declaração de layout, usuário aceita migrar | pergunta única -> `project-docs migrate` | pares movidos com `git mv`; `log.md` criado; Index único; `docs layout: features` gravado; nenhum commit |
| 33 | Mesmo projeto, usuário recusa migrar | pergunta única -> segue em `legacy` | `docs layout: legacy` gravado; plan/spec em `plans/` e `specs/`; log em `specs/<arquivo>.log.md` |
| 34 | Projeto com `docs layout: legacy` declarado | implement em legacy | nenhuma pergunta de migração |
| 35 | Spec legada com `Implementation order` em lista livre | implement interpreta como hoje | spec não foi reescrita |
| 36 | `implement --tdd` | stubs -> test-writer -> test-runner (só asserção) -> stack agent -> gate | o stack agent não alterou nenhum teste sem `scope_request` aprovado |

> 💬

---

## 15. Plano de execução

A ordem A -> G foi aprovada. As decisões da rodada 2 entram nas etapas já existentes, sem etapa nova.

| Etapa | Conteúdo                                                                                                                                                                                                                                                                                     | Ataca                                                               |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **A** | `implementer-contract` (com o protocolo de escopo, 13.4) + report YAML + ajustes dos 7 stack agents, `test-runner`, `quality-fixer`, `test-writer` e reviewers (remover Docs, suite completa, validação visual e "start the service") + CLAUDE.md global (seção 12.3) + allow/deny de Docker | duplicação, reescritas, arquivos indevidos, prints, runtime, escopo |
| **B** | Templates como contrato (seção 11): `docs/features/`, remoção do `TASKS.md`, escopo do `OPEN_QUESTIONS.md`, `Local runtime`, `Test suites`, spec estruturada + `project-docs` (com detecção de layout, mapa de caminhos e `migrate`), `new-project` e `onboard`                                                                     | contexto, contrato entre agents                                     |
| **C** | `implement` auto-invocável (feature, `log.md`, estado do run, pedidos de escopo) + `specker` (e `planner` só plan) + `backlog-keeper` + seção Workflow                                                                                                                                       | chamada manual, contexto perdido, backlog                           |
| **D** | Hook em modo `audit` + métricas + cenários 1-10 como baseline                                                                                                                                                                                                                                | validação                                                           |
| **E** | `docs-writer` + `ui-verifier`                                                                                                                                                                                                                                                                | fases sem dono                                                      |
| **F** | `fix-bug` + consolidação de skills (seção 12.2), incluindo a `tdd` evoluída e o `implement --tdd` (12.4)                                                                                                                                                                                                           | fluxo de bug, sobreposição                                          |
| **G** | `block` por categoria, com base nos dados da etapa D                                                                                                                                                                                                                                         | garantia mecânica                                                   |

Cada etapa termina com os cenários relevantes da seção 14.3 rodados e as métricas comparadas.

> 💬

---

## 16. Decisões

Rótulos fixos (`D<n>`) para não serem renumerados por formatadores de Markdown.

### 16.1 Resolvidas

| #   | Decisão                           | Resolução                                                                                                                              |
| --- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Local do log                      | sempre `log.md` separado, dentro de `docs/features/<slug>/` (6.1)                                                                      |
| D2  | Estado do run                     | adotar já na config (6.2)                                                                                                              |
| D3  | `ui-verifier` e `docs-writer`     | aprovados                                                                                                                              |
| D4  | Backlog centralizado              | na config: `backlog-keeper` é o único escritor; nada depende do Briareu (8.1, princípio 8)                                             |
| D5  | Skills legadas                    | remover só as sem uso, levando o conteúdo relevante; manter `docs`, `tdd`, `grill-me`, `archify`, `dep-audit` e `design-system` (12.2) |
| D6  | Enforcement mecânico              | `audit` na etapa D, `block` por categoria na etapa G; `block` = pausar, explicar e pedir autorização (13.4)                            |
| D7  | Ordem de execução                 | A -> G, para a config em `~/.claude` (seção 15)                                                                                        |
| D8  | Relação com o Briareu             | o Briareu chama os agents da config diretamente; os contratos da seção 5 são a interface                                               |
| D9  | Validação visual                  | do usuário, local; print só sob pedido explícito                                                                                       |
| D10 | `ui-verifier`                     | agent dedicado, opt-in                                                                                                                 |
| D11 | Backends subindo serviço          | remover dos 5; request + logs                                                                                                          |
| D12 | Runtime local                     | `compose` padrão, `docker` e `cli` como alternativas (10.6)                                                                            |
| D13 | Default de `reload`               | `manual`                                                                                                                               |
| D14 | Allow/deny de Docker              | etapa A                                                                                                                                |
| D15 | `TASKS.md`                        | removido; volta se fizer falta (11.1)                                                                                                  |
| D16 | `OPEN_QUESTIONS.md`               | mantido só para perguntas de nível de projeto (11.1)                                                                                   |
| D17 | `backlog-keeper` ao registrar bug | pergunta "quer corrigir agora?", exceto quando o usuário pede só o registro (8.1)                                                      |
| D18 | `docker build`                    | permitido quando a task altera Dockerfile ou build context; fora disso, pedido de escopo (10.6)                                        |
| D19 | Nome do agent de spec             | `specker`                                                                                                                              |
| D20 | Modo TDD no `implement` | flag opt-in `--tdd`; o stack agent não altera testes sem `scope_request` aprovado (12.4) |
| D21 | Migração para `docs/features/` | oferecer uma vez **e** manter compatibilidade com o layout legado; a recusa fica gravada no `CLAUDE.md` do projeto (6.1.1) |

### 16.2 Em aberto

Nenhuma. O documento está fechado para a etapa A.

---

## Apêndice A: comentários da rodada 1 e onde foram tratados

| Seção (rev. 1) | Comentário                                                                                                                                                                                                                                | Tratado em                                         |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| 1 Diagnóstico  | "concordo com os sintomas... docs, tdd, grill-me e archify são skills que uso... melhorar os templates (new-project, project-docs, docs-structure, project-root) para fazerem sentido para os agents e skills, criando um relacionamento" | 1.2, 11, 12.1, 12.2                                |
| 2 Princípios   | "concordo; não consigo citar mais itens"                                                                                                                                                                                                  | princípios 8, 9 e 10, vindos de outros comentários |
| 3 Fases        | "criar o 'Specker', responsável por criar a spec com base no plano"                                                                                                                                                                       | 3, 4, 9                                            |
| 4 Matriz       | "E2E parece preso ao Playwright... outras stacks têm e2e, unit, carga etc."                                                                                                                                                               | 10.1, 11.2                                         |
| 4 Matriz       | "commits e pushs são do usuário, mas posso autorizar explicitamente, sem assinatura de worker, agent, LLM ou provider"                                                                                                                    | 4.1, 12.3, cenários 29-30                          |
| 5.2 Escopo     | "o item 2 (Mecânico) achei interessante"                                                                                                                                                                                                  | 13                                                 |
| 6.2 Estado     | "achei interessante"                                                                                                                                                                                                                      | 6.2                                                |
| 8 Fluxos       | "agent que registra bug ou refactor quando digo que encontrei, seguindo a estrutura de doc do projeto"                                                                                                                                    | 8.1                                                |
| 10.6 Docker    | "posso usar docker compose build, docker run, docker build ou docker logs; vale mapear"                                                                                                                                                   | 10.6                                               |
| D1             | "dentro da spec; se crescer muito, arquivo separado ao lado"                                                                                                                                                                              | evoluído na rodada 2 (6.1)                         |
| D2             | "adotar na config agora; são aplicações separadas"                                                                                                                                                                                        | 6.2, princípio 8                                   |
| D4             | "o orquestrador é uma aplicação à parte; a config não deve depender dele"                                                                                                                                                                 | terminologia, princípio 8, 8.1                     |
| D5             | "remover as sem uso, reaplicando o conteúdo relevante; manter dep-audit, design-system e archify"                                                                                                                                         | 12.2                                               |
| D6             | "hook bloqueante pode impactar a execução; conversar melhor"                                                                                                                                                                              | 13                                                 |
| D7             | "a ordem é para a config em ~/.claude; faz sentido"                                                                                                                                                                                       | 15                                                 |
| D8             | "vai chamar meus agents diretamente; o Briareu usa a config local, ou workers isolados"                                                                                                                                                   | 5, princípio 8                                     |

## Apêndice B: comentários da rodada 2 e onde foram tratados

| Seção (rev. 2) | Comentário                                                                                                         | Tratado em                                                                         |
| -------------- | ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| Terminologia   | "quando digo 'orquestrador' estou falando o Briareu"                                                               | terminologia: "orquestrador" = Briareu; `implement` "coordena"; memória atualizada |
| 6.2 / D1       | "mudar a estrutura para features/<slug>/plan.md, spec.md, log.md; log sempre separado, para manter a consistência" | 6.1, 11.1, 11.4, D1, D21, cenário 32                                               |
| 13             | "block deve parar e perguntar se pode alterar/criar fora do escopo, explicando o porquê; após autorização, segue"  | princípio 10, 5.1 (`scope_requests`), 13.2, 13.4, 12.3, cenários 7-10              |
| D6             | "aceito"                                                                                                           | 13.3                                                                               |
| D15            | "opção A; remover, se fizer sentido voltar, alteramos"                                                             | 11.1                                                                               |
| D16            | "opção A"                                                                                                          | 11.1                                                                               |
| D17            | "pergunte, a menos que o usuário diga explicitamente para apenas registrar"                                        | 7, 8, 8.1, cenários 25-26                                                          |
| D18            | "permite, se faz sentido e está dentro do escopo da tarefa"                                                        | 10.6, 12.3, cenários 22-23                                                         |
| D19            | "sim"                                                                                                              | `specker`                                                                          |
| D20            | "faz sentido manter? TDD: o teste não pode falhar só porque a implementação real não existe"                       | 12.4 (resposta) e D20 reformulada                                                  |

## Apêndice C: comentários da rodada 3 e onde foram tratados

| Decisão | Comentário | Tratado em |
|---|---|---|
| D20 | "aceito a recomendação" | 12.2, 12.4 (`implement --tdd`), etapa F, cenário 36 |
| D21 | "opção B e C; alguns projetos já têm a estrutura antiga, migrar mesmo que aos poucos eleva tempo e custo que não fazem sentido no momento" | 6.1.1, 11.4, etapa B, cenários 32-35 |

---

## Registro de execução

### Etapa A - 2026-11-10 (concluída)

**Arquivos (em `~/dotfiles/.claude/`):**

| Arquivo | Mudança |
|---|---|
| `skills/implementer-contract/SKILL.md` | **novo**: contrato comum dos stack agents (entrada, escopo e `scope_requests`, checks estreitos, validação em runtime por request + logs, política de UI, `out_of_scope_issues`, report YAML) |
| `agents/backend-{node,go,python,rust,spring}.md`, `agents/frontend-react.md`, `agents/mobile-react-native.md` | pré-carregam `implementer-contract`; ficam só com regras da stack; sem seção Docs, sem suite completa, sem subir serviço, sem browser/simulador, sem gravar backlog; propagam `X-Request-Id` nos logs (backends) |
| `agents/test-runner.md` | dono único do gate; escopo `task`/`full`; lê a tabela `Test suites`; suites `on-demand` só quando nomeadas; report YAML |
| `agents/quality-fixer.md` | sem suite completa no fim (re-gate é do `test-runner`); escopo de escrita; reporta em vez de gravar backlog; report YAML |
| `agents/test-writer.md` | uso restrito (pedido, legado, report sem testes); só arquivos de teste; reporta em vez de gravar backlog; report YAML |
| `agents/code-reviewer.md`, `agents/security-reviewer.md` | report YAML; o code-reviewer lê spec e log da feature |
| `CLAUDE.md` | commits só com autorização; protocolo de escopo; runtime local; bug repro por request + logs; UI validada pelo usuário; backlog gravado uma vez pela sessão principal; checks estreitos; docs uma vez no fim |
| `settings.json` | allow para `~/.claude/**` e `~/dotfiles/.claude/**` (Read e Edit); allow dos comandos Docker de leitura; deny dos de ciclo de vida e `exec`/`run` |
| `skills/implement/SKILL.md` | **ponte até a etapa C**: repassa `allowed_paths`, decisões e premissas; trata `scope_requests` (uma pergunta, retoma o mesmo agent); um gate `full` no fim; checklist "Para validar localmente"; grava `out_of_scope_issues` uma vez; lista `needs_docs` para o passe de documentação |
| `skills/bug-repro/SKILL.md` | repro por request + logs (backend) ou passos confirmados pelo usuário (UI); sem prints |
| `README.md` | documenta o contrato, as regras novas e as permissões |

**Decisões tomadas durante a execução:**
- A ponte no `implement` foi antecipada da etapa C: sem ela, `scope_requests`, `manual_checks`, `needs_docs` e `out_of_scope_issues` reportados pelos agents seriam descartados até lá.
- Até existirem `backlog-keeper` (etapa C) e `docs-writer` (etapa E), quem grava backlog e faz o passe de docs é a sessão principal, uma única vez.
- `docker build`/`docker compose build` ficaram fora de allow e de deny (seguem o fluxo normal de permissão); a condição "task altera Dockerfile" está na instrução.
- `security-reviewer` ainda não pré-carrega `dep-audit`: a skill continua `off` até a etapa F.

**Pendências conhecidas:**
- As regras de permissão casam por prefixo; formas como `docker compose -f x.yml up` ou com prefixo `rtk` não são pegas. A garantia mecânica fica para o hook (etapas D e G).
- Mudanças em agents e skills valem a partir de uma sessão nova do Claude Code.
- Validação em uso real: cenários 1-10, 13 e 16-19 da seção 14.3, na etapa D.

### Etapa B - 2026-11-10 (concluída)

**Arquivos (em `~/dotfiles/.claude/`):**

| Arquivo | Mudança |
|---|---|
| `templates/docs-structure/features/README.md` | **novo**: Index único (feature, status do plan, status da spec, atualização) e regras de dono de cada arquivo |
| `templates/docs-structure/features/_template/plan.md` | movido de `plans/TEMPLATE.md`; aponta para `spec.md` |
| `templates/docs-structure/features/_template/spec.md` | movido de `specs/TEMPLATE.md`; tasks estruturadas (Stack, Files, Depends on, Done when, Status); links para plan e log; Testing e Verification referenciam suites pelo nome |
| `templates/docs-structure/features/_template/log.md` | **novo**: log de implementação, escrito só pelo `/implement` |
| `templates/docs-structure/plans/`, `specs/` | **removidos** (projetos legados continuam com as cópias locais) |
| `templates/docs-structure/backlog/bugs/TEMPLATE.md` | campos `Source`, `Related` e seção `Evidence` |
| `templates/docs-structure/backlog/refactor/README.md`, `concepts/README.md` | referências para `features/` |
| `templates/docs-structure/requests/README.md` | `.http` preferido; usado pelos agents na validação em runtime; sem credenciais reais |
| `templates/project-root/CLAUDE.md` | seções `Local runtime` (substitui `Running locally`), `Test suites` (substitui `Testing`) e `Workflow` (substitui `Docs`, com `docs layout: features`); `TASKS.md` removido das referências |
| `templates/project-root/TASKS.md` | **removido** (D15) |
| `templates/project-root/OPEN_QUESTIONS.md` | só perguntas de nível de projeto (D16) |
| `templates/project-root/PRD.md`, `STRUCTURE.md` | `docs/features/`; sem `TASKS.md`; o root `CLAUDE.md` descrito como contrato com os agents |
| `templates/project-root/gitignore.template` | `.claude/runs/` |
| `skills/project-docs/SKILL.md` | reescrita: única fonte do layout (detecção, oferta única de migração, mapa de caminhos), modos `scaffold`, `resolve`, `add entry` e `migrate` |
| `skills/new-project/SKILL.md` | não copia `TASKS.md`; novo passo 7 preenche `Local runtime` (reload `auto` só com bind mount + watch) e `Test suites` |
| `skills/onboard/SKILL.md` | novo passo 7 gera `Local runtime`, `Test suites` e `Workflow` a partir do repo, com confirmação do usuário |
| `agents/planner.md` | **ponte até a etapa C**: caminhos via `project-docs`, oferta única de migração, tasks estruturadas sempre, Verification por nome de suite |
| `skills/implement/SKILL.md` | **ponte até a etapa C**: caminhos via `project-docs`, `allowed_paths` a partir de `Files`, `Status: done`, escreve `log.md`, status `In progress` |
| `README.md` | templates como contrato; workflow com `docs/features/`; regra `ask` dos settings |
| `settings.json` | regra `ask` para `settings*.json` (alerta de segurança: um agent poderia reescrever as próprias permissões) |

**Decisões tomadas durante a execução:**
- Nomes legados corrigidos no mapa (6.1.1): `-plan.md` e `-design.md`, como o `project-docs` já usava; o log legado fica em `<spec>-design.log.md`.
- O `implement` passou a escrever o `log.md` já na etapa B, porque o template de spec aponta para ele; a etapa C mantém o estado do run (`.claude/runs/`), a auto-invocação, o `specker` e o `backlog-keeper`.
- O `planner` ganhou permissão de escrever só a linha `docs layout` do `CLAUDE.md` do projeto, necessária para registrar a recusa da migração.
- `migrate` usa `mv`, não `git mv`, para não mexer no index do git do usuário.

**Pendências conhecidas:**
- `planner` ainda escreve plan e spec; a separação para o `specker` é da etapa C.
- Os `CLAUDE.md` de serviço dos templates de stack (`node-ts-react`, `react-native`) mantêm a seção `Testing` própria do serviço; a tabela `Test suites` do root é a fonte do gate.

### Etapa C - 2026-11-10 (concluída)

**Arquivos (em `~/dotfiles/.claude/`):**

| Arquivo | Mudança |
|---|---|
| `agents/specker.md` | **novo**: dono único das specs (a partir do plan aprovado ou de uma entrada de refactor); tasks estruturadas; `Files` como `allowed_paths` com guia de largura; aprova um plan `Draft` ao ser chamado; nunca edita `docs/backlog/` (reporta `backlog_updates`); report YAML |
| `agents/backlog-keeper.md` | **novo**: escritor único de `docs/backlog/`; modos user report, run batch e update; deduplica contra o Index (e entre issues do mesmo lote); no máximo uma pergunta (via `needs_input`); `offer_fix` para o "quer corrigir agora?"; sonnet, effort baixo |
| `agents/planner.md` | só escreve o plan; perguntas e a oferta de migração voltam como `needs_input`; nunca muda o plan para `Approved`; report YAML |
| `skills/implement/SKILL.md` | auto-invocável (gatilhos em PT e EN); resolução da spec em 3 passos sem chute; pré-condições (plan `Approved`; spec `Draft` por frase pede confirmação, por `/implement` vale como aprovação); estado do run em `.claude/runs/<slug>.json` com retomada, orçamentos e `approved_scope`; pedidos de escopo de agents em paralelo numa só pergunta; backlog via `backlog-keeper` em uma chamada |
| `CLAUDE.md` (global) | seção **Workflow** com a tabela de roteamento por frase, fase, dono e pré-condição; regra geral de `needs_input` / `scope_requests` (a sessão principal pergunta e retoma o mesmo agent); backlog só via `backlog-keeper` |
| `agents/quality-fixer.md`, `agents/test-writer.md` | issues fora de escopo vão para o `backlog-keeper` |
| `skills/project-docs/SKILL.md` | um escritor por tipo de documento; oferta de migração também para `specker`, via `needs_input` em subagents |
| `templates/docs-structure/features/README.md`, `templates/project-root/CLAUDE.md`, `STRUCTURE.md` | `planner` escreve plan, `specker` escreve spec, `backlog-keeper` escreve backlog |
| `templates/docs-structure/backlog/bugs/README.md` | escrito só pelo `backlog-keeper`; bug relatado pelo usuário é registrado com os passos observados e reproduzido pelo fluxo de correção |
| `README.md` | tabela de agents, roteamento por frase, `needs_input`, workflow com frases |

**Decisões tomadas durante a execução:**
- Subagents não conseguem perguntar ao usuário. Toda pergunta de `planner`, `specker` e `backlog-keeper` (inclusive a oferta única de migração) volta como `result: needs_input`; a sessão principal pergunta e retoma o mesmo agent com `SendMessage`. Isso virou regra geral no `CLAUDE.md` global.
- O `specker` não edita a entrada de refactor de origem: reporta `backlog_updates`, e a sessão principal repassa ao `backlog-keeper` (escritor único).
- Uma spec `Draft` aprovada por `/implement` explícito continua valendo como aprovação; por frase, pede confirmação (cenário 2).
- `.claude/runs/` fora do git: o `implement` verifica com `git check-ignore` e pergunta uma vez antes de mexer no `.gitignore`.
- A linha de Discover no Workflow não cita `grill-me` nem `pr-description`, que continuam `off` até a etapa F; a linha de correção de bug descreve o fluxo com `bug-repro` até existir o `fix-bug` (etapa F).

**Pendências conhecidas:**
- `specker` e `backlog-keeper` só ficam disponíveis numa sessão nova do Claude Code; o teste de fumaça feito nesta sessão falhou por isso ("Agent type 'backlog-keeper' not found"), não por erro de definição.
- Validação em uso real: cenários 1-3, 6-9, 25-27 e 29-30 da seção 14.3, na etapa D.

### Etapa D - 2026-11-10 (concluída, baseline pendente)

**Arquivos (em `~/dotfiles/.claude/`):**

| Arquivo | Mudança |
|---|---|
| `hooks/agent-audit.py` | **novo**: hook de auditoria, assíncrono, nunca bloqueia. Grava um JSONL por sessão em `~/.claude/metrics/`. Classifica comandos Bash (testes narrow/package/full/load, lint, typecheck, docker read/build/lifecycle, git commit/push, requests locais/externas), confere escritas contra `allowed_paths` + `approved_scope` do run ativo, marca cada evento com o run, e sinaliza as violações das seções 13 e 14 |
| `hooks/agent-audit.json` | modo `audit` (alternativas: `off`; `block` reservado para a etapa G) |
| `hooks/agent-metrics.py` | **novo**: relatório por sessão, por período ou por run (`--run <slug>`): chamadas e duração por agent, ações por categoria e ator, gates do `test-runner`, escritas fora de escopo e todas as flags com exemplos |
| `settings.json` | hooks em `PostToolUse` e `PostToolUseFailure` (Bash, Write, Edit, MultiEdit, NotebookEdit, `mcp__.*`), `SubagentStart` e `SubagentStop` |
| `~/.claude/hooks` | link para `~/dotfiles/.claude/hooks` (criado à mão, como `agents/` e `skills/`) |
| `agents/backlog-keeper.md` | regra de "falta o essencial" apertada depois do teste de fumaça (ver abaixo) |
| `README.md` | seção `hooks/` |

**Validação feita nesta sessão:**
- Classificador: 31 comandos sintéticos (testes por runner e escopo, prefixos `rtk`/`npx`/`pnpm exec`, `docker compose -f x.yml up`, git, curl local e externo), todos corretos.
- Ponta a ponta pelo stdin, com repo git temporário e run ativo: escrita dentro do escopo, escrita em `approved_scope`, `NOTES.md` fora de `docs/`, implementer editando spec, suite rodada por implementer, `docker compose restart`, ferramenta de screenshot, leitura (ignorada) e entrada inválida (exit 0, nada gravado).
- Ao vivo nesta sessão: o hook disparou em comandos da sessão principal, em `SubagentStart`/`SubagentStop` e num Bash executado dentro de um subagent, que foi atribuído ao agent certo (o payload traz `agent_type` e `agent_id` também nos eventos de ferramenta de subagents).
- Teste de fumaça do `backlog-keeper`: cumpriu o contrato (YAML, sem gravar sem `docs/backlog/`), mas pediu um detalhe quando o relato já tinha onde, o que foi feito e o que aconteceu. A regra passou a exigir só esses três elementos.

**Decisões tomadas durante a execução:**
- Três níveis de teste em vez de dois: `test-narrow` (arquivo ou nome de teste), `test-package` (um serviço, o gate de task) e `test-full` (repo inteiro). Implementer rodando `package` ou `full` gera `suite_by_non_runner`.
- O classificador normaliza `docker compose -f x.yml up` e o prefixo `rtk`, cobrindo a lacuna das regras de permissão por prefixo (pelo menos na auditoria).
- Hooks assíncronos: auditoria não adiciona latência às ferramentas.
- Nada de conteúdo de arquivo ou saída de comando nas métricas: só linha de comando truncada (300 caracteres) e caminhos.

**Pendências:**
- Baseline: rodar os cenários 1-10 da seção 14.3 num projeto real, na sessão de validação, e guardar o relatório (`agent-metrics.py --run <slug>`).
- Métricas de tokens por task não vêm do hook (o payload não traz uso de tokens); ficam para o Briareu ou para a leitura do transcript.
