# agent-audit: heredoc body lines classified as commands (false docker_lifecycle)

- **Status:** Fixed
- **Reported:** 2026-11-11
- **Severity:** medium
- **Environment:** local (Claude Code config, hooks)
- **Source:** feature design-director (stage H), /implement run 2026-11-11, backend-python
- **Related:** [design-director spec](../../features/design-director/spec.md)

## Evidence

`classify_command` in `.claude/hooks/agent-audit.py`; /implement log task 1 note.

## Steps to reproduce

1. Run a Bash heredoc that writes a file containing a line `docker compose ... restart` or `up`.

## Expected behavior

The heredoc body is data and is not classified.

## Actual behavior

The command is denied as `docker_lifecycle`.

## Root cause

`SEGMENT_SPLIT` (agent-audit.py) splits on newlines and `classify_command` classified every line, heredoc bodies included.

## Fix

New pre-pass `strip_heredoc_bodies()` (single-pass scanner `_scan_heredocs`) removes heredoc bodies before classification, fail-closed: only provable data sinks are stripped.

- Top-level `cat`/`tee` with no pipe or process/command substitution on the opener line.
- `git commit -F -`, or `$(cat <<EOF)` as the `-m`/`--message` value, without `-c alias.*`/`core.*`.
- `gh pr|issue|release create|edit|comment|review` with `--body-file -`/`-F -`, or `$(cat)` as `--body`/`-b`/`--title`/`-t`.

Every other heredoc body is still classified. Fail-safe markers disable stripping: `${`, `$'`, `$[`, backticks, `\r`, `>(`, `<(`, `mkfifo`, `coproc`, `exec` redirection, `cat`/`tee` function definitions, fd>=3 redirects, newline in quotes while a heredoc is pending. Decided by the user after code and security review (3 rounds).

- Changed files: `.claude/hooks/agent-audit.py`; new `.claude/hooks/tests/__init__.py`, `_loader.py`, `test_agent_audit.py`.
- Regression test: `.claude/hooks/tests/test_agent_audit.py` (stdlib unittest, 27 tests; `cd .claude/hooks && python3 -m unittest discover -s tests -t .`).
- Verify: the repro payload (`cat > /tmp/notes.md <<'EOF'` with `docker compose restart api` in the body) piped into the hook gets no deny.
