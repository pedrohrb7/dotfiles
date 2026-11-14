# Proposta: workflow de agents por fase de execução

- **Data**: 2026-11-10
- **Revisão**: 3 (incorpora os comentários das rodadas 1 e 2; ver Apêndices A e B)
- **Status**: Aprovado (rodada 3 fechada em 2026-11-10); pronto para a etapa A
- **Adendo 2026-11-11**: etapa H, agent `design-director` (D22), **Status: Implemented** (aprovada e implementada em 2026-11-11); ver 15.1. As linhas marcadas "(etapa H)" nas outras seções valem a partir desta aprovação; spec em `~/dotfiles/.claude/docs/features/design-director/spec.md`
- **Adendo 2026-11-12**: etapa I, agent `lua` (D23), **Status: Implemented** (aprovada e implementada em 2026-11-13); ver 15.2. As linhas marcadas "(etapa I)" nas outras seções valem a partir desta aprovação; spec em `~/dotfiles/.claude/docs/features/lua-agent/spec.md`
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
| Criar `DESIGN_SYSTEM.md` (direção visual do zero; etapa H) | `design-director`, depois de um sim do usuário | só quando o arquivo falta ou a seção `Principles` está vazia; ninguém mais cria (15.1) |
| Manter `DESIGN_SYSTEM.md` (valores novos, ajustes e extração de tokens já existentes em código; etapa H) | sessão principal, seguindo a skill `design-system` | stack agents só propõem valores em `scope_requests`; `docs-writer` não toca |
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
| `design-director` (etapa H)             | `DESIGN_SYSTEM.md` na raiz do projeto                                            | código, config, fontes, assets, qualquer outro doc                                           |
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

*Adendo 2026-11-13:* os caminhos desta subseção são relativos à raiz de docs resolvida, `<docs>/` (linha `- docs root:` da `## Workflow`, padrão `docs/`; ver 13.5).

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
  "current_task": 3,
  "running_tasks": [3],
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
- **alimentar o hook** (seção 13), que lê `allowed_paths`, `approved_scope`, `current_task` e `running_tasks` daqui;
- **auditar** cada autorização de escopo dada pelo usuário;
- **observar**: o Briareu, ao usar a config, pode ler o mesmo arquivo, mas a config não depende disso.

`running_tasks` lista as tasks com agents rodando agora: o `implement` a define antes de um lote paralelo, remove a task quando a marca como `done` (uma task bloqueada continua listada) e, na rodada de correção do review, a define com as tasks que recebem correções. `current_task` continua sendo a primeira do lote. O `fix-bug` não usa `running_tasks`: os runs de bug são sequenciais e ficam só com `current_task` escalar.

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
| "cria a identidade visual", "define o design do zero", "vamos criar o frontend do zero" (etapa H) | Direção visual (`design-director`) | `DESIGN_SYSTEM.md` ausente ou com `Principles` vazia, e sem UI com tokens próprios em código; senão, é manutenção (ou extração dos tokens existentes) pela skill `design-system` |
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
| **Projeto novo**        | skill `new-project` -> (com serviço de UI e um sim do usuário, etapa H) `design-director` -> Descobrir -> Planejar ...                                                                                                                                    |
| **Direção visual do zero** (etapa H) | `design-director`: briefing (só se faltar o básico) -> duas direções contrastantes -> escolha do usuário -> `DESIGN_SYSTEM.md`. Levar os tokens ao código vira tasks de spec normais (15.1) |

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
| `design-director`   | **novo** (etapa H, implementada) | cria a direção visual de um projeto sem frontend definido e escreve só `DESIGN_SYSTEM.md`, em rodadas via `needs_input` (15.1); opus, effort alto; pré-carrega `design-system`; sem `Bash` |

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
| `DESIGN_SYSTEM.md`                | todo                                                                                            | `new-project` (só copia o esqueleto); etapa H: `design-director` (criação), sessão principal com a skill `design-system` (manutenção) | `frontend-react`, `mobile-react-native`, `code-reviewer`  |
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
| `design-director` (etapa H)             | `design-system` (o know-how de direção fica no corpo do agent, não na skill) |
| `lua` (etapa I)                         | `implementer-contract`, `design-system`, `neovim-plugin`, `lua-tui` (o know-how de Neovim e de TUI fica nas skills, não no corpo do agent) |
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
| `design-system`                                       | ativar           | lê e escreve `DESIGN_SYSTEM.md`; pré-carregada pelos agents de UI; reavaliar depois. Etapa H: fica só com a **manutenção** (a criação passa ao `design-director`), também é pré-carregada pelo `design-director` e perde a referência ao plugin `frontend-design` |
| `pr-description`                                      | ativar           | fase Entregar                                                                                                                                           |
| `neovim-plugin` (etapa I)                             | **nova**         | know-how de plugin Neovim (API, autocmds, setup e lazy-loading, `:checkhealth`, `vim.validate`, testes headless, janelas e buffers como UI); pré-carregada pelo `lua`, usável sozinha |
| `lua-tui` (etapa I)                                   | **nova**         | know-how de UI dentro do Neovim e de TUI de terminal (raw mode, alternate screen, `luv`, `SIGWINCH`, ANSI); pré-carregada pelo `lua`, usável sozinha |
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
  - caminho escrito x `allowed_paths` de qualquer task em execução (`running_tasks`, mais a `current_task`) + `approved_scope` aprovado dessas tasks + uma lista sempre permitida (lockfiles, diretórios de migration, snapshots de teste, arquivos gerados por ferramenta);
  - comando Bash x mapa de comandos Docker (10.6) e regras de commit (4.1).
- *Adendo 2026-11-13 (feature `audit-hook-hardening`):* a análise de Bash, escritas de arquivo e tools de browser roda num **processo filho** (`fork` + `socketpair`) com prazo duro; o pai só decide, imprime e grava. O filho responde em duas linhas JSON (análise, depois as tags do run), lidas com teto de 1 MiB; no `PreToolUse` ele espera um byte de "go" do pai antes de marcar o run. É líder do próprio grupo de processos: o pai o encerra com `killpg(SIGKILL)` (alcança os `git` netos) e um alarme de autodestruição o encerra se o pai falhar. Sem resposta no prazo: `analysis_timeout`; filho morto ou resposta inválida: `unclassified_command` (motivo `analysis_crash`). Se `fork` ou `socketpair` falham, vale o `SIGALRM` em processo. Toda leitura e gravação de arquivo do hook é limitada (config, run states, métricas) e o processo termina com `os._exit(0)` depois de descarregar a saída. Detalhes em 13.8 e no `README.md` dos hooks.

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
4. **Etapa H** (implementada, 15.1, 13.5): categoria nova `design_system_write_by_other` em `warn` (escrita em um `DESIGN_SYSTEM.md` por quem não é `design-director` nem a sessão principal) e categoria nova `design_director_write_outside` em `block` (qualquer escrita do `design-director` que não seja um `DESIGN_SYSTEM.md`); o `design-director` fica isento de `md_outside_docs` só para esse arquivo. A promoção da `design_system_write_by_other` a `block` segue a mesma regra dos dados.

*Adendo 2026-11-13 (feature `audit-md-outside-docs`):* o falso positivo S5 do `md_outside_docs` está resolvido (ver 13.5, 13.7 e a spec da feature) e a flag está pronta para a análise de promoção a `block` do item 3. A promoção segue como decisão posterior, que exige dados de uso real.

*Adendo 2026-11-13 (feature `audit-hook-hardening`):* o corpo de um heredoc só é dado se o **prefixo estiver limpo**: o texto antes do sink tem uma única leitura, sem fallback do shlex e, para `git`/`gh`, sem `$` (para `cat`/`tee`, `$` depois da cabeça é aceito, então `cat > $SP/x.sh <<EOF` continua sink); no `$(cat <<EOF)` o texto externo não pode ter `$`. Fora disso o corpo é classificado como comandos e, havendo leitura `cat`/`tee`/`git`/`gh`, o motivo `heredoc_unclean_prefix` (nível A, 13.8) é registrado. Ver 13.8.

*Adendo 2026-11-13 (etapa I, feature `lua-agent`):* duas categorias novas nascem direto em `block`, por serem guardas do próprio classificador e não regras de fluxo: `command_too_long` e `analysis_timeout` (13.6, adendo; 15.2, adendo). Aprovadas pelo usuário durante a revisão.

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

### 13.5 Regras do hook da etapa H (`DESIGN_SYSTEM.md` e `docs_roots`)

**`DESIGN_SYSTEM.md` por nome.** A regra vale para qualquer caminho cujo nome de arquivo, sem diferenciar maiúsculas (`casefold`), seja `design_system.md`, em qualquer diretório do repositório (cobre `apps/web/` num monorepo e sistemas de arquivos que ignoram caixa). A redação antiga, só o arquivo da raiz, está obsoleta. Consequência aceita: `templates/**/DESIGN_SYSTEM.md` também é protegido (stack agents recebem aviso, o `design-director` pode escrever, a sessão principal é livre).

| Quem escreve | Resultado |
|---|---|
| `design-director` em um `DESIGN_SYSTEM.md` | silencioso (isento de `md_outside_docs` só para esse nome) |
| `design-director` em qualquer outro arquivo | `design_director_write_outside` (`block`), também sem raiz git |
| sessão principal | silencioso |
| qualquer outro ator | `design_system_write_by_other` (`warn`) |

*Adendo 2026-11-13 (feature `audit-md-outside-docs`):* a sessão principal e o `docs-writer` não geram `md_outside_docs` (a linha da sessão principal acima vale também para essa flag; as demais flags deles continuam). A flag só vale para agents, só ao **criar** um `.md` novo dentro do repositório e fora da raiz de docs. Novo vem de `tool_response.type` no Post, ou do alvo ainda não existir no Pre; sem informação, conta como novo; `PostToolUseFailure` nunca conta. A extensão é checada sem diferenciar maiúsculas. `README.md`, `CHANGELOG.md`, `DEPLOY.md` e `CLAUDE.md` são isentos por nome exato, em qualquer caixa; durante um run, caminhos `.md` ou globs terminados em `.md` em `allowed_paths` ou `approved_scope` da task também isentam (um glob amplo como `services/api/**` não). `docs_write_by_implementer` casa os nomes de `DOC_FILES` sem diferenciar maiúsculas. A flag segue em `warn`.

Alvos de `approved_scope` que casam com a regra são descartados dos caminhos permitidos derivados do run: aprovar o pedido não libera a escrita do agent, então o `out_of_scope_write` continua valendo (regra 29).

**`docs_roots`.** Lista em `agent-audit.json` das pastas, relativas à raiz git, que contam como área de docs. Padrão: `["docs/"]`; neste repositório, `["docs/", ".claude/docs/"]`, porque os docs das features da própria config ficam em `.claude/docs/`.

- Normalização de cada entrada: tira espaços, troca `\\` por `/`, remove `./` e `/` iniciais, garante a `/` final e elimina duplicatas. Entradas que não são texto, vazias, `.` ou com `..` são ignoradas.
- Fallback: chave ausente, valor que não é lista ou nenhuma entrada válida -> `["docs/"]`.
- Efeito: `.md` dentro de uma raiz não gera `md_outside_docs`, e `<raiz>backlog/` só é escrito pelo `backlog-keeper` (`backlog_write_by_other`), checado por raiz. A comparação é por prefixo: `services/x/docs/` não é raiz.
- `project-docs` e `/implement` ainda resolvem `docs/` na raiz do repositório; aqui o caminho da feature é passado explicitamente.

*Adendo 2026-11-13 (feature `skills-docs-root`):* a lista `docs_roots` do `agent-audit.json` foi substituída por uma declaração por projeto, `- docs root: <caminho>/` na seção `## Workflow` do `CLAUDE.md` da raiz git (padrão `docs/`; este repositório declara `.claude/docs/`). O hook lê a linha por raiz git (`normalize_docs_root()` e `project_docs_root()`), sem bloquear e só de arquivo regular; valor inválido cai em `docs/` no hook, e as skills param e perguntam. `project-docs` (**Docs root**) resolve a mesma linha, e skills e agents escrevem `<docs>/...`. Por isso a última frase acima ("`project-docs` e `/implement` ainda resolvem `docs/`...") deixou de valer, assim como a lista, a normalização por entrada e o fallback `["docs/"]` descritos nesta seção. Spec em `~/dotfiles/.claude/docs/features/skills-docs-root/spec.md`.

### 13.6 Heredoc no Bash: corpo é dado só para sinks conhecidos

O classificador do `hooks/agent-audit.py` (`strip_heredoc_bodies`) separa o comando em segmentos. Sem tratar heredoc, cada linha do corpo viraria um "comando" (um `docker compose up` dentro de um `git commit -F - <<EOF` seria `docker_lifecycle`). Mas o contrário é pior: tirar o corpo de um `bash <<EOF` esconderia código de verdade. Por isso a regra é **fail-closed**: o corpo só é removido (tratado como dado) para uma lista fechada de sinks; qualquer outro heredoc mantém o corpo, que é classificado como comandos (só a linha do terminador sai).

**Sinks de dados (corpo removido):**

| Sink | Condição |
|---|---|
| `cat` ou `tee` no nível raiz | sem pipe, sem `<(`/`>(` e sem `$(` na linha do abridor |
| `git commit -F -` / `--file -` | sem `-c alias.*` nem `-c core.*` (executam código) |
| `$(cat <<EOF ...)` como valor de `git commit -m` / `--message` | mesma restrição de `-c` |
| `gh pr\|issue\|release create\|edit\|comment\|review` com `--body-file -` / `-F -` | |
| `$(cat <<EOF ...)` como valor de `--body` / `-b` / `--title` / `-t` desses comandos `gh` | |

Todo o resto (`bash`, `sh`, `python3`, `... | bash`, `eval`, `xargs`, `cat <<EOF | sh` etc.) tem o corpo classificado.

**Marcadores de falha segura:** se o comando contém qualquer construção que o scanner não modela, **nada** é removido e o comando inteiro é classificado: `${`, `$'`, `$[`, crase, `\r`, `>(`, `<(`, `mkfifo`, `coproc`, redirecionamento de `exec`, definição de função `cat`/`tee`, redirecionamento para fd >= 3, e quebra de linha dentro de aspas enquanto há heredoc pendente. Um erro do scanner também devolve o comando original.

**Limite declarado:** um script gravado em arquivo por heredoc e executado depois (`cat > x.sh <<EOF ...; bash x.sh`) está fora do alcance do classificador: o corpo é dado no `cat`, e o `bash x.sh` não mostra o conteúdo. É o mesmo limite de `Write` seguido de execução.

**Testes:** `hooks/tests/` (`unittest` da biblioteca padrão), suite `claude-hooks` da tabela `Test suites` do `CLAUDE.md` da raiz do repo: `python3 -I -B -m unittest discover -s .claude/hooks/tests -t .claude/hooks`, a partir de `~/dotfiles` (`-I -B` isola do ambiente e não cria `__pycache__`).

*Adendo 2026-11-13 (etapa I, feature `lua-agent`):* o classificador reconhece comandos Lua (busted, `luarocks test`, `nvim --headless` com plenary ou mini.test, tasks do mise, luacheck, selene, stylua, treefmt) e classifica os shell escapes do Neovim (`-c`, `--cmd`, `+`: `!`, `:!`, `silent !`, `w !`, `r !`) até 3 níveis de aninhamento (além disso, falha fechada: `unclassified_command`, motivo `nested_shell_depth`; a flag `nested_shell_unclassified` deixou de existir, ver 13.8). `strip_prefixes` (hoje `command_readings`, ver 13.8) remove, para toda stack, `timeout [opções] <duração>` (qualquer forma GNU; ilegível, a leitura falha fechada), `mise exec|x [flags] --` e o caminho de `busted`, `luacheck`, `selene`, `stylua` e `nvim`. Duas categorias novas em `block`, para todo ator: `command_too_long` (comando Bash acima de 16384 caracteres) e `analysis_timeout` (guarda de 7 s de relógio; `AGENT_AUDIT_ANALYSIS_TIMEOUT` só em testes, só baixa o limite). Mais de 32 abridores de heredoc (`MAX_HEREDOC_OPENERS`) deixam o comando classificado como comandos, não como dado. A suite `claude-hooks` tem 317 testes. Ver 15.2 (adendo) e a spec da feature `lua-agent`.

> 💬

### 13.7 Escritas fora da raiz git

A raiz que governa uma escrita é a raiz git do `cwd` da sessão (onde mora o run); sem ela, a raiz do próprio alvo. Se o alvo está em outro repositório aninhado nessa raiz (submódulo), as duas raízes julgam e as flags são unidas (vale a mais estrita). O alvo tem `~` expandido e é resolvido; com `..` no caminho, a forma resolvida e a léxica são julgadas.

