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
| [agent-audit: a group or subshell reading a pipe is not flagged](2026-11-14-audit-pipe-into-group-not-flagged.md) | high | Open |
| [agent-audit: git config keys that execute commands are not modeled (and cross-call aliases)](2026-11-14-audit-git-config-keys-run-commands.md) | high | Open |
| [agent-audit: dc, GNU sed e and awk system() execute commands without classification](2026-11-14-audit-dc-sed-awk-execute-code.md) | medium | Open |
| [agent-audit: env with a dynamic NAME stops the wrapper reading before GIT_CONFIG_PARAMETERS](2026-11-14-audit-env-dynamic-word-stops-wrapper.md) | low | Open |
| [agent-audit: ${!x[@]} with a tainted x is classified dynamic_code (false positive)](2026-11-14-audit-indirect-subscript-false-positive.md) | low | Open |
| [agent-audit: whole-script disqualifier sends a python or markdown heredoc body to the shell parser when the text has mkfifo](2026-11-14-audit-mkfifo-disqualifier-false-positive.md) | low | Open |
| [agent-audit: canary spans inside a backtick with escapes are relative to the unescaped text](2026-11-14-audit-canary-span-backtick-escapes.md) | low | Open |
| [agent-audit: heredoc with HTML body and a group-level redirect, or HEAD() { cat <<EOF }, reads as code (lex_error)](2026-11-14-audit-html-heredoc-group-redirect.md) | low | Open |
| [hooks tests: SP8 linearity test compares CPU times with a 5x ratio (flake risk)](2026-11-14-audit-sp8-linearity-flake-risk.md) | low | Open |
