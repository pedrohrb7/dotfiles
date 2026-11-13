# agent-audit: no guard against interactive programs run through Bash

- **Status:** Proposed
- **Opened:** 2026-11-13
- **Scope:** `.claude/hooks/agent-audit.py`
- **Source:** agent run: specker, feature lua-agent (spec `../../features/lua-agent/spec.md`)

## Motivation

An interactive program run through Bash blocks or takes over the session. Examples: `nvim` without `--headless`, `love`, and host app reloads such as wezterm or hammerspoon. The new `lua` agent is told not to run them and metric 14.2 in `agent-workflow.md` tracks it, but nothing enforces it.

## Current state

The hook has no category for interactive programs. Only the agent instructions and metric 14.2 cover it.

## Proposed change

A new hook category, for example `interactive_app`. It needs its own design: some nvim modes are legitimate and the list of host apps is open. Needs a spec.

User decision 2026-11-13: decide later, using the 14.2 metric data from the first scenarios 46-52.

## Risks

False positives on legitimate nvim modes (`--headless`) and an incomplete host app list.

## Out of scope

Changing the `lua` agent instructions.
