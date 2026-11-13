# audit-hook-test-suite - suite versionada do hook agent-audit

- **Date:** 2026-11-12
- **Status:** Implemented
- **Source:** [docs/backlog/refactor/2026-11-11-audit-hook-test-suite.md](../../backlog/refactor/2026-11-11-audit-hook-test-suite.md) (refactor sem plan; não há `plan.md` nesta pasta)
- **Implementation log:** [log.md](log.md) (criado pelo `/implement` na primeira task)

## Summary

Transforma os checks avulsos do hook de enforcement (casos H, G, C, D e M, que viviam num harness pelo stdin no scratchpad de uma sessão e se perderam) numa suite versionada em `.claude/hooks/tests/`, ao lado dos 82 testes que já existem. Só muda código de teste; o hook, o config e as métricas ficam intactos.

| Camada | Arquivos | Mudança |
|---|---|---|
| Base da suite | `hooks/tests/__init__.py`, `hooks/tests/_support.py` (novo) | ambiente hermético (métricas, git, scratch), fixtures compartilhadas, chamada do `main()` em processo e do hook como processo real |
| Testes existentes | `hooks/tests/test_agent_audit.py` -> `test_heredoc.py` + `test_write_scope.py` | divididos por unidade, sem mudar nenhum teste; corrigida a dependência do `TMPDIR` |
| Testes novos | `test_classify.py`, `test_write_areas.py`, `test_decide.py`, `test_hook_main.py`, `test_design_system.py`, `test_hook_process.py`, `test_config_contract.py`, `test_agent_metrics.py` | classificação de comandos, áreas de escrita e `docs_roots`, decisão do `PreToolUse`, eventos e modos, regras do `DESIGN_SYSTEM.md`, contrato stdin/stdout/exit, coerência do config e do `settings.json`, relatório de métricas |
| Docs (fim, `docs-writer`) | `/home/void/dotfiles/CLAUDE.md` (novo, raiz do repo) | seção `## Test suites` com a suite `claude-hooks` (Verification, needs_docs) |

Framework: **stdlib `unittest`** (decisão em Alternatives considered). Não há serviço, API, banco, flag nem migração.

## Background

**O que a entrada pede e o que mudou desde então.** A entrada diz que a suite em `.claude/hooks/tests/` "cobre só o heredoc". Está desatualizada: o commit `a7e66c0` ("fix bugs") trouxe `test_agent_audit.py` (~40 KB, 82 testes, todos verdes em 2026-11-12, 0,5 s), que cobre:

| Classe | Testes | O que cobre |
|---|---|---|
| `HeredocBodyIsData`, `HeredocOpenerStillClassified`, `NotAHeredoc`, `DataSinkHeredocsAreStripped`, `BodyKeptUnlessDataSink`, `FailSafeStripsNothing`, `TerminatorSemantics`, `ScannerFallback`, `SubstitutionOnlyDataAsMessageValue`, `StdinFileSinkLimits`, `QuotesAndTopLevel`, `FailSafeMarkersAnywhere` | 22 (com muitos `subTest`) | `strip_heredoc_bodies` / `classify_command` com heredoc (bug `2026-11-11-audit-heredoc-docker-lifecycle`) |
| `ParallelTasksScope` | 23 | `running_tasks`, `run_task_keys`, `approved_scope` por task, tag do `SubagentStart` (bug `2026-11-11-audit-parallel-task-out-of-scope`) |
| `OutsideRepoWrites`, `OutsideRepoHardening` | 37 | escritas fora da raiz git, symlinks, `~`, `..`, repo aninhado, scratch, erro de resolução (bug `2026-11-11-audit-path-checks-outside-git-root`) |

**Lacunas reais** (nenhum teste versionado): a classificação de comandos sem heredoc (os 37 casos C), as flags de área dentro do repo (`md_outside_docs`, `docs_write_by_implementer`, `backlog_write_by_other`), `docs_roots()` (D1-D10), o escopo dentro do repo (`ALWAYS_ALLOWED`, run mais recente, `matches()`), as regras do `DESIGN_SYSTEM.md` dentro do repo (H1-H28), `decide()` e `what_to_do()`, o `main()` (modos, eventos, ator, `suite_by_non_runner`, ferramenta visual, privacidade do registro), o contrato do processo (G1-G11, exit 0, fail-open), a coerência entre `agent-audit.json`, `WHY`, `FLAG_LABELS` e `settings.json`, e todo o `agent-metrics.py` (M1-M5).

**Casos reconstruídos.** O harness do scratchpad (`harness.py`, 119 checks; `harness_m.py`, 9) não existe mais. Os casos foram reconstruídos da [spec do design-director](../design-director/spec.md) (seção Testing: tabelas H1-H28, M1-M5, G1-G11 e os 37 comandos C), do [log](../design-director/log.md) ("Added scope r3": regras de `docs_roots` que geraram D1-D10, sem tabela publicada) e do código atual. Todos os esperados de H, C e as regras de `decide()` foram conferidos contra o código em 2026-11-12, em processo, num repo temporário: batem com as tabelas.

**Defeito de ambiente na suite atual.** Com `TMPDIR` dentro de um diretório `/tmp/claude-*` (o que acontece quando um agent roda com o scratchpad como temp), 14 dos 82 testes falham: os diretórios "de fora" que os testes criam ficam sob `/tmp/claude-*`, e `is_scratch()` os trata como scratchpad (base literal `/tmp` em `SCRATCH_BASES`). A premissa do teste ("um diretório que não é scratch") é falsa nesse ambiente. Reproduzido com `TMPDIR=<scratchpad>/tmpprobe python3 -m unittest discover -s tests -t .` (14 failures). A task 1 corrige isso no teste, sem mexer no hook.

**Regras que o hook aplica** (fonte: `~/.claude/CLAUDE.md` global e [agent-workflow.md, seções 13 e 14](../../../agent-workflow.md)): commit e push só com autorização; o usuário é dono dos containers; ferramentas visuais só no `ui-verifier`; agents read-only não escrevem; escopo do run (`allowed_paths`, `approved_scope`); suites só pelo `test-runner`; docs só pelo `docs-writer` e nada de `.md` solto; `backlog/` só pelo `backlog-keeper`; `DESIGN_SYSTEM.md` criado pelo `design-director` e mantido pela sessão principal; requests só para hosts locais; o hook nunca quebra uma sessão (fail-open); nada de conteúdo guardado no registro. Em Testing, cada uma vira pelo menos um teste.

**Não existe tabela `Test suites`.** `/home/void/dotfiles` não tem `CLAUDE.md` na raiz, e `/home/void/dotfiles/.claude/CLAUDE.md` é o `~/.claude/CLAUDE.md` global (symlink): uma tabela ali vazaria para todos os projetos. A tabela vai num `CLAUDE.md` novo na raiz do repo (Verification).

## Design

### 1. Princípios da suite