- **Registro:** um alvo fora de toda raiz grava `area: "outside"` e `rel` igual ao caminho absoluto.
- **Flags de ator** (`write_by_readonly_agent`, `design_director_write_outside`, `design_system_write_by_other`, esta pelo nome bruto ou resolvido) valem para qualquer caminho. **Flags de área** (`md_outside_docs`, `docs_write_by_implementer`, `backlog_write_by_other`) só valem dentro de um repositório.
- **`out_of_scope_write` fora do repositório:** um ator de escopo fixo (implementers, `quality-fixer`, `test-writer`) em um run só escreve fora se o alvo casar com um glob **absoluto** aprovado em `approved_scope`, do diretório canônico (casado literalmente após expandir `~`, sem resolver symlinks: escrever por um alias symlink é sinalizado), ou for scratch (`<tempdir>/claude-*` ou `/tmp/claude-*`). Globs relativos e a lista sempre permitida (`ALWAYS_ALLOWED`, convenções do repositório) nunca cobrem caminhos fora dele. *Adendo 2026-11-12 (feature `audit-scratch-exemption`):* o scratch passou a ser só o scratchpad da sessão, campo `scratchpad_dir` do payload (estritamente dentro dele, comparado como veio, sem resolver); sem o campo, sem isenção. O registro ganha `scratch` (`match`, `no-match`, `unavailable`) e o relatório de métricas separa os quatro casos.
- **`md_outside_docs` (adendo 2026-11-13, feature `audit-md-outside-docs`):** não vale para a sessão principal nem para o `docs-writer`; para agents segue a regra acima (só `.md` novo, dentro do repositório e fora da raiz de docs, com as isenções de 13.5).
- **Falha fechada:** caminho que não resolve mantém as flags de ator e, para ator de escopo fixo com run ativo (ou run que não dá para determinar), soma `out_of_scope_write`.

### 13.8 Incerteza do parser: fail closed

*Adendo 2026-11-13 (feature `audit-hook-hardening`).* Quando o classificador não tem certeza do que um comando é, ele nunca escolhe a leitura mais branda. Dois níveis:

- **Nível A (registrar e classificar):** toda leitura possível é classificada e vale a mais estrita (`command_readings`, que substituiu `strip_prefixes`: `timeout`, `mise exec` e o resto são passos de prefixo por posição). O registro ganha `uncertainty` (lista de motivos) e a flag de auditoria `parse_uncertain` (`audit`, não nega). Motivos: `prefix_readings`, `shlex_fallback` (só quando as duas leituras diferem no texto e no que classificam), `heredoc_unclean_prefix` (13.6), `loose_assignment_truncated` (atribuição que abre aspa sem fechar; só registro, porque falhar fechado negou 91 comandos reais no replay), `git_root_unknown` (a raiz git do alvo de uma escrita não foi determinada; ator de escopo fixo recebe `out_of_scope_write`, os demais só registram).
- **Nível B (negar):** o comando não pode ser lido. Categoria `block` `unclassified_command`, para todo ator, com a mensagem de simplificar ou dividir o comando. Motivos: `readings_cap` (mais de 8 inícios de comando distintos numa peça), `nested_shell_depth` (texto de shell do nvim além de 3 níveis), `classifier_error` (o classificador lançou; o registro guarda `error` com o nome da exceção, nunca a mensagem) e `analysis_crash` (o filho do watchdog morreu ou mandou resposta inválida, 13.1).
- **Canário:** `deny_token_unmatched` (só registro) marca um token de container ou git fora de posição de comando seguido de verbo de lifecycle, push ou commit sem flag correspondente. Não nega; mostra a próxima forma que escapa.

Registro: `uncertainty`, `error` e `run_tags` (`"timeout"` quando a marcação do run perdeu o prazo; o registro é gravado mesmo assim, com `in_run: false`). Atribuições `NOME=valor` e `NOME+=valor` antes do comando são puladas, com valor entre aspas. Lacunas conhecidas, para a spec `audit-shell-lexer`: expansões sem aspas com espaço no valor (`A=$(echo a b)`), separador entre aspas no valor (`A="x;y" ...`), `&`, subshells, `if`/`for`, `$(...)`, crases, `bash -c`, `eval`, `sudo -u`, `nohup`, `xargs`, `watch`.

**Válvula de emergência:** se uma regra bloquear trabalho normal antes da correção, `"mode": "audit"` no `agent-audit.json` (só registra; a suite acusa no `test_config_contract.py`, de propósito) ou reverter a task.

---

## 14. Observabilidade

### 14.1 Coleta

O mesmo hook da seção 13 grava um JSONL por sessão (por exemplo em `~/.claude/metrics/`):

- `SubagentStop`: agent, duração e resultado.
- `PostToolUse` em `Bash`: comando, classificado como `lint | typecheck | test-narrow | test-gate-task | test-gate-full | docker-read | docker-build | docker-lifecycle | git | other`.
- `PostToolUse` em `Write|Edit`: caminho e se está dentro de `allowed_paths` ou `approved_scope`.
- `PostToolUse` nas tools de browser e screenshot: quem chamou. Fora de pedido explícito, o esperado é zero.
- Etapa H: o relatório do `agent-metrics.py` ganha a seção `## design-director`, só quando a sessão tem um `SubagentStart` ou algum evento desse ator. Traz as chamadas, as escritas fora de um `DESIGN_SYSTEM.md` (alvo 0, até 5 exemplos com horário e caminho) e uma linha lembrando de conferir à mão, no transcript, as chamadas sem um sim prévio do usuário (o hook não vê a conversa; alvo 0). Os rótulos das categorias `design_system_write_by_other` e `design_director_write_outside` entram na lista de flags. Sem eventos do `design-director`, o relatório fica idêntico ao anterior.

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
| Escritas em `DESIGN_SYSTEM.md` fora do `design-director` e da sessão principal (etapa H) | não medido | 0 |
| Chamadas do `design-director` sem um sim do usuário antes (etapa H) | não existe | 0 |
| Neovim interativo, app TUI ou app hospedeiro (wezterm, awesome, hammerspoon) aberto ou recarregado por agents (etapa I) | não existe | 0 |

*Adendo 2026-11-13 (feature `audit-hook-hardening`): incerteza do parser.* O relatório do `agent-metrics.py` ganha a seção "Parser uncertainty and hook health", depois de "Enforcement decisions": tabela por motivo (registros, negados, perguntados, até 3 exemplos), **candidatos a falso positivo** (decisões block/ask com motivo de nível A e toda negação `unclassified_command`), **candidatos a falso negativo** (registros `deny_token_unmatched` sem decisão) e **saúde do hook** (`analysis_timeout`, `analysis_crash`, `classifier_error`, `run_tags: "timeout"`). Sem nada no período, diz "None.". Procedimento de ajuste:

1. Antes do merge, a sessão principal reexecuta os comandos Bash das métricas locais nas duas versões do classificador; cada diferença é mudança pretendida ou defeito.
2. Depois de cerca de uma semana nas duas máquinas: `agent-metrics.py --since <data do merge> --merge` e ler a seção.
3. Falso positivo (trabalho legítimo bloqueado): a correção é uma regra de parse precisa para aquela forma (teste primeiro, entrada no backlog pelo `backlog-keeper`); nunca remover o fail-closed nem subir um teto às cegas (`MAX_READINGS` e `NVIM_MAX_DEPTH` são fixados por teste).
4. Falso negativo: uma forma que escapou; vira entrada para a spec do lexer.
5. Metas: zero negação de trabalho normal; `analysis_timeout`, `analysis_crash` e `classifier_error` em zero.
6. Válvula de emergência: ver 13.8.

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
| 37 | Etapa H: "cria a identidade visual", projeto sem `DESIGN_SYSTEM.md` e `PRD.md` completo | `design-director` rodada 2 -> `needs_input` -> escolha -> rodada 3 | duas direções contrastantes, cada uma revisada contra a lista de padrões; arquivo com todas as tabelas, light e dark, `Layout concept`, fontes de licença aberta com origem registrada, razões de contraste AA no report; nenhum outro arquivo escrito |
| 38 | Etapa H: mesma frase, `PRD.md` sem público | rodada 1 | só as perguntas do básico; nenhuma direção proposta |
| 39 | Etapa H: mesma frase, `Principles` preenchida | `design-director` não escreve | `result: blocked`; arquivo intocado; aponta a `design-system` |
| 40 | Etapa H: usuário recusa as duas direções | nova rodada 2 | duas direções novas que levam em conta a recusa; nada escrito |
| 41 | Etapa H: `new-project` com serviço web, usuário diz sim / não | sim: `design-director`; não: tabelas em branco | nenhuma chamada sem a resposta; no "não", nenhuma pergunta repetida no `new-project` |
| 42 | Etapa H: task de UI do `implement` sem `DESIGN_SYSTEM.md` | `frontend-react` blocked + `scope_requests` -> pergunta -> `design-director` só depois do sim | nenhum token inventado; nenhuma chamada automática; recusa = pedido negado (13.4) |
| 43 | Etapa H: stack agent edita `DESIGN_SYSTEM.md` | hook `warn` (`design_system_write_by_other`) | o valor vai para `scope_requests`; a sessão principal aplica depois do sim |
| 44 | Etapa H: monorepo com web e mobile | um só `DESIGN_SYSTEM.md` na raiz | uma direção para as duas plataformas; wireframe por plataforma na rodada 2 |
| 45 | Etapa H: "cria a identidade visual" num projeto com UI e tokens próprios em código, sem `DESIGN_SYSTEM.md` | sessão principal segue para a extração com a `design-system` | `design-director` não roda (ou termina `blocked`); os tokens documentados são os do código, sem direção nova |
| 46 | Etapa I: task de um plugin Neovim (`lua/` + `plugin/`, busted, luacheck), spec com `Stack: lua` | implement -> `lua` -> test-runner (task) -> ... | só checks estreitos (arquivo de teste, lint dos arquivos tocados); runtime e versão detectados em `notes`; nenhum `nvim` sem `--headless` no registro do hook |
| 47 | Etapa I: task de janela flutuante no plugin | `lua` | highlights com link a grupo padrão, sem cor fixa; layout refeito em `VimResized`; `manual_checks` com o comando de abertura, redimensionamento, janela pequena demais, tema claro e escuro e cada estado |
| 48 | Etapa I: task de TUI de terminal standalone | `lua` | raw mode e alternate screen restaurados na saída normal, no erro e em Ctrl-C (lido no código e coberto por teste quando o projeto tem framework); `SIGWINCH` tratado; sem `DESIGN_SYSTEM.md`, só cores ANSI nomeadas e atributos, sem pedido de escopo; nenhuma dependência nova; o app não foi executado; `manual_checks` inclui "Ctrl-C e erro deixam o terminal normal" |
| 49 | Etapa I: `test-runner` num projeto Lua sem `## Test suites` | detecção (prompt, CI, tasks do mise, Makefile/justfile, padrões Lua) | busted ou `nvim --headless` com plenary/mini.test e o `minimal_init` do projeto; lint luacheck/selene; sem `minimal_init`: `blocked` com o motivo, nada criado |
| 50 | Etapa I: repo com serviço Go e gateway OpenResty | `specker` -> tasks separadas por stack -> implement | cada task com um stack só; a de Lua vai ao `lua`, a de Go ao `backend-go`; a task OpenResty faz a validação por request + logs (contract, seção 4) |
| 51 | Etapa I: repo de config do Neovim (`init.lua` + `lua/`, sem testes) | `lua` | nenhuma convenção de plugin imposta (`setup`, `health.lua`, `<Plug>`); nenhum framework de teste adicionado sem pedido de escopo; `manual_checks` com o que conferir |
| 52 | Etapa I: config embarcada (wezterm, hammerspoon ou awesome) | `lua` | API do hospedeiro respeitada; o hospedeiro não foi executado nem recarregado; `manual_checks` com "recarregar `<app>`" e o resultado esperado |
| 53 | Etapa I: projeto preso à semântica do Lua 5.1 (`std = lua51`, rockspec `lua >= 5.1, < 5.2`) | `lua` | nenhuma construção acima de 5.1 (`//`, operadores bit a bit nativos, `utf8`, `<const>`/`<close>`, `goto` em PUC 5.1) |
| 54 | Etapa I: `onboard` num plugin Neovim sem pastas de serviço | `onboard` | projeto reconhecido como Lua; `LUA.md` na raiz com todas as seções; `Test suites` e `Workflow` propostos ao usuário e escritos só depois do sim; sem `Local runtime` |
| 55 | Etapa I: hook com o ator `lua` | stdin + suite `claude-hooks` | `lua` em `IMPLEMENTERS` e no conjunto literal de E9; regras de implementer valem para ele; `busted` e `mise run test` sinalizados como `suite_by_non_runner`, `busted tests/x_spec.lua` não; luacheck, selene e stylua como lint |

> 💬

---

## 15. Plano de execução

A ordem A -> G foi aprovada. As decisões da rodada 2 entram nas etapas já existentes, sem etapa nova. A etapa H (adendo de 2026-11-11, implementada) vem depois da G e não muda as anteriores (15.1). A etapa I (adendo de 2026-11-12, implementada) vem depois da H e também não muda as anteriores (15.2).

| Etapa | Conteúdo                                                                                                                                                                                                                                                                                     | Ataca                                                               |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **A** | `implementer-contract` (com o protocolo de escopo, 13.4) + report YAML + ajustes dos 7 stack agents, `test-runner`, `quality-fixer`, `test-writer` e reviewers (remover Docs, suite completa, validação visual e "start the service") + CLAUDE.md global (seção 12.3) + allow/deny de Docker | duplicação, reescritas, arquivos indevidos, prints, runtime, escopo |
| **B** | Templates como contrato (seção 11): `docs/features/`, remoção do `TASKS.md`, escopo do `OPEN_QUESTIONS.md`, `Local runtime`, `Test suites`, spec estruturada + `project-docs` (com detecção de layout, mapa de caminhos e `migrate`), `new-project` e `onboard`                                                                     | contexto, contrato entre agents                                     |
| **C** | `implement` auto-invocável (feature, `log.md`, estado do run, pedidos de escopo) + `specker` (e `planner` só plan) + `backlog-keeper` + seção Workflow                                                                                                                                       | chamada manual, contexto perdido, backlog                           |
| **D** | Hook em modo `audit` + métricas + cenários 1-10 como baseline                                                                                                                                                                                                                                | validação                                                           |
| **E** | `docs-writer` + `ui-verifier`                                                                                                                                                                                                                                                                | fases sem dono                                                      |
| **F** | `fix-bug` + consolidação de skills (seção 12.2), incluindo a `tdd` evoluída e o `implement --tdd` (12.4)                                                                                                                                                                                                           | fluxo de bug, sobreposição                                          |
| **G** | `block` por categoria, com base nos dados da etapa D                                                                                                                                                                                                                                         | garantia mecânica                                                   |
| **H** (implementada) | `design-director` (criação de `DESIGN_SYSTEM.md`) + `design-system` só com a manutenção + pontos de entrada (`new-project`, Workflow, `design-system`) + hook (`design_system_write_by_other`, `design_director_write_outside`, isenção de `md_outside_docs`, `docs_roots`) + remoção do plugin `frontend-design` (15.1) | criação da direção visual sem dono, dependência de fonte externa desligada |
| **I** (implementada) | agent `lua` + skills `neovim-plugin` e `lua-tui` + `Stack: lua` no `implement`, no `specker` e no template de spec + detecção de Lua no `test-runner` e no `onboard` + `lua` no hook (`IMPLEMENTERS` e E9) (15.2) | código Lua (Neovim, TUI, configs embarcadas) sem dono; inferência de stack sem Lua |

Cada etapa termina com os cenários relevantes da seção 14.3 rodados e as métricas comparadas.

### 15.1 Etapa H - `design-director` (adendo 2026-11-11)

- **Status**: Approved (2026-11-11); implementada em 2026-11-11 (Registro de execução)
- **Origem**: grill-me de 2026-11-11 (D22; Apêndice D)
- **Spec**: `~/dotfiles/.claude/docs/features/design-director/spec.md`

#### Objetivo

Um projeto sem frontend definido ganha uma direção visual própria antes da primeira tela: o usuário escolhe entre duas propostas contrastantes, e a escolhida vira um `DESIGN_SYSTEM.md` completo, que os agents de UI já sabem consumir. A config deixa de apontar para uma fonte externa desligada.

| Critério de sucesso | Como medir | Alvo |
|---|---|---|
| Rodada de direções entrega duas propostas completas | cenário 37: paleta de 4-6 hex, tipografias com papéis, wireframe ASCII, princípios e revisão contra a lista de padrões, nas duas | 100% |
| Arquivo final completo | todas as tabelas do template preenchidas (ou "não se aplica" explícito); light e dark sempre; escala de 5-7 passos; `Layout concept` preenchida | 100% |
| Fontes utilizáveis | famílias com licença aberta ou do sistema, com origem e licença registradas no arquivo | 100% |
| Contraste | todo par texto/fundo com razão listada no report, AA nos dois temas | 100% dos pares |
| Escrita restrita | escritas do `design-director` fora de um `DESIGN_SYSTEM.md` (hook; seção `## design-director` das métricas) | 0 |
| Nada automático | chamadas do `design-director` sem um sim do usuário antes (14.2) | 0 |
| Um dono por ação | `design_system_write_by_other` no relatório de métricas | 0 |
| Sem fonte externa | `grep -r frontend-design` na config, fora deste documento | 0 ocorrências |

