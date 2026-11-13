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
| [agent-audit: active_run crashes on a run state that is not a JSON object](2026-11-12-audit-active-run-non-object-state.md) | medium | Open |
