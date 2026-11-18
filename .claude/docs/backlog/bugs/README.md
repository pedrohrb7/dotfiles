# Bug backlog

Confirmed bugs that need fixing, one file per bug.

- File name: `YYYY-MM-DD-short-slug.md` (date the bug was reported, slug is a few words describing it).
- Start every new entry from `TEMPLATE.md`.
- Update `Status` in place as the bug moves through `Open` -> `In progress` -> `Fixed` (link the fix) or `Won't fix` (say why). Don't delete resolved entries - they're a record.
- Entries are written only by `backlog-keeper`, so they stay deduplicated.
- An entry needs real repro steps and evidence: the request and its filtered log lines, the failing command and its output, or the UI steps the user observed. A bug reported by the user is recorded with the steps as they observed them (`Evidence: reported by the user`); the bug fix flow reproduces it end to end before fixing. A bug report with no way to reproduce it isn't actionable.
- Keep the index below in sync whenever an entry is created or its status changes.

## Index

| Entry | Severity | Status |
| --- | --- | --- |
| [agent-audit: parallel tasks' writes flagged out_of_scope_write](2026-11-11-audit-parallel-task-out-of-scope.md) | medium | Fixed |
| [agent-audit: heredoc body lines classified as commands (false docker_lifecycle)](2026-11-11-audit-heredoc-docker-lifecycle.md) | medium | Fixed |
| [Write-capable agents can disable or rewrite the audit hook and agent definitions](2026-11-11-audit-hook-self-protection.md) | medium | Open |
| [agent-audit: path checks skip targets outside the git root](2026-11-11-audit-path-checks-outside-git-root.md) | low | Fixed |
| [agent-audit: external_request misses bash /dev/tcp egress](2026-11-11-audit-dev-tcp-egress.md) | low | Open |
| [agent-audit: classify_command ignores python3 -m unittest/pytest as test commands](2026-11-12-audit-python3-test-commands-not-classified.md) | low | Open |
| [agent-audit tests: 14 fail when TMPDIR is under /tmp/claude-*](2026-11-12-audit-tests-fail-under-tmp-claude.md) | medium | Fixed |
| [agent-audit: active_run crashes on a run state that is not a JSON object](2026-11-12-audit-active-run-non-object-state.md) | medium | Fixed |
| [agent-audit: heredoc data-sink misjudged after a command substitution (sh body stripped)](2026-11-13-audit-heredoc-sink-runs-sh.md) | medium | Fixed |
| [agent-audit: unquoted heredoc body with command substitution is stripped as data](2026-11-13-audit-heredoc-unquoted-substitution.md) | high | Fixed |
| [agent-audit: a group or subshell reading a pipe is not flagged](2026-11-14-audit-pipe-into-group-not-flagged.md) | high | Fixed |
| [agent-audit: git config keys that execute commands are not modeled (and cross-call aliases)](2026-11-14-audit-git-config-keys-run-commands.md) | high | Fixed |
| [agent-audit: dc, GNU sed e and awk system() execute commands without classification](2026-11-14-audit-dc-sed-awk-execute-code.md) | medium | Open |
| [agent-audit: env with a dynamic NAME stops the wrapper reading before GIT_CONFIG_PARAMETERS](2026-11-14-audit-env-dynamic-word-stops-wrapper.md) | low | Open |
| [agent-audit: ${!x[@]} with a tainted x is classified dynamic_code (false positive)](2026-11-14-audit-indirect-subscript-false-positive.md) | low | Open |
| [agent-audit: whole-script disqualifier sends a python or markdown heredoc body to the shell parser when the text has mkfifo](2026-11-14-audit-mkfifo-disqualifier-false-positive.md) | low | Open |
| [agent-audit: canary spans inside a backtick with escapes are relative to the unescaped text](2026-11-14-audit-canary-span-backtick-escapes.md) | low | Open |
| [agent-audit: heredoc with HTML body and a group-level redirect, or HEAD() { cat <<EOF }, reads as code (lex_error)](2026-11-14-audit-html-heredoc-group-redirect.md) | low | Open |
| [hooks tests: SP8 linearity test compares CPU times with a 5x ratio (flake risk)](2026-11-14-audit-sp8-linearity-flake-risk.md) | low | Open |
| [agent-audit: git_commit matches only the commit subcommand (commit-tree, update-ref, merge, cherry-pick, revert, am, rebase regression)](2026-11-14-audit-git-commit-subcommand-regression.md) | medium | Fixed |
| [agent-audit: a shell reading stdin from a process-substitution writer is not flagged](2026-11-16-audit-procsub-writer-shell-not-flagged.md) | high | Fixed |
| [agent-audit: a function or coproc used as a pipe receiver is not followed](2026-11-16-audit-function-coproc-pipe-receiver-not-followed.md) | high | Fixed |
| [agent-audit: a group or subshell with a process-substitution stdin is not flagged](2026-11-16-audit-group-procsub-stdin-not-flagged.md) | high | Fixed |
| [agent-audit: plain pipe readers other than a shell are not flagged as piped_shell](2026-11-16-audit-pipe-readers-not-piped-shell.md) | medium | Fixed |
| [agent-audit: operand-path stdin aliases are matched exactly](2026-11-16-audit-operand-stdin-alias-exact-match.md) | medium | Fixed |
| [agent-audit: git subcommands that run shell code are not read as code](2026-11-16-audit-git-subcommands-run-shell-code.md) | high | Fixed |
| [agent-audit: repo-alias trust allowlist includes programs that write files or run programs](2026-11-16-audit-repo-alias-allowlist-writes-and-runs.md) | high | Open |
| [agent-audit: git config keys gc.recentObjectsHook and man.<tool>.path not modeled](2026-11-16-audit-git-config-keys-missing-hook-path.md) | medium | Open |
| [agent-audit: env vars SSH_ASKPASS, SSH_ASKPASS_REQUIRE and BROWSER not modeled as program kind](2026-11-16-audit-git-env-vars-askpass-browser.md) | medium | Open |
| [agent-audit: code fed through xargs to a git code option, and variable clone URLs, get no flag](2026-11-16-audit-xargs-git-code-option-variable-clone-url.md) | low | Open |
| [agent-audit: other git programs that start arbitrary programs are not modeled (svn --authors-prog, hook run, submodule update=!cmd)](2026-11-16-audit-git-other-program-starters.md) | low | Open |
| [agent-audit: a pipe into a code string (eval, bash -c) is not followed](2026-11-18-audit-pipe-into-code-string-not-followed.md) | high | Fixed |
| [agent-audit: trap actions run with the stdin of the context they fire in, not followed](2026-11-18-audit-trap-action-stdin-context.md) | medium | Fixed |
| [agent-audit: a mapfile/readarray -C callback runs with mapfile's stdin, not followed](2026-11-18-audit-mapfile-callback-stdin.md) | medium | Fixed |
| [agent-audit: a shell reading a named pipe or an fd set up elsewhere is not tracked](2026-11-18-audit-named-pipe-fd-stdin-not-tracked.md) | medium | Fixed |
| [agent-audit: stdin set by exec is not followed](2026-11-18-audit-exec-stdin-not-followed.md) | medium | Fixed |
| [agent-audit: a file written earlier in the same text and then sourced is not read](2026-11-18-audit-sourced-file-written-in-same-text.md) | medium | Open |
| [agent-audit: time and ! after a pipe are not parsed (lex_error, fail closed)](2026-11-18-audit-time-bang-after-pipe-lex-error.md) | low | Open |
| [agent-audit: a glob receiver head on a heredoc or here-string is not resolved as a possible same-shell loader](2026-11-18-audit-glob-receiver-head-not-same-shell.md) | high | Fixed |
| [agent-audit: zsh command_not_found_handler is not modeled](2026-11-18-audit-zsh-command-not-found-handler-not-modeled.md) | high | Fixed |
| [agent-audit: the stdin facts pass lacks function positional values and exported GIT_CONFIG_*](2026-11-18-audit-stdin-facts-pass-diverges.md) | medium | Open |
| [agent-audit: a code string registered by complete -C or bind -x is not read as code](2026-11-18-audit-code-string-registered-by-complete-bind.md) | medium | Open |
| [agent-audit: _brace_words keeps the empty alternative ({git,} push passes)](2026-11-18-audit-brace-empty-alternative.md) | high | Open |
| [agent-audit: the GNU parallel command line is not classified or read as code](2026-11-18-audit-parallel-command-line-not-read-as-code.md) | medium | Open |
| [agent-audit: zsh function table misses hook installation shapes and the functions parameter](2026-11-18-audit-zsh-hook-installation-shapes.md) | medium | Open |
| [agent-audit: BASH_ENV is not modeled (a stdin or process-substitution file is sourced by bash)](2026-11-18-audit-bash-env-not-modeled.md) | high | Open |
| [agent-audit: env -C / --chdir is not counted as a directory change](2026-11-18-audit-env-chdir-not-a-directory-change.md) | medium | Open |
| [agent-audit: stdin alias `..` order, and fifo movers and link makers inside wrappers or variable heads are not resolved](2026-11-18-audit-stdin-alias-fifo-movers-and-dotdot.md) | medium | Open |
| [agent-audit: a backtick in a `<&` target and a dynamic attached `at -f$s` value are not resolved](2026-11-18-audit-stdin-dynamic-fd-and-at-file-value.md) | low | Open |
