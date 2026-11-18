# agent-audit: the GNU parallel command line is not classified or read as code

- **Status:** Fixed (2026-11-19, not committed)
- **Note:** closed by the allow-list rewrite of `_parallel_code` (user decisions of 2026-11-19), fix-bug run .claude/runs/bug-audit-regex-and-tables-46ae3a7.json. The option-by-option check against man parallel is a separate refactor.
- **Reported:** 2026-11-18
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: fix bug-audit-stdin-other-sources-family, out_of_scope_collected (pre-existing) and round-2 security review (user decision)
- **Related:** none

## Evidence

- `parallel ::: 'git push'`, `parallel eval ::: ...`, `parallel bash -c ::: ...` run their arguments as commands: only deny_token_unmatched.
- `parallel -j4 'git push {}' ::: a` and `parallel "bash -c 'git push {}'" ::: a` give no git_push flag.
- Not read as code: `parallel 'bash -c {}'`, `'eval {}'`, `echo {} '|' bash`, `nice sh -c`, `--pipe 'cat | bash'`.

## Seen again (2026-11-18)

Source: agent run: security review of commit 46ae3a7 (stdin family fix), confirmed with analyze_command on synthetic strings.

- (high) A `-c` string or command word with a replacement string `{}` is not dynamic_code, and wrapper heads before a shell are not followed. `parallel sh -c {} ::: 'git push'` gives [] / [deny_token_unmatched]. `echo x | parallel sh -c {}`, `echo x | parallel nohup sh` and `echo x | parallel timeout 5 bash` give [] / []. Suggested fix: a `{...}` pattern in the -c string or command words gives dynamic_code, and the head follows `_prefix_steps` before the reader check, failing closed on an unresolved wrapped command; remove the dead `unknown` variable in `_parallel_code`.
- (medium) Option table mismatch: `-m` and `--plus` are in `_PARALLEL_VALUE` but take no value in GNU parallel, so the next word is eaten as their value (parser differential; `parallel -m echo ::: a` reads `echo` as the value). Suggested fix: move them to `_PARALLEL_FLAGS` and check the remaining entries against the man page.

Severity of this entry raised to high by the first item.

## Steps to reproduce

1. Run analyze_command on the strings above (nothing is executed).

## Expected behavior

The command template and the ::: arguments are classified as code.

## Actual behavior

No flag beyond deny_token_unmatched.

## Root cause

`_parallel_code` modeled parallel piecemeal: the -c string was returned as literal code with `{}`, the reader check ran only on the first command word, wrappers fell through, and `-m`/`--plus` sat in `_PARALLEL_VALUE`.

## Fix

Replaced by an allow-list (`_parallel_code`, `_parallel_template`, `_parallel_takes_file`, `_PARALLEL_FORBIDDEN`): clean only when every option is known, the command template (words joined, `{...}` replaced by a placeholder) parses and every command site has a literal program that is not a shell, code reader, eval/source or wrapper. The composed command is classified normally (git_push propagates; `parallel git ::: push` is judged as git unknown). Wrappers, shells, readers and `-c` strings block; `:::` literal arguments are data or classified one level down; `::::`, `-a`, stdin and `{=` give dynamic_code. Round 5 hardening: `{}` in any quoting context or heredoc gives dynamic_code unless the sources are safe literals; `-S` hosts must start alphanumeric; PARALLEL/PARALLEL_SHELL set in the text gives dynamic_code.

Coverage of this entry: Evidence lines (`parallel ::: 'git push'`, `eval`, `bash -c`, `git push {}`, `bash -c 'git push {}'`, `bash -c {}`, `eval {}`, `| bash`, `nice sh -c`, `--pipe 'cat | bash'`) and both "Seen again" items (`sh -c {}`, `nohup sh`, `timeout 5 bash`, `-m`/`--plus` moved to flags, dead variable removed) are covered. Remaining: none in this entry; the full option table review is logged in the refactor backlog. Gate: 1145 tests pass.
