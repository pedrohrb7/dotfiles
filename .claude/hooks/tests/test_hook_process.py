"""The hook as a real process (stdin -> stdout/exit code), run from a private copy.

Source: audit-hook-test-suite spec, section Testing, `test_hook_process.py` (G1-G11, P1-P6). The
process runs `HookProcess`'s copy of the hook with its own `agent-audit.json`, metrics directory and
HOME: the live hook and the live config are never executed or read here. Every case also asserts
exit code 0 and an empty stderr.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from ._support import HookProcess, config, declare_docs_root, payload, write_run_state

MCP_SCREENSHOT = "mcp__playwright__browser_take_screenshot"
RUN_ALLOWED = {"1": ["services/web/src/**"]}
_DEFAULT = object()  # `hook()` default: the standard test config (None and str are meaningful values)


class ProcessCase(unittest.TestCase):
    """Temp dir with a git repo and helpers that run the hook copy and check the process contract."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-audit-tests-proc-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def hook(self, cfg: "dict | str | None | object" = _DEFAULT) -> HookProcess:
        """cfg: a dict (JSON), a str (raw file content), None (no file) or the default test config."""
        return HookProcess(self.tmp, config() if cfg is _DEFAULT else cfg)  # type: ignore[arg-type]

    def write_run(self, allowed=RUN_ALLOWED, **extra):
        write_run_state(self.repo, allowed, **extra)

    def run_hook(self, hp: HookProcess, stdin, cwd=None) -> subprocess.CompletedProcess:
        """Run the hook and assert the contract every case shares: exit 0 and empty stderr."""
        proc = hp.run(stdin, cwd or self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        return proc

    def output(self, proc: subprocess.CompletedProcess) -> dict | None:
        """The one JSON line the hook printed, or None when silent."""
        if proc.stdout == "":
            return None
        self.assertTrue(proc.stdout.endswith("\n"), repr(proc.stdout))
        self.assertEqual(len(proc.stdout.splitlines()), 1, repr(proc.stdout))
        return json.loads(proc.stdout)

    def pre(self, hp, actor, tool, tool_input=None, event="PreToolUse", tool_response=None):
        return self.output(self.run_hook(hp, payload(
            event, tool, actor=actor, cwd=self.repo, tool_input=tool_input, tool_response=tool_response)))

    def bash(self, hp, actor, command, event="PreToolUse"):
        return self.pre(hp, actor, "Bash", {"command": command}, event=event)

    def edit(self, hp, actor, rel, tool="Edit", event="PreToolUse", tool_response=None):
        return self.pre(hp, actor, tool, {"file_path": str(self.repo / rel)}, event=event, tool_response=tool_response)

    def assert_decision(self, out, decision, category):
        self.assertIsNotNone(out)
        spec = out["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PreToolUse")
        self.assertEqual(spec["permissionDecision"], decision)
        self.assertIn(f"Agent workflow ({category})", spec["permissionDecisionReason"])

    def assert_warn(self, out, category):
        self.assertIsNotNone(out)
        spec = out["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PreToolUse")
        self.assertNotIn("permissionDecision", spec)
        self.assertIn(f"Reminder from the agent workflow ({category})", spec["additionalContext"])

    def post_flags(self, hp, session="t"):
        """Flags of the PostToolUse records written by the process."""
        return [r["flags"] for r in hp.records(session) if r["event"] == "PostToolUse"]


class StageGRegression(ProcessCase):
    """Stage G enforcement through the real process: spec design-director, Casos G (G1-G11)."""

    def test_g1_implementer_docker_restart_is_denied(self):
        out = self.bash(self.hook(), "backend-node", "docker compose -f x.yml restart api")
        self.assert_decision(out, "deny", "docker_lifecycle")

    def test_g2_main_rtk_docker_restart_is_denied(self):
        out = self.bash(self.hook(), "main", "rtk docker compose restart api")
        self.assert_decision(out, "deny", "docker_lifecycle")

    def test_g3_main_git_commit_asks(self):
        out = self.bash(self.hook(), "main", "git commit -m x")
        self.assert_decision(out, "ask", "git_commit")

    def test_g4_readonly_agent_write_is_denied(self):
        out = self.edit(self.hook(), "ui-verifier", "services/web/src/a.tsx", tool="Write")
        self.assert_decision(out, "deny", "write_by_readonly_agent")

    def test_g5_visual_tool_outside_ui_verifier_is_denied(self):
        out = self.pre(self.hook(), "frontend-react", MCP_SCREENSHOT)
        self.assert_decision(out, "deny", "visual_tool")

    def test_g6_visual_tool_by_ui_verifier_is_silent(self):
        self.assertIsNone(self.pre(self.hook(), "ui-verifier", MCP_SCREENSHOT))

    def test_g7_out_of_scope_write_in_a_run_warns(self):
        self.write_run()
        out = self.edit(self.hook(), "frontend-react", "services/api/x.ts")
        self.assert_warn(out, "out_of_scope_write")

    def test_g8_in_scope_write_in_a_run_is_silent(self):
        self.write_run()
        self.assertIsNone(self.edit(self.hook(), "frontend-react", "services/web/src/a.tsx"))

    def test_g9_narrow_test_by_implementer_is_silent(self):
        self.assertIsNone(self.bash(self.hook(), "backend-python", "pytest tests/test_a.py"))

    def test_g10_invalid_json_stdin_is_silent_and_records_nothing(self):
        hp = self.hook()
        proc = self.run_hook(hp, "not json")
        self.assertEqual(proc.stdout, "")
        self.assertFalse(hp.metrics_dir.exists() and any(hp.metrics_dir.iterdir()))

    def test_g11_audit_mode_never_decides(self):
        hp = self.hook(config(mode="audit"))
        self.assertIsNone(self.bash(hp, "backend-node", "docker compose -f x.yml restart api"))
        self.assertEqual(hp.records(), [])


class ProcessContract(ProcessCase):
    """Fail-open and output contract of the process: spec, Casos P (P1-P6), rules R11 and R9."""

    def test_p1_json_that_is_not_an_object_exits_zero_silently(self):
        hp = self.hook()
        proc = self.run_hook(hp, "[]")
        self.assertEqual(proc.stdout, "")
        self.assertFalse(hp.metrics_dir.exists() and any(hp.metrics_dir.iterdir()))

    def test_p2_empty_stdin_exits_zero_silently(self):
        proc = self.run_hook(self.hook(), "")
        self.assertEqual(proc.stdout, "")

    def _assert_falls_back_to_audit(self, hp):
        self.assertIsNone(self.bash(hp, "backend-node", "docker compose -f x.yml restart api"))
        self.assertIsNone(self.bash(hp, "backend-node", "docker compose -f x.yml restart api", event="PostToolUse"))
        records = [r for r in hp.records() if r["event"] == "PostToolUse"]
        self.assertEqual(len(records), 1)
        self.assertIn("docker_lifecycle", records[0]["flags"])

    def test_p3_invalid_config_json_behaves_as_audit(self):
        self._assert_falls_back_to_audit(self.hook("{not valid json"))

    def test_p4_missing_config_behaves_as_audit(self):
        hp = self.hook(None)
        self.assertFalse((hp.dir / "agent-audit.json").exists())
        self._assert_falls_back_to_audit(hp)

    def test_p5_deny_ask_and_warn_are_exactly_one_json_line(self):
        self.write_run()
        hp = self.hook()
        cases = {
            "deny": payload("PreToolUse", "Bash", actor="backend-node", cwd=self.repo,
                            tool_input={"command": "docker compose -f x.yml restart api"}),
            "ask": payload("PreToolUse", "Bash", cwd=self.repo, tool_input={"command": "git commit -m x"}),
            "warn": payload("PreToolUse", "Edit", actor="frontend-react", cwd=self.repo,
                            tool_input={"file_path": str(self.repo / "services/api/x.ts")}),
        }
        for name, stdin in cases.items():
            with self.subTest(case=name):
                proc = self.run_hook(hp, stdin)
                self.assertTrue(proc.stdout.endswith("\n"))
                lines = proc.stdout.splitlines()
                self.assertEqual(len(lines), 1, repr(proc.stdout))
                out = json.loads(lines[0])
                self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PreToolUse")
                if name == "warn":
                    self.assertIn("additionalContext", out["hookSpecificOutput"])
                else:
                    self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], name)

    def test_p6_design_system_rules_match_the_h_table(self):
        """H1, H3 and H5 of test_design_system.py, through the process."""
        hp = self.hook()
        with self.subTest(case="H1"):
            args = ("design-director", "DESIGN_SYSTEM.md")
            self.assertIsNone(self.edit(hp, *args, tool="Write"))
            self.edit(hp, *args, tool="Write", event="PostToolUse")
            self.assertEqual(self.post_flags(hp), [[]])
        with self.subTest(case="H3"):
            args = ("design-director", "NOTES.md")
            self.assert_decision(self.edit(hp, *args, tool="Write"), "deny", "design_director_write_outside")
            self.edit(hp, *args, tool="Write", event="PostToolUse")
            self.assertEqual(self.post_flags(hp)[-1], ["design_director_write_outside", "md_outside_docs"])
        with self.subTest(case="H5"):
            self.write_run()
            args = ("frontend-react", "DESIGN_SYSTEM.md")
            self.assert_warn(self.edit(hp, *args), "design_system_write_by_other")
            self.edit(hp, *args, event="PostToolUse")
            self.assertEqual(self.post_flags(hp)[-1], ["design_system_write_by_other", "out_of_scope_write"])

    def test_p_dr_declared_docs_root_is_read_by_the_process(self):
        """Skills-docs-root spec, P-DR: the real process judges `kb/` as docs and `docs/` as code.

        Uses `specker`: per spec audit-md-outside-docs (M1) the main session never gets `md_outside_docs`."""
        declare_docs_root(self.repo, "kb/")
        hp = self.hook()
        with self.subTest(target="kb/a.md"):
            self.assertIsNone(self.edit(hp, "specker", "kb/a.md", tool="Write"))
        with self.subTest(target="docs/a.md"):
            self.assert_warn(self.edit(hp, "specker", "docs/a.md", tool="Write"), "md_outside_docs")

    def test_p_md_md_outside_docs_is_for_agents_only(self):
        """Spec audit-md-outside-docs, P-MD: real process, main session silent, agent warned."""
        hp = self.hook()
        with self.subTest(actor="main", target="PRD.md"):
            self.assertIsNone(self.edit(hp, "main", "PRD.md", tool="Write"))
        with self.subTest(actor="backend-node", target="NOTES.md"):
            self.assert_warn(self.edit(hp, "backend-node", "NOTES.md", tool="Write"), "md_outside_docs")

    def test_sc20_scratchpad_dir_exempts_a_write_outside_the_repo(self):
        """Spec audit-scratch-exemption, SC20: real process, env without TMPDIR."""
        self.write_run()
        sp = self.tmp.resolve() / f"claude-{os.getuid() if hasattr(os, 'getuid') else 0}" / "-proj" / "s1" / "scratchpad"
        sp.mkdir(parents=True, mode=0o700)
        hp = self.hook()
        target = {"file_path": str(sp / "n.txt")}
        with self.subTest(case="with scratchpad_dir"):
            pl = payload("PreToolUse", "Write", actor="frontend-react", cwd=self.repo, tool_input=target,
                         scratchpad=sp)
            self.assertIsNone(self.output(self.run_hook(hp, pl)))
        with self.subTest(case="without scratchpad_dir"):
            pl = payload("PreToolUse", "Write", actor="frontend-react", cwd=self.repo, tool_input=target)
            self.assert_warn(self.output(self.run_hook(hp, pl)), "out_of_scope_write")


