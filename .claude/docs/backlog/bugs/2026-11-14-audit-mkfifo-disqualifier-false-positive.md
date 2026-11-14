# agent-audit: whole-script disqualifier sends a python or markdown heredoc body to the shell parser when the text has mkfifo

- **Status:** Open
- **Reported:** 2026-11-14
- **Severity:** low
- **Environment:** local (Claude Code hooks)
- **Source:** agent run: feature audit-shell-lexer, first review (code-reviewer)
- **Related:** [audit-shell-lexer spec](../../features/audit-shell-lexer/spec.md), [log](../../features/audit-shell-lexer/log.md)

## Evidence

- First review (replay E3): 4 `mkfifo` probes flagged. Shape: `mkfifo p; cat > f.py <<'EOF'` with a python or markdown body.

## Steps to reproduce

1. Classify `mkfifo p; cat > f.py <<'EOF'` followed by a python body and `EOF`.

## Expected behavior

The body is data (`cat` sink with its own redirect).

## Actual behavior

The whole-script disqualifier reads the body as shell code.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
