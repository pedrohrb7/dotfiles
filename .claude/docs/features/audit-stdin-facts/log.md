# Implementation log - audit-stdin-facts

<!-- Written by /implement only, append-only. One "Run" section per /implement run and one block per task, filled from the agents' YAML reports. The stack agents read this file before coding and follow the decisions recorded here; never re-decide something already logged without a scope request. -->

## Run 2026-11-19

Starting point: commit 473021b (prerequisite fix-bug run audit-regex-and-tables-46ae3a7 landed; suite 1145 tests).

### Task 1 - Testes que fixam o comportamento aceito e as leituras dos resolvedores (done)

- **Files:** `.claude/hooks/tests/test_stdin_facts.py` (new: load_tests via ForkedSuite, AcceptedBehaviour 19 tests, ResolverReads 7 tests)
- **Decisions:** ResolverReads uses a distinct name per git call, because HEAD reads `git_external('zzz')` twice for `git zzz; git zzz`; Task 5 adds the repeated-name case with the once-per-name memo. `$cmd < <(x)` alone is clean at HEAD; the accepted false positive is its effect on later sites (`$cmd < <(x); bash` and `; eval y` pinned as dynamic_code). `exec 3< <(x); source $f; ls` pinned as dynamic_code; plain `source $f; ls` and `source $f; echo x | bash 0` pinned clean. `eval 'x=$(f() { :; }; f)'` pinned dynamic_code, `x=$(f() { :; }; f)` clean. Everyday commands asserted with `flags == []`.
- **Assumptions:** pinning today's outputs for the limitations matches "estado de hoje"; Task 5 changes none of them.
- **Approved scope:** none
- **Migrations / env vars:** none
- **Docs pending:** none

### Task 2 - Valor `Facts` e contexto montado a partir de fatos no parser (done)

- **Files:** `.claude/hooks/agent_audit_shell.py` (Facts, NO_FACTS, UNKNOWN_FACTS, StdinContext.facts(), StdinContext.of(fds, facts, end=None)), `.claude/hooks/tests/test_shell_lexer.py` (FactsValue, 7 tests)
- **Decisions:** `Facts.for_parent(kind)` takes the strings "child", "same" and "body"; the classifier must define `_CHILD = "child"`, `_SAME = "same"`, `_BODY = "body"` with exactly these values (the shell module cannot import the classifier). Facts is immutable (object.__setattr__ in __init__, __setattr__/__delattr__ raise); fifos accepts any iterable and is stored as a frozenset. Facts and the constants sit after StdinContext and before NO_CONTEXT (forward-reference annotations). `StdinContext.of(fds, facts, end)` passes end through; end defaults to fds when None. Fifos, fd_states, exec_fds and StdinContext(...) keep their API. No new imports.
- **Assumptions:** none
- **Approved scope:** none
- **Migrations / env vars:** none
- **Docs pending:** none

Check after tasks 1-2: claude-hooks suite 1178 tests, pass.

### Task 3 - Estado por texto (`_Text`) separado do estado por rodada (`_Run`), sem mudança de resultado (done)

- **Files:** `.claude/hooks/agent_audit_classify.py` (new `_Text`, `_Run(text)`, `analyze_command` rewired; `_git_alias_variants(..., external=None)`)
- **Decisions:** `_Text(command, depth, outer_env, budget, code, script, cwd, outer_fn)` holds the tree, has_dollar, funcs, fwd_spans, steps, values and views, function names and verdicts, cwd_moved, repo_aliases (memo) and the `git_external(name)` memo (looks up module-level `_git_external_exists` at call time, so mock.patch still works). Text-level blocks go through `_Text.block(reason)` into `_Text.blocks` (deduplicated) and `_Run.result()` applies them first, so every round reports them: implicit-function hooks, the `_same` function-readers block, code_evaluation, and analysis_budget from function_verdicts. `_Text.charge` blocks into the text (function_verdicts); `_Run.charge` blocks into the run (per-variant costs). `_Text` also caches code_evaluation(), readings(site) (keyed by id(cmd)), heredocs(items) and in_function. `_Run` copies command, depth, budget, code, script, cwd, steps, has_dollar, funcs, fwd_spans from the text; its own state is categories, flags, reasons, forwarded, raws, in_fwd; functions, function_verdicts, values, view_at, in_function are thin delegators to the text. The facts pass is unchanged (one `_Run` before it; its resolved/head_readings still used; blocks inside it stay run-level). The git_external memo reads a repeated name once (`git zzz; git zzz`), results unchanged; Task 5 adds the repeated-name ResolverReads case.
- **Assumptions:** applying the text-level blocks in result() is equivalent to adding them directly (nothing reads categories/flags/reasons during a run; output is sorted sets).
- **Approved scope:** none
- **Migrations / env vars:** none
- **Docs pending:** none

