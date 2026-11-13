# hooks tests: docstrings cite docs/ paths that live under .claude/docs/

- **Status:** Proposed
- **Opened:** 2026-11-12
- **Scope:** `.claude/hooks/tests/*.py` (`test_write_areas.py`, `test_write_scope.py`, `test_heredoc.py`, `test_classify.py`, `test_design_system.py`)
- **Source:** feature skills-docs-root, specker, 2026-11-12
- **Priority:** low

## Motivation

References in docstrings point to files that do not exist at the cited path, so readers cannot follow them.

## Current state

Docstrings cite `docs/backlog/...` and `docs/features/...`, but in this repo those files live under `.claude/docs/`, so the references are stale. Root cause: the tests were written before the docs root was declared. Examples: `test_write_areas.py:3`, `test_write_scope.py:3`, `test_heredoc.py:3`, `test_classify.py:3`, `test_design_system.py:4`.

## Proposed change

Prefix the cited paths with `.claude/` in docstrings and comments only. Fixtures that use `docs/` as test data stay as they are.

## Risks

Low: docstring-only edits. Do not touch path strings that are test inputs.

## Out of scope

Test logic and the hook itself.
