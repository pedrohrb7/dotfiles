# Implementation log - design-director

<!-- Written by /implement only, append-only. One "Run" section per /implement run and one block per task, filled from the agents' YAML reports. The stack agents read this file before coding and follow the decisions recorded here; never re-decide something already logged without a scope request. -->

## Run 2026-11-11

### Task 3 - Template DESIGN_SYSTEM.md: criação x manutenção, Layout concept e Font family (done)

- **Files:** `.claude/templates/project-root/DESIGN_SYSTEM.md`
- **Decisions:** top comment says creation by `design-director` and maintenance by the main session with `design-system`; `Color` comment asks for light and dark always; new `## Layout concept` section right after `## Principles` (concept, one wireframe per platform in a code fence, avoided-patterns table with `Source`), inserted verbatim from the spec; `Font family` is now a `### Font family` subsection at the end of `Type scale`, table header `| Role | Family | Weights | Fallback stack | Source | License |`; nothing else changed.
- **Assumptions:** none
- **Approved scope:** none
- **Migrations / env vars:** none
- **Docs pending:** none
- **Note:** the hook flagged the edits as `out_of_scope_write` because it reads only `current_task`'s `allowed_paths` and task 1 ran in parallel as `current_task`; false positive, edits are inside the task's Files.

### Task 1 - Hook: isenção de md_outside_docs e categoria design_system_write_by_other (done)

- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/agent-audit.json`
- **Decisions:** constants `ROOT_DESIGN_SYSTEM` and `DESIGN_SYSTEM_WRITERS`; in `evaluate_write()` the `design-director` is exempt from `md_outside_docs` only for the root `DESIGN_SYSTEM.md`, and any actor outside `{design-director, main}` writing that file gets `design_system_write_by_other`; `WHY` entry and docstring updated; `agent-audit.json` has `"design_system_write_by_other": "warn"` after `backlog_write_by_other`. Flags exactly as in Design 2.1. The stdin harness (H1-H14, G1-G11, 37 C commands, 75 checks, all pass) is at `/tmp/claude-1000/-home-phrb-dotfiles/39adab46-c88f-4f19-a0f8-a267ae4d1871/scratchpad/harness.py` and copies the hook files, never touching the live hook; rerun it in Verification.
- **Assumptions:** none
- **Approved scope:** harness files in the session scratchpad (test-only, outside the repo)
- **Migrations / env vars:** none
- **Docs pending:** none
- **Note:** writing the harness through a Bash heredoc was denied as `docker_lifecycle` (heredoc body lines classified as commands); write harness files with the Write tool and run them with a plain `python3 -I <file>`.

### Task 2 - Métricas: rótulo da categoria nova e seção design-director (done)

- **Files:** `.claude/hooks/agent-metrics.py`
- **Decisions:** `FLAG_LABELS["design_system_write_by_other"]` with the Design 2.3 text; new `## design-director` section after `## Writes`, shown only when there is a `design-director` `SubagentStart` or any event with that actor: `calls`, writes outside the root `DESIGN_SYSTEM.md` (categories == [write], event != PreToolUse, rel != DESIGN_SYSTEM.md, up to 5 examples with `ts` and `rel`) and the by-hand transcript check line; reuses the existing `writes` list. A session without `design-director` events produces a byte-identical report (M3). Harness: `/tmp/claude-1000/-home-phrb-dotfiles/39adab46-c88f-4f19-a0f8-a267ae4d1871/scratchpad/m/harness_m.py` (synthetic JSONL via `AGENT_AUDIT_DIR`, diff against `agent-metrics.orig.py`).
- **Assumptions:** none
- **Approved scope:** harness files in the session scratchpad
- **Migrations / env vars:** none
- **Docs pending:** none

### Task 4 - Agent design-director (done)