| Princípio | Como |
|---|---|
| Hermética | nenhum teste escreve em `~/.claude/metrics`, lê o config vivo (exceto o teste de contrato, só leitura), depende de `TMPDIR`, de `GIT_*` do ambiente ou do `HOME` |
| Mecanismo x política | os testes de mecanismo usam um config fixo (`TEST_CONFIG`); só `test_config_contract.py` lê `agent-audit.json` e `settings.json` vivos, e checa pisos, não valores exatos, para que uma promoção `warn` -> `block` não quebre a suite |
| Premissas explícitas | toda fixture que depende de uma condição do ambiente (diretório sem raiz git, diretório que não é scratch) afirma a condição antes do teste, com mensagem clara |
| Comportamento pretendido | um teste fixa o comportamento atual só quando ele é o pretendido. Bugs abertos não viram teste; comportamentos aceitos com entrada de refactor aberta são marcados (seção 5) |
| Nada é executado | comandos como `docker compose up` e `git push` são só strings; os únicos processos são `git init`, `git rev-parse` (do próprio hook) e a cópia do hook |
| Rápida | em processo por padrão; processo real só para o contrato stdin/stdout/exit. Meta: suite inteira < 5 s |

Requisitos: Python >= 3.13 (o hook usa `PurePosixPath.full_match`; as duas máquinas têm 3.14), `git` no `PATH`, Linux (symlinks). Comando sempre com `-I -B`: isola de `PYTHON*` e do site do usuário e não gera `__pycache__` no repo.

### 2. `hooks/tests/__init__.py`

Hoje vazio. Passa a preparar o ambiente antes de qualquer `load_hook`, porque `METRICS_DIR` é lido do ambiente na importação do módulo:

- `os.environ["AGENT_AUDIT_DIR"] = tempfile.mkdtemp(prefix="agent-audit-tests-metrics-")`, removido no `atexit`. Um teste que esqueça de redirecionar as métricas escreve ali, nunca em `~/.claude/metrics`.
- Remove do `os.environ` `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_COMMON_DIR`, `GIT_OBJECT_DIRECTORY` e `GIT_CEILING_DIRECTORIES`, para que `git_root()` dependa só do caminho (a suite pode rodar de dentro de um git hook).

### 3. `hooks/tests/_support.py` (novo)

Toda a infraestrutura compartilhada fica aqui, escrita na task 1, para que as tasks 2-7 não editem o mesmo arquivo (podem rodar em paralelo). Uma task que precise de um helper novo o define no próprio módulo de teste. API:

| Nome | Contrato |
|---|---|
| `audit`, `metrics` | `load_hook("agent-audit.py", "agent_audit")` e `load_hook("agent-metrics.py", "agent_metrics")` |
| `HOOKS_DIR`, `CLAUDE_DIR` | `.claude/hooks/` e `.claude/` (de `_loader.HOOKS_DIR`) |
| `TEST_CONFIG` | dict literal: `mode: "enforce"`, `docs_roots: ["docs/", ".claude/docs/"]` e as 14 categorias com as ações vigentes em 2026-11-12 (block: `docker_lifecycle`, `write_by_readonly_agent`, `visual_tool`, `design_director_write_outside`; ask: `git_commit`, `git_push`; audit: `docker_build`; warn: as outras 7). Nunca lido do arquivo vivo. `config(**overrides)` devolve uma cópia profunda com mudanças |
| `assert_not_scratch(path)`, `assert_no_git_root(path)` | falham com mensagem "premissa do ambiente: ..." |
| `TempRepoCase(unittest.TestCase)` | o atual, movido de `test_agent_audit.py` com a mesma semântica (`ALLOWED`, `write_run(**extra)`, `make_dir(prefix, git)`, `eval_at(target, actor, cwd)`, `evaluate(rel, actor)`), mais: `remove_run()`; `make_dir()` chama `assert_not_scratch` e, com `git=False`, `assert_no_git_root`; no `setUp`, `mock.patch.object(audit, "SCRATCH_BASES", ())` enquanto o atributo de classe `REAL_SCRATCH_BASES` for `False` (padrão), e o método `use_real_scratch_bases()` desfaz o patch para os testes que verificam o próprio scratch |
| `payload(event, tool=None, *, actor="main", cwd, session="t", tool_input=None, tool_response=None)` | monta o JSON do hook: `actor="main"` sem `agent_type`/`agent_id`; `"subagent"` só com `agent_id`; outro nome com os dois |
| `call_main(payload, config=TEST_CONFIG) -> HookResult` | roda `audit.main()` em processo com `load_config` e `METRICS_DIR` (diretório temporário próprio) trocados por `mock.patch.object`, `sys.stdin` em `StringIO` e `stdout` capturado; `HookResult(output: dict | None, records: list[dict])`, com `output` = o JSON impresso (ou `None`) e `records` = as linhas gravadas nessa chamada |
| `HookProcess(tmp: Path, config=TEST_CONFIG)` | copia `agent-audit.py` (e `agent-metrics.py`) para `tmp/hook/` e escreve `tmp/hook/agent-audit.json` a partir do dict (`config=None`: sem arquivo; `str`: conteúdo cru, para JSON inválido). `run(stdin: dict | str, cwd) -> CompletedProcess`: `[sys.executable, "-I", "-B", <cópia>]`, `input` = JSON ou texto cru, `timeout=10` (o mesmo do `settings.json`), env mínimo `{PATH, HOME=<tmp/home>, AGENT_AUDIT_DIR=<tmp/metrics>, LANG=C.UTF-8, GIT_CONFIG_NOSYSTEM=1}`. `records(session)` lê o JSONL |
| `read_jsonl(path)` | lista de dicts; arquivo ausente -> `[]` |

### 4. Módulos de teste

Testes table-driven usam `subTest` com o id do caso (`with self.subTest(case="C12")`), para que a falha aponte a linha da tabela de Testing. Docstring de cada classe cita a fonte (seção da spec, bug ou entrada de backlog), como os testes atuais.

| Módulo | Classes | Unidade |
|---|---|---|
| `test_heredoc.py` | as 12 classes de heredoc atuais, sem mudança de código além do import de `_support` | `strip_heredoc_bodies`, `classify_command` |
| `test_write_scope.py` | `ParallelTasksScope`, `OutsideRepoWrites`, `OutsideRepoHardening` (movidas), `InRepoScope` (nova, S1-S11) | `evaluate_write` (escopo), `active_run`, `run_task_keys`, `matches`, `is_scratch` |
| `test_classify.py` | `CommandTable` (C1-C37), `PrefixesAndSegments` (X1-X14) | `classify_command`, `strip_prefixes` |
| `test_write_areas.py` | `AreaFlags` (A1-A9), `DocsRoots` (D1-D11) | `evaluate_write` (áreas), `docs_roots` |
| `test_decide.py` | `Decide` (K1-K12) | `decide`, `what_to_do`, `SEVERITY`, `WHY` |
| `test_hook_main.py` | `Modes`, `Events`, `Actor`, `BashRecords`, `Visual`, `WriteRecords`, `MetricsFile` (E1-E16) | `main` em processo |
| `test_design_system.py` | `DesignSystemRules` (H1-H28) | `main` em processo (`PreToolUse` + `PostToolUse`) |
| `test_hook_process.py` | `StageGRegression` (G1-G11), `ProcessContract` (P1-P6) | o hook como processo real, sobre a cópia |
| `test_config_contract.py` | `ConfigContract` (F1-F6) | `agent-audit.json`, `WHY`, `FLAG_LABELS`, `settings.json` |
| `test_agent_metrics.py` | `DesignDirectorSection` (M1-M5), `ReportSections` (R1-R9), `Cli` (L1-L7) | `load`, `report`, `main` do `agent-metrics.py` |

