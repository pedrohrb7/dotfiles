# dotfiles

## Workflow

- docs layout: features
- docs root: .claude/docs/

This repo's docs live under `.claude/docs/`, not `docs/` (the folder is not linked into `~/.claude`). The `docs root` line above is the single source: the `project-docs` skill resolves every plan, spec, log and backlog path under it, and the `agent-audit` hook reads it to define the docs area.

## Test suites

| Suite | Service | Type | Command | Gate |
|---|---|---|---|---|
| claude-hooks | .claude/hooks | unit + integration | `python3 -I -B -m unittest discover -s .claude/hooks/tests -t .claude/hooks` | task |

Always run with `-I -B` (isolates from `PYTHON*` and the user site, and keeps `__pycache__` out of the repo). Narrow run of one module: the same command with `-p 'test_<module>.py'`.