#### Contexto

- Hoje ninguém é dono da **criação** do `DESIGN_SYSTEM.md`. O `new-project` deixa as tabelas em branco "para a `design-system`"; a `design-system` (passo 1) manda estabelecer a direção com o usuário na sessão principal e cita o plugin `frontend-design`, que está `false` em `enabledPlugins`. Na prática, a instrução aponta para algo que não roda, e o resultado tende ao palpite genérico que a própria skill proíbe.
- A `design-system` mistura criação (rara, cara, precisa de escolha do usuário) e manutenção (frequente, pré-carregada em todo agent de UI). Separar segue o princípio 2 (um dono por ação) e tira o know-how de direção do contexto dos implementers.
- Base já existente: protocolo `needs_input` e retomada com `SendMessage` (etapa C), `scope_requests` (13.4), hook em `enforce` (etapa G), template `project-root/DESIGN_SYSTEM.md` (11.1) e a regra global de UI sem prints.

#### Decisões (D22, grill-me de 2026-11-11)

| # | Decisão |
|---|---|
| a | **Sem fonte externa.** O plugin `frontend-design@claude-plugins-official` não é adotado; as referências saem da `design-system`, dos `CLAUDE.md` dos templates `node-ts-react` e `react-native`, do `README.md` e de `enabledPlugins`. Só ideias são reaproveitadas, reescritas com as palavras do usuário: um plano compacto de tokens revisado contra o brief antes de virar valores, e uma lista de padrões genéricos "padrão de IA" a evitar onde o brief deixa o eixo livre. Os passos do plugin "escrever o código" e "tirar prints para criticar" ficam de fora: código passa por spec + implementers, e prints são proibidos para agents (regra global de UI; `visual_tool` bloqueado pelo hook) |
| b | **Agent novo, só criação.** O `design-director` cria a direção visual do zero, só em projetos sem frontend definido. Ele é dono da **criação** do `DESIGN_SYSTEM.md`; a skill `design-system` continua dona da **manutenção** |
| c | **Ciclo em rodadas via `needs_input`**: briefing (só se faltar o básico) -> duas direções contrastantes -> o usuário escolhe, mistura ou pede mudanças -> o agent, retomado com `SendMessage`, preenche o arquivo |
| d | **Três pontos de entrada**, todos só com `DESIGN_SYSTEM.md` ausente ou `Principles` vazia, nenhum automático dentro de uma task: `new-project`, linha nova no Workflow e passo 1 da `design-system` |
| e | **Escopo de escrita**: só `DESIGN_SYSTEM.md` na raiz. Sem código (`theme.ts`, config do Tailwind, carga de fontes, `expo-font`): levar tokens ao código vira tasks de spec para `frontend-react` / `mobile-react-native`. Tools `Read`, `Grep`, `Glob`, `Write`, `Edit`; sem `Bash`. Hook: isenção de `md_outside_docs` para esse arquivo e categoria nova `design_system_write_by_other` em `warn` |
| f | **Definição do agent**: `model: opus`, `effort: high` (política do README: opus onde o erro é caro e os runs são raros); `skills: [design-system]`; o know-how de direção fica no corpo do agent. Description: _"Defines a project's visual direction from scratch and writes DESIGN_SYSTEM.md. Use only when the project has no DESIGN_SYSTEM.md (or its Principles are empty) and the user wants a visual identity created ("cria a identidade visual", "define o design do zero"), or when new-project or design-system hands off to it."_ |
| g | **UI já existente em código, sem `DESIGN_SYSTEM.md`** (resposta de 2026-11-11 à pergunta 1, opção b): fora do escopo do `design-director`; a sessão principal documenta os tokens existentes seguindo a `design-system` (extração, não criação) (regra 33) |
| h | **Conceito de layout, wireframe e padrões evitados** (pergunta 2, opção b): seção nova `Layout concept` no template `project-root/DESIGN_SYSTEM.md`, aprovada pelo usuário (regra 34) |
| i | **Tipografia** (pergunta 3, opção a): só fontes com licença aberta (ex.: SIL OFL) ou do sistema, com a origem registrada no `DESIGN_SYSTEM.md` (regras 12 e 22) |
| j | **`PRD.md` exclui tema escuro** (pergunta 4, opção a): light e dark sempre preenchidos (regra 20) |

#### Escopo

| Dentro | Fora |
|---|---|
| Agent `design-director` e seu ciclo de rodadas | Redesign de projeto com `Principles` preenchida (é manutenção ou um plan próprio) |
| `DESIGN_SYSTEM.md` da raiz, criado a partir do template `project-root` | Qualquer código: tokens no código, fontes, `theme.ts`, Tailwind, `expo-font` (tasks de spec) |
| Pontos de entrada em `new-project`, Workflow e `design-system` | Prints, browser, simulador ou crítica visual por imagem |
| Hook: isenção e categoria nova | Adotar ou copiar o plugin `frontend-design` |
| Remoção das referências ao plugin e da entrada em `enabledPlugins` | Assets de marca (logo, ícones, ilustrações) |
| Cenários 37-45 (14.3) e métricas novas (14.2) | `DESIGN_SYSTEM.md` por serviço (o arquivo é um só, na raiz) |
| Seção nova `Layout concept` e origem das fontes no template `project-root/DESIGN_SYSTEM.md` | Documentar tokens que já existem em código (extração pela sessão principal, com a `design-system`) |
| | Fontes pagas ou sem licença aberta |

#### Regras de negócio

**Pré-condição e pontos de entrada**

1. O `design-director` só escreve quando o `DESIGN_SYSTEM.md` da raiz não existe ou a seção `Principles` está vazia (sem texto além do comentário do template), e o projeto ainda não tem UI com identidade própria em código (regra 33).
2. Com `Principles` preenchida, não escreve nada e termina `result: blocked`, dizendo que ajustes são manutenção pela skill `design-system` e que redesign está fora do escopo.
3. Projeto sem serviço de UI (tabela `Services` do `CLAUDE.md` do projeto sem web nem mobile): não escreve e termina `result: blocked` com o motivo.
4. Nenhuma chamada é automática dentro de uma task: o `design-director` só é chamado depois de um sim do usuário na conversa (pergunta do `new-project`, frase do Workflow ou oferta da `design-system`).
5. `new-project`: com serviço de UI no perfil, o passo que hoje deixa as tabelas em branco pergunta se o usuário quer definir a direção visual agora. Sim: chama o `design-director` depois de `PRD.md` preenchido. Não: tabelas em branco, sem repetir a pergunta no `new-project`. Sem serviço de UI, o arquivo continua sendo descartado, como hoje.
6. Workflow: as frases "cria a identidade visual", "define o design do zero" e "vamos criar o frontend do zero" vão para o `design-director` quando a pré-condição (regra 1) vale; senão, a sessão principal diz que o arquivo já tem direção e segue pela `design-system`.
7. `design-system`, passo 1: na sessão principal, arquivo ausente ou `Principles` vazia leva a oferecer o `design-director` ao usuário, em vez de estabelecer a direção na conversa. Num subagent, o arquivo ausente vai para `scope_requests`, e a sessão principal leva a oferta ao usuário.
8. Recusa no meio de uma task de UI: o pedido de escopo conta como negado (13.4); o stack agent conclui `partial` ou declara blocker; nenhum token genérico é inventado.

**Rodada 1 - briefing**

9. Lê `PRD.md`, `CONSTRAINTS.md`, o `CLAUDE.md` do projeto (`Services`, `Documentation language`) e o brief recebido no prompt.
10. Faltando assunto, público ou tarefa principal, termina `needs_input` só com as perguntas do que falta (no máximo essas três), sem propor direção.
11. Com o básico presente, segue direto para a rodada 2.

**Rodada 2 - duas direções**

12. Cada direção traz: paleta base de 4 a 6 hex, com o papel de cada cor; tipografias e seus papéis (display, texto e, quando houver, mono), só com licença aberta ou do sistema (regra 22); conceito de layout com wireframe ASCII da tela da tarefa principal; 2-4 princípios; e a revisão contra a lista de padrões genéricos (qual padrão a direção poderia repetir e como evita, ou "nenhum").
13. Antes de ser apresentada, cada direção é revisada como um plano compacto de tokens contra o brief (público, tarefa principal, restrições); uma direção que não se sustenta contra o brief é refeita, não apresentada.
14. As duas direções são contrastantes: diferem em pelo menos dois dos três eixos (paleta, tipografia, conceito de layout).
15. A lista de padrões genéricos vale só para os eixos que o brief deixa livres. Uma escolha explícita do usuário ou de `CONSTRAINTS.md` (ex.: cor de marca, fonte institucional) vence a lista, e a direção registra que aquele elemento veio do brief.
16. Lista inicial de padrões a evitar: fundo creme + serifa + acento terracota; quase preto + um único acento ácido; kit de cards SaaS (cards idênticos arredondados com sombra cinza suave); eyebrow labels em caixa alta; acento numa única palavra do título; entradas com fade-and-slide em tudo.
17. A rodada termina com `needs_input`: o usuário escolhe uma direção, mistura (ex.: paleta da A com tipografia da B) ou pede mudanças. A sessão principal pergunta e retoma o mesmo agent com `SendMessage`.
18. Pedido de mudança ou recusa das duas: nova rodada 2, com duas direções novas que levam em conta o que foi rejeitado e por quê; nada é escrito enquanto não há escolha.

**Rodada 3 - `DESIGN_SYSTEM.md`**

19. Preenche o arquivo a partir da direção escolhida, no formato de `templates/project-root/DESIGN_SYSTEM.md`; copia o template quando o arquivo não existe.
20. Cor: tokens semânticos, nomeados por papel, com valor light e dark para cada token, sempre, inclusive quando o `PRD.md` exclui tema escuro (D22 j).
21. Contraste: todo par texto/fundo atende WCAG AA nos dois temas (4.5:1 para texto normal; 3:1 para texto grande e para ícones e bordas de componentes). A razão de cada par vai no report.
22. Tipografia: escala de 5 a 7 passos; cada família com stack de fallback. Só famílias com licença aberta (ex.: SIL OFL) ou do sistema; a origem e a licença de cada família ficam registradas no `DESIGN_SYSTEM.md` (D22 i). Em monorepo, a família precisa servir para web e mobile.
23. Todas as tabelas do template são preenchidas; linha que não se aplica diz isso explicitamente (ex.: "não se aplica: sem alvo tablet"), nunca fica vazia nem com placeholder.
24. `Principles`: 2-4 frases da direção escolhida, incluindo as regras duras que guiam o resto (ex.: densidade, uma cor de ação só); o detalhe de layout e os padrões evitados vão para `Layout concept` (regra 34).
25. Prosa no idioma de `Documentation language`; nomes de token e cabeçalhos do template ficam como estão.
26. Uma mistura que quebra o contraste AA não é escrita: o agent propõe o ajuste mais próximo num novo `needs_input`.
27. O report final aponta o próximo passo: levar os tokens ao código é um plan/spec normal (`planner` -> `specker` -> `frontend-react` / `mobile-react-native`); o agent não faz isso.

**Escrita, ferramentas e manutenção**

28. O `design-director` escreve só o `DESIGN_SYSTEM.md` da raiz: nenhum código, config, fonte, asset, estado de run ou outro doc. Tools: `Read`, `Grep`, `Glob`, `Write`, `Edit`; sem `Bash`, browser ou screenshot.
29. Depois da criação, o arquivo é escrito só pela sessão principal seguindo a `design-system`. Stack agents propõem valores em `scope_requests`; com o sim do usuário, a sessão principal aplica o valor e retoma o agent (exceção ao passo 5 de 13.4, em que o próprio agent faria a ação). `docs-writer` continua sem tocar no arquivo.
30. Hook: o `design-director` não gera `md_outside_docs` ao escrever um `DESIGN_SYSTEM.md` (regra por nome, 13.5); qualquer outro ator que não seja `design-director` ou a sessão principal gera `design_system_write_by_other` (`warn`); qualquer escrita do `design-director` em outro arquivo é negada (`design_director_write_outside`, `block`). Uma chamada negada nunca é repetida; o agent termina `blocked`, dizendo o estado do arquivo. Um aviso numa escrita bem-sucedida é reportado e a rodada segue.
31. Report: bloco YAML final no formato comum (5.1), com `result: done | needs_input | blocked`, `files_written`, `question` (rodadas 1 e 2), as duas direções resumidas (rodada 2), os pares de contraste com as razões (rodada 3), o próximo passo e `needs_docs: []`.
32. Contrato para o Briareu: a entrada é autossuficiente (fase, raiz do projeto, brief e, na retomada, a direção escolhida em texto), sem depender da conversa principal (seção 5).

**Perguntas respondidas em 2026-11-11**

33. Projeto que já tem UI em código com tokens próprios (tema, CSS de tokens, config do Tailwind nos serviços de UI), mas sem `DESIGN_SYSTEM.md` ou com `Principles` vazia: fora do escopo do `design-director`. O agent não escreve e termina `result: blocked`, apontando a extração; a sessão principal documenta os tokens existentes seguindo a `design-system` (extração, não criação). Nos pontos de entrada (regras 6 e 7), a sessão principal já segue direto para a extração, sem oferecer o agent (D22 g).
34. A direção escolhida também preenche a seção nova `Layout concept` do template: o conceito de layout, o wireframe ASCII (um por plataforma, em monorepo) e os padrões genéricos evitados, inclusive os que vieram do brief por escolha explícita (regra 15) (D22 h).

#### Casos de borda

| Situação | Comportamento esperado |
|---|---|
| Monorepo com web e mobile | um só `DESIGN_SYSTEM.md` na raiz e uma direção para as duas plataformas; na rodada 2, um wireframe por plataforma; nomes de token iguais nas duas; tipografias com licença aberta ou do sistema que funcionem nas duas (regra 22); `Layout concept` com um wireframe por plataforma (regra 34) |
| Arquivo existe com `Principles` e tabelas vazias (cópia do `new-project`) | fluxo normal; o agent preenche o arquivo existente |
| `Principles` vazia, mas algumas tabelas já têm valores | os valores existentes entram como restrição do brief; se a direção escolhida conflita com eles, a rodada 2 lista o que mudaria, e só muda com a escolha do usuário |
| `Principles` preenchida | `blocked`, arquivo intocado (regra 2); redesign fora do escopo |
| Usuário recusa as duas direções | nova rodada 2 com duas direções novas (regra 18); nada escrito |
| Usuário mistura direções | o agent confere o contraste da mistura; se quebra AA, propõe o ajuste antes de escrever (regra 26) |
| Brief pede explicitamente um padrão da lista (ex.: serifa sobre creme) | o brief vence; a direção registra que veio do brief (regra 15) |
| `CONSTRAINTS.md` traz cor de marca | entra nas duas direções; os tokens semânticos garantem AA (ex.: a marca vira `accent` só onde o contraste passa) |
| Projeto sem `PRD.md` (não veio do `new-project`) | o básico vem do brief; faltando, rodada 1 |
| Chamado enquanto um run do `implement` está ativo (regra 7) | não mexe no estado do run; a task que pediu fica parada até a sessão principal retomar o stack agent |
| Sessão reiniciada entre as rodadas (sem `SendMessage`) | uma chamada nova com a direção escolhida em texto vai direto para a rodada 3, depois de rechecar a pré-condição |
| Projeto sem serviço de UI | `blocked` (regra 3) |
| Projeto já tem UI com identidade própria em código, mas sem `DESIGN_SYSTEM.md` | fora do escopo: `blocked`; a sessão principal documenta os tokens existentes seguindo a `design-system` (regra 33) |
| `PRD.md` diz que não há tema escuro | light e dark preenchidos mesmo assim (regra 20) |
| Brief ou `CONSTRAINTS.md` pede uma fonte paga | não entra; a direção propõe a alternativa de licença aberta mais próxima e registra o motivo (regra 22) |

#### Abordagem (nível de produto)

**Fluxo por ponto de entrada:**

| Entrada | Quem pergunta | Pré-condição checada | Resultado |
|---|---|---|---|
| `new-project`, perfil com UI | o próprio `new-project` (sessão principal) | arquivo recém-copiado, `Principles` vazia | sim: `design-director`; não: tabelas em branco |
| Frase do Workflow | sessão principal | regra 1 | `design-director`, ou aviso de que a direção já existe |
| `design-system` na sessão principal | sessão principal | regra 1 | oferta do `design-director`; recusa: segue sem inventar tokens |
| `design-system` num subagent | stack agent -> `scope_requests` -> sessão principal | regra 1 | oferta ao usuário; recusa = pedido negado (13.4) |