`test_agent_audit.py` deixa de existir (o conteúdo vai para `test_heredoc.py` e `test_write_scope.py`). Os nomes `Classe.método` dos 82 testes não mudam; só o módulo.

### 5. Testes que fixam comportamento com entrada aberta no backlog

Esses testes fixam o comportamento aceito hoje. Quando a entrada for resolvida, o teste muda junto, na mesma mudança. A docstring de cada um cita a entrada.

| Entrada | Testes afetados |
|---|---|
| [refactor scratch-exemption-too-broad](../../backlog/refactor/2026-11-11-audit-scratch-exemption-too-broad.md) | `test_scratchpad_under_tmp_claude_dir_is_allowed`, `test_literal_tmp_claude_dir_is_scratch_even_if_tempdir_differs` |
| [refactor nested-repo-run-lookup](../../backlog/refactor/2026-11-11-audit-nested-repo-run-lookup.md) | `test_nested_repo_*` de `OutsideRepoHardening` |
| [refactor md-outside-docs-false-positive](../../backlog/refactor/2026-11-11-audit-md-outside-docs-false-positive.md) | H14, A1 |

Bugs abertos que **não** viram teste (nenhum teste afirma o comportamento errado; o `fix-bug` escreve o teste de regressão quando corrigir): [audit-dev-tcp-egress](../../backlog/bugs/2026-11-11-audit-dev-tcp-egress.md) (`/dev/tcp` não é `external_request`) e [audit-hook-self-protection](../../backlog/bugs/2026-11-11-audit-hook-self-protection.md) (escrita em `hooks/` e `agents/` sem flag).

### 6. Segurança, privacidade e observabilidade

- Os testes não guardam nem imprimem conteúdo real de sessão; payloads são sintéticos.
- E11 fixa a regra de privacidade do hook: o registro guarda o comando truncado em `MAX_CMD` (300) e caminhos, nunca `tool_input.content`, `new_string` ou `tool_response`.
- Observabilidade: não se aplica (sem runtime novo). A saída do `unittest -v` com os ids de `subTest` é o diagnóstico.

### 7. Rollout e reversão

Sem flag. Cada task é um commit revertível isolado; reverter qualquer uma não afeta o hook vivo, porque nenhum arquivo fora de `.claude/hooks/tests/` muda. O `__pycache__` não é gerado (`-B`).

## Alternatives considered

### Framework

| Opção | Corretude e robustez | Simplicidade e manutenção | Decisão |
|---|---|---|---|
| **stdlib `unittest`** | `subTest`, `mock`, `addCleanup` cobrem tudo o que a suite precisa; roda com o mesmo `python3` do sistema que executa o hook | zero dependência; funciona logo depois do bootstrap do dotfiles nas duas máquinas; os 82 testes já são `unittest`; o `pytest`, se um dia for instalado, roda esta suite sem mudança | **escolhida** |
| `pytest` pelo pacote do sistema (`xbps-install python3-pytest`) | `parametrize`, fixtures (`tmp_path`, `monkeypatch`) e diffs de asserção melhores | dependência de sistema a mais no bootstrap das duas máquinas; exige instalação que só o usuário faz; a seção 11.4 do `agent-workflow.md` diz que nenhum agent adiciona um framework que o projeto não tem | rejeitada |
| `pytest` num venv do repo | idem | `pip`/`uv` não estão instalados; um venv versionável é infraestrutura nova para uma suite stdlib | rejeitada |

O título da entrada diz "pytest suite"; a decisão acima troca o meio, não o objetivo (suite versionada). A entrada deve ser renomeada pelo `backlog-keeper` (Open questions, 1).

### Organização

| Opção | Por que não |
|---|---|
| Um arquivo só (`test_agent_audit.py` crescendo para ~150 KB) | difícil de navegar e revisar; tasks paralelas brigariam pelo mesmo arquivo |
| Só caixa-preta pelo stdin, como o harness antigo | lento (um processo por caso, ~300 casos), sem acesso a `decide()`/`docs_roots()` isolados e difícil de simular erros (`Path.resolve` levantando) |
| Só em processo | não prova o contrato real: exit 0, uma linha JSON no stdout, `CONFIG_PATH` ao lado do script, fail-open do `__main__` |
| **Misto** (escolhida) | em processo para a amplitude, processo real (sobre uma cópia, com config próprio) para o contrato |

### Config nos testes

| Opção | Por que não |
|---|---|
| Testes de mecanismo lendo o `agent-audit.json` vivo | toda promoção de categoria quebraria dezenas de testes sem regressão nenhuma |
| **`TEST_CONFIG` fixo + pisos no config vivo** (escolhida) | separa "o hook aplica a ação configurada" de "a política cumpre o `CLAUDE.md`" |

### Defeito do `TMPDIR`

| Opção | Por que não |
|---|---|
| Forçar `TMPDIR=/tmp` no comando da suite | esconde o problema e falha num sandbox que só deixa escrever no scratchpad |
| Procurar uma base fora de `/tmp/claude-*` subindo a árvore | precisa de escrita fora do scratchpad, que o sandbox pode negar |
| **Patch de `SCRATCH_BASES` para `()` nos testes de escopo + asserção da premissa** (escolhida) | o diretório de fora deixa de ser scratch por acidente, qualquer que seja o `TMPDIR`; os dois testes do próprio scratch usam as bases reais |

### Métricas

| Opção | Por que não |
|---|---|
| Golden file do relatório inteiro | quebra a cada mudança de rótulo ou ordem de seção, sem regressão |
| **Asserções por seção e por linha** (escolhida) | fixa o que importa (contagens, presença ou ausência de seção, exemplos) |

## Trade-offs