class AnalysisTimeoutProcess(ProcessCase):
    """Wall-clock guard through the real process (lua-agent review round 4). The limit is lowered with the
    test-only env var AGENT_AUDIT_ANALYSIS_TIMEOUT; the default (7 s) is left alone in the other cases."""

    TINY = {"AGENT_AUDIT_ANALYSIS_TIMEOUT": "0.000001"}

    def run_bash(self, hp, event, command, extra_env=None, actor="backend-node"):
        pl = payload(event, "Bash", actor=actor, cwd=self.repo, tool_input={"command": command})
        proc = hp.run(pl, self.repo, extra_env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")  # never a stack trace
        return self.output(proc)

    def test_pre_deny_with_analysis_timeout_and_the_record(self):
        hp = self.hook()
        out = self.run_bash(hp, "PreToolUse", "pytest tests/test_a.py", self.TINY)
        self.assert_decision(out, "deny", "analysis_timeout")
        reason = out["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("too complex to analyze in time", reason)
        self.assertIn("Write tool", reason)
        [record] = hp.records()
        self.assertEqual(record["flags"], ["analysis_timeout"])
        self.assertEqual(record["decision"], "block")
        self.assertEqual(record["decision_category"], "analysis_timeout")
        self.assertEqual(record["cmd"], "pytest tests/test_a.py")

    def test_deny_holds_for_the_main_session_too(self):
        out = self.run_bash(self.hook(), "PreToolUse", "echo hi", self.TINY, actor="main")
        self.assert_decision(out, "deny", "analysis_timeout")

    def test_post_records_the_flag_and_does_not_block(self):
        hp = self.hook()
        self.assertIsNone(self.run_bash(hp, "PostToolUse", "pytest tests/test_a.py", self.TINY))
        self.assertEqual(self.post_flags(hp), [["analysis_timeout"]])

    def test_a_normal_command_is_unaffected_by_the_guard(self):
        hp = self.hook()
        self.assertIsNone(self.run_bash(hp, "PreToolUse", "pytest tests/test_a.py"))
        out = self.run_bash(hp, "PreToolUse", "docker compose restart api")
        self.assert_decision(out, "deny", "docker_lifecycle")
        self.assertIsNone(self.run_bash(hp, "PostToolUse", "pytest tests/test_a.py"))
        self.assertEqual(self.post_flags(hp), [[]])

    def test_an_invalid_override_falls_back_to_the_default_limit(self):
        for value in ("abc", "0", "-1", ""):
            with self.subTest(value=value):
                out = self.run_bash(self.hook(), "PreToolUse", "pytest tests/test_a.py",
                                    {"AGENT_AUDIT_ANALYSIS_TIMEOUT": value})
                self.assertIsNone(out)

    def test_huge_or_non_finite_overrides_are_clamped_never_a_silent_allow(self):
        """Round 5: inf / 1e300 / 1e10 made setitimer raise OverflowError and the hook allowed everything."""
        for value in ("inf", "-inf", "nan", "1e300", "1e10"):
            with self.subTest(value=value):
                env = {"AGENT_AUDIT_ANALYSIS_TIMEOUT": value}
                hp = self.hook()
                out = self.run_bash(hp, "PreToolUse", "docker compose restart api", env)
                self.assert_decision(out, "deny", "docker_lifecycle")
                self.assertIsNone(self.run_bash(hp, "PreToolUse", "pytest tests/test_a.py", env))
                self.assertIsNone(self.run_bash(hp, "PostToolUse", "pytest tests/test_a.py", env))
                self.assertEqual(self.post_flags(hp)[-1], [])  # the hook is shared by the subtests


if __name__ == "__main__":
    unittest.main()