**Estados de cada chamada:**

| Estado | Quando | O que o usuário vê |
|---|---|---|
| Briefing (`needs_input`) | falta assunto, público ou tarefa principal | até 3 perguntas, numa chamada de `AskUserQuestion` |
| Direções (`needs_input`) | básico presente | duas direções lado a lado (paleta, tipografia, wireframe, princípios, revisão de padrões) e a pergunta "qual, mistura ou mudanças?" |
| Concluído (`done`) | direção escolhida e contraste AA ok | caminho do arquivo, pares de contraste e o próximo passo (tokens no código via spec) |
| Bloqueado (`blocked`) | `Principles` preenchida, sem UI, UI já existente em código, ou ação negada pelo hook | o motivo e o caminho certo (`design-system`, extração dos tokens existentes, nada a fazer, ou pedido de escopo) |
| Erro de escrita | o `Write`/`Edit` falha | `blocked` com o erro; nenhuma escrita parcial é dada como concluída |

**Formato esperado de uma direção na rodada 2** (ilustrativo):

```
Direção A - "Arquivo técnico"
Paleta: #F4F4F1 fundo · #1B1D1F texto · #5A6B7A apoio · #2F6FED acento · #D64545 erro
Tipografia: display Space Grotesk 600 · texto Inter 400 · mono JetBrains Mono (todas SIL OFL, Google Fonts)
Layout: barra lateral fixa, tabela densa, detalhe em painel
  +--------+------------------------+
  | nav    | filtros         [Novo] |
  |        | tabela ............... |
  |        | tabela ............... |
  +--------+------------------------+
Princípios: densidade acima de respiro; uma cor de ação só
Padrões: poderia cair no kit de cards SaaS; evita com tabela e divisórias, sem sombra
```

**Arquivos (em `~/dotfiles/.claude/`):**

| Arquivo | Mudança |
|---|---|
| `agents/design-director.md` | **novo**: frontmatter de D22 (f); corpo com o ciclo de rodadas, a lista de padrões genéricos, o plano compacto de tokens revisado contra o brief, as regras de contraste, de escala e de licença das fontes, o `Layout concept` e o report YAML (regras 1-34) |
| `skills/design-system/SKILL.md` | passo 1: arquivo ausente ou `Principles` vazia -> oferecer o `design-director` (sessão principal) ou `scope_requests` (subagent); com UI já em código e tokens próprios, documentar os tokens existentes (extração) em vez de oferecer o agent (regra 33); sai a referência ao `frontend-design`; a skill fica só com a manutenção; valores propostos por subagent passam pela sessão principal (regra 29) |
| `skills/new-project/SKILL.md` | passo 1 (~linha 45): com serviço de UI, pergunta se define a direção agora; sim -> `design-director` depois de `PRD.md`; não -> tabelas em branco |
| `CLAUDE.md` (global) | linha nova no Workflow: "cria a identidade visual", "define o design do zero", "vamos criar o frontend do zero" -> `design-director`, com a pré-condição da regra 1; bullet de `scope_requests` no `DESIGN_SYSTEM.md` da raiz com três ramos (arquivo ausente -> oferta do `design-director`; extração -> a sessão principal documenta os tokens com a `design-system`; valor proposto -> a sessão principal escreve), e o caminho nunca entra em `allowed_paths` |
| `skills/implement/SKILL.md` | passo 5.2: exceção para pedidos de escopo no `DESIGN_SYSTEM.md` com os mesmos três ramos; a decisão do usuário continua registrada em `approved_scope`, mas o caminho nunca entra em `allowed_paths` (regra 29) |
| `templates/node-ts-react/CLAUDE.md`, `templates/react-native/CLAUDE.md` | linha 25: sai o `frontend-design`; criação da direção pelo `design-director`, manutenção pela `design-system` |
| `templates/project-root/DESIGN_SYSTEM.md` | comentário do topo: criado pelo `design-director`, mantido pela `design-system`; seção nova `Layout concept` depois de `Principles` (conceito, wireframe ASCII por plataforma, padrões evitados), aprovada pelo usuário em 2026-11-11 (D22 h); linha `Font family` com origem e licença de cada família (D22 i) |
| `hooks/agent-audit.py` | regra por nome (13.5): `DESIGN_SYSTEM.md` em qualquer diretório, sem diferenciar maiúsculas; isenção de `md_outside_docs` para `design-director` nesse arquivo; flags `design_system_write_by_other` e `design_director_write_outside` (de ator, valem para qualquer caminho, dentro ou fora de repositório); escritas fora da raiz git (13.7): raiz governante, união com repositório aninhado, `..` nas formas resolvida e léxica, `area: outside`, glob absoluto aprovado ou scratch para `out_of_scope_write`, falha fechada; mensagens em `WHY`; alvos de `approved_scope` que casam com a regra saem dos caminhos permitidos derivados, para o `out_of_scope_write` continuar valendo; lista `docs_roots` (13.5) no lugar do `docs/` fixo |
| `hooks/agent-audit.json` | `design_system_write_by_other: warn`, `design_director_write_outside: block`, `docs_roots: ["docs/", ".claude/docs/"]` |
| `hooks/agent-metrics.py` | rótulos das duas categorias novas (alvo 0); seção `## design-director` (14.1) |
| `settings.json` | sai `frontend-design@claude-plugins-official` de `enabledPlugins` (arquivo com regra `ask`: o usuário confirma) |
| `README.md` | pelo `docs-writer`, no fim: linha do `design-director` na tabela de agents; `design-system` pré-carregada também pelo `design-director`; o parágrafo do `frontend-design` vira a divisão criação x manutenção; categoria nova na política do hook |
| `agent-workflow.md` | "Registro de execução" da etapa H, depois de executada |

#### Verificação

- **Estática**: frontmatter do agent novo válido (`model`, `effort`, `tools`, `skills`); `settings.json` como JSON válido, sem o plugin e com hooks e `ask` intactos; `grep -r frontend-design` sem ocorrências fora deste documento; template `project-root/DESIGN_SYSTEM.md` com a seção `Layout concept` e a origem/licença em `Font family`; nenhum em dash nos arquivos tocados.
- **Hook pelo stdin**, como na etapa G, com repo git temporário:

  | Caso | Esperado |
  |---|---|
  | `design-director` faz `Write` em `DESIGN_SYSTEM.md` na raiz | silencioso |
  | `design-director` faz `Write` em `services/web/DESIGN_SYSTEM.md` | silencioso (regra por nome, 13.5) |
  | `design-director` faz `Write` em `NOTES.md` | negado: `design_director_write_outside` (`block`) |
  | `frontend-react` faz `Edit` no `DESIGN_SYSTEM.md` da raiz | `design_system_write_by_other` (`warn`) |
  | `docs-writer` faz `Edit` no mesmo arquivo | `design_system_write_by_other` (`warn`) |
  | sessão principal faz `Edit` no mesmo arquivo | silencioso |
  | modo `audit` | silencioso |

- **Regressão**: a bateria pelo stdin de 119 checagens (H1-H28 da etapa H, G1-G11 da etapa G, 37 comandos de classificação C e D1-D10 dos `docs_roots`) passa, e as métricas M1-M5 também (o relatório de uma sessão sem `design-director` é idêntico ao anterior).
- **Uso real** (sessão nova do Claude Code, porque agents novos só aparecem nela): cenários 37-45 da seção 14.3, mais o relatório `agent-metrics.py` com as métricas novas de 14.2.

#### Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Contraste calculado sem `Bash` sai errado | a razão de cada par fica no report e no arquivo, para o usuário conferir em qualquer verificador; o `code-reviewer` e o `ui-verifier` (sob pedido) já leem o arquivo |
| As duas direções saem como variações de uma só | regra 14 (dois de três eixos diferentes) e o cenário 37 confere |
| A lista de padrões vira um novo clichê ("evitar X" sempre leva a Y) | a lista é revisada quando os runs mostrarem repetição; vale só para eixos livres (regra 15) |
| Custo de opus com effort alto | runs raros (uma vez por projeto), gatilhos estreitos e nada automático (regra 4) |
| "vamos criar o frontend do zero" também pode significar código | a pré-condição desvia para a `design-system` quando a direção existe; o código continua no plan/spec |
| Implementer grava um valor direto no arquivo | hook em `warn` agora; promoção a `block` com os dados (13.3) |
| Fonte escolhida sem licença ou indisponível numa plataforma | regra 22: só licença aberta ou do sistema, com origem registrada; em monorepo, a família precisa servir para web e para `expo-font` |
| A seção nova `Layout concept` muda o template de todos os projetos | aprovada pelo usuário (D22 h); projetos existentes não são migrados, e a seção vazia não quebra os leitores atuais do arquivo |

#### Perguntas em aberto

Nenhuma. As quatro perguntas foram respondidas em 2026-11-11 (D22 g-j) e viraram as regras 20, 22, 33 e 34.