- **`SCRATCH_BASES` trocado nos testes de escopo**: esses testes não exercitam a base literal `/tmp`; ela fica coberta só pelo `test_literal_tmp_claude_dir_is_scratch_even_if_tempdir_differs`, que usa as bases reais e pula quando `/tmp` não é gravável.
- **Pisos, não valores, no config vivo**: uma regressão de `block` para `warn` numa categoria sem piso (ex.: `out_of_scope_write`) não quebra a suite. Aceito: os pisos são as regras explícitas do `CLAUDE.md`; o resto é política ajustada pelos dados (seção 13.3).
- **Python >= 3.13 e Linux**: a suite não roda em versões antigas nem em sistemas sem symlink. Aceito: é o ambiente do hook.
- **Dependência do `git`**: a raiz do repo vem do `git rev-parse`; sem `git`, os testes de escrita falham. Aceito: o hook tem a mesma dependência.
- **Cópia do hook nos testes de processo**: testa o código atual com config próprio, mas não o caminho `$HOME/.claude/hooks/agent-audit.py` do `settings.json`; F5 cobre o registro do comando.
- **Comportamentos aceitos fixados** (seção 5): quem resolver as entradas de refactor precisa mudar os testes junto; a docstring aponta a entrada.

## Testing

Suite: `claude-hooks` (tabela proposta em Verification). "pre" = saída do `PreToolUse` em `enforce` com `TEST_CONFIG`; "silencioso" = nenhuma saída; "warn X" = `additionalContext` com `Reminder from the agent workflow (X)`; "deny/ask X" = `permissionDecision` com `Agent workflow (X)`; "flags" = as do registro do `PostToolUse` com o mesmo payload.

### `test_heredoc.py` e `test_write_scope.py` (movidos)

Os 82 testes atuais, com os mesmos nomes. Critério: o conjunto de `Classe.método` antes e depois é idêntico, e todos passam também com `TMPDIR` dentro de um diretório `claude-*`.

### `test_write_scope.py` - `InRepoScope` (novo)

Run ativo com `allowed_paths {"1": ["services/api/**"]}`, ator `backend-node` salvo indicação.

| # | Caso | Esperado |
|---|---|---|
| S1 | escrita em `services/api/x.py` | `in_scope: True`, sem `out_of_scope_write`, `area: code`, `run: feat-x`, `task: "1"` |
| S2 | escrita em `services/web/x.ts` | `out_of_scope_write`, `in_scope: False` |
| S3 | `ALWAYS_ALLOWED` fora dos `allowed_paths`: `services/web/package-lock.json`, `go.sum`, `services/x/migrations/001.sql`, `db/migrate/1.rb`, `alembic/versions/a.py`, `src/__snapshots__/a.snap`, `a.snap` | sem `out_of_scope_write` (um `subTest` por caminho) |
| S4 | `quality-fixer` e `test-writer` em `services/web/x.ts` | `out_of_scope_write` |
| S5 | `main`, `docs-writer`, `planner` em `services/web/x.ts` | sem `out_of_scope_write` e sem a chave `in_scope` |
| S6 | sem pasta `runs/`; só um run com `phase: done` | `in_run: False`, sem flag de escopo |
| S7 | dois runs ativos com `os.utime` diferentes | vale o mais recente; `run` é o nome do arquivo sem `.json` |
| S8 | um run com JSON inválido ao lado de um válido | o inválido é ignorado, o válido vale |
| S9 | `approved_scope` sem `decision` | vale como aprovado |
| S10 | `matches()`: padrão sem glob `services/api` cobre `services/api/x.py`; padrão entre crases funciona; padrões vazios são ignorados; `services/api/**` não cobre `services/apix/a` | como descrito |
| S11 | `matches()` com `PurePosixPath.full_match` levantando (patch) | cai no fallback por prefixo: `services/api/x.py` casa com `services/api/**` |

### `test_classify.py`

`CommandTable`: os 37 comandos da [spec do design-director, Casos C](../design-director/spec.md), um `subTest` cada, comparando `classify_command(cmd)` com `(categorias, flags)`:

| # | Comando | Categorias | Flags |
|---|---|---|---|
| C1 | `pytest tests/test_orders.py` | test-narrow | - |
| C2 | `pytest -k export` | test-narrow | - |
| C3 | `pytest` | test-full | - |
| C4 | `go test ./internal/orders/` | test-package | - |
| C5 | `go test ./...` | test-full | - |
| C6 | `go test -run TestExport ./internal/orders` | test-narrow | - |
| C7 | `cargo test` | test-full | - |
| C8 | `cargo test -p orders` | test-package | - |
| C9 | `npx vitest run src/a.test.ts` | test-narrow | - |
| C10 | `pnpm exec vitest run src/a.test.ts` | test-narrow | - |
| C11 | `pnpm vitest run` | test-full | - |
| C12 | `pnpm --filter api test` | test-package | - |
| C13 | `pnpm -r test` | test-full | - |
| C14 | `npm test` | test-full | - |
| C15 | `rtk pnpm test` | test-full | - |
| C16 | `./mvnw test -Dtest=OrderTest` | test-narrow | - |
| C17 | `./gradlew :api:test` | test-package | - |
| C18 | `uv run pytest tests/test_x.py::test_y` | test-narrow | - |
| C19 | `k6 run load.js` | test-load | - |
| C20 | `eslint src/a.ts` | lint | - |
| C21 | `pnpm lint` | lint | - |
| C22 | `ruff check .` | lint | - |
| C23 | `tsc --noEmit` | typecheck | - |
| C24 | `pnpm typecheck` | typecheck | - |
| C25 | `uv run mypy src` | typecheck | - |
| C26 | `docker compose ps` | docker-read | - |
| C27 | `docker compose -f x.yml up -d` | docker-lifecycle | docker_lifecycle |
| C28 | `rtk docker compose restart api` | docker-lifecycle | docker_lifecycle |
| C29 | `docker build -t x .` | docker-build | docker_build |
| C30 | `docker logs api --since 2m` | docker-read | - |
| C31 | `git status` | git-other | - |
| C32 | `git commit -m x` | git-commit | git_commit |
| C33 | `git push origin main` | git-push | git_push |
| C34 | `curl -s http://localhost:3000/health` | request-local | - |
| C35 | `curl -s http://api:3000/orders` | request-local | - |
| C36 | `curl https://example.com/x` | request-external | external_request |
| C37 | `cd /tmp && ls` | other | - |

`PrefixesAndSegments` (conferidos no código em 2026-11-12):

| # | Comando | Categorias | Flags |
|---|---|---|---|
| X1 | `sudo docker restart api` | docker-lifecycle | docker_lifecycle |
| X2 | `docker-compose up` | docker-lifecycle | docker_lifecycle |
| X3 | `docker compose -p p --profile dev up` | docker-lifecycle | docker_lifecycle |
| X4 | `docker compose --env-file .env logs api` | docker-read | - |
| X5 | `docker compose build api`, `docker buildx build .` | docker-build | docker_build |
| X6 | `docker compose exec api sh` | docker-lifecycle | docker_lifecycle |
| X7 | `docker version` | docker-other | - |
| X8 | `git -C repo commit -m x` | git-commit | git_commit |
| X9 | `git add . && git commit -m x && git push` | git-commit, git-other, git-push | git_commit, git_push |
| X10 | `curl http://localhost:3000 https://example.com` | request-external | external_request |
| X11 | `curl -s http://[::1]:8080/x`, `wget http://0.0.0.0/`, `http :3000/x`, `curl -s` | request-local | - |
| X12 | `go test ./... -run X` (o hint full vence o narrow) | test-full | - |
| X13 | `time FOO=1 rtk proxy pytest tests/test_a.py`; `yarn jest src/a.test.ts` | test-narrow | - |
| X14 | `""` e `None` | other | - |

