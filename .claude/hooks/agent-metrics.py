#!/usr/bin/env python3
"""Report on what agents did, from the JSONL written by agent-audit.py.

Usage:
  agent-metrics.py                 # the most recent session
  agent-metrics.py --last 5        # the 5 most recent sessions, one report each
  agent-metrics.py --session <id>  # one session
  agent-metrics.py --since 2026-11-10 [--merge]  # sessions changed since a date (--merge: one combined report)
  agent-metrics.py --run <slug>    # only events of one /implement run (any session)

The targets come from agent-workflow.md, section 14.2.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

METRICS_DIR = Path(os.environ.get("AGENT_AUDIT_DIR", str(Path.home() / ".claude" / "metrics")))

FLAG_LABELS = {
    "out_of_scope_write": "writes outside allowed_paths (target 0 without approval)",
    "md_outside_docs": "new .md files outside docs/ (target 0)",
    "docs_write_by_implementer": "docs (docs/, README, CHANGELOG, .env.example, DEPLOY.md) edited by implementers - docs-writer owns them (target 0)",
    "write_by_readonly_agent": "files written by a read-only agent: ui-verifier, test-runner, reviewers (target 0)",
    "backlog_write_by_other": "backlog written by someone other than backlog-keeper (target 0)",
    "design_system_write_by_other": "a DESIGN_SYSTEM.md written by someone other than design-director or the main session - propose values in scope_requests (target 0)",
    "design_director_write_outside": "design-director write outside DESIGN_SYSTEM.md, blocked by the hook (target 0)",
    "suite_by_non_runner": "suites run by agents other than test-runner (target 0)",
    "docker_lifecycle": "docker up/down/restart/exec/run (target 0)",
    "docker_build": "docker builds (only when the task changes a Dockerfile)",
    "git_commit": "commits (only with explicit authorization)",
    "git_push": "pushes (only with explicit authorization)",
    "visual_tool": "browser/screenshot tool calls outside ui-verifier (target 0)",
    "external_request": "requests to non-local hosts (target 0)",
}


def load(paths: list[Path]) -> list[dict]:
    events = []
    for p in paths:
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def report(title: str, events: list[dict]) -> str:
    out = [f"# {title}", ""]
    if not events:
        return "\n".join(out + ["No events."])
    out.append(f"- events: {len(events)}, from {events[0].get('ts')} to {events[-1].get('ts')}")
    runs = sorted({e["run"] for e in events if e.get("run")})
    if runs:
        out.append(f"- runs: {', '.join(runs)}")
    out.append("")

    starts = Counter(e.get("agent_type") or "?" for e in events if e.get("event") == "SubagentStart")
    durations: dict[str, list[float]] = defaultdict(list)
    started: dict[str, datetime] = {}
    for e in events:
        ts = datetime.strptime(e["ts"], "%Y-%m-%dT%H:%M:%S%z") if e.get("ts") else None
        if e.get("event") == "SubagentStart" and e.get("agent_id") and ts:
            started[e["agent_id"]] = ts
        elif e.get("event") == "SubagentStop" and e.get("agent_id") in started and ts:
            durations[e.get("agent_type") or "?"].append((ts - started.pop(e["agent_id"])).total_seconds())
    if starts:
        out += ["## Agent calls", "", "| agent | calls | avg duration (s) |", "|---|---|---|"]
        for agent, n in starts.most_common():
            d = durations.get(agent)
            out.append(f"| {agent} | {n} | {sum(d) / len(d):.0f} |" if d else f"| {agent} | {n} | - |")
        out.append("")

    by_cat: dict[str, Counter] = defaultdict(Counter)
    for e in events:
        for c in e.get("categories") or []:
            by_cat[c][e.get("actor", "?")] += 1
    if by_cat:
        out += ["## Actions by category", "", "| category | total | by actor |", "|---|---|---|"]
        for cat in sorted(by_cat):
            actors = ", ".join(f"{a} {n}" for a, n in by_cat[cat].most_common())
            out.append(f"| {cat} | {sum(by_cat[cat].values())} | {actors} |")
        out.append("")

    gates = [e for e in events if e.get("actor") == "test-runner" and set(e.get("categories") or []) & {"test-full", "test-package"}]
    full = [e for e in gates if "test-full" in e.get("categories", [])]
    out += [
        "## Gates (test-runner)",
        "",
        f"- suite commands run by test-runner: {len(gates)} (full-repo: {len(full)}; target: 1 full gate per run)",
        "",
    ]

    writes = [e for e in events if e.get("categories") == ["write"]]
    in_run = [e for e in writes if e.get("in_run")]
    checked = [e for e in in_run if e.get("in_scope") is not None]
    if writes:
        out += [
            "## Writes",
            "",
            f"- total: {len(writes)}; during a run: {len(in_run)}; checked against allowed_paths: {len(checked)}; "
            f"outside: {sum(1 for e in checked if not e['in_scope'])}",
            "",
        ]

    director_calls = sum(1 for e in events if e.get("event") == "SubagentStart" and e.get("agent_type") == "design-director")
    if director_calls or any(e.get("actor") == "design-director" for e in events):
        stray = [
            e
            for e in writes
            if e.get("actor") == "design-director" and e.get("event") != "PreToolUse" and Path(e.get("rel") or e.get("path") or "").name.casefold() != "design_system.md"
        ]
        out += [
            "## design-director",
            "",
            f"- calls: {director_calls}",
            f"- writes other than to a DESIGN_SYSTEM.md: {len(stray)} (target 0)",
        ]
        for e in stray[:5]:
            out.append(f"  - {e.get('ts')} `{e.get('rel') or e.get('path')}`")
        if len(stray) > 5:
            out.append(f"  - ... {len(stray) - 5} more")
        out += [
            "- calls without a prior yes from the user: check by hand in the transcript (the hook does not see the conversation; target 0)",
            "",
        ]

    decisions = [e for e in events if e.get("event") == "PreToolUse" and e.get("decision")]
    if decisions:
        out += ["## Enforcement decisions (PreToolUse)", "", "| decision | category | count | examples |", "|---|---|---|---|"]
        grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for e in decisions:
            grouped[(e["decision"], e.get("decision_category", "?"))].append(e)
        for (decision, cat), items in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
            examples = "; ".join(f"{e.get('actor')}: `{(e.get('rel') or e.get('cmd') or e.get('tool') or '')[:60]}`" for e in items[:3])
            out.append(f"| {decision} | {cat} | {len(items)} | {examples} |")
        out += ["", "A blocked action that the user later approved, or a warn category with no real violation, is a false positive: keep it at warn. A warn category with only real violations and no false positives can be promoted to block in agent-audit.json.", ""]

    flagged = defaultdict(list)
    for e in events:
        if e.get("event") == "PreToolUse":
            continue  # counted above; the action itself is recorded by PostToolUse when it runs
        for f in e.get("flags") or []:
            flagged[f].append(e)
    out += ["## Flags", ""]
    if not flagged:
        out.append("None.")
    for flag, items in sorted(flagged.items(), key=lambda kv: -len(kv[1])):
        out.append(f"- **{flag}** ({len(items)}): {FLAG_LABELS.get(flag, '')}")
        for e in items[:5]:
            what = e.get("rel") or e.get("cmd") or e.get("tool")
            out.append(f"  - {e.get('ts')} {e.get('actor')}: `{what}`")
        if len(items) > 5:
            out.append(f"  - ... {len(items) - 5} more")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session")
    ap.add_argument("--last", type=int)
    ap.add_argument("--since", help="YYYY-MM-DD")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--run")
    args = ap.parse_args()

    if not METRICS_DIR.is_dir():
        sys.exit(f"No metrics yet in {METRICS_DIR}")
    files = sorted(METRICS_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if args.session:
        files = [METRICS_DIR / f"{args.session}.jsonl"]
    elif args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d").timestamp()
        files = [f for f in files if f.stat().st_mtime >= since]
    elif args.run:
        pass
    else:
        files = files[-(args.last or 1):]
    files = [f for f in files if f.exists()]
    if not files:
        sys.exit("No matching sessions.")

    if args.run:
        events = [e for e in load(files) if e.get("run") == args.run]
        print(report(f"Run {args.run}", events))
    elif args.merge:
        print(report(f"{len(files)} sessions", load(files)))
    else:
        print("\n\n".join(report(f"Session {f.stem}", load([f])) for f in files))


if __name__ == "__main__":
    main()
