"""Tests for agent-metrics.py (the report over the JSONL written by agent-audit.py).

Source: spec audit-hook-test-suite, section Testing / test_agent_metrics.py (M1-M5 come from the
design-director spec, cases M). Everything runs in process with `metrics.METRICS_DIR` pointed at a
temporary directory and synthetic JSONL: nothing reads `~/.claude/metrics`.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ._support import metrics

T0 = "2026-11-12T10:00:00+00:00"


def ev(event="PostToolUse", **kw) -> dict:
    out = {"ts": T0, "event": event}
    out.update(kw)
    return out


def write_event(rel, actor="design-director", event="PostToolUse", **kw) -> dict:
    return ev(event, actor=actor, categories=["write"], rel=rel, **kw)


class MetricsCase(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="agent-metrics-test-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        patch = mock.patch.object(metrics, "METRICS_DIR", self.dir)
        patch.start()
        self.addCleanup(patch.stop)

    def session(self, name, events, mtime=None) -> Path:
        path = self.dir / f"{name}.jsonl"
        path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def report(self, events, title="T") -> str:
        return metrics.report(title, events)

    def cli(self, *args) -> str:
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["agent-metrics.py", *args]), contextlib.redirect_stdout(buf):
            metrics.main()
        return buf.getvalue()


def section(text: str, heading: str) -> str:
    """Body of the `## heading` section ('' when absent)."""
    parts = text.split(f"## {heading}")
    if len(parts) < 2:
        return ""
    return parts[1].split("\n## ")[0]


class DesignDirectorSection(MetricsCase):
    """Cases M1-M5 (design-director spec, cases M): the `## design-director` section and its flags."""

    def test_m1_stray_write_counted_and_flag_labelled(self):
        with self.subTest(case="M1"):
            events = [
                ev("SubagentStart", agent_type="design-director", agent_id="a1"),
                write_event("DESIGN_SYSTEM.md", flags=[]),
                write_event("NOTES.md", flags=["design_director_write_outside", "md_outside_docs"]),
                write_event("services/web/DESIGN_SYSTEM.md", flags=[]),
                ev("PostToolUse", actor="frontend-react", categories=["write"], rel="DESIGN_SYSTEM.md",
                   flags=["design_system_write_by_other"]),
            ]
            text = self.report(events)
            flags = section(text, "Flags")
            self.assertIn("**design_system_write_by_other** (1): " + metrics.FLAG_LABELS["design_system_write_by_other"], flags)
            dd = section(text, "design-director")
            self.assertIn("- calls: 1", dd)
            self.assertIn("writes other than to a DESIGN_SYSTEM.md: 1", dd)
            self.assertIn("`NOTES.md`", dd)
            self.assertEqual(dd.count("`NOTES.md`"), 1)
            self.assertNotIn("DESIGN_SYSTEM.md`", dd)

    def test_m2_only_design_system_writes(self):
        with self.subTest(case="M2"):
            events = [
                ev("SubagentStart", agent_type="design-director", agent_id="a1"),
                write_event("DESIGN_SYSTEM.md"),
                write_event("DESIGN_SYSTEM.md"),
            ]
            self.assertIn("writes other than to a DESIGN_SYSTEM.md: 0", section(self.report(events), "design-director"))

    def test_m3_no_design_director_events(self):
        with self.subTest(case="M3"):
            events = [
                ev("SubagentStart", agent_type="backend-node", agent_id="a1"),
                ev("PostToolUse", actor="backend-node", categories=["write"], rel="a.ts", flags=["out_of_scope_write"]),
            ]
            text = self.report(events)
            self.assertNotIn("## design-director", text)
            for heading in ("Agent calls", "Actions by category", "Gates (test-runner)", "Writes", "Flags"):
                self.assertIn(f"## {heading}", text)

    def test_m4_case_insensitive_name_in_subdirectory(self):
        with self.subTest(case="M4"):
            events = [
                ev("SubagentStart", agent_type="design-director", agent_id="a1"),
                write_event("apps/web/Design_System.md"),
            ]
            self.assertIn("writes other than to a DESIGN_SYSTEM.md: 0", section(self.report(events), "design-director"))

    def test_m5_record_without_rel_uses_path_and_category_label(self):
        with self.subTest(case="M5"):
            events = [
                ev("SubagentStart", agent_type="design-director", agent_id="a1"),
                ev("PostToolUse", actor="design-director", categories=["write"], path="/x/y.ts",
                   flags=["design_director_write_outside"]),
            ]
            text = self.report(events)
            dd = section(text, "design-director")
            self.assertIn("writes other than to a DESIGN_SYSTEM.md: 1", dd)
            self.assertIn("`/x/y.ts`", dd)
            self.assertIn(metrics.FLAG_LABELS["design_director_write_outside"], section(text, "Flags"))

    def test_pretooluse_write_is_not_counted_as_stray(self):
        events = [
            ev("SubagentStart", agent_type="design-director", agent_id="a1"),
            write_event("NOTES.md", event="PreToolUse"),
        ]
        self.assertIn("writes other than to a DESIGN_SYSTEM.md: 0", section(self.report(events), "design-director"))


class ReportSections(MetricsCase):
    """Cases R1-R9: `load` and `report` sections (agent-workflow.md, section 14.2)."""

    def test_r1_empty_list(self):
        with self.subTest(case="R1"):
            self.assertEqual(self.report([], "Session x"), "# Session x\n\nNo events.")

    def test_r2_load_skips_invalid_lines(self):
        with self.subTest(case="R2"):
            path = self.dir / "s.jsonl"
            path.write_text('{"a": 1}\nnot json\n{"b": 2}\n', encoding="utf-8")
            self.assertEqual(metrics.load([path]), [{"a": 1}, {"b": 2}])

    def test_r3_agent_calls_and_durations(self):
        with self.subTest(case="R3"):
            events = [
                ev("SubagentStart", ts="2026-11-12T10:00:00+00:00", agent_type="backend-node", agent_id="a1"),
                ev("SubagentStop", ts="2026-11-12T10:01:40+00:00", agent_type="backend-node", agent_id="a1"),
                ev("SubagentStart", ts="2026-11-12T10:02:00+00:00", agent_type="frontend-react", agent_id="a2"),
            ]
            calls = section(self.report(events), "Agent calls")
            self.assertIn("| backend-node | 1 | 100 |", calls)
            self.assertIn("| frontend-react | 1 | - |", calls)

    def test_r4_actions_by_category_and_actor(self):
        with self.subTest(case="R4"):
            events = [
                ev(actor="backend-node", categories=["lint"]),
                ev(actor="backend-node", categories=["lint"]),
                ev(actor="test-runner", categories=["lint", "typecheck"]),
            ]
            text = section(self.report(events), "Actions by category")
            self.assertIn("| lint | 3 | backend-node 2, test-runner 1 |", text)
            self.assertIn("| typecheck | 1 | test-runner 1 |", text)

    def test_r5_gates_count_only_test_runner(self):
        with self.subTest(case="R5"):
            events = [
                ev(actor="test-runner", categories=["test-full"]),
                ev(actor="test-runner", categories=["test-package"]),
                ev(actor="backend-node", categories=["test-full"]),
            ]
            self.assertIn("suite commands run by test-runner: 2 (full-repo: 1", section(self.report(events), "Gates (test-runner)"))

    def test_r6_writes_line(self):
        with self.subTest(case="R6"):
            events = [
                write_event("a", actor="backend-node"),
                write_event("b", actor="backend-node", in_run=True, in_scope=True),
                write_event("c", actor="backend-node", in_run=True, in_scope=False),
                write_event("d", actor="backend-node", in_run=True),
            ]
            self.assertIn(
                "- total: 4; during a run: 3; checked against allowed_paths: 2; outside: 1",
                section(self.report(events), "Writes"),
            )

    def test_writes_section_absent_without_writes(self):
        self.assertNotIn("## Writes", self.report([ev(actor="main", categories=["lint"])]))

    def test_r7_enforcement_decisions_grouped(self):
        with self.subTest(case="R7"):
            events = [
                ev("PreToolUse", actor="backend-node", decision="deny", decision_category="docker_lifecycle", cmd=f"docker restart {i}")
                for i in range(4)
            ]
            events.append(ev("PreToolUse", actor="main", decision="ask", decision_category="git_commit", cmd="git commit -m x"))
            text = section(self.report(events), "Enforcement decisions (PreToolUse)")
            self.assertIn("| deny | docker_lifecycle | 4 |", text)
            self.assertIn("| ask | git_commit | 1 |", text)
            deny_row = next(line for line in text.splitlines() if line.startswith("| deny |"))
            self.assertEqual(deny_row.count("`docker restart"), 3)
            self.assertLess(text.index("| deny |"), text.index("| ask |"))

    def test_r7_section_absent_without_decisions(self):
        self.assertNotIn("## Enforcement decisions", self.report([ev(actor="main", categories=["lint"])]))

    def test_r8_flags_count_only_posttooluse(self):
        with self.subTest(case="R8"):
            events = [
                ev("PreToolUse", actor="main", flags=["docker_lifecycle"], cmd="docker up"),
                ev("PostToolUse", actor="main", flags=["docker_lifecycle"], cmd="docker up"),
            ]
            self.assertIn("**docker_lifecycle** (1)", section(self.report(events), "Flags"))
            only_pre = [ev("PreToolUse", actor="main", flags=["docker_lifecycle"], cmd="docker up")]
            self.assertEqual(section(self.report(only_pre), "Flags").strip(), "None.")

    def test_r9_flag_examples_capped_at_five(self):
        with self.subTest(case="R9"):
            events = [ev(actor="main", flags=["git_push"], cmd=f"git push {i}") for i in range(7)]
            flags = section(self.report(events), "Flags")
            self.assertIn("**git_push** (7)", flags)
            self.assertEqual(flags.count("`git push "), 5)
            self.assertIn("... 2 more", flags)

    def test_flags_sorted_by_count(self):
        events = [ev(actor="main", flags=["git_push"], cmd="a")] + [
            ev(actor="main", flags=["git_commit"], cmd="b") for _ in range(2)
        ]
        flags = section(self.report(events), "Flags")
        self.assertLess(flags.index("git_commit"), flags.index("git_push"))

    def test_header_lists_runs_and_event_range(self):
        events = [
            ev(ts="2026-11-12T10:00:00+00:00", run="feat-b"),
            ev(ts="2026-11-12T11:00:00+00:00", run="feat-a"),
        ]
        text = self.report(events)
        self.assertIn("- events: 2, from 2026-11-12T10:00:00+00:00 to 2026-11-12T11:00:00+00:00", text)
        self.assertIn("- runs: feat-a, feat-b", text)


class Cli(MetricsCase):
    """Cases L1-L7: `main` argument handling, with `METRICS_DIR` patched to a temp dir."""

    def sessions(self):
        """Three sessions with increasing mtime: old < mid < new."""
        self.session("old", [ev(actor="main", categories=["lint"], run="r1")], mtime=1_000_000_000)
        self.session("mid", [ev(actor="main", categories=["lint"], run="r2")], mtime=1_100_000_000)
        self.session("new", [ev(actor="main", categories=["lint"], run="r1")], mtime=1_200_000_000)

    def test_l1_missing_metrics_dir(self):
        with self.subTest(case="L1"):
            missing = self.dir / "does-not-exist"
            with mock.patch.object(metrics, "METRICS_DIR", missing):
                with self.assertRaises(SystemExit) as cm:
                    self.cli()
            self.assertIn("No metrics yet", str(cm.exception.code))

    def test_l2_default_is_most_recent_session(self):
        with self.subTest(case="L2"):
            self.sessions()
            out = self.cli()
            self.assertIn("# Session new", out)
            self.assertNotIn("# Session mid", out)
            self.assertNotIn("# Session old", out)

    def test_l3_last_n(self):
        with self.subTest(case="L3"):
            self.sessions()
            out = self.cli("--last", "2")
            self.assertIn("# Session mid", out)
            self.assertIn("# Session new", out)
            self.assertNotIn("# Session old", out)
            self.assertEqual(out.count("# Session "), 2)

    def test_l4_session(self):
        with self.subTest(case="L4"):
            self.sessions()
            out = self.cli("--session", "mid")
            self.assertIn("# Session mid", out)
            self.assertEqual(out.count("# Session "), 1)

    def test_l5_since_with_merge(self):
        with self.subTest(case="L5"):
            # mtimes: old 2001, mid 2004, new 2008; the cutoff drops only "old".
            self.sessions()
            out = self.cli("--since", "2004-01-01", "--merge")
            self.assertTrue(out.startswith("# 2 sessions"), out[:40])
            self.assertNotIn("# Session ", out)
            self.assertIn("- events: 2", out)

    def test_since_without_merge_reports_each_file(self):
        self.sessions()
        out = self.cli("--since", "2004-01-01")
        self.assertIn("# Session mid", out)
        self.assertIn("# Session new", out)
        self.assertNotIn("# Session old", out)

    def test_l6_run_filters_events_across_sessions(self):
        with self.subTest(case="L6"):
            self.sessions()
            out = self.cli("--run", "r1")
            self.assertTrue(out.startswith("# Run r1"))
            self.assertIn("- events: 2", out)
            self.assertIn("- runs: r1", out)
            self.assertNotIn("r2", out)

    def test_l7_unknown_session(self):
        with self.subTest(case="L7"):
            self.sessions()
            with self.assertRaises(SystemExit) as cm:
                self.cli("--session", "nope")
            self.assertEqual(cm.exception.code, "No matching sessions.")

    def test_since_matching_nothing_exits(self):
        self.sessions()
        with self.assertRaises(SystemExit) as cm:
            self.cli("--since", "2099-01-01")
        self.assertEqual(cm.exception.code, "No matching sessions.")

    def test_never_touches_real_metrics_dir(self):
        self.assertEqual(metrics.METRICS_DIR, self.dir)
        self.assertNotEqual(metrics.METRICS_DIR, Path.home() / ".claude" / "metrics")


if __name__ == "__main__":
    unittest.main()