### `test_write_areas.py`

`AreaFlags`, repo temporário sem run, raízes `["docs/", ".claude/docs/"]` passadas a `evaluate_write`:

| # | Caso | Esperado |
|---|---|---|
| A1 | `main`, Write `notes.md` na raiz | `md_outside_docs`, `area: code` (fixado; ver seção 5) |
| A2 | `main`, Edit `notes.md` sem `tool_response.type: create` | nenhuma flag |
| A3 | Write `README.md`, `services/api/README.md`, `CLAUDE.md`, `CHANGELOG.md` | sem `md_outside_docs` |
| A4 | Write `docs/x.md` e `.claude/docs/x.md` | `area: docs`, sem `md_outside_docs` |
| A5 | Write `services/api/x.py` | sem `md_outside_docs` |
| A6 | `backend-node` em `docs/x.md`, `services/api/README.md`, `.env.example`, `DEPLOY.md`, `CHANGELOG.md`; `docs-writer` e `main` nos mesmos | `docs_write_by_implementer` só para o `backend-node` |
| A7 | `docs/backlog/bugs/x.md` por `backend-node`, `docs-writer`, `main`; por `backlog-keeper` e `unknown` | `backlog_write_by_other` só para os três primeiros |
| A8 | `.claude/runs/x.json` | `area: run-state` |
| A9 | registro sem run | `rel` relativo à raiz, `in_run: False`, sem `run`/`task` |

`DocsRoots` (D1-D7 em `docs_roots()`, D8-D11 em `evaluate_write`/`main`):

| # | Entrada | Esperado |
|---|---|---|
| D1 | config sem `docs_roots` | `["docs/"]` |
| D2 | `docs_roots: "docs"` (não é lista) | `["docs/"]` |
| D3 | `docs_roots: []` | `["docs/"]` |
| D4 | só entradas inválidas: `3`, `""`, `"."`, `".."`, `"a/../b"`, `None` | `["docs/"]` |
| D5 | `" ./x\\y/ "`, `"/z"`, `"kb"` | `["x/y/", "z/", "kb/"]` |
| D6 | `["docs", "docs/", "./docs/"]` | `["docs/"]` (sem duplicata) |
| D7 | `["b/", "a/"]` | ordem preservada |
| D8 | `.claude/docs/features/x.md` com as duas raízes | `area: docs`, sem `md_outside_docs` |
| D9 | `.claude/docs/backlog/refactor/x.md` por `specker`; por `backlog-keeper` | `backlog_write_by_other` só para o `specker` |
| D10 | `services/x/docs/a.md` (aninhado); `.claude/docs/a.md` com as raízes padrão (`None`) | os dois `area: code` e `md_outside_docs` |
| D11 | `main()` com `TEST_CONFIG` + `docs_roots: ["kb/"]`, Write `kb/a.md`; e com `docs_roots: 7` | `kb/a.md` sem `md_outside_docs`; com valor inválido, `kb/a.md` ganha `md_outside_docs` (fallback `docs/`) |

### `test_decide.py`

| # | Caso | Esperado |
|---|---|---|
| K1 | `flags: []` | `None`; registro sem `decision` |
| K2 | só `docker_build` (`audit`) | `None` |
| K3 | flag que não está no config | `None` (fail-open) |
| K4 | ação desconhecida no config (`"bogus"`) | `None` |
| K5 | `block` | `permissionDecision: deny`; razão `Agent workflow (<cat>): <WHY>. <what_to_do>`; `record["decision"]`, `record["decision_category"]` preenchidos |
| K6 | `ask` | `permissionDecision: ask`; razão sem o texto de `what_to_do` |
| K7 | `warn` | só `additionalContext`, sem `permissionDecision` |
| K8 | `warn` + `block` em qualquer ordem | `block` vence |
| K9 | duas `warn`, ordens diferentes | vence a primeira da lista (o `main()` ordena as flags; H5 fixa o resultado alfabético) |
| K10 | `what_to_do`: `docker_lifecycle` e `visual_tool` (qualquer ator); `main` em outra categoria; subagent em outra categoria | `manual_checks`; `manual_checks` + `ui-verifier`; "Explain to the user..."; "Do not retry ... scope_requests" |
| K11 | config sem `categories` | `None` |
| K12 | para cada chave de `WHY`, config com essa categoria em `block` | a razão contém o texto de `WHY` |

### `test_hook_main.py`

Tudo por `call_main`.

| # | Caso | Esperado |
|---|---|---|
| E1 | `mode: off`, `PreToolUse` com `docker compose up` e `PostToolUse` com o mesmo | nenhuma saída, nenhum registro |
| E2 | `mode: audit`: `PreToolUse` e depois `PostToolUse` com `docker compose up` | `PreToolUse` silencioso e sem registro; `PostToolUse` grava `flags: [docker_lifecycle]` |
| E3 | `enforce`, `PreToolUse` sem flag (`ls`) | nenhuma saída, nenhum registro |
| E4 | `enforce`, `PreToolUse` `warn` (`curl https://example.com`) | `additionalContext`, nenhum registro |
| E5 | `enforce`, `PreToolUse` `block` e `ask` | saída e um registro com `event: PreToolUse`, `decision`, `decision_category` |
| E6 | `PostToolUse` e `PostToolUseFailure` | `failed: False` e `failed: True` |
| E7 | `Read`, `Grep`, `Glob`, `WebFetch` | nenhum registro |
| E8 | ator: `agent_type` presente; só `agent_id`; nenhum dos dois | `agent_type`; `subagent`; `main` |
| E9 | `suite_by_non_runner`: cada implementer, `quality-fixer` e `test-writer` com `pytest`, `pnpm --filter api test`, `k6 run x.js` | flag presente; com `pytest tests/test_a.py` ausente; `test-runner` e `main` com `pytest` sem a flag |
| E10 | tool `mcp__playwright__browser_take_screenshot` por `frontend-react` e por `ui-verifier` | `categories: [visual]`; `visual_tool` só para o primeiro |
| E11 | Bash com comando de 1000 caracteres; Write com `content` e `tool_response` | `cmd` com 300 caracteres; o registro não tem `content`, `tool_input` nem `tool_response` |
| E12 | `SubagentStop` com run ativo | `agent_type`, `in_run: True`, `run`, `task` |
| E13 | `MultiEdit` com `file_path`; `NotebookEdit` com `notebook_path` | `categories: [write]`, `path` igual ao recebido |
| E14 | `METRICS_DIR` inexistente; dois eventos da mesma sessão; payload sem `session_id` | diretório criado; duas linhas no mesmo arquivo; arquivo `unknown.jsonl` |
| E15 | config sem `mode` | tratado como `audit`: `PreToolUse` silencioso |
| E16 | Bash `ls` em `PostToolUse` com run ativo | `in_run: True`, `run`, `task` |

