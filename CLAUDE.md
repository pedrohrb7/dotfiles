# dotfiles

## Workflow

- docs layout: features

This repo's docs root is `.claude/docs/`, not `docs/` (the folder is not linked into `~/.claude`). Plans, specs, logs and the backlog live under it, and `docs_roots` in `.claude/hooks/agent-audit.json` lists it.

## Test suites

| Suite | Service | Type | Command | Gate |
|---|---|---|---|---|
| claude-hooks | .claude/hooks | unit + integration | `python3 -I -B -m unittest discover -s .claude/hooks/tests -t .claude/hooks` | task |

Always run with `-I -B` (isolates from `PYTHON*` and the user site, and keeps `__pycache__` out of the repo). Narrow run of one module: the same command with `-p 'test_<module>.py'`.