Check after task 3: claude-hooks suite 1178 tests, pass.

### Task 4 - Observação dos fatos e retorno interno `(Analysis, Facts)`, ainda sem uso (done)

- **Files:** `.claude/hooks/agent_audit_classify.py` (`_CHILD`/`_SAME`/`_BODY`, `ExecSeen`, `_analyze`, `_Run.observe_reading`/`observe_site`/`finish`/`absorb`; `_code_text` and `_heredoc_code` return Facts; `analyze_command(command, _depth=0, _budget=None, cwd=None)`), `.claude/hooks/tests/test_stdin_facts.py` (ObservedFacts 22 tests, ObservedCoversTheFactsPass 2 tests, CORPUS, DIVERGENCES, observe/covers helpers)
- **Decisions:** `_analyze(command, depth=0, env=None, budget=None, code=False, cwd=None, fn=None, kind=_CHILD, stdin=None)` returns `(Analysis, Facts)`; `cwd=False` marks nested text; returned facts = stdin.facts() joined with run.observed; early failures return UNKNOWN_FACTS. `_code_text(..., kind=_CHILD, stdin=None, lift=None)` returns `facts.for_parent(lift or kind)`; NO_FACTS for empty text and past MAX_CODE_DEPTH; `_heredoc_code` returns the union of its bodies' facts. `_Run.code_text(..., kind, stdin, lift)` absorbs; forwarded_calls passes _BODY; code_arguments and _heredoc_code pass _SAME or _CHILD. DEVIATION from Design 5: extra `lift` parameter, because Design 3 says zsh_hooks and compound_heredocs are _SAME but today they run with same_shell=False and passing _SAME would fire the same-shell blocks and change results; they pass kind=_CHILD, lift=_SAME (facts rise as _SAME, blocks unchanged). Tasks 5-6 may unify (drop lift, pass _SAME) only if the blocks are meant to change. `_Text` has a `kind` slot; `_Run(text, assumed=NO_FACTS)`; `_Run.finish()`: moving plus any assumed or observed fifo makes the fifo unknown. observe_reading runs from `_Run.reading` for every resolved reading, and on the words as written for a site with incomplete readings. `_bare_exec(site, tokens, words=None)`. A site's `_made` flag (set by observe_reading, reset at the start of simple) decides the mention rule. Unknown code: code_arguments with text None and reason dynamic_code sets fifo-unknown (+ moved for a same-shell loader head); in variant, 'dynamic_code' in alias_reasons sets fifo-unknown. Precision gain (section 10): `${S:-mkfifo} p` observes {p} (old pass: unknown), pinned. Mentions of mkfifo in words, git alias values or a plain `bash <<E` body set fifo-unknown like the old mention rule; only the compound heredoc form (D6) avoids it. ObservedCoversTheFactsPass is a differential on the old _stdin_facts (every old fifo name/unknown, moved and exec start still found; D1, D2, D4-D7 checked; D3 only changes an exec's incoming, not asserted).
- **Assumptions:** `ExecSeen.incoming` is PIPED for stage > 0, else site.stdin of the walk in the round (spec definition; unread until Task 5). Run.execs and observed are public for Task 5; `_Run.observed` is a property over private accumulators.
- **Approved scope:** none
- **Migrations / env vars:** none
- **Docs pending:** none
- **Note for Tasks 5-6:** suite time 18.2 s after this task (13.9 s before); test_uncertainty about +0.6 s while the old pass and the observation both run. The spec's Verification allows at most +0.5 s over HEAD at the end, so check timing once the old pass stops running (Task 5) and is removed (Task 6).

Check after task 4: claude-hooks suite 1203 tests, pass.

### Task 5 - Ponto fixo com teto de rodadas; a passada antiga deixa de ser chamada (done)

- **Files:** `.claude/hooks/agent_audit_classify.py` (round loop in `_analyze`: MAX_FACT_ROUNDS = 3, charge TEXT_COST + len(command) per extra round, analysis_budget at the cap; new `_contexts`, `_exec_key`, `_Run.classify`, `_Run.exec_key`, `_Run.unknown_code`, `_Text.bare_site`; context passed down carries moved; git_external memo shared across nested texts and rounds), `.claude/hooks/tests/test_stdin_facts.py` (StdinFactsFromAnalysis 6, FactRounds 7, FactsLinearity 5, repeated-name ResolverReads case; `observe` helper runs the old _stdin_facts itself; two of its own Task 4 ObservedFacts expectations changed; 70 tests)
- **Decisions:** `_Run(text, assumed=NO_FACTS, given=(), stdin=None)`; `_Run.classify()` is one round (contexts from `_contexts(assumed, given_execs, stdin)`, walk with resolve, items, simple and zsh_hooks per site, heredocs, finish(), then nested _SAME blocks); text-level blocks decided once per text. The old nested _SAME moved block is kept with `assumed.moved or observed moved` (cannot fire in the converging round; may go in Task 6). `_stdin_context` and zsh_hooks build contexts with `StdinContext.of(fds, ctx.facts())` (decision 1); trap_stdin goes through _stdin_context. `_contexts` uses `incoming or current.fds.get(0)`. DEVIATION from Design 4's convergence claim: unknown code observed (CodeArg(None, 'dynamic_code')) depended on the assumed descriptor state, so round 3 flipped dynamic_code into piped_shell and broke 17 existing tests; fix: `_Run.unknown_code` re-reads the command's `_code_args` on the matching site of a context-free walk (`_Text.bare_site`, built lazily only when a command has unknown code), making the observation independent of the assumed facts. Consequence: `exec 3< <(x); source $f` observes no facts (still blocked dynamic_code by the main analysis); Design 3's remark that `source $f` under an active state marks moved does not hold. DEVIATION from Design 5: extra `shared` dict passed through `_code_text` and `_heredoc_code` so git_external is memoized per name for the whole analysis; git_aliases stays at one read. Design 10 row "a value resolves the name" holds for `s=mkfifo; bash -c '$s p'; bash x.sh` and `s=mkfifo; $s p; bash x.sh` (clean); `eval '$s p'` is blocked by the main analysis (X3), as at HEAD. Rounds: CORPUS texts take at most 2, texts without facts take 1; D3 and D7 take 3 (within the cap; pinned by FactRounds). `_stdin_resolver`, `_stdin_facts`, `_nested_facts`, `_site_code_facts`, `_CODE_PROGRAMS`, `_changes_directory` stay for Task 6 (only the differential calls `_stdin_facts`). `exec 3< <(x); { eval y; } <&3` still clean (Task 7).
- **Assumptions:** the `shared` parameter and the `bare_site` re-read are acceptable deviations (results unchanged, I/O reads bounded). To confirm at review.
- **Approved scope:** none
- **Migrations / env vars:** none
- **Docs pending:** none
- **Timing:** in-process analyze_command CPU per text +2-3% vs HEAD; suite 1222 tests 14.3 s / 13.9 s at load 3-4 (HEAD 1145 tests about 13 s).

Check after task 5: claude-hooks suite 1222 tests, pass (two runs).

### Task 6 - Remoção da passada de fatos duplicada e teste de propriedade (done)

- **Files:** `.claude/hooks/agent_audit_classify.py` (removed `_stdin_facts`, `_nested_facts`, `_site_code_facts`, `_changes_directory`, `_stdin_resolver`, `_Run.resolved`, `_Run.head_readings` and the nested moved block; `_analyze` and `_Run` docstrings describe the fixed point), `.claude/hooks/tests/test_stdin_facts.py` (dropped ObservedCoversTheFactsPass, covers and the old-pass parts of observe; added NestedEqualsInline (283 wrapper/text combinations + 200 seeded compositions) and RemovedFactsPass; 73 tests)
- **Decisions:** removal confirmed decision 1 (tests green without the nested moved block). DEVIATION: `_CODE_PROGRAMS` is NOT removed, because `_parallel_template` (the parallel allow-list) uses it to refuse code programs; only its comment changed. `lift` is kept: passing kind=_SAME for zsh_hooks and compound_heredocs keeps existing tests green but changes results (`{ bash; } <<E` with `f() { bash; }` in the body, `functions[precmd]='exec 3< <(x)'; ls`, `{ bash; } <<<'f() { eval x; }'; f` go from clean to dynamic_code); pending user decision. `_STRIPPABLE_EXPANSION` used as is by `_Run.observe_site`; `_EXPANSION` and `_head_is_dynamic` untouched. NestedEqualsInline wrappers: eval, `source /dev/stdin` with a heredoc, `trap ... EXIT` (_SAME); bash -c, sh -c, timeout 5 bash -c, su -c, `git -c alias.x='!X' x`, `parallel ::: X` (_CHILD); property `facts(W(X)) == facts(X).for_parent(kind(W))` with three relaxations: (a) texts naming a fifo maker compared as wrapped covers inline (the wrapper's mention rule adds unknown); (b) compositions past MAX_CODE_DEPTH skipped; (c) the git alias wrapper skipped for inner texts with `$`. Inner texts: CORPUS without heredocs, `$cmd`, descriptor copies, exec and pipes (32 of 43).
- **Assumptions:** the three relaxations are the spec's "outside the property" set (to confirm at review).
- **Approved scope:** none
- **Migrations / env vars:** none
- **Docs pending:** none
- **Timing:** in-process analyze_command CPU per text +4% vs HEAD; suite back to back 14.6 s (1225 tests) vs HEAD 13.7 s (1145 tests) at load 4-5. test_hook_process.py is the slowest module (about 6.7 s, pre-existing).

Check after task 6: claude-hooks suite 1225 tests, pass.

### Task 7 - `compound_procsub_stdin` unificado com o estado do walker (`Site.given`) (done)

- **Files:** `.claude/hooks/agent_audit_shell.py` (`Site.given` slot and constructor argument; `given` argument on `_walk` and `_walk_redirects`; StdinContext docstring says contexts are built from a round's assumed Facts), `.claude/hooks/agent_audit_classify.py` (new `_site_reads_code(words, readings, functions)` used by `_compound_reads_code` and `_Run.simple`; `simple` blocks `site.given` when the command may read code; `_Run.compound_procsub_stdin` and its `<(` gate removed), `.claude/hooks/tests/test_shell_lexer.py` (SiteGiven, 5 tests), `.claude/hooks/tests/test_stdin_facts.py` (CompoundGiven, 7 tests)
- **Decisions:** for a Compound with redirections, `here = given or DYNAMIC` when DYNAMIC is among `fd_states(cmd.redirects, None, ctx).values()` (PIPED from a fifo does not count); `here` goes to the bodies only (incl. function bodies and inner compounds); the compound's word-list substitutions and own redirect targets get the outer given; a simple command's substitutions and redirect targets inherit given. `Site.given` is DYNAMIC or None. `_Run.simple` checks it at its top, before the incomplete-readings early return, ignoring the command's own redirections (keeps the accepted false positive `{ bash <<< x; } < <(y)`). Section 10 row `exec 3< <(x); { eval y; } <&3` is now dynamic_code (also the `< /dev/fd/3` form); `mkfifo p; { eval y; } < p` stays clean; nested code inheriting an exec-given descriptor is blocked too.
- **Assumptions:** the StdinContext docstring wording.
- **Approved scope:** none
- **Migrations / env vars:** none
- **Docs pending:** none

Check after task 7: claude-hooks suite 1237 tests, pass (26.9 s at load 5.6-7.4, not a clean measure).

### User decisions after task 7 (2026-11-19)

- Drop `lift`: zsh_hooks and compound_heredocs pass kind=_SAME, as Design 3 says; the 3 forms `{ bash; } <<E` with `f() { bash; }` in the body, `functions[precmd]='exec 3< <(x)'; ls` and `{ bash; } <<<'f() { eval x; }'; f` become dynamic_code (follow-up of task 6).
- Keep `_CODE_PROGRAMS`: the parallel allow-list (added after the spec) uses it to refuse code programs.

### Task 6 follow-up - `lift` removed (done)

- **Files:** `.claude/hooks/agent_audit_classify.py` (removed `lift` from `_code_text` and `_Run.code_text`, uses and docstrings; zsh_hooks (functions[...] assignment) and compound_heredocs pass kind=_SAME), `.claude/hooks/tests/test_stdin_facts.py` (SameShellHooksAndCompoundHeredocs: the 3 forms pinned dynamic_code; `{ cat; } <<E` plain body, `{ bash; } <<<'echo hi'`, `functions[precmd]='ls'; ls` pinned clean; 82 tests)
- **Decisions:** supersedes the Task 4 and Task 6 notes about `lift`. No other existing test depended on the old clean results.
- **Approved scope:** user decision 2026-11-19 (drop lift).
- **Migrations / env vars:** none
- **Docs pending:** none

### Review fix round (done)

- **Files:** `.claude/hooks/agent_audit_classify.py`, `.claude/hooks/agent_audit_shell.py`, `.claude/hooks/tests/test_stdin_facts.py`, `.claude/hooks/tests/test_shell_lexer.py`
- **Decisions (user, 2026-11-19):** fix the regression (forwarded `_BODY` exec), the 4-round minor, the standards notes and 5 pre-existing boundary findings in this run; confirm the decision-1 class (every eval/source `cd X` under an active state is clean, like the inline cd). Implemented: fd-change block for kind != _CHILD; heredoc/here-string to a function of the text or a rebound name is _SAME; a bare exec copying input is a stdin reader, and a copy of a descriptor no exec of the text opens (not 0, not >&1/>&2) is dynamic_code; function and loop bodies get the union of every exec context of the text; `Facts.linked` (child links that reach outside plain names are lifted, cd stays local); zsh `functions[NAME]=BODY` / `functions+=(NAME BODY)` of any name classified as _SAME and the names join `_Text.functions()`; MAX_FACT_ROUNDS = 4 (two forms need exactly 4; a text needing 5 fails closed); `unknown_code`/`bare_site` removed (no result change); `_CODE_PROGRAMS` merged into `_PARALLEL_FORBIDDEN` (supersedes the Task 6 "keep" note); `_Run.given` renamed `prior_execs`; docstrings fixed. Supersedes the Task 4-6 notes on `lift`, `bare_site` and `_CODE_PROGRAMS`.
- **Accepted (user):** false positives `exec 4>&3; ls`, `exec 5<&4; ls`, `functions+=(g)`, `{ exec 4<&3; } 3< z; ls`, `f() { cat; }; f <<E` with a function definition in the body; limitation `f() { exec 4>&1; }; f 1< <(x)`.

### Final fail-closed round (done)

- **Files:** same four files (test_shell_lexer.py unchanged this round)
- **Decisions (user, 2026-11-19, last round, gate only after it):** a bare exec copying input inside a function or loop body is dynamic_code (`_Run.in_repeated`); with `linked` any absolute or `~` path may be a descriptor (`StdinContext.linked`, `_path_code`, `_file_state`); an ln behind a wrapper that does not keep operands as written (all but env, sudo, doas, timeout, nice, nohup, ionice, time, stdbuf, setsid, command, builtin), with a `{}` operand, via find -exec, or after a cd/pushd/popd/chdir anywhere in the text is linked; any word naming the zsh `functions` parameter outside the read assignment path (functions[, functions=, ${functions, bare name after set/typeset/declare/local/export/readonly/read/print/printf/integer/float, also behind noglob) is dynamic_code. Accepted false positives pinned as blocked in FinalRoundFixes.
- **Timing:** in-process CPU on 6067 literals HEAD 1.37-1.45 s vs 1.53-1.59 s (about +10%, noise about 0.2 s).

### Verification 3 and 4, and the follow-up (done)

- **First measurement (spec Verification 3 and 4, 26,177 real commands from local transcripts and metrics, HEAD 473021b vs new):** 0 unexpected decision differences; 4 allow -> deny from the functions-parameter rule (one a plain `grep -rn "functions\[..."`, a false positive); 3 analysis-only precision gains (`T=ls; zsh -c "$T"; bash s.sh` no longer piped_shell). `analyze_command` median +36.8%, p99 +27.1% (FAIL against +10%): any cd/pushd/popd set moved and forced a second full round for 66.6% of real commands. Hook process latency median +1.1-1.25 ms (PASS, at most +3 ms).
- **User decisions (2026-11-19):** re-run a round only when a fact the round consulted changed; restrict the functions-parameter rule to where zsh defines functions.
- **Files:** `.claude/hooks/agent_audit_shell.py` (Fifos and StdinContext record consulted facts `reads`; moved/linked are properties; `StdinContext.inherit(fds)` with `sink`; `StdinContext.of` takes reads), `.claude/hooks/agent_audit_classify.py` (`_Run.reads`, `_changed_facts`, test-only `_FORCE_FACT_ROUNDS`; nested contexts via `ctx.inherit` and the nested run's reads deposited in the parent through `sink`; `_names_functions_parameter(tokens, words)` limited to assignment words at a command head (also after noglob/command), operands of typeset/declare/local/export/readonly/integer/float, bare `functions`/`functions[...]` operands of set/read, the operand after `-v` of print/printf, and `${functions...}` in any word not in single quotes), `.claude/hooks/tests/test_stdin_facts.py` (ReadFactsDecideTheRounds 13 tests incl. optimized == forced equivalence on CORPUS, DIVERGENCES, every test-module string and everyday forms; TheFunctionsParameterOnlyWhereZshDefinesFunctions; 5 existing round tests edited with user approval: examples changed to `mkfifo p; bash < p` (and `bash < p` for the growing-observation cap test, since `cat x | bash` consults no fifos), and the convergence assertion is now "changed facts disjoint from last.reads"; 128 tests)
- **Decisions:** facts tracked as three names (fifos, moved, linked); a bare exec change (exec key) always forces another round (descriptor reads not tracked separately); the zsh rule uses Word.dynamic to tell an expansion from single-quoted text (a double-quoted `${functions[...]}` stays blocked); plain `functions[g]=x` / `functions+=(g x)` stay with zsh_hooks.
- **Second measurement:** median +3.4% (0.486 -> 0.502 ms), p99 +0.1% (PASS); rounds 0: 3.42%, 1: 95.95%, 2: 0.63%, 3-4: 0; 0 decision differences vs HEAD (the grep is allow again); 3 analysis-only precision gains; optimized == forced on all 26,177 commands. Scripts in the session scratchpad `verify34/`.
Gate after the verification follow-up: claude-hooks suite 1287 tests, pass (5 runs, no flaky; CPU per test unchanged vs HEAD).