### `test_design_system.py`

Os 28 casos da [spec do design-director, Casos H](../design-director/spec.md), por `call_main` (um `PreToolUse` e um `PostToolUse` com o mesmo payload; `tool_response: {"type": "create"}` quando indicado). Run "sim": `allowed_paths {"1": ["services/web/src/**"]}`; H26-H28: o mesmo, mais `approved_scope` com `DESIGN_SYSTEM.md` e `services/api/**` aprovados. H23-H25: `cwd` e alvo num diretório sem raiz git (`assert_no_git_root`). Conferidos no código em 2026-11-12.

| # | Ator | Tool | Caminho | Run | pre | flags |
|---|---|---|---|---|---|---|
| H1 | `design-director` | Write | `DESIGN_SYSTEM.md` | não | silencioso | `[]` |
| H2 | `design-director` | Write | `services/web/DESIGN_SYSTEM.md` | não | silencioso | `[]` |
| H3 | `design-director` | Write | `NOTES.md` | não | deny `design_director_write_outside` | `[design_director_write_outside, md_outside_docs]` |
| H4 | `frontend-react` | Edit | `DESIGN_SYSTEM.md` | não | warn `design_system_write_by_other` | `[design_system_write_by_other]` |
| H5 | `frontend-react` | Edit | `DESIGN_SYSTEM.md` | sim | warn `design_system_write_by_other` (desempate) | `[design_system_write_by_other, out_of_scope_write]` |
| H6 | `docs-writer` | Edit | `DESIGN_SYSTEM.md` | não | warn `design_system_write_by_other` | `[design_system_write_by_other]` |
| H7 | main | Edit | `DESIGN_SYSTEM.md` | não | silencioso | `[]` |
| H8 | `frontend-react`, `mode: audit` | Edit | `DESIGN_SYSTEM.md` | não | silencioso | `[design_system_write_by_other]` |
| H9 | `subagent` (só `agent_id`) | Edit | `DESIGN_SYSTEM.md` | não | warn `design_system_write_by_other` | `[design_system_write_by_other]` |
| H10 | `frontend-react` | Edit | `.claude/templates/project-root/DESIGN_SYSTEM.md` | não | warn `design_system_write_by_other` | `[design_system_write_by_other]` |
| H11 | `design-director` | Edit | `DESIGN_SYSTEM.md` (existente) | não | silencioso | `[]` |
| H12 | `design-director` | Write, create | `DESIGN_SYSTEM.md` | não | - | `[]` |
| H13 | `backend-node` | Write, create | `DESIGN_SYSTEM.md` | não | warn `design_system_write_by_other` | `[design_system_write_by_other, md_outside_docs]` |
| H14 | main | Write, create | `DESIGN_SYSTEM.md` | não | warn `md_outside_docs` (seção 5) | `[md_outside_docs]` |
| H15 | `design-director` | Edit | `src/a.ts` | não | deny `design_director_write_outside` | `[design_director_write_outside]` |
| H16 | `design-director` | Write, create | `src/a.ts` | não | deny `design_director_write_outside` | `[design_director_write_outside]` |
| H17 | `design-director` | Edit | `apps/web/DESIGN_SYSTEM.md` | não | silencioso | `[]` |
| H18 | `design-director` | Write, create | `apps/web/DESIGN_SYSTEM.md` | não | - | `[]` |
| H19 | `frontend-react` | Edit | `design_system.md` | não | warn `design_system_write_by_other` | `[design_system_write_by_other]` |
| H20 | `design-director` | Write, create | `design_system.md` | não | - | `[]` |
| H21 | `frontend-react` | Edit | `apps/web/DESIGN_SYSTEM.md` | não | warn `design_system_write_by_other` | `[design_system_write_by_other]` |
| H22 | main | Edit | `apps/web/Design_System.md` | não | silencioso | `[]` |
| H23 | `design-director` | Edit | `x.ts`, sem raiz git | não | deny `design_director_write_outside` | - |
| H24 | `design-director` | Edit | `DESIGN_SYSTEM.md`, sem raiz git | não | silencioso | - |
| H25 | `design-director` | Edit | `app/design_system.MD`, sem raiz git | não | silencioso | - |
| H26 | `frontend-react` | Edit | `DESIGN_SYSTEM.md` | sim + `approved_scope` | - | `[design_system_write_by_other, out_of_scope_write]` |
| H27 | `frontend-react` | Edit | `apps/web/design_system.md` | sim + `approved_scope` | - | `[design_system_write_by_other, out_of_scope_write]` |
| H28 | `frontend-react` | Edit | `services/api/x.ts` | sim + `approved_scope` | - | `[]` |

### `test_hook_process.py`

Sobre `HookProcess` (cópia do hook, config próprio, métricas e `HOME` temporários). Todo caso também afirma `returncode == 0` e stderr vazio.

| # | Caso | Esperado |
|---|---|---|
| G1 | `backend-node`, Bash `docker compose -f x.yml restart api` | deny `docker_lifecycle` |
| G2 | main, Bash `rtk docker compose restart api` | deny `docker_lifecycle` |
| G3 | main, Bash `git commit -m x` | ask `git_commit` |
| G4 | `ui-verifier`, Write `services/web/src/a.tsx` | deny `write_by_readonly_agent` |
| G5 | `frontend-react`, tool `mcp__playwright__browser_take_screenshot` | deny `visual_tool` |
| G6 | `ui-verifier`, mesma tool | silencioso |
| G7 | `frontend-react`, Edit `services/api/x.ts`, run ativo (`services/web/src/**`) | warn `out_of_scope_write` |
| G8 | `frontend-react`, Edit `services/web/src/a.tsx`, run ativo | silencioso |
| G9 | `backend-python`, Bash `pytest tests/test_a.py` | silencioso |
| G10 | stdin `not json` | nenhuma saída, nada gravado |
| G11 | G1 com `mode: audit` | silencioso |
| P1 | stdin `[]` (JSON que não é objeto: o `main()` levanta) | exit 0, nenhuma saída, nada gravado |
| P2 | stdin vazio | exit 0, nenhuma saída |
| P3 | `agent-audit.json` com JSON inválido | como `audit`: G1 silencioso no `PreToolUse`; `PostToolUse` grava `docker_lifecycle` |
| P4 | sem `agent-audit.json` | igual a P3 |
| P5 | saída de deny, ask e warn | exatamente uma linha, JSON válido, `hookSpecificOutput.hookEventName == "PreToolUse"` |
| P6 | H1, H3 e H5 pelo processo | o mesmo pre e as mesmas flags da tabela H |

### `test_config_contract.py`

Lê os arquivos vivos, só leitura.

