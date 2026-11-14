# Refactor backlog

Planned refactors that aren't urgent bugs but are worth doing deliberately, one file per refactor.

- File name: `YYYY-MM-DD-short-slug.md` (date opened, slug describing the refactor).
- Start every new entry from `TEMPLATE.md`.
- Update `Status` as it moves through `Proposed` -> `In progress` -> `Done` (link the PR) or `Dropped` (say why).
- If a refactor is large enough to need a design decision, write a spec first - a feature folder `../../features/<slug>/` with only `spec.md` (its **Source** points back to this entry) - and link it here instead of duplicating the reasoning. In a project still on the legacy layout, the spec goes in `../../specs/`.
- Keep the index below in sync whenever an entry is created or its status changes.

## Index

| Entry | Status |
| --- | --- |
| [Versioned unittest suite for agent-audit hook](2026-11-11-audit-hook-test-suite.md) | Done | |
| [md_outside_docs false positive on main-session root .md files](2026-11-11-audit-md-outside-docs-false-positive.md) | Done |
| [Align project-docs and implement skills with configurable docs root](2026-11-11-skills-configurable-docs-root.md) | Done |
| [agent-audit: nested repo cwd does not consult the parent repo's run](2026-11-11-audit-nested-repo-run-lookup.md) | Proposed |
| [agent-audit: scratch exemption accepts any /tmp/claude-* dir](2026-11-11-audit-scratch-exemption-too-broad.md) | Done |
| [agent-audit: out_of_scope_write fallback sets no scratch key](2026-11-12-audit-scratch-missing-on-resolution-failure.md) | Proposed |
| [agent-audit: docs_write_by_implementer covers only stack implementers](2026-11-12-audit-docs-write-flag-implementers-only.md) | Proposed |
| [agent-audit: md_outside_docs README exemption matches by suffix](2026-11-12-audit-md-exemption-basename.md) | Done |
| [hooks tests: Pyright noise (unresolved _support, possibly unbound out)](2026-11-12-hooks-tests-pyright-noise.md) | Proposed |
| [hooks tests: docstrings cite docs/ paths that live under .claude/docs/](2026-11-12-hooks-tests-stale-docs-paths.md) | Proposed |
| [agent-audit: edits to the root CLAUDE.md docs root declaration are not flagged](2026-11-13-audit-docs-root-declaration-unprotected.md) | Proposed |
| [agent-audit: Bash-based file writes are not audited as writes](2026-11-13-audit-bash-writes-unaudited.md) | Proposed |
| [planner agent contradicts itself on where it may write (OPEN_QUESTIONS.md)](2026-11-13-planner-write-scope-contradiction.md) | Proposed |
| [agent-workflow.md 13.1 says the hook is a no-op without an active run](2026-11-13-agent-workflow-13-1-outdated.md) | Proposed |
| [agent-audit: no guard against interactive programs run through Bash](2026-11-13-audit-interactive-app-guard.md) | Proposed |
| [agent-audit: strip_prefixes does not strip env, nice and nohup wrappers](2026-11-13-audit-strip-prefixes-wrappers.md) | Merged into audit-shell-lexer |
| [agent-audit: hook hardening (metrics file, run state size, timeouts)](2026-11-13-audit-hook-hardening.md) | Done |
| [agent-audit: quote-blind SEGMENT_SPLIT splits inside quoted arguments](2026-11-13-audit-segment-split-quote-blind.md) | Merged into audit-shell-lexer |
| [agent-audit: nvim shell-execution forms not classified](2026-11-13-audit-nvim-shell-exec-unclassified.md) | Merged into audit-shell-lexer |
| [agent-audit: timeout parsing limits (locale strtod, nested unknown durations)](2026-11-13-audit-timeout-parsing-limits.md) | Done |
| [agent-audit: nvim nesting depth cap reuses the docker_lifecycle deny](2026-11-13-audit-nvim-depth-cap-category.md) | Done |
| [agent-audit: nvim -l ... --busted (lazy.nvim minit) not recognized as a Lua test runner](2026-11-13-audit-nvim-busted-minit-runner.md) | Proposed |
| [agent-audit: PACKAGE_HINT treats ./spec and ./tests as package paths](2026-11-13-audit-package-hint-dot-slash.md) | Proposed |
| [tdd skill: step 2 allows not-implemented throws, step 4 requires assertion failures](2026-11-13-tdd-stub-throw-rule.md) | Proposed |
| [hooks tests: claude-hooks suite exceeds the 5 s target (about 6 s for 462 tests, goal under 5 s)](2026-11-13-hooks-tests-suite-slow.md) | Proposed (partly done by audit-hook-hardening) |
| [agent-audit: shell lexer and parser for command positions (fails closed)](2026-11-13-audit-shell-lexer.md) | Proposed |
| [agent-audit: hook compiled on every call (launcher with cached bytecode)](2026-11-13-audit-hook-launcher-performance.md) | Proposed |
| [agent-audit: watchdog robustness notes](2026-11-13-audit-watchdog-robustness-notes.md) | Proposed |