- **Files:** `.claude/agents/design-director.md` (new)
- **Decisions:** frontmatter per D22 (f); body in English with the ten Design 4.2 sections in order, each with a "(plan rules ...)" line; uses the task 3 Layout concept and `### Font family` formats; Round 2 example is the 15.1 "Direction A" translated; added: the pattern list is a check, not a recipe; contrast ratios are computed by hand and the report says so; the agent does not offer to keep editing the file once it exists. The `md_outside_docs` warn on creating the file is the expected false positive. V5 script: `/tmp/claude-1000/-home-phrb-dotfiles/39adab46-c88f-4f19-a0f8-a267ae4d1871/scratchpad/v5.py`.
- **Assumptions:** none
- **Approved scope:** harness files in the session scratchpad
- **Migrations / env vars:** none
- **Docs pending:** none (README agents row already in the spec's docs list)
- **Manual checks:** scenarios 37-40 and U1-U6 in a new Claude Code session (the agent only loads in a new session).

### Task 5 - Manutenção: design-system e os CLAUDE.md dos templates (done)

- **Files:** `.claude/skills/design-system/SKILL.md`, `.claude/templates/node-ts-react/CLAUDE.md`, `.claude/templates/react-native/CLAUDE.md`
- **Decisions:** `design-system` description names `design-director` and says the skill maintains `DESIGN_SYSTEM.md`; step 1 is four bullets (not a table, to keep the preloaded skill short): offer, extraction, proposed value, and the note for `design-director` itself, each with main-session and subagent behavior; steps 2-5 and the pixel pass unchanged; `frontend-design` removed. Line 25 of both templates per Design 5 ("on any layout" in node-ts-react, "on any screen" in react-native).
- **Assumptions:** none
- **Approved scope:** none
- **Migrations / env vars:** none
- **Docs pending:** none

### Task 6 - Pontos de entrada: new-project, Workflow global e exceção no implement (done)

- **Files:** `.claude/skills/new-project/SKILL.md`, `.claude/CLAUDE.md`, `.claude/skills/implement/SKILL.md`
- **Decisions:** new-project step 3.1 `DESIGN_SYSTEM.md` item with nested Yes / No sub-bullets (UI service only, asked once; yes calls `design-director` after `PRD.md`, `CONSTRAINTS.md` and `Services` are filled; no leaves the tables blank and names the Workflow phrase and the `design-system` offer as later paths); step 8 report line covers created, left blank, or not applicable. Global `CLAUDE.md`: new Workflow row right after Discover (Visual direction -> `design-director`) and a `scope_requests` bullet on the root `DESIGN_SYSTEM.md` after "Subagents cannot ask the user". implement step 5.2: Design 6 exception appended (the path never enters `allowed_paths`). The only em dash in `CLAUDE.md` is the pre-existing quoted one in the "Never use the em dash" rule.
- **Assumptions:** none
- **Approved scope:** none
- **Migrations / env vars:** none
- **Docs pending:** none
- **Manual checks:** `/new-project` with a react profile (question once, agent only after yes) and with a backend-only profile (no question), in a new session.

### Task 7 - settings.json: remover o plugin frontend-design (done)

- **Files:** `.claude/settings.json`
- **Decisions:** removed only the `frontend-design@claude-plugins-official` line from `enabledPlugins` (one-line diff); hooks keep their five events, `ask` keeps two entries.
- **Assumptions:** none
- **Approved scope:** none
- **Migrations / env vars:** none
- **Docs pending:** `.claude/README.md:69` - the `frontend-design` paragraph becomes the creation (`design-director`) vs maintenance (`design-system`) split; V4 must return empty after the docs pass.

### Review fix r1 - hook: design_director_write_outside, name rule, approved_scope (done)

- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/agent-audit.json`, `.claude/hooks/agent-metrics.py`
- **Decisions:** new category `design_director_write_outside` (`block`): any `design-director` write that is not a `DESIGN_SYSTEM.md` is denied, also with no git root; WHY text and FLAG_LABELS entry added. Protection rule everywhere (md_outside_docs exemption, `design_system_write_by_other`, the block, metrics stray count): `PurePosixPath(path).name.casefold() == "design_system.md"`, anywhere in the repo (covers monorepo `apps/web/` and case-insensitive filesystems); `ROOT_DESIGN_SYSTEM` removed. Consequence: `.claude/templates/**/DESIGN_SYSTEM.md` is protected too (stack agents warn, the director can write it, main is free). Approved_scope targets matching the rule are dropped from the derived allowed paths, so `out_of_scope_write` still fires. Changed expectations: H2 now silent, H3 now deny, H10 now warn, M1 stray count 2 -> 1; new cases H15-H28 and M4-M5; harness 95 checks and metrics 9 checks, all pass.
- **Assumptions:** templates protected by name is accepted (no special case for `.claude/templates/`).
- **Approved scope:** harness files in the session scratchpad
- **Migrations / env vars:** none
- **Docs pending:** `agent-workflow.md` sections 13/14: the new block category and the name-based rule (root-only wording is obsolete).
- **Note:** the docs folder was moved from `docs/` to `.claude/docs/` at the user's request after this fix; paths in the run state, the spec and Index plan links and `agent-workflow.md` were updated.

### Review fix r2 - markdown: extraction branch, approved_scope wording, warn vs deny, UI detection (done)

- **Files:** `.claude/skills/design-system/SKILL.md`, `.claude/skills/implement/SKILL.md`, `.claude/CLAUDE.md`, `.claude/agents/design-director.md`
- **Decisions:** extraction requests have a fixed shape in `design-system` step 1 (`action: create`, `target: DESIGN_SYSTEM.md`, `reason: extraction of tokens in <files>`) and are told apart by the reason prefix; implement 5.2 and the global `CLAUDE.md` bullet have the three branches (missing file -> offer `design-director`; extraction -> main documents the tokens following `design-system`; proposed value -> main writes it), the decision is still recorded in `approved_scope` but the path never enters `allowed_paths`. `design-director`: a hook deny (`design_director_write_outside`) is never retried and the agent finishes `blocked` with `hook-denied` stating the file's state; a warn on a successful write is reported and the round continues. UI-service detection aligned with `new-project` (react / react-native by stack only).
- **Assumptions:** none
- **Approved scope:** none
- **Migrations / env vars:** none
- **Docs pending:** none

### Added scope r3 - configurable docs roots in the hook (done)

- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/agent-audit.json`
- **Decisions:** `agent-audit.json` has `"docs_roots": ["docs/", ".claude/docs/"]` (global list, user's choice) and a `_docs_roots` comment key; `docs_roots()` normalizes entries (strip, backslash to `/`, drop leading `./` and `/`, add trailing `/`, dedupe), skips non-string, empty, `.` and `..`; missing key, non-list or no valid entry -> `["docs/"]`; `evaluate_write` takes the roots with a `["docs/"]` default. The docs area and the backlog owner check (`<root>backlog/`) use the roots by prefix; nested `services/x/docs/` is not a root. `agent-metrics.py` unchanged. Harness: 119 ok (new D1-D10), metrics 9 pass.
- **Assumptions:** none
- **Approved scope:** user-approved addition to stage H after the docs folder moved to `.claude/docs/`
- **Migrations / env vars:** none
- **Docs pending:** `agent-workflow.md` sections 13/14: the `docs_roots` key (default, normalization, fallback) and the backlog check per root. Note: `project-docs` and `/implement` still resolve `docs/` at the repo root, so in this repo the feature path is passed explicitly.

### Review fix r4 - name-based wording and metrics example (done)

- **Files:** `.claude/hooks/agent-audit.py`, `.claude/hooks/agent-metrics.py`
- **Decisions:** `design_system_write_by_other` WHY says "a project's DESIGN_SYSTEM.md (any directory)"; its FLAG_LABELS entry starts "a DESIGN_SYSTEM.md written by someone other..."; metrics line is "writes other than to a DESIGN_SYSTEM.md: N (target 0)"; the design-director example prints `rel`, or `path` when there is no `rel`. No "root DESIGN_SYSTEM" wording left in either file. `harness_m.py` M1 examples scoped to the design-director section; label strings updated; M3 unchanged.
- **Assumptions:** none
- **Approved scope:** harness files in the session scratchpad
- **Migrations / env vars:** none
- **Docs pending:** none beyond r1/r3