| # | Check | Esperado |
|---|---|---|
| F1 | `agent-audit.json` | JSON válido; `mode` em `{off, audit, enforce}`; toda ação em `SEVERITY` |
| F2 | pisos das regras do `CLAUDE.md` | `mode == "enforce"`; `docker_lifecycle`, `write_by_readonly_agent`, `visual_tool`, `design_director_write_outside` em `block`; `git_commit`, `git_push` pelo menos `ask` |
| F3 | conjuntos | chaves de `categories` == chaves de `WHY` == chaves de `FLAG_LABELS` (14 hoje) |
| F4 | `docs_roots` vivo | `docs_roots(config)` contém `docs/` e `.claude/docs/` |
| F5 | `settings.json` | os eventos `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `SubagentStart`, `SubagentStop` chamam `python3 "$HOME/.claude/hooks/agent-audit.py"`; o do `PreToolUse` não é `async` (precisa decidir antes da ação); todos com `timeout`; o `matcher` do `PreToolUse` (como regex completo) casa com `Bash`, `Write`, `Edit`, `MultiEdit`, `NotebookEdit` e `mcp__playwright__browser_take_screenshot`, e não casa com `Read` |
| F6 | `TEST_CONFIG` | tem as mesmas 14 categorias que o config vivo (a ação pode diferir); avisa quando uma categoria nova entra no hook sem entrar nos testes |

### `test_agent_metrics.py`

Em processo, com `metrics.METRICS_DIR` trocado por um diretório temporário e JSONL sintético. M1-M5 vêm da [spec do design-director, Casos M](../design-director/spec.md).

| # | Entrada | Esperado |
|---|---|---|
| M1 | `PostToolUse` de H2, H3, H4 e um `SubagentStart` do `design-director` | `## Flags` lista `design_system_write_by_other` com o rótulo de `FLAG_LABELS`; `## design-director` com `calls: 1` e `writes other than to a DESIGN_SYSTEM.md: 1`, só com `NOTES.md` |
| M2 | só H1 e H11 | `writes other than to a DESIGN_SYSTEM.md: 0` |
| M3 | nenhum evento do `design-director` | sem `## design-director`; as outras seções presentes |
| M4 | `SubagentStart` e escrita em `apps/web/Design_System.md` | `writes other than to a DESIGN_SYSTEM.md: 0` |
| M5 | `SubagentStart` e registro sem `rel`, `path: /x/y.ts`, flag `design_director_write_outside` | contagem 1, exemplo `/x/y.ts`; `## Flags` com o rótulo da categoria |
| R1 | lista vazia | `No events.` |
| R2 | arquivo com uma linha inválida entre duas válidas | `load` devolve as duas válidas |
| R3 | `SubagentStart`/`SubagentStop` com `ts` | `## Agent calls` com chamadas e duração média; agent sem `Stop` mostra `-` |
| R4 | registros com `categories` de atores diferentes | `## Actions by category` com total e contagem por ator |
| R5 | `test-runner` com `test-full` e `test-package` | `suite commands run by test-runner: 2 (full-repo: 1 ...)` |
| R6 | escritas dentro e fora de run, com `in_scope` `True`/`False` | linha `total / during a run / checked / outside` com as contagens |
| R7 | `PreToolUse` com `decision` | `## Enforcement decisions` agrupado por (decisão, categoria), até 3 exemplos |
| R8 | flags em `PreToolUse` e em `PostToolUse` | `## Flags` conta só as do `PostToolUse`; sem flags, `None.` |
| R9 | 7 eventos com a mesma flag | 5 exemplos e `... 2 more` |
| L1 | `METRICS_DIR` inexistente | `SystemExit` com `No metrics yet` |
| L2 | sem argumentos, três sessões com `mtime` diferentes | só a mais recente |
| L3 | `--last 2` | as duas mais recentes, um relatório cada |
| L4 | `--session <id>` | só a sessão pedida |
| L5 | `--since <data>` com `--merge` | um relatório `N sessions` com os arquivos alterados desde a data |
| L6 | `--run <slug>` | só os eventos com `run == slug`, de qualquer sessão |
| L7 | `--session` inexistente | `SystemExit` com `No matching sessions.` |

### Regras -> testes

| Regra (fonte) | Testes |
|---|---|
| R1 commit e push só com autorização (`CLAUDE.md`) | C32, C33, X8, X9, K6, G3, F2 |
| R2 o usuário é dono dos containers; build só com Dockerfile; leitura livre (`CLAUDE.md`, `Local runtime`) | C26-C30, X1-X7, G1, G2, G11, F2 |
| R3 ferramentas visuais só no `ui-verifier` (`CLAUDE.md`) | E10, G5, G6, F2 |
| R4 agents read-only não escrevem (13, etapa E) | `OutsideRepoWrites.test_readonly_*`, G4, F2 |
| R5 escopo do run (13.1, 13.4, 13.7) | `ParallelTasksScope`, `OutsideRepo*`, S1-S11, G7, G8, H5, H26-H28 |
| R6 suites só pelo `test-runner` (`CLAUDE.md`, 11.2) | C1-C19, X12, X13, E9, G9 |
| R7 docs só pelo `docs-writer`; nada de `.md` solto (`CLAUDE.md`) | A1-A6, D8, D10, D11, H13, H14 |
| R8 `backlog/` só pelo `backlog-keeper` (`CLAUDE.md`) | A7, D9, `test_nested_repo_area_flags_come_from_the_target_root` |
| R9 `DESIGN_SYSTEM.md` criado pelo `design-director`, mantido pela sessão principal (15.1, 13.5) | H1-H28, P6, testes de `DESIGN_SYSTEM.md` em `OutsideRepo*`, M1, M4, M5 |
| R10 requests só para hosts locais (`CLAUDE.md`) | C34-C36, X10, X11, E4 |
| R11 decisões por categoria e modos; fail-open (13.2, docstring do hook) | K1-K12, E1-E5, E15, G10, G11, P1-P5 |
| R12 sem conteúdo no registro (docstring do hook) | E11 |
| R13 `docs_roots` configurável (13.5, log r3) | D1-D11, F4 |
| R14 heredoc é dado só em sinks conhecidos (13.6) | `test_heredoc.py` |
| R15 relatório de métricas (14.2) | M1-M5, R1-R9, L1-L7 |
| R16 config, rótulos e registro do hook coerentes | F1-F6 |

## Implementation order

### Task 1 - Base da suite: ambiente hermético, _support e divisão do arquivo atual

- **Stack:** backend-python
- **Files:** `.claude/hooks/tests/__init__.py`, `.claude/hooks/tests/_support.py`, `.claude/hooks/tests/test_agent_audit.py`, `.claude/hooks/tests/test_heredoc.py`, `.claude/hooks/tests/test_write_scope.py`
- **Depends on:** -
- **Done when:** `__init__.py` e `_support.py` com a API da Design (seções 2 e 3); `test_agent_audit.py` removido e seu conteúdo em `test_heredoc.py` e `test_write_scope.py`; o conjunto de `Classe.método` de `python3 -I -B -m unittest discover -s .claude/hooks/tests -t .claude/hooks -v` é idêntico ao de antes (82 testes) e todos passam; também passam com `TMPDIR` apontando para um diretório `claude-*` dentro do scratchpad (hoje 14 falham); nenhum arquivo novo em `~/.claude/metrics` durante a suite; nenhum `__pycache__` criado; `git diff --stat` não mostra nada fora de `.claude/hooks/tests/`
- **Status:** done

