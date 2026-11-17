# agent-audit: repo-alias trust allowlist includes programs that write files or run programs

- **Status:** Open
- **Reported:** 2026-11-16
- **Severity:** high
- **Environment:** local (Claude Code hooks)
- **Source:** automated security review of commit 02a51c3
- **Related:** Follow-up of [git-config-keys entry](2026-11-14-audit-git-config-keys-run-commands.md)

## Evidence

`_READ_ONLY_PROGRAMS` / `_GIT_READ_VERBS` in `_script_moves` (`.claude/hooks/agent_audit_classify.py`) trust programs that can write files or run programs: `sort -o/--output`, `sort --compress-program`, `uniq IN OUT`, `tree -o`, `rg --pre/--pre-glob`; git `log/show/diff/whatchanged/format-patch --output=`. The `.gitconfig`/`.git/config` check runs on the raw text instead of parsed, de-quoted words.

## Steps to reproduce

1. Classify a command using the items above with a blocked command or a write outside scope (synthetic input).

## Expected behavior

Reject output/program options per program or drop them from the allowlist; treat git `--output` as a write; check parsed words; or resolve repo aliases only when the text is a single git command.

## Actual behavior

Allowed, or only an unmatched-token result; no flag.

## Root cause

Not diagnosed yet.

## Fix

Not fixed yet.