**Fontes**: WCAG 2.2, critérios [1.4.3 Contrast (Minimum)](https://www.w3.org/TR/WCAG22/#contrast-minimum) e [1.4.11 Non-text Contrast](https://www.w3.org/TR/WCAG22/#non-text-contrast).

> 💬

### 15.2 Etapa I - agent `lua` (adendo 2026-11-12)

- **Status**: Implemented (2026-11-13; aprovado ao pedir a spec, implementado no mesmo dia, ver Registro de execução)
- **Origem**: grill-me de 2026-11-12 (D23; Apêndice E)
- **Spec**: `~/dotfiles/.claude/docs/features/lua-agent/spec.md` (Index: `lua-agent`); log na mesma pasta. O adendo de 2026-11-13 da spec (A1-A7) vale sobre o corpo

#### Objetivo

Código Lua ganha um dono no workflow: plugins e configs de Neovim, UI dentro do Neovim, TUIs de terminal, jogos LÖVE, OpenResty, bibliotecas e configs embarcadas (wezterm, hammerspoon, awesome, conky) passam por um stack agent que conhece o runtime, a versão da linguagem e as ferramentas do projeto. O `implement` e o `specker` passam a rotear tasks Lua, e o `test-runner` e o `onboard` reconhecem projetos Lua sem configuração extra.

| Critério de sucesso | Como medir | Alvo |
|---|---|---|
| Task Lua chega ao `lua` | cenários 46 e 50: `Stack: lua` na spec ou inferido pelo `implement`; tasks Lua entregues a outro stack agent | 0 tasks mal roteadas |
| Corpo do agent curto | tamanho de `agents/lua.md` comparado aos stack agents irmãos (hoje 3,4k a 4,6k bytes) | dentro da faixa |
| UI do Neovim segue o tema | cenário 47: cores fixas (hex, `guifg`/`guibg` literais) em código de UI do Neovim escrito pelo agent | 0 |
| Terminal sempre restaurado | cenário 48: caminhos de saída (normal, erro, Ctrl-C) que restauram raw mode, cursor e alternate screen | 100% |
| Nada interativo | registro do hook (comando gravado, E11) com ator `lua`: `nvim` sem `--headless`, execução de app TUI ou LÖVE, recarga de hospedeiro ou de nginx | 0 |
| Checks estreitos | `suite_by_non_runner` com ator `lua` no relatório de métricas (comandos Lua classificados pelo hook, D23 f) | 0 |
| UI com `manual_checks` | tasks de UI do `lua` (Neovim ou terminal) com `manual_checks` preenchido | 100% |
| Versão respeitada | cenário 53: construções acima da menor versão de Lua declarada pelo projeto | 0 |
| `test-runner` acha as suites | cenário 49: projeto Lua sem `## Test suites` | suites certas, sem e2e |
| Hook reconhece o ator e os comandos | cenário 55: suite `claude-hooks` passa com `lua` em `IMPLEMENTERS`, no conjunto literal de E9 e com os casos novos de classificação Lua | 100% |
| Projeto Lua documentado no `onboard` | cenário 54: `LUA.md` com todas as seções do template preenchidas (ou "não se aplica" explícito), mais `Test suites` e `Workflow` | 100% |

#### Contexto

- Os stack agents cobrem Node, Spring, Go, Rust, Python, React e React Native. Código Lua não tem dono: cai na sessão principal ou num agent sem o know-how, e o `implement` não infere o stack (a lista de inferência não tem Lua). O próprio repo dotfiles tem Lua embarcado (`awesome/`, `conky/`).
- Neovim e TUI têm armadilhas que o contract genérico não cobre: chamadas de `vim.api` em callbacks assíncronos, temas que só se aplicam via grupos de highlight padrão, layout que quebra em `VimResized`, raw mode que deixa o terminal do usuário quebrado quando o app cai, diferenças entre LuaJIT/5.1 e 5.4.
- Base já existente: `implementer-contract` (etapa A), tasks estruturadas com **Stack** (B), `implement` com inferência de stack (C), hook em `enforce` (G), `design-system` só com manutenção (H) e a regra global de UI validada pelo usuário.
- Fora desta etapa: `new-project` (um template de plugin Neovim é uma feature própria).

#### Decisões (D23, grill-me de 2026-11-12)

| # | Decisão |
|---|---|
| a | **Agent novo `lua`**, especialista geral em Lua com profundidade em Neovim e TUIs, no padrão de `backend-go` e irmãos: `model: sonnet`, `effort: medium`, pré-carrega `implementer-contract`. Detecta o runtime (Neovim por `lua/` + `plugin/` ou `vim.*`, LÖVE por `conf.lua`, OpenResty, LuaJIT/5.x standalone) e a versão (LuaJIT/5.1 no Neovim, 5.4 standalone). Segue as ferramentas que o projeto já tem: busted, plenary ou mini.test; luacheck ou selene; stylua ou treefmt; mise |
| b | **TUI nos dois mundos, Neovim primeiro.** Dentro do Neovim: janelas flutuantes, buffers como UI (`nofile`, keymaps buffer-local), namespaces de extmark, highlights com link a grupos padrão, layout responsivo em `VimResized`, cuidado com `vim.schedule` e redraw. Terminal standalone: dependências mínimas, raw mode com restauração garantida, alternate screen, event loop `luv`, `SIGWINCH`, ANSI; biblioteca só se o projeto já usa uma |
| c | **Duas skills de conhecimento novas**, pré-carregadas pelo agent e usáveis sozinhas: `neovim-plugin` e `lua-tui`. O corpo do agent fica curto. O agent também pré-carrega `design-system`, como o `frontend-react`, porque TUI é UI |
| d | **Integração ao workflow**: hook (`lua` em `IMPLEMENTERS` e nos conjuntos literais de E9); `implement` e `specker` inferem `Stack: lua` por `*.rockspec`, `.luarc.json`, `stylua.toml`, `.luacheckrc` ou `lua/` + `plugin/`; `test-runner` detecta suites Lua sem `## Test suites` (busted, `nvim --headless` com plenary ou mini.test); `onboard` reconhece projetos Lua e Neovim e preenche `Test suites` e `Workflow`. `new-project` fica fora |
| e | **Política de UI**: segue o `implementer-contract` e a regra global de validação visual pelo usuário. Pode rodar `nvim --headless` para testes; nunca abre um Neovim interativo nem roda um app TUI interativamente; lista o que o usuário deve conferir |
| f | **Comandos Lua no hook** (resposta de 2026-11-12 à pergunta 1, opção a): `classify_command` reconhece busted, `nvim --headless` com plenary ou mini.test, as tasks do mise que rodam testes, lint ou formatação, luacheck, selene e stylua, e classifica cada um como teste ou lint do mesmo jeito que as outras stacks (formatadores contam como lint, como `gofmt` e `prettier`); `_spec.lua` e `_test.lua` contam como teste de arquivo único; com isso, `suite_by_non_runner` (E9) vale para o `lua`; a suite `claude-hooks` cobre tudo isso (regras 37, 46) |
| g | **`test-writer` e `tdd` conhecem Lua** (pergunta 2, opção a): busted, plenary e mini.test na lista de frameworks do `test-writer`; a forma de stub `error("not implemented")` na `tdd` (regra 47) |
| h | **`onboard` com documento Lua** (pergunta 3, opções a e c): preenche `Test suites` e `Workflow` e escreve um documento do projeto a partir de um template novo `templates/onboarding/LUA.md`, ao lado de `BACKEND.md`, `FRONTEND.md` e `MOBILE.md`, para projetos Lua e Neovim, inclusive sem pastas de serviço; criação do template aprovada pelo usuário (regras 43, 48-50) |
| i | **TUI de terminal sem `DESIGN_SYSTEM.md`** (pergunta 4, opção a): as 16 cores ANSI nomeadas mais atributos, que herdam o tema do terminal do usuário, sem pedido de escopo; vale só sem o arquivo; com ele, o arquivo vence (regra 24) |
| j | **Lua como uma unidade entre outras no `onboard`** (resposta de 2026-11-12 à pergunta que nasceu de h, opção a): um só `LUA.md` na raiz do repo, com um bloco por unidade Lua (ex.: gateway OpenResty em `services/`, pastas `awesome/` e `conky/`); as outras unidades seguem com os seus documentos (regras 48-49) |

#### Escopo

| Dentro | Fora |
|---|---|
| Agent `agents/lua.md` | `new-project` e um template de plugin Neovim (feature própria) |
| Lua no `test-writer` e na `tdd` | |
| Skills `neovim-plugin` e `lua-tui` | `templates/lua/STRUCTURE.md` ou qualquer template novo de stack (o `LUA.md` é de onboarding, não de stack) |
| `Stack: lua` no `implement`, no `specker` e no template de spec | Executar Neovim interativo, apps TUI, jogos LÖVE ou apps hospedeiros, inclusive para "conferir" |
| Detecção de suites Lua no `test-runner` | Prints ou captura de tela de terminal |
| Reconhecimento de projetos Lua e Neovim no `onboard`, com o template novo `templates/onboarding/LUA.md` | Linguagens que compilam para Lua (Fennel, MoonScript, Teal) |
| `lua` no hook (`IMPLEMENTERS`, conjunto literal de E9) e classificação de comandos Lua | Instalar ferramentas no ambiente (`mise install`, `luarocks install` global) por conta própria |
| Descrições que listam os stack agents (`implementer-contract`, `design-system`) e a seção de UI do contract | Publicação de rocks ou releases de plugin |
| Cenários 46-55 (14.3) e a métrica nova (14.2) | Mudança no `ui-verifier` (segue só para browser e simulador) |

#### Regras de negócio

**Definição do agent**

1. Agent novo `agents/lua.md`, no padrão dos stack agents: `model: sonnet`, `effort: medium`, todas as tools, `skills: [implementer-contract, design-system, neovim-plugin, lua-tui]`.
2. A description o apresenta como especialista geral em Lua, com profundidade em Neovim e TUIs, e o auto-invoca ("Use proactively when...") para código Lua: plugins e configs de Neovim, UI dentro do Neovim, TUIs de terminal, LÖVE, OpenResty, bibliotecas, scripts e configs embarcadas, e seus testes. A redação final fica na spec.
3. O corpo segue o `implementer-contract` e acrescenta só o que é de Lua: detecção de runtime e versão, regras por runtime, checks estreitos, arquivos gerados e extras do report. O know-how de Neovim e de TUI fica nas skills (regras 27-31), e o tamanho do corpo fica na faixa dos stack agents irmãos.
4. O `lua` entra em toda lista de stack agents da config: hook, `implement`, `specker`, template de spec e as descrições do `implementer-contract` e da `design-system` (regras 37-44).

**Runtime e versão (antes de codar)**

5. O runtime sai dos sinais do projeto, perto dos arquivos da task:

   | Sinal | Runtime | Lua padrão |
   |---|---|---|
   | `lua/` + `plugin/`, ou uso de `vim.*` | Neovim (plugin) | LuaJIT (5.1) |
   | `init.lua` + `lua/`, sem `plugin/` nem rockspec | Neovim (config) | LuaJIT (5.1) |
   | `conf.lua`, ou `main.lua` com `love.*` | LÖVE | LuaJIT (5.1) |
   | diretivas `*_by_lua*` em config do nginx, ou dependências `lua-resty-*` | OpenResty | LuaJIT (5.1) |
   | API de um app hospedeiro (`wezterm`, `hs`, `awesome`, `conky_*`) | embarcado (regra 8) | a do hospedeiro |
   | nenhum dos acima | standalone | 5.4 |

6. Declaração explícita vence o padrão: `runtime.version` do `.luarc.json`, `std` do `.luacheckrc` ou do `selene.toml`, `dependencies` do rockspec (`lua >= x, < y`), ferramenta `lua`/`luajit` no `mise.toml`, matriz da CI. Declarações em conflito: vale a menor versão, registrada em `assumptions`.
7. O código respeita a menor versão suportada pelo projeto. Abaixo de 5.3: sem `//`, sem operadores bit a bit nativos (usa `bit` no LuaJIT ou `bit32`, conforme o projeto), sem `utf8`; abaixo de 5.4: sem `<const>`/`<close>`; `goto` só em LuaJIT ou 5.2+. Projeto que suporta várias versões usa a camada de compatibilidade que já tem (ex.: `table.unpack or unpack`).
8. Embarcado: a API do hospedeiro é tratada como globais do ambiente. A versão de Lua é a que o projeto ou a doc do hospedeiro declara; desconhecida, o código fica no subconjunto comum de 5.1 a 5.4 e a suposição vai para `assumptions`. O hospedeiro nunca é executado nem recarregado (regra 34).
9. Neovim: a versão mínima suportada sai do README, da matriz da CI, do `health.lua` ou das guardas `vim.fn.has('nvim-0.x')`. Nenhuma API mais nova que ela é usada; com mínimo abaixo de 0.10, `vim.uv or vim.loop`. Sem nenhuma declaração, vale a versão do `mise.toml` ou da CI, registrada em `assumptions`.
10. Sinais de dois runtimes no mesmo lugar: segue o do módulo parecido mais próximo do arquivo da task e registra em `assumptions`. A spec pode fixar o runtime na task, e isso vence a detecção.

**Ferramentas do projeto**

11. Usa as ferramentas que o projeto já tem e nunca introduz outra que duplique uma em uso: testes com busted, plenary.nvim ou mini.test; lint com luacheck ou selene; formatação com stylua ou treefmt; versões e comandos pelo mise (`mise exec --`) quando o projeto usa mise.
12. Projeto sem framework de teste: o agent não adiciona um por conta própria. Se a task pede testes, termina `blocked` com um `scope_requests` que propõe o framework do runtime (o que a `neovim-plugin` indica para Neovim; busted para os demais). Sem testes pedidos, valida com o lint e o formatador configurados, registra a falta de testes em `notes` e lista em `manual_checks` como conferir.
13. Dependência nova (rock, plugin Neovim, biblioteca de TUI) só quando a task a nomeia; senão, `scope_requests` com o motivo.
14. Ferramentas do projeto ausentes no ambiente (ex.: tool do `mise.toml` não instalada): o agent não instala; o check vai para `blocked` no report, com o comando que o usuário roda.

**Neovim (know-how na `neovim-plugin`)**

15. Plugin: `plugin/<nome>.lua` mínimo, com `require` adiado para dentro dos comandos e mapeamentos (lazy-loading); `setup(opts)` só sobrescreve defaults, e a config mesclada passa por `vim.validate`; nenhum keymap padrão criado sem pedido (mapeamentos `<Plug>`); autocmds sempre num augroup nomeado com `clear = true`; `lua/<nome>/health.lua` cobre config e dependências externas e é atualizado quando a task muda uma delas.
16. Toda chamada de `vim.api` vinda de callback de `vim.uv` (ou de outro contexto assíncrono) passa por `vim.schedule` ou `vim.schedule_wrap`.
17. UI no Neovim: buffers de UI com `buftype=nofile`, sem swap e com `bufhidden` definido; keymaps buffer-local; um namespace de extmarks por plugin ou feature, limpo a cada re-render; highlights próprios com link a grupos padrão (`NormalFloat`, `FloatBorder`, `Comment`, `Diagnostic*`...) e `default = true`, nunca cor fixa, para o tema e os overrides do usuário valerem; layout recalculado em `VimResized`, com tamanho mínimo e limitado à área do editor; atualizações em lote, sem redraw em laço.
18. Fechar a UI por qualquer caminho (`:q`, `<C-w>o`, comando do plugin, troca de tabpage) limpa o estado: autocmds, timers, handles de `vim.uv` e extmarks. Reabrir funciona como na primeira vez.
19. Config de Neovim (não plugin): nenhuma convenção de plugin imposta (`setup`, `health.lua`, `<Plug>`); a estrutura existente manda.

**TUI de terminal (know-how na `lua-tui`)**

20. Dependências mínimas: sequências ANSI diretas e `luv` como event loop. Biblioteca de TUI só se o projeto já usa uma.
21. Raw mode com restauração garantida em todo caminho de saída: término normal, erro (tratador em volta do loop) e sinais de término (SIGINT, SIGTERM). Restaurar = sair do raw mode, mostrar o cursor e sair do alternate screen; o erro, se houver, é impresso depois da restauração.
22. Alternate screen ao entrar e saída dele ao terminar; `SIGWINCH` recalcula o layout.
23. Sem TTY (entrada ou saída redirecionada): não entra em raw mode nem emite sequências de controle; o comportamento visível (mensagem ou saída em texto) segue a spec da feature. A variável `NO_COLOR` desliga cores.
24. Cores: com `DESIGN_SYSTEM.md`, os tokens dele vencem. Sem o arquivo, a TUI usa só as 16 cores ANSI nomeadas (as 8 básicas e as 8 brilhantes) e atributos (negrito, dim, sublinhado, reverso), que herdam o tema do terminal do usuário; nada de cor 256 ou RGB fixa, e nenhum pedido de escopo para criar o arquivo (D23 i).

**Estados de UI (Neovim e terminal)**

25. Toda UI cobre no código os estados carregando, vazio, erro, sucesso, área pequena demais (janela ou terminal abaixo do mínimo, com aviso em vez de layout quebrado) e redimensionamento.
26. Uma operação assíncrona que termina depois de a UI fechar não escreve em buffer, janela ou terminal que não existe mais.

**Skills**

27. `neovim-plugin`: API (`vim.api`, `vim.uv`, `vim.schedule`), autocmds e augroups, setup e lazy-loading, `:checkhealth`, `vim.validate`, testes headless (busted, plenary, mini.test, `minimal_init`), janelas e buffers como UI.
28. `lua-tui`: a UI dentro do Neovim (regras 17-18) e a TUI de terminal (regras 20-23), com os estados das regras 25-26.
29. As duas são usáveis sozinhas: carregadas pela description (não `user-invocable: false`) quando a sessão principal, o `code-reviewer` ou outro agent trabalha com Lua, sem depender do agent `lua` para fazer sentido.
30. As duas são compactas: conteúdo pré-carregado é pago em todo run (regra de economia de tokens do `README.md`).
31. `design-system` pré-carregada: vale para os tokens de TUI de terminal quando o `DESIGN_SYSTEM.md` existe (regra 24). No Neovim, o design system é o link a grupos padrão (regra 17). Nem plugin Neovim nem TUI de terminal sem `DESIGN_SYSTEM.md` geram pedido de escopo para o arquivo.

**Checks e política de UI**

32. Checks estreitos: um arquivo ou nome de teste (busted com o arquivo; `nvim --headless` com plenary ou mini.test num arquivo, com o `minimal_init` do projeto), lint e verificação de formato nos arquivos tocados. Nunca a suite inteira nem tasks do mise, Makefile ou justfile que rodam suites (`test`, `all`, `check`): o gate é do `test-runner`.
33. `nvim --headless` só para testes e checks não interativos. O agent nunca abre um Neovim interativo, nunca roda app TUI ou jogo LÖVE e nunca executa ou recarrega um app hospedeiro ou o nginx.
34. `manual_checks` de toda task de UI ou config embarcada: o comando, keymap ou ação que abre a UI (ou "recarregar `<app>`"), o tamanho de janela ou terminal (inclusive redimensionar e pequeno demais), o tema (colorscheme claro e escuro no Neovim, tema do terminal na TUI), cada estado da regra 25 e o resultado esperado. TUI de terminal acrescenta "Ctrl-C e erro deixam o terminal normal".
35. OpenResty faz a validação de runtime do contract (seção 4: request + logs na instância local), como os backends; recarga do nginx é reinício e vai para `manual_checks`. Os outros runtimes não têm serviço: `local_checks` fica vazio.
36. Fase `scaffold` (TDD): módulos com a forma real (tabela retornada, assinaturas, anotações LuaCATS) e corpos `error("not implemented")`. Arquivos gerados (`doc/tags`, vimdoc gerado por ferramenta) são regenerados, nunca editados. No report, `needs_docs` lista README, vimdoc escrito à mão (`doc/<plugin>.txt`) e opções novas de `setup`; anotações LuaCATS são código, escritas com ele; `notes` traz o runtime, a versão de Lua e a versão mínima do Neovim detectados.

**Integração ao workflow**

37. Hook: `lua` entra em `IMPLEMENTERS`, e com isso valem para ele as regras de implementer (escopo de run por `allowed_paths`, `docs_write_by_implementer`, `suite_by_non_runner`). O conjunto literal de `hooks/tests/test_hook_main.py` (E9) recebe `lua`, e os comandos Lua passam a ser classificados (regra 46).
38. `implement`: o stack vem do **Stack** da task; na inferência pelos arquivos (spec antiga), `*.rockspec`, `.luarc.json`, `stylua.toml`, `.luacheckrc` ou `lua/` + `plugin/` perto dos arquivos da task, ou arquivos `.lua` na task, levam ao `lua`. Arquivos de outro stack vão ao agent desse stack, mesmo num repo com marcadores Lua.
39. `specker`: a lista de **Stack** ganha `lua`, inferido pelos mesmos sinais. Uma task, um stack: trabalho Lua e de outro stack ficam em tasks separadas.
40. Template de spec (`templates/docs-structure/features/_template/spec.md`): a linha **Stack** ganha `lua`.
41. `test-runner`, sem `## Test suites`: segue a ordem atual (prompt, CI, scripts do projeto, padrões do ecossistema); tasks do `mise.toml` contam como scripts do projeto. A tabela de padrões ganha a linha Lua: lint com luacheck ou selene quando configurados; verificação de formato com `stylua --check` ou `treefmt --ci` quando configurados; testes com busted quando há `.busted` ou `spec/`; testes Neovim com `nvim --headless` e plenary ou mini.test, usando o `minimal_init` do projeto.
42. `test-runner` sem o `minimal_init` que a suite Neovim exige: `blocked` com o motivo; nunca cria um.
43. `onboard`: sem pastas de serviço e com sinais Lua na raiz (regras 5 e 38), reconhece o repo como um projeto Lua. Preenche `## Test suites` (CI primeiro, depois tasks do mise, Makefile/justfile, `.busted` e pastas de teste) e `## Workflow`, propondo ao usuário e escrevendo só depois do sim, como hoje. `## Local runtime` só quando o Lua roda como serviço (OpenResty); plugin, config, LÖVE e biblioteca não têm a seção. Além das seções, escreve o documento do projeto a partir do `LUA.md` (regras 48-50).
44. Descrições: o `implementer-contract` lista o `lua` entre os stack agents, e a seção 5 (UI) passa a valer também para UI de terminal, com `nvim --headless` permitido para testes e Neovim interativo, app TUI e recarga de hospedeiro na lista do que nunca se abre. A description da `design-system` lista o `lua` entre os que a pré-carregam.

**Documentação (pelo `docs-writer`, no fim)**

45. `README.md`: linha do `lua` na tabela de agents; linhas de `neovim-plugin` e `lua-tui` na tabela de skills; `lua` em "preloaded by" da `design-system` e do `implementer-contract`; "the seven agent files" vira oito; o parágrafo de `onboarding/` cita o `LUA.md` ao lado de `BACKEND.md`/`FRONTEND.md`/`MOBILE.md`. O `CLAUDE.md` global não tem lista de agents (conferido em 2026-11-12) e a tabela Workflow roteia para o `implement` sem nomear stacks: nada muda nele.

**Perguntas respondidas em 2026-11-12**

46. Classificação de comandos Lua no hook (`classify_command`), com as mesmas dicas de estreito, pacote e completo das outras stacks (D23 f):

    | Comando | Categoria |
    |---|---|
    | `busted` | teste: estreito com um arquivo `_spec.lua`/`_test.lua` ou filtro (`--filter`, `-t`); pacote com um caminho de pasta; completo sem argumento |
    | `nvim --headless` com plenary (`PlenaryBustedFile`, `PlenaryBustedDirectory`) | teste: estreito com um arquivo; pacote ou completo com pasta, pelas mesmas dicas |
    | `nvim --headless` com mini.test (`MiniTest.run_file`, `MiniTest.run`) | teste: estreito com `run_file`; completo com `run` |
    | `nvim --headless` sem plenary nem mini.test | não é teste (categoria atual) |
    | `mise run <task>` / `mise r <task>`, task `test*` | teste, como `make test` (completo sem dica de estreito ou pacote) |
    | `mise run <task>`, task `lint*`, `format*` ou `fmt*` | lint, como `make lint` |
    | `mise run all`, `check` ou `ci` | teste completo (rodam a suite; regra 32) |
    | `mise exec -- <cmd>` / `mise x -- <cmd>` | a categoria do `<cmd>` |
    | `luacheck`, `selene` | lint |
    | `stylua` (com ou sem `--check`) | lint, como `gofmt` e `prettier` (formatador conta como lint) |

    Arquivos `_spec.lua` e `_test.lua` num comando de teste contam como teste de arquivo único. Com isso, `suite_by_non_runner` (E9) sinaliza o `lua` rodando suite completa ou de pacote e não sinaliza o teste de arquivo único. A suite `claude-hooks` cobre cada linha da tabela (`test_classify.py`) e o E9 com o ator `lua` (`test_hook_main.py`).
47. `test-writer` e `tdd` conhecem Lua (D23 g): busted, plenary e mini.test entram na lista de frameworks e runners do `test-writer` (que continua sem introduzir framework novo); a `tdd`, no passo de scaffold, dá a forma do stub Lua: módulo com a forma real (tabela retornada, assinaturas, anotações LuaCATS) e corpos `error("not implemented")`, a mesma da fase `scaffold` do `lua` (regra 36).
48. `onboard` usa o `LUA.md` para um projeto Lua ou Neovim: repo sem pastas de serviço com sinais Lua na raiz (regras 5 e 38), inclusive config de Neovim e config embarcada, e também cada unidade Lua de um repo com outras unidades: serviço Lua num monorepo (ex.: gateway OpenResty em `services/`) ou pasta Lua num repo misto (ex.: `awesome/` e `conky/` neste dotfiles). Há um só `LUA.md`, na raiz do repo, como `BACKEND.md`, `FRONTEND.md` e `MOBILE.md`, com um bloco por unidade Lua; as outras unidades seguem com os seus documentos (um gateway OpenResty vai para o `LUA.md`, não para o `BACKEND.md`). Só entram as unidades que o usuário escolheu onboardar (passo 2 do `onboard`) (D23 h, j).
49. Template novo `templates/onboarding/LUA.md`, aprovado pelo usuário, com a mesma forma dos outros (comentário de topo "realidade atual, não aspiração"; seções com comentários-guia). Um bloco por unidade Lua (regra 48): título `## <caminho da unidade>` (`## .` quando o repo inteiro é a unidade), e as seções abaixo dentro de cada bloco, um nível abaixo; um projeto inteiramente Lua tem um bloco só:

    | Seção | Conteúdo |
    |---|---|
    | `Stack` | runtime (Neovim plugin, Neovim config, LÖVE, OpenResty, standalone, embarcado com o nome do hospedeiro); versão de Lua e onde está declarada; versão mínima do Neovim (só Neovim); dependências principais (rocks, plugins como plenary); ferramentas (testes, lint, formatação, mise) |
    | `Folder structure` | a árvore real, anotada |
    | `Design patterns in use` | organização de módulos e API pública; pontos de entrada e carga (`plugin/`, `setup`, lazy-loading, comandos, entrada do hospedeiro); configuração e validação; assíncrono e event loop (`vim.uv`/`luv`, `vim.schedule`, coroutines); UI (janelas, buffers, extmarks, highlights; ou raw mode e alternate screen; ou "não se aplica"); tratamento de erro e notificação; health check; testes (framework, `minimal_init`, helpers, onde ficam) |
    | `Conventions observed` | nomes; organização de arquivos; anotações LuaCATS |
    | `Inconsistencies` | o mesmo problema resolvido de jeitos diferentes |
    | `Recommendations` | comparação com as convenções das skills `neovim-plugin` e `lua-tui` (não há `STRUCTURE.md` de Lua); ponto de partida para conversa, não mandato de refactor |
    | `Open questions` | o que o código sozinho não responde |

50. Preenchimento do `LUA.md`: como os outros documentos do `onboard` (prosa no idioma de `Documentation language`, identificadores como estão no código); item que não se aplica ao runtime diz isso explicitamente (ex.: "não se aplica: biblioteca sem UI"), nunca fica com placeholder.

#### Casos de borda

| Situação | Comportamento esperado |
|---|---|
| Repo com Lua e outro stack (serviço Go + gateway OpenResty; este dotfiles, com hooks Python e configs `awesome/`/`conky/`) | stack por task, pelos arquivos (regra 38); o `specker` separa as tasks (regra 39); o `test-runner` em escopo `task` roda só as suites do que foi tocado; no `onboard`, um bloco por unidade Lua no `LUA.md` (regra 48) |
| Repo de config do Neovim, não plugin | runtime Neovim (config); nenhuma convenção de plugin (regra 19); sem testes, vale a regra 12 |
| Lua embarcado (wezterm, hammerspoon, awesome, conky) | API do hospedeiro como globais; versão do hospedeiro ou subconjunto 5.1-5.4 (regra 8); hospedeiro nunca executado ou recarregado; `manual_checks` com "recarregar `<app>`" |
| Projeto sem framework de teste | nenhum framework adicionado sem pedido; `scope_requests` se a task pede testes (regra 12) |
| Projeto preso à semântica do 5.1 | nada acima de 5.1 (regra 7); o `std` do luacheck é respeitado; recursos só do LuaJIT (`goto`, `ffi`, `bit`) evitados se o projeto também roda em PUC 5.1 |
| Suite que exige LuaJIT (ex.: yield de coroutine atravessando `pcall`) | os checks rodam sob o LuaJIT que o projeto declara; o agent não troca o runtime para "consertar" o teste |
| Plugin que suporta Neovim abaixo de 0.10 | `vim.uv or vim.loop`; nenhuma API mais nova que o mínimo (regra 9) |
| Plugin com testes plenary sem `minimal_init` | o check estreito vai para `blocked` no report; o `test-runner` termina `blocked` (regra 42); ninguém cria o arquivo sem pedido |
| Usuário fecha a janela flutuante com `:q` ou `<C-w>o` | estado limpo; reabrir funciona (regra 18) |
| Resposta assíncrona chega depois de a UI fechar | descartada sem erro (regra 26) |
| Terminal ou janela abaixo do tamanho mínimo | estado "pequeno demais", sem quebra nem erro (regra 25) |
| TUI recebe Ctrl-C ou lança erro | terminal restaurado; o erro aparece depois da restauração (regra 21) |
| TUI com saída redirecionada (pipe, arquivo) | sem raw mode nem sequências de controle (regra 23) |
| TUI de terminal sem `DESIGN_SYSTEM.md` | 16 cores ANSI nomeadas e atributos, herdando o tema do terminal; nenhum pedido de escopo (regra 24) |
| TUI de terminal com `DESIGN_SYSTEM.md` | os tokens do arquivo vencem as cores ANSI (regra 24) |
| `lua` roda `mise run test` ou `busted` sem argumento | hook sinaliza `suite_by_non_runner` (regra 46); a suite fica com o `test-runner` |
| `onboard` num repo de config embarcada ou de config do Neovim, sem pastas de serviço | projeto Lua: `LUA.md` na raiz com um bloco só, com os itens de UI ou health check marcados "não se aplica" quando for o caso (regras 48-50) |
| `onboard` num monorepo com gateway OpenResty em `services/` e serviços de outra linguagem | `LUA.md` na raiz com o bloco do gateway; os outros serviços seguem com `BACKEND.md`, `FRONTEND.md` ou `MOBILE.md` (regra 48) |
| `onboard` num repo misto com pastas Lua (`awesome/`, `conky/`) e código de outra linguagem | um `LUA.md` na raiz com um bloco por pasta Lua escolhida; o resto segue o fluxo atual (regra 48) |
| Projeto LÖVE | o jogo nunca é executado; testes só se o projeto tem framework; `manual_checks` com o que conferir no jogo |
| OpenResty | validação por request + logs na instância local (regra 35); recarga do nginx em `manual_checks` |
| Biblioteca Lua só com rockspec | runtime standalone; versão pelo rockspec (regra 6); busted se configurado |
| Spec com `Stack: lua` num projeto sem marcador Lua (primeiro módulo Lua) | o agent segue a spec; runtime pela task ou pela regra 10, em `assumptions` |
| Tool do `mise.toml` não instalada | nada instalado; check em `blocked` com o comando para o usuário (regra 14) |
| Prompt pede print ou conferência visual | não faz; registra em `notes` e lista os estados em `manual_checks` (contract, seção 5) |
| Fennel, MoonScript ou Teal no repo | fora do escopo; o agent só toca o Lua e reporta em `notes` quando a task exigiria a outra linguagem |

#### Abordagem (nível de produto)

**Pontos de entrada:**

| Entrada | Quem escolhe o `lua` | Resultado |
|---|---|---|
| Task do `implement` com `Stack: lua` | a spec | `lua` em `implement`, `scaffold` (TDD) ou `fix` |
| Task de spec antiga, sem **Stack**, com arquivos Lua | inferência do `implement` (regra 38) | `lua` |
| Pedido direto na sessão ("ajusta a janela flutuante do plugin") | description do agent | `lua`, com o escopo do pedido |
| Bug em código Lua (`fix-bug`) | dono dos arquivos | `lua` nas fases `diagnose` e `fix` |
| Gate de uma task Lua | `test-runner` (`Test suites` ou detecção, regra 41) | resumo YAML das suites Lua |
| Projeto Lua ou Neovim no `onboard` | `onboard` (regras 43, 48) | `LUA.md` na raiz, mais `Test suites` e `Workflow` propostos e escritos depois do sim |

**Estados de cada chamada do `lua`:**

| Estado | Quando | O que o usuário vê |
|---|---|---|
| Concluído (`done`) | task feita, checks estreitos passando | arquivos, checks, runtime e versão em `notes`, `manual_checks` (UI ou embarcado), `local_checks` (OpenResty) |
| Parcial (`partial`) | pedido de escopo negado (dependência, framework de teste, arquivo fora de `allowed_paths`) | o que foi feito, o que ficou de fora e por quê |
| Bloqueado (`blocked`) | precisa de escopo, ação negada pelo hook ou ferramenta ausente no ambiente | o pedido com o motivo, ou o comando que o usuário roda |
| Sem serviço (`local_checks` vazio) | runtime sem serviço (Neovim, LÖVE, standalone, embarcado) | só `manual_checks` |
| Validação de runtime pulada | OpenResty parado, sem `reload: auto` ou sem dados no `Local runtime` | `skipped` com o motivo e o `curl` em `manual_checks` (contract, seção 4) |

**Exemplo de `manual_checks` de uma janela flutuante** (ilustrativo):

```
- :MeuPlugin open -> janela centralizada, borda e cores do tema atual
- redimensionar o terminal com a janela aberta -> janela recentralizada, sem corte
- terminal com 40 colunas -> aviso "janela pequena demais", sem erro
- :colorscheme de tema claro e de tema escuro -> cores acompanham o tema
- lista vazia / erro de rede / carregando -> textos de cada estado
- :q na janela e reabrir -> abre igual à primeira vez, sem erro em :messages
```

**Arquivos (em `~/dotfiles/.claude/`):**

| Arquivo | Mudança |
|---|---|
| `agents/lua.md` | **novo**: frontmatter de D23 (a, c); corpo com detecção de runtime e versão, ferramentas, checks estreitos, política de UI, arquivos gerados e extras do report (regras 1-14, 32-36) |
| `skills/neovim-plugin/SKILL.md` | **nova** (regras 15-19, 27, 29-30) |
| `skills/lua-tui/SKILL.md` | **nova** (regras 17-18, 20-26, 28-30) |
| `skills/implementer-contract/SKILL.md` | description lista o `lua`; seção 5 vale para UI de terminal, com `nvim --headless` permitido para testes e Neovim interativo, app TUI e recarga de hospedeiro proibidos (regra 44) |
| `skills/design-system/SKILL.md` | description: o `lua` entre os que a pré-carregam (regra 44) |
| `skills/implement/SKILL.md` | inferência de stack com Lua (regra 38) |
| `agents/specker.md` | `lua` na lista de **Stack** e inferência (regra 39) |
| `templates/docs-structure/features/_template/spec.md` | `lua` na linha **Stack** (regra 40) |
| `agents/test-runner.md` | tasks do mise como scripts do projeto; linha Lua na tabela de padrões; `minimal_init` ausente = `blocked` (regras 41-42) |
| `skills/onboard/SKILL.md` | reconhecimento de projeto Lua sem pastas de serviço; fontes de `Test suites`; `Local runtime` só com serviço; padrões a observar num projeto Lua; `LUA.md` no passo de escrita, um só na raiz com um bloco por unidade Lua (regras 43, 48-50) |
| `templates/onboarding/LUA.md` | **novo**, aprovado pelo usuário; um bloco por unidade Lua (regra 49) |
| `hooks/agent-audit.py` | `lua` em `IMPLEMENTERS` (regra 37); classificação de comandos Lua em `classify_command` (regra 46) |
| `hooks/tests/test_hook_main.py` | `lua` no conjunto literal de E9; E9 com o ator `lua` (suite sinalizada, arquivo único não) (regras 37, 46) |
| `hooks/tests/test_classify.py` | um caso por linha da tabela da regra 46 |
| `agents/test-writer.md` | busted, plenary e mini.test na lista de frameworks (regra 47) |
| `skills/tdd/SKILL.md` | forma do stub Lua no scaffold (regra 47) |
| `README.md` | pelo `docs-writer`, no fim (regra 45) |
| `agent-workflow.md` | "Registro de execução" da etapa I, depois de executada |

#### Verificação

- **Estática**: frontmatter do `lua` válido (`model`, `effort`, `skills`, todas as skills existentes); `neovim-plugin` e `lua-tui` com description que dispara em código Lua e sem `user-invocable: false`; `grep` de `mobile-react-native` em listas de stack (hook, testes do hook, `implement`, `specker`, template de spec, `implementer-contract`, `design-system`) mostra o `lua` em todas; tamanho de `agents/lua.md` na faixa dos irmãos; nenhum em dash nos arquivos tocados.
- **Hook**: a suite `claude-hooks` (`## Test suites` do `CLAUDE.md` do repo) passa, com o conjunto literal novo, um caso de `test_classify.py` por linha da tabela da regra 46 e o E9 com o ator `lua` (suite completa ou de pacote sinalizada; `_spec.lua`/`_test.lua` de arquivo único não).
- **Template**: `templates/onboarding/LUA.md` com as seções da regra 49, na mesma forma de `BACKEND.md` (comentário de topo, comentários-guia), e a instrução de um bloco por unidade Lua.
- **`onboard`**: a skill manda escrever um só `LUA.md` na raiz, com um bloco por unidade Lua, e deixa as outras unidades com os seus documentos (regra 48).
- **Uso real** (sessão nova do Claude Code, porque agents e skills novos só aparecem nela): cenários 46-55 da seção 14.3, num plugin Neovim com busted e luacheck, numa TUI de terminal de teste (com e sem `DESIGN_SYSTEM.md`) e numa config embarcada; mais o relatório `agent-metrics.py` (métrica nova de 14.2 e escritas do `lua`).

#### Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Quatro skills pré-carregadas pesam em toda task Lua, até em OpenResty ou biblioteca | skills compactas (regra 30); tokens por task medidos contra o baseline (14.2); se pesar, o detalhe sai para carga sob demanda |
| Runtime detectado errado (config x plugin, hospedeiro desconhecido) | tabela de sinais e precedência (regras 5-6, 10); dúvida vai para `assumptions`; a spec pode fixar o runtime |
| Código usa recurso de versão mais nova que a do projeto | regra 7; `std` do luacheck/selene pega parte; cenário 53 |
| Classificação nova do hook pega comando que não é teste (ex.: `nvim --headless` de outra coisa) | só `nvim --headless` com plenary ou mini.test é teste (regra 46); caso negativo na suite `claude-hooks` |
| Task do mise com nome fora do padrão (`spec`, `unit`) roda a suite sem ser sinalizada | o padrão segue o de `make`/`just` das outras stacks; nomes novos entram quando os dados do registro mostrarem (13.3) |
| `LUA.md` muda os templates de todos os projetos | aprovado pelo usuário (D23 h); só é usado em projetos Lua, e os outros templates não mudam |
| Agent tenta abrir `nvim` ou o app TUI e trava o `Bash` | regras 33-34 no corpo e no contract; métrica nova (14.2) pelo comando gravado no registro do hook |
| TUI que cai deixa o terminal do usuário quebrado | regra 21 em todos os caminhos de saída; item fixo em `manual_checks` |
| Inferência marca como Lua uma task de outro stack num repo com `.luarc.json` | arquivos da task vencem os marcadores do repo (regra 38) |
| API do Neovim muda entre versões (ex.: forma de `vim.validate`, `vim.loop` -> `vim.uv`) | versão mínima detectada (regra 9); `notes` traz a versão usada |

#### Perguntas em aberto

Nenhuma. As quatro perguntas da primeira versão foram respondidas em 2026-11-12 (D23 f-i) e viraram as regras 24, 31, 37, 43 e 46-50; a que nasceu da resposta sobre o `LUA.md` (Lua como uma unidade entre outras) foi respondida no mesmo dia (D23 j) e entrou nas regras 48-49.

#### Adendo 2026-11-13 (implementação)

Registrado depois da implementação e da revisão; não reabre as decisões a-j.

- **Stub Lua (muda D23 g e as regras 36 e 47)**: o stub Lua da fase `scaffold` do `lua` e do passo de scaffold da `tdd` devolve um valor vazio ou zero do tipo certo (`{}`, `""`, `0`, `false`, `nil` documentado, iterador ou callback vazio), nunca `error("not implemented")`. Motivo: o busted reporta `error()` como Error, e o `test-runner` o classificaria como falha de runtime em vez de falha de asserção. Onde D23 (g) e as regras 36 e 47 dizem `error("not implemented")`, vale esta linha. Decisão do usuário durante a task 8; registrada no log e no adendo da spec.
- **Decisões da spec aceitas pelo usuário (S3-S10)**, além do texto do plan:
  - S3: busted, `luarocks test`, luacheck, selene, stylua e treefmt entram nas regex genéricas do hook; `mise` e `nvim` ganham ramos próprios; a dica `--filter` vale só para o busted (`pnpm --filter api test` segue `test-package`).
  - S4: formas do mise além da regra 46: `mise tasks run <task>`, o atalho `mise <task>`, várias tasks com `:::` e flags antes do nome da task; `mise test-tool` não é task.
  - S5: `luarocks test` é teste completo; `treefmt` (com ou sem `--ci`) é lint.
  - S6: `timeout [opções] <duração>` é prefixo removido pelo `strip_prefixes` (hoje `command_readings`, ver 13.8) **para todas as stacks** (`timeout 5 git push` passa a ser `git-push`, `timeout 60 pytest` passa a ser `test-full`). O adendo A2 da spec estende a toda forma GNU, com falha fechada.
  - S7: `busted`, `luacheck`, `selene`, `stylua` e `nvim` chamados por caminho (`./.luarocks/bin/busted`) contam pelo nome do arquivo.
  - S8: marcadores de roteamento `.stylua.toml` e `selene.toml`, além dos da regra 38.
  - S9: a `design-system` ganha um bullet no passo 1: UI de Neovim ou TUI de terminal sem `DESIGN_SYSTEM.md` não abre pedido de escopo (evita o conflito com as regras 24 e 31).
  - S10: `agents/lua.md` entre 3.400 e 4.600 bytes; cada skill nova com no máximo 120 linhas e 7.000 bytes.
- **Duas categorias novas de bloqueio no hook, aprovadas pelo usuário durante a revisão** (não estavam no plan; entram em `agent-audit.json` como `block`, valem para todo ator):
  - `command_too_long`: comando Bash com mais de 16384 caracteres é negado sem ser analisado (`MAX_COMMAND_LEN`); o texto orienta a gravar conteúdo grande com a ferramenta Write.
  - `analysis_timeout`: guarda de 7 s de relógio em torno da classificação (`ANALYSIS_TIMEOUT_S`); uma chamada complexa demais para analisar a tempo é negada. A variável `AGENT_AUDIT_ANALYSIS_TIMEOUT` é só de teste e só pode baixar o limite. O hook imprime a decisão antes de gravar o registro, e mais de 32 abridores de heredoc (`MAX_HEREDOC_OPENERS`) classificam o comando como comandos.
- **Escopo do hook ampliado pela revisão**: shell escapes do Neovim (`-c`, `--cmd`, `+`) são classificados; `timeout` e `mise exec|x --` são prefixos removidos; flags globais do mise e do luarocks são puladas. Detalhes em 13.6 (adendo) e na spec (A2-A5).

**Fontes**: Neovim, [Lua plugin guide](https://neovim.io/doc/user/lua-plugin/) (lazy-loading, `setup`, `vim.validate`, `health.lua`, `<Plug>`) e [Lua API](https://neovim.io/doc/user/lua/) (`vim.uv`: "It is an error to directly invoke `vim.api` functions (except api-fast) in `vim.uv` callbacks"; `vim.validate(name, value, validator[, optional][, message])`, com a forma de tabela marcada como DEPRECATED); [NO_COLOR](https://no-color.org/).

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
| D22 | `design-director` (etapa H, implementada) | agent novo cria a direção visual de projetos sem frontend definido, em rodadas via `needs_input` (duas direções contrastantes, o usuário escolhe), e escreve só `DESIGN_SYSTEM.md`; a manutenção fica com a `design-system`; três pontos de entrada, nenhum automático; plugin `frontend-design` não adotado, só ideias reescritas; opus, effort alto, sem `Bash`; hook com isenção, categoria `design_system_write_by_other` (`warn`) e categoria `design_director_write_outside` (`block`); UI já existente em código fica com a extração pela `design-system`; seção nova `Layout concept` no template; só fontes de licença aberta ou do sistema; light e dark sempre (15.1, decisões a-j) |
| D23 | Agent `lua` (etapa I, implementada) | stack agent novo `lua` (sonnet, effort médio), especialista geral em Lua com profundidade em Neovim e TUI; detecta runtime (Neovim, LÖVE, OpenResty, standalone) e versão (LuaJIT/5.1 no Neovim, 5.4 standalone) e segue as ferramentas do projeto; TUI nos dois mundos, Neovim primeiro; skills novas `neovim-plugin` e `lua-tui`, pré-carregadas com `implementer-contract` e `design-system` e usáveis sozinhas; `Stack: lua` no `implement` e no `specker`, detecção no `test-runner` e no `onboard`, `lua` no hook; `nvim --headless` só para testes, nada interativo; `new-project` fora; respostas de 2026-11-12: comandos Lua classificados no hook (E9 vale para o `lua`), `test-writer` e `tdd` conhecem Lua, `onboard` escreve `LUA.md` a partir de template novo aprovado, TUI sem `DESIGN_SYSTEM.md` usa as 16 cores ANSI nomeadas, um só `LUA.md` na raiz com um bloco por unidade Lua (15.2, decisões a-j) |

### 16.2 Em aberto

Nenhuma. As perguntas da etapa I foram respondidas em 2026-11-12 (15.2, D23 f-j); as da etapa H, em 2026-11-11 (15.1, D22 g-j).

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

## Apêndice D: decisões do grill-me de 2026-11-11 (etapa H) e onde foram tratadas

| Decisão | Resumo | Tratado em |
|---|---|---|
| D22 (a) | sem fonte externa: plugin `frontend-design` não adotado; só as ideias do plano compacto de tokens e da lista de padrões genéricos, reescritas; sem "escrever o código" nem prints | 12.2, 15.1 (regras 13, 15-16; arquivos), cenário 37 |
| D22 (b) | `design-director` cria; `design-system` mantém | 4, 9, 11.1, 12.2, 15.1 (regras 1-2, 29) |
| D22 (c) | rodadas via `needs_input`: briefing se faltar o básico, duas direções, escolha, arquivo | 8, 15.1 (regras 9-27), cenários 37-40 |
| D22 (d) | três pontos de entrada, só sem direção definida, nenhum automático | 7, 8, 15.1 (regras 4-8), cenários 41-42 |
| D22 (e) | escreve só `DESIGN_SYSTEM.md`; sem código nem `Bash`; hook com isenção e `design_system_write_by_other` | 5.2, 13.3, 14.2, 15.1 (regras 28-30; verificação), cenário 43 |
| D22 (f) | opus, effort alto, `skills: [design-system]`, know-how no corpo do agent, description fixa | 9, 12.1, 15.1 (decisões; arquivos) |
| D22 (g) | resposta à pergunta 1: UI já em código sem `DESIGN_SYSTEM.md` fica fora do agent; extração pela sessão principal com a `design-system` | 4, 7, 15.1 (regras 1, 33; casos de borda; arquivos), cenário 45 |
| D22 (h) | resposta à pergunta 2: seção nova `Layout concept` no template `project-root/DESIGN_SYSTEM.md`, aprovada | 15.1 (regras 24, 34; arquivos; verificação; riscos), cenário 37 |
| D22 (i) | resposta à pergunta 3: só fontes de licença aberta (ex.: SIL OFL) ou do sistema, com a origem registrada | 15.1 (regras 12, 22; casos de borda; arquivos; riscos), cenário 37 |
| D22 (j) | resposta à pergunta 4: light e dark sempre, mesmo com o `PRD.md` excluindo tema escuro | 15.1 (regra 20; casos de borda) |

## Apêndice E: decisões do grill-me de 2026-11-12 (etapa I) e onde foram tratadas

| Decisão | Resumo | Tratado em |
|---|---|---|
| D23 (a) | agent `lua` no padrão dos stack agents (sonnet, effort médio, `implementer-contract`); detecção de runtime e versão; ferramentas do projeto | 12.1, 15.2 (regras 1-14; casos de borda), cenários 46, 51-53 |
| D23 (b) | TUI dentro do Neovim e no terminal, Neovim primeiro | 15.2 (regras 15-26; casos de borda), cenários 47-48 |
| D23 (c) | skills `neovim-plugin` e `lua-tui`, pré-carregadas e usáveis sozinhas; corpo curto; `design-system` pré-carregada | 12.1, 12.2, 15.2 (regras 3, 27-31) |
| D23 (d) | hook, `implement`, `specker`, `test-runner` e `onboard`; `new-project` fora | 15.2 (regras 37-44), cenários 49-50, 54-55 |
| D23 (e) | política de UI: `nvim --headless` só para testes, nada interativo, `manual_checks` | 14.2, 15.2 (regras 32-35, 44), cenários 46-48, 52 |
| D23 (f) | resposta à pergunta 1: `classify_command` reconhece busted, `nvim --headless` com plenary ou mini.test, tasks do mise, luacheck, selene e stylua; `_spec.lua`/`_test.lua` estreitos; E9 vale para o `lua`; suite `claude-hooks` cobre | 15.2 (regras 37, 46; critérios; casos de borda; arquivos; verificação; riscos), cenário 55 |
| D23 (g) | resposta à pergunta 2: busted, plenary e mini.test no `test-writer`; stub `error("not implemented")` na `tdd` | 15.2 (regra 47; escopo; arquivos) |
| D23 (h) | resposta à pergunta 3 (opções a e c): `Test suites`, `Workflow` e documento do projeto a partir do template novo `templates/onboarding/LUA.md`, aprovado | 15.2 (regras 43, 45, 48-50; critérios; casos de borda; arquivos; verificação; riscos), cenário 54 |
| D23 (i) | resposta à pergunta 4: TUI sem `DESIGN_SYSTEM.md` usa as 16 cores ANSI nomeadas e atributos, sem pedido de escopo; com o arquivo, ele vence | 15.2 (regras 24, 31; casos de borda), cenário 48 |
| D23 (j) | resposta à pergunta que nasceu de h: um só `LUA.md` na raiz, um bloco por unidade Lua (gateway OpenResty em `services/`, pastas `awesome/` e `conky/`); as outras unidades seguem com os seus documentos | 15.2 (regras 48-49; casos de borda; verificação), cenário 54 |

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

### Etapa E - 2026-11-10 (concluída)

**Arquivos (em `~/dotfiles/.claude/`):**

| Arquivo | Mudança |
|---|---|
| `agents/docs-writer.md` | **novo**: dono único do passe de documentação; roda uma vez no fim, a partir dos `needs_docs`; confere cada item contra o código antes de escrever; cuida da coerência ao redor (env var no `.env.example` e na tabela do README, endpoint na doc de API e em `docs/requests/`, serviço ou suite nas seções do `CLAUDE.md` do projeto); nunca edita código, arquivos gerados, `docs/features/`, `docs/backlog/` nem documentos de produto e design; sonnet, effort médio |
| `agents/ui-verifier.md` | **novo, opt-in**: só sob pedido explícito de print; usa o app que o usuário já tem rodando (nunca sobe nada); método mais barato primeiro (texto ou árvore de acessibilidade, depois medição de estilos, print por último, um por estado, recortado); imagens fora do repo; report só em texto; somente leitura no projeto |
| `skills/docs/SKILL.md` | vira o know-how do `docs-writer`; comentários de código ficam com quem escreve o código; idioma vindo do `CLAUDE.md`, ou pergunta via `needs_input` |
| `settings.json` | skill `docs` reativada (antecipado da etapa F, porque o `docs-writer` a pré-carrega) |
| `skills/implementer-contract/SKILL.md` | comentários de código e anotações de API são parte do código; prints pedidos explicitamente são delegados ao `ui-verifier` |
| `agents/backend-*.md` | `needs_docs` sem godoc, rustdoc, docstrings e anotações de OpenAPI (escritos junto com o código) |
| `skills/implement/SKILL.md` | fase `document`: `docs-writer` uma vez antes do backlog; plan marcado `Implemented` junto com a spec; `ui-verifier` só sob pedido; relatório final lista as docs atualizadas |
| `CLAUDE.md` (global) | documentação pelo `docs-writer`; prints explícitos pelo `ui-verifier`; linhas novas no Workflow ("documenta", "tira um print") e o `docs-writer` no fluxo de bug |
| `hooks/agent-audit.py`, `hooks/agent-metrics.py` | novo sinal `write_by_readonly_agent`; `docs_write_by_implementer` cobre README, CHANGELOG, `.env.example` e `DEPLOY.md`; print feito pelo `ui-verifier` não é sinalizado |
| `README.md` | agents novos, skill `docs`, passo de documentação automático no workflow |

**Decisões tomadas durante a execução:**
- O `docs-writer` roda dentro do `/implement`, depois do gate final e antes do backlog, em vez de esperar a validação manual. Isso segue a seção 3 (Documentar faz parte do fluxo de feature) e deixa o relatório final completo.
- O plan passa para `Implemented` junto com a spec, pelo `implement`, que é o dono dos status.
- O `ui-verifier` não restringe `tools` no frontmatter, porque as ferramentas de browser são MCP com nomes que variam. A regra de somente leitura fica no prompt, e o hook sinaliza qualquer escrita dele (`write_by_readonly_agent`).

**Validação feita nesta sessão:**
- Hook: escrita de `.env.example` por implementer sinalizada e pelo `docs-writer` não; README pelo `docs-writer` sem sinal; escrita do `ui-verifier` sinalizada; print do `ui-verifier` sem sinal e de um implementer sinalizado; os 31 casos de classificação continuam passando.

**Pendências:**
- `docs-writer` e `ui-verifier` sem teste de uso real: cenários 1 (fechamento do `/implement`), 11 e 14 da seção 14.3, na sessão de validação. O `ui-verifier` precisa de um app rodando e de uma ferramenta de browser disponível na sessão.

### Etapa F - 2026-11-10 (concluída)

**Arquivos (em `~/dotfiles/.claude/`):**

| Arquivo | Mudança |
|---|---|
| `skills/fix-bug/SKILL.md` | **nova**: fluxo de bug com estado em `.claude/runs/bug-<slug>.json`: entrada no backlog (registra se faltar) -> reproduzir como o usuário vê (request + logs, comando, ou passos de UI confirmados) -> diagnóstico só leitura pelo stack agent dono -> teste de regressão pelo `test-writer`, vermelho por asserção -> fix sem tocar no teste -> gate -> review (com checagem de intenção) -> repetir a reprodução -> `docs-writer` -> `backlog-keeper` fecha a entrada. Não reproduziu: para e registra a tentativa |
| `skills/tdd/SKILL.md` | absorve a `scaffold`; regra "vermelho pelo motivo certo"; stubs que compilam -> `test-writer` em modo tdd -> `test-runner` com escopo `files` exige `failure_kind: assertion` -> entrega ao usuário |
| `skills/implement/SKILL.md` | flag `--tdd` (também "com TDD"): por task, `scaffold` -> testes em modo tdd -> vermelho por asserção -> stack agent implementa sem editar os testes; registrada no estado do run |
| `skills/implementer-contract/SKILL.md` | fases `implement`, `scaffold`, `diagnose` (só leitura, devolve `diagnosis` com causa raiz, plano, `fix_paths` e onde fica o teste de regressão) e `fix` |
| `agents/test-writer.md` | modos `coverage`, `tdd` e `regression`, com `red_check` por teste no report |
| `agents/test-runner.md` | escopo `files`; toda falha classificada em `failure_kind` (assertion, compile, import, runtime, timeout, other) |
| `agents/code-reviewer.md` | checagem de intenção (vinda da skill `review`): cada critério `Done when` (ou o comportamento esperado do bug) com `met` e evidência; critério não cumprido vira `major` |
| `agents/security-reviewer.md` | pré-carrega `dep-audit` |
| `agents/frontend-react.md`, `agents/mobile-react-native.md` | pré-carregam `design-system` |
| `skills/design-system/SKILL.md` | passe de pixel no código, não na tela; o que está fora do escopo vira out-of-scope; `DESIGN_SYSTEM.md` ausente ou incompleto vira pedido de escopo num subagent |
| `skills/pr-description/SKILL.md` | usa plan, spec, log ou entrada do bug para o "porquê"; test plan com os checks locais e o "Para validar localmente"; sem linhas de atribuição |
| `skills/grill-me/SKILL.md` | fase Descobrir; no fim, decisões de produto no `PRD.md` e perguntas de projeto no `OPEN_QUESTIONS.md` (com confirmação) e entrega ao `planner` |
| `skills/review`, `codebase-standards`, `scaffold`, `code-simplify` | **removidas**, com o conteúdo útil levado para `code-reviewer`, `tdd`, a fase `scaffold` e a tabela Workflow (`/simplify` só aplica depois da aprovação) |
| `settings.json` | `skillOverrides` removido: nenhuma skill desligada |
| `CLAUDE.md` (global) | Workflow: Discover -> `grill-me`; Fix -> `fix-bug`; linhas novas para `tdd`, `implement --tdd`, `pr-description`, `/simplify`, `dep-audit` e `archify` |
| `README.md` | tabela de skills com quem pré-carrega cada uma; skills removidas; fluxo de bug |

**Decisões tomadas durante a execução:**
- No `fix-bug`, o teste de regressão é escrito pelo `test-writer`, não pelo stack agent que faz o fix: o teste nasce da evidência e do diagnóstico, independente da correção, como no TDD.
- O diagnóstico é uma fase só leitura do stack agent dono do código, e não da sessão principal, para manter a conversa principal enxuta.
- A `design-system` perdeu o "corrija ao longo do caminho mesmo sem relação com a task", que conflitava com a regra de escopo e com a validação visual pelo usuário.

**Validação feita nesta sessão:**
- Frontmatter dos arquivos novos e alterados, `settings.json` (JSON válido, sem `skillOverrides`, hooks e `ask` intactos), nenhum em dash, nenhuma referência às skills removidas.
- As skills reativadas apareceram na listagem da sessão logo após a mudança.
- Um teste real do `failure_kind` no `test-runner` não foi possível: o ambiente não tem `pytest`, e instalar dependências só para isso foi descartado.

**Pendências:**
- Cenários 8, 31 e 36 da seção 14.3 (fix-bug, tdd e implement --tdd) na sessão de validação, num projeto com runner de testes.
- Etapa G (bloqueio por categoria) depende dos dados do hook em uso real.

### Etapa G - 2026-11-10 (concluída; promoção de categorias pendente da rodada de testes)

**Decisão (conversa de 2026-11-10):** implementar a G antes da validação, dividindo por categoria: bloqueio só onde alarme falso é improvável por definição; o resto em aviso até os dados da rodada de testes.

**Arquivos (em `~/dotfiles/.claude/`):**

| Arquivo | Mudança |
|---|---|
| `hooks/agent-audit.py` | fase `PreToolUse` (síncrona) que decide pela categoria mais grave sinalizada: `block` (nega com o motivo e o que fazer: pedido de escopo no subagent, perguntar ao usuário na sessão principal, `manual_checks` para Docker), `ask` (o Claude Code pergunta ao usuário), `warn` (deixa passar e injeta um lembrete no contexto do agent), `audit` (só registra). Registra blocks e asks. Fail-open em qualquer erro. Modo `audit` desliga as decisões |
| `hooks/agent-audit.json` | modo `enforce` e a ação por categoria: `block` para `docker_lifecycle`, `write_by_readonly_agent` e `visual_tool`; `ask` para `git_commit` e `git_push`; `warn` para `out_of_scope_write`, `suite_by_non_runner`, `md_outside_docs`, `docs_write_by_implementer`, `backlog_write_by_other` e `external_request`; `audit` para `docker_build` |
| `hooks/agent-metrics.py` | seção "Enforcement decisions" por decisão e categoria, com a regra de promoção (sem falso positivo -> `block`) |
| `settings.json` | `PreToolUse` para Bash, escritas e só as ferramentas MCP de browser e screenshot (para não pagar a latência em toda chamada MCP) |
| `skills/implementer-contract/SKILL.md`, `CLAUDE.md` (global) | chamada negada pelo hook nunca é repetida nem contornada; seguir a mensagem; commit e push passam por confirmação mesmo depois de autorizados |
| `README.md` | gravação x enforcement, política atual e a lacuna das regras de permissão agora coberta |

**Validação feita nesta sessão:**
- 10 casos pelo stdin: Docker `-f`/`rtk` de agent e da sessão principal bloqueados; `git commit` vira confirmação; escrita do `ui-verifier` bloqueada; screenshot de implementer bloqueado e do `ui-verifier` liberado; escrita fora do escopo com aviso; escrita no escopo, teste específico e entrada inválida passam em silêncio; modo `audit` silencioso.
- Latência da fase síncrona: cerca de 50 ms por chamada (Bash, escrita com run ativo, MCP).
- Ao vivo: `docker compose -f /nonexistent-compose-file.yml restart none`, que as regras de permissão não pegam, foi negado pelo hook com a mensagem esperada, e a decisão apareceu no relatório.

**Decisões tomadas durante a execução:**
- Commit e push ficaram em `ask`, e não em `block`: o hook não sabe se o usuário autorizou na conversa, então quem decide é o prompt do Claude Code. Na prática, uma confirmação dupla.
- `warn` usa `additionalContext` no `PreToolUse` para lembrar o agent; a ação continua e o `PostToolUse` a registra com os sinais.

**Pendências:**
- Rodada de testes (sessão de validação): cenários da seção 14.3 e o relatório `agent-metrics.py`. Com ele, promover a `block` as categorias em `warn` sem falso positivo (candidatas: `md_outside_docs`, `docs_write_by_implementer`, `backlog_write_by_other`).
- Confirmar no uso real que o lembrete de `warn` (`additionalContext` no `PreToolUse`) chega ao contexto do agent.

### Etapa H - 2026-11-11 (concluída; uso real pendente)

Spec: `~/dotfiles/.claude/docs/features/design-director/spec.md`; log: `log.md` na mesma pasta. Sete tasks, quatro correções de review (r1, r2, r4 e uma adição de escopo r3).

**O que foi feito (em `~/dotfiles/.claude/`):**

| Arquivo | Mudança |
|---|---|
| `agents/design-director.md` | **novo**: opus, effort alto, tools `Read`, `Grep`, `Glob`, `Write`, `Edit`, pré-carrega `design-system`; corpo em inglês com as rodadas (briefing, duas direções, `DESIGN_SYSTEM.md`), a lista de padrões a evitar, a fórmula de contraste (razões calculadas à mão, e o report diz isso) e o report YAML. Negado pelo hook, nunca repete: termina `blocked` com `hook-denied` e o estado do arquivo |
| `templates/project-root/DESIGN_SYSTEM.md` | comentário do topo (criação x manutenção), `Color` com light e dark sempre, seção nova `Layout concept` depois de `Principles`, `Font family` como subseção de `Type scale` com origem e licença |
| `skills/design-system/SKILL.md` | só manutenção; passo 1 com quatro situações (oferta do `design-director`, extração, valor proposto, nota para o próprio agent); sai o `frontend-design` |
| `templates/node-ts-react/CLAUDE.md`, `templates/react-native/CLAUDE.md` | linha 25: criação pelo `design-director`, manutenção pela `design-system` |
| `skills/new-project/SKILL.md` | passo 3.1: pergunta uma vez, só com serviço de UI (react ou react-native); sim chama o `design-director` depois de `PRD.md`, `CONSTRAINTS.md` e `Services`; não deixa as tabelas em branco |
| `CLAUDE.md` (global), `skills/implement/SKILL.md` | linha do Workflow e bullet de `scope_requests` com os três ramos (15.1) |
| `hooks/agent-audit.py`, `hooks/agent-audit.json`, `hooks/agent-metrics.py` | ver 15.1, 13.5 e 14.1 |
| `settings.json` | sai `frontend-design@claude-plugins-official` de `enabledPlugins` (uma linha) |
| `.gitignore` | `.claude/runs/` |
| `README.md` | agents, skills, parágrafo criação x manutenção, hooks, `.claude/docs/` |

**Verificação:** bateria pelo stdin com 119 checagens (H1-H28, G1-G11, 37 comandos C, D1-D10) e métricas M1-M5, todas passando; harnesses no scratchpad da sessão, que copiam os arquivos do hook sem tocar o hook vivo. *Adendo 2026-11-12:* esse harness avulso foi substituído pela suite versionada `claude-hooks` (`hooks/tests/`, feature `audit-hook-test-suite`), que reconstrói esses casos. `grep frontend-design` fora de `.claude/docs/` e deste documento sem ocorrências.

**Achados do review corrigidos:**
- r1: o `design-director` podia escrever fora do `DESIGN_SYSTEM.md` com só um aviso -> categoria `design_director_write_outside` em `block`; a regra da raiz virou regra por nome (monorepo e sistemas de arquivos que ignoram caixa); alvos de `approved_scope` no arquivo saem dos caminhos permitidos.
- r2: ramo de extração no passo 1 da `design-system` com formato fixo do pedido (`action: create`, `target: DESIGN_SYSTEM.md`, motivo `extraction of tokens in <files>`); redação de `approved_scope` no `implement` e no `CLAUDE.md` global com três ramos; agent distingue negação do hook (`blocked`) de aviso (segue); detecção de serviço de UI alinhada ao `new-project`.
- r4: textos do hook e das métricas sem a redação "raiz"; exemplo da seção `## design-director` usa `rel`, ou `path` quando não há `rel`.
- r3 (adição de escopo aprovada pelo usuário): `docs_roots` configurável no hook (13.5).

**Mudança de pasta de docs:** a pasta `docs/` desta config foi movida para `.claude/docs/` a pedido do usuário depois da r1, e não é ligada a `~/.claude`. Por isso a `docs_roots` e a nota em 13.5 sobre `project-docs` e `/implement`.

**Decisões tomadas durante a execução:**
- O `md_outside_docs` (`warn`) ao criar `agents/design-director.md` e o `out_of_scope_write` nas edições do template em paralelo são falsos positivos esperados (corrigido depois: o hook aceita a escrita que casa com qualquer task de `running_tasks`, além da `current_task`). *Adendo 2026-11-13:* o falso positivo do `md_outside_docs` em `agents/design-director.md` agora é coberto pela isenção de `.md` listado nos Files da task (M6; feature `audit-md-outside-docs`).
- Na época, todo heredoc no Bash tinha o corpo classificado como comandos (um corpo com `docker compose up` virava `docker_lifecycle`), e por isso os harnesses foram escritos com `Write` e rodados com `python3 -I`. Corrigido depois (bug `2026-11-11-audit-heredoc-docker-lifecycle`): o corpo é dado para `cat`/`tee`, `git commit -F -` e `gh ... --body-file -`, e continua classificado nos demais (13.6). O `Write` deixou de ser necessário para esses casos; um script gravado e executado depois continua fora do alcance do hook.

**Pendências:**
- Sessão nova do Claude Code (o agent só carrega nela): cenários 37-45 da seção 14.3, `/new-project` com perfil react e com perfil só backend, e o relatório `agent-metrics.py` com a seção `## design-director`.
- Promover a `design_system_write_by_other` a `block` só com os dados do uso real.

### Etapa I - 2026-11-13 (concluída; uso real pendente)

Spec: `~/dotfiles/.claude/docs/features/lua-agent/spec.md` (adendo de 2026-11-13, A1-A7, vale sobre o corpo); log: `log.md` na mesma pasta. Nove tasks, cinco rodadas de correção do hook (review de código e de segurança). Tasks de Markdown rodaram pelo `frontend-react`, porque o `lua` ainda não existia na sessão.

**O que foi feito (em `~/dotfiles/.claude/`):**

| Arquivo | Mudança |
|---|---|
| `agents/lua.md` | **novo**: sonnet, effort médio, pré-carrega `implementer-contract`, `design-system`, `neovim-plugin` e `lua-tui`; corpo em inglês com detecção de runtime e versão, comandos estreitos (`timeout 60 nvim --headless` com o `minimal_init` do projeto), política de UI com `manual_checks`, fase `scaffold` e extras do report |
| `skills/neovim-plugin/SKILL.md`, `skills/lua-tui/SKILL.md` | **novas**, sem `user-invocable: false`, dentro dos limites S10 |
| `skills/implementer-contract/SKILL.md`, `skills/design-system/SKILL.md` | `lua` nas descriptions; seção 5 do contract vale para Neovim e terminal; bullet S9 na `design-system` |
| `skills/implement/SKILL.md`, `agents/specker.md`, `templates/docs-structure/features/_template/spec.md` | `Stack: lua` e inferência por marcadores (`*.rockspec`, `.luarc.json`, `stylua.toml`/`.stylua.toml`, `selene.toml`, `.luacheckrc`, `lua/` + `plugin/`); os arquivos da task vencem os marcadores do repo |
| `agents/test-runner.md` | tasks do mise como scripts do projeto; linha Lua na tabela de padrões; `minimal_init` ausente = `blocked`, nada criado |
| `agents/test-writer.md`, `skills/tdd/SKILL.md` | busted, plenary e mini.test; stub Lua com valor vazio do tipo certo (ver adendo de 15.2) |
| `skills/onboard/SKILL.md`, `templates/onboarding/LUA.md` | reconhece unidades Lua sem pastas de serviço; um só `LUA.md` na raiz com um bloco por unidade; `Local runtime` só com serviço (OpenResty) |
| `hooks/agent-audit.py`, `hooks/agent-audit.json` | `lua` em `IMPLEMENTERS`; comandos Lua, `timeout`, `mise exec|x` e shell escapes do Neovim; categorias `command_too_long` e `analysis_timeout` em `block` (13.6, adendo) |
| `hooks/tests/test_classify.py`, `test_hook_main.py`, `test_hook_process.py`, `_support.py`, `test_config_contract.py` | casos L1-L25, LR1-LR13, LE1-LE7, cap de tamanho, guarda de tempo e ordem decisão-antes-do-registro; suite com 317 testes |
| `README.md` | agents, skills, hook (comandos Lua, prefixos, categorias novas), `onboarding/`, contagem de testes |

**Verificação:** suite `claude-hooks` com 317 testes passando (264 após a task 1; 268, 272, 286, 310 e 317 após cada rodada de correção); frontmatters válidos; `agents/lua.md` com 4.591 bytes (faixa S10); nenhum em dash nos arquivos tocados. Cenários 46-55 da seção 14.3 ainda não rodados em sessão nova.

**Achados do review corrigidos (cinco rodadas, todas na task 1, `backend-python`):**
- r1: parser do `timeout` reescrito como parse GNU estrito com leitura de fallback que falha fechada; flags globais do mise; shell escapes do Neovim classificados; formas `test_harness` e `require"mini.test"`; `luarocks [flags] test`.
- r2: regressão de tempo no `_NUM` (token de dígitos longo passava de 10 s, e o hook falha aberto); espaço em branco de `strtod`; floats hexadecimais; variantes de leitura do `timeout`; aninhamento de shell escape acima de 3 níveis falha fechado.
- r3: opções com valor (`-s`, `-k`, `--signal`, `--kill-after`) seguidas de duração ilegível; cache do trabalho de nvim; cap de 16384 caracteres (`command_too_long`, aprovado pelo usuário); `SEGMENT_SPLIT` linear.
- r4: guarda de 7 s (`analysis_timeout`, aprovada pelo usuário); veredito de sink de heredoc calculado uma vez e limite de 32 abridores; regex do nvim sem ambiguidade; `NARROW_HINT` dividido (token de nome de arquivo acima de 512 caracteres é `test-full`).
- r5 (estreita): `AGENT_AUDIT_ANALYSIS_TIMEOUT` só baixa o limite e valores não finitos são rejeitados; a decisão é impressa antes de gravar o registro.

**Decisões tomadas durante a execução:**
- Stub Lua com valor vazio em vez de `error("not implemented")` (decisão do usuário; adendo de 15.2).
- S6 vale para todas as stacks: `timeout 5 git push` é `git-push`.
- Um guarda contra programas interativos no hook (`nvim` sem `--headless`, `love`, apps hospedeiros) ficou fora da spec e foi registrado como refactor no backlog; decide-se com os dados da métrica de 14.2.
- Limites conhecidos do hook, levados ao backlog (a maior parte para uma spec dedicada de endurecimento): trabalho pós-decisão do hook, sink de heredoc após `)`, `nvim -l ... --busted`, `SEGMENT_SPLIT` cego a aspas, `mise exec -c`, binários não Lua por caminho, `exe "!..."`, `system()`, `os.execute`, `io.popen`, `jobstart` e `:terminal`.

**Pendências:**
- Sessão nova do Claude Code (agents e skills novos só aparecem nela): cenários 46-55 da seção 14.3 num plugin Neovim com busted e luacheck, numa TUI de teste (com e sem `DESIGN_SYSTEM.md`) e numa config embarcada; relatório `agent-metrics.py` com a métrica nova de 14.2.
- Medir tokens por task com quatro skills pré-carregadas contra o baseline (riscos de 15.2).