### Task 2 - Classificação de comandos

- **Stack:** backend-python
- **Files:** `.claude/hooks/tests/test_classify.py`
- **Depends on:** Task 1
- **Done when:** C1-C37 e X1-X14 passam como `subTest` com o id do caso; o módulo roda sozinho com `-p 'test_classify.py'`; nenhum arquivo fora de `.claude/hooks/tests/` muda
- **Status:** done

### Task 3 - Áreas de escrita, docs_roots e escopo dentro do repo

- **Stack:** backend-python
- **Files:** `.claude/hooks/tests/test_write_areas.py`, `.claude/hooks/tests/test_write_scope.py`
- **Depends on:** Task 1
- **Done when:** A1-A9, D1-D11 (em `test_write_areas.py`) e S1-S11 (classe `InRepoScope` em `test_write_scope.py`) passam; os testes movidos na task 1 continuam com os mesmos nomes; as docstrings de A1 e dos testes da seção 5 citam a entrada de backlog; nenhum arquivo fora de `.claude/hooks/tests/` muda
- **Status:** done

### Task 4 - decide e main em processo

- **Stack:** backend-python
- **Files:** `.claude/hooks/tests/test_decide.py`, `.claude/hooks/tests/test_hook_main.py`
- **Depends on:** Task 1
- **Done when:** K1-K12 e E1-E16 passam; nenhum teste lê o `agent-audit.json` vivo (só `TEST_CONFIG`); nenhum arquivo fora de `.claude/hooks/tests/` muda
- **Status:** done

### Task 5 - Regras do DESIGN_SYSTEM.md (casos H)

- **Stack:** backend-python
- **Files:** `.claude/hooks/tests/test_design_system.py`
- **Depends on:** Task 1
- **Done when:** H1-H28 passam como `subTest` com o id do caso, com o pre e as flags da tabela; H23-H25 afirmam a premissa "sem raiz git"; a docstring de H14 cita a entrada `md-outside-docs-false-positive`; nenhum arquivo fora de `.claude/hooks/tests/` muda
- **Status:** done

### Task 6 - Processo real e contrato do config

- **Stack:** backend-python
- **Files:** `.claude/hooks/tests/test_hook_process.py`, `.claude/hooks/tests/test_config_contract.py`
- **Depends on:** Task 1
- **Done when:** G1-G11, P1-P6 e F1-F6 passam; todo caso de processo afirma exit 0 e stderr vazio; nenhum caso de processo usa o hook vivo nem o `agent-audit.json` vivo (só a cópia); `test_config_contract.py` só lê arquivos; nenhum arquivo fora de `.claude/hooks/tests/` muda
- **Status:** done

### Task 7 - Relatório de métricas

- **Stack:** backend-python
- **Files:** `.claude/hooks/tests/test_agent_metrics.py`
- **Depends on:** Task 1
- **Done when:** M1-M5, R1-R9 e L1-L7 passam; nenhum teste lê `~/.claude/metrics`; nenhum arquivo fora de `.claude/hooks/tests/` muda
- **Status:** done

## Verification

**Suite.** A tabela `Test suites` não existe ainda. Proposta para o `docs-writer`, num `CLAUDE.md` novo na raiz do repo (`/home/void/dotfiles/CLAUDE.md`), nunca no `.claude/CLAUDE.md` (que é o `~/.claude/CLAUDE.md` global e vazaria para todos os projetos):

```markdown
## Test suites

| Suite        | Service       | Type               | Command                                                                       | Gate |
| ------------ | ------------- | ------------------ | ----------------------------------------------------------------------------- | ---- |
| claude-hooks | .claude/hooks | unit + integration | `python3 -I -B -m unittest discover -s .claude/hooks/tests -t .claude/hooks` | task |
```

Rodada estreita de um módulo (para os agents): o mesmo comando com `-p 'test_<módulo>.py'`.

No fim do run, pelo `test-runner`:

1. Suite `claude-hooks` inteira, verde, em menos de 5 s.
2. A mesma suite com `TMPDIR` apontando para um diretório `claude-*` dentro do scratchpad (prova de que a suite não depende do `TMPDIR`).
3. `git diff --stat main -- .claude/hooks/agent-audit.py .claude/hooks/agent-audit.json .claude/hooks/agent-metrics.py .claude/settings.json` vazio (o hook vivo não mudou).
4. `git status --porcelain --ignored .claude/hooks` sem `__pycache__` novo.

Sem runtime local nem UI: não há request nem check visual. Check manual do usuário: depois do merge, uma sessão normal segue sem negação nova do hook (o hook não mudou; é só a confirmação de que nada vazou da suite para `~/.claude/metrics`, olhando que o arquivo mais novo ali é o da sessão).

**needs_docs** (para o `docs-writer`, no fim):

- `/home/void/dotfiles/CLAUDE.md` (novo): `## Workflow` com `- docs layout: features` e a nota de que o docs root deste repo é `.claude/docs/`; `## Test suites` com a tabela acima.
- `.claude/README.md` (seção dos hooks): onde fica a suite e como rodar.
- `agent-workflow.md`, seção 13: a suite `claude-hooks` substitui o harness avulso do scratchpad.

## Open questions

1. **Título da entrada de refactor.** A entrada pede "pytest suite"; a spec escolhe `unittest` (Alternatives considered). Opções: (a) o `backlog-keeper` renomeia para "Versioned unittest suite for agent-audit hook" e atualiza o "Current state" (82 testes, não só heredoc); (b) manter o título. Recomendação: (a).
2. **`CLAUDE.md` novo na raiz do dotfiles.** Ele passa a ser carregado em toda sessão aberta em `/home/void/dotfiles`. Opções: (a) criar, só com `Workflow` e `Test suites`; (b) não criar, e a suite fica sem tabela (o `test-runner` não a encontra pela stack, porque não há `pytest`/`package.json`). Recomendação: (a).
3. **Achados fora do escopo, para o `backlog-keeper`** (nenhum teste os fixa): (a) `classify_command` não reconhece `python3 -m unittest` nem `python3 -m pytest` como teste (só `python -m pytest`), então um implementer rodando a suite inteira desta spec não recebe `suite_by_non_runner`; (b) `quality-fixer` e `test-writer` editando `README.md` ou `docs/` não recebem `docs_write_by_implementer`; (c) a isenção de `md_outside_docs` usa `endswith("README.md")`, então `MY_README.md` também é isento; (d) a suite atual falha com `TMPDIR` sob `/tmp/claude-*` (corrigido pela task 1, mas pode ser registrado como bug de teste flaky e fechado com ela). Recomendação: registrar (a) como bug, (b) e (c) como refactor, e (d) como bug ligado a esta spec.
