"""Tests for audit.main() in process: modes, events, actor, records and the metrics file.

Source: spec audit-hook-test-suite, section Testing, `test_hook_main.py` (E1-E16). Every call goes
through `call_main` with TEST_CONFIG (or a copy); the live agent-audit.json is never read.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from ._support import TempRepoCase, TEST_CONFIG, audit, call_main, config, payload, read_jsonl, write_run_state

DOCKER_UP = "docker compose up"
SCREENSHOT = "mcp__playwright__browser_take_screenshot"

# Literal copies of the hook's sets (asserted equal in BashRecords).
IMPLEMENTERS = (
    "backend-node", "backend-spring", "backend-go", "backend-rust", "backend-python",
    "frontend-react", "mobile-react-native",
)
READ_ONLY_AGENTS = ("ui-verifier", "test-runner", "code-reviewer", "security-reviewer", "Explore", "Plan")


class Modes(TempRepoCase):
    """E1, E2, E15: `mode` off / audit / missing."""

    def pre_post(self, command, cfg):
        pre = call_main(payload("PreToolUse", "Bash", cwd=self.repo, tool_input={"command": command}), cfg)
        post = call_main(payload("PostToolUse", "Bash", cwd=self.repo, tool_input={"command": command}), cfg)
        return pre, post

    def test_e1_mode_off_is_silent_and_records_nothing(self):
        pre, post = self.pre_post(DOCKER_UP, config(mode="off"))
        for res in (pre, post):
            self.assertIsNone(res.output)
            self.assertEqual(res.records, [])

    def test_e2_mode_audit_never_decides_but_records_flags(self):
        pre, post = self.pre_post(DOCKER_UP, config(mode="audit"))
        self.assertIsNone(pre.output)
        self.assertEqual(pre.records, [])
        self.assertIsNone(post.output)
        self.assertEqual(len(post.records), 1)
        self.assertEqual(post.records[0]["flags"], ["docker_lifecycle"])

    def test_e15_missing_mode_is_treated_as_audit(self):
        cfg = copy.deepcopy(TEST_CONFIG)
        del cfg["mode"]
        pre, post = self.pre_post(DOCKER_UP, cfg)
        self.assertIsNone(pre.output)
        self.assertEqual(pre.records, [])
        self.assertEqual(post.records[0]["flags"], ["docker_lifecycle"])


class Events(TempRepoCase):
    """E3-E7, E12, E13: what each event emits and records."""

    def pre(self, command, actor="main"):
        return call_main(payload("PreToolUse", "Bash", actor=actor, cwd=self.repo, tool_input={"command": command}))

    def test_e3_pre_without_flag_is_silent_and_unrecorded(self):
        res = self.pre("ls")
        self.assertIsNone(res.output)
        self.assertEqual(res.records, [])

    def test_e4_pre_warn_adds_context_and_records_nothing(self):
        res = self.pre("curl https://example.com/x")
        spec = res.output["hookSpecificOutput"]
        self.assertIn("Reminder from the agent workflow (external_request)", spec["additionalContext"])
        self.assertNotIn("permissionDecision", spec)
        self.assertEqual(res.records, [])  # PostToolUse records the action with its flags

    def test_e5_pre_block_and_ask_output_and_record_the_decision(self):
        for case, command, decision, category, perm in (
            ("block", DOCKER_UP, "block", "docker_lifecycle", "deny"),
            ("ask", "git commit -m x", "ask", "git_commit", "ask"),
        ):
            with self.subTest(case="E5", kind=case):
                res = self.pre(command)
                self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], perm)
                self.assertEqual(len(res.records), 1)
                rec = res.records[0]
                self.assertEqual(rec["event"], "PreToolUse")
                self.assertEqual(rec["decision"], decision)
                self.assertEqual(rec["decision_category"], category)

    def test_e6_failed_follows_the_event(self):
        for event, failed in (("PostToolUse", False), ("PostToolUseFailure", True)):
            with self.subTest(case="E6", event=event):
                res = call_main(payload(event, "Bash", cwd=self.repo, tool_input={"command": "ls"}))
                self.assertEqual(len(res.records), 1)
                self.assertIs(res.records[0]["failed"], failed)
                self.assertEqual(res.records[0]["event"], event)

    def test_e7_read_only_tools_are_not_audited(self):
        for tool in ("Read", "Grep", "Glob", "WebFetch"):
            for event in ("PreToolUse", "PostToolUse"):
                with self.subTest(case="E7", tool=tool, event=event):
                    res = call_main(payload(event, tool, cwd=self.repo, tool_input={"file_path": "x"}))
                    self.assertIsNone(res.output)
                    self.assertEqual(res.records, [])

    def test_e12_subagent_stop_is_tagged_with_the_active_run(self):
        self.write_run()
        res = call_main(payload("SubagentStop", actor="test-runner", cwd=self.repo))
        self.assertEqual(len(res.records), 1)
        rec = res.records[0]
        self.assertEqual(rec["agent_type"], "test-runner")
        self.assertIs(rec["in_run"], True)
        self.assertEqual(rec["run"], "feat-x")
        self.assertEqual(rec["task"], "1")

    def test_e13_edit_tools_record_path_from_either_key(self):
        target = str(self.repo / "services" / "api" / "a.py")
        for tool, key in (("MultiEdit", "file_path"), ("NotebookEdit", "notebook_path")):
            with self.subTest(case="E13", tool=tool):
                res = call_main(payload("PostToolUse", tool, actor="main", cwd=self.repo, tool_input={key: target}))
                self.assertEqual(len(res.records), 1)
                self.assertEqual(res.records[0]["categories"], ["write"])
                self.assertEqual(res.records[0]["path"], target)

    def test_e16_bash_post_is_tagged_with_the_active_run(self):
        self.write_run()
        res = call_main(payload("PostToolUse", "Bash", cwd=self.repo, tool_input={"command": "ls"}))
        rec = res.records[0]
        self.assertIs(rec["in_run"], True)
        self.assertEqual(rec["run"], "feat-x")
        self.assertEqual(rec["task"], "1")

    def test_bash_without_run_is_not_in_run(self):
        res = call_main(payload("PostToolUse", "Bash", cwd=self.repo, tool_input={"command": "ls"}))
        self.assertIs(res.records[0]["in_run"], False)
        self.assertNotIn("run", res.records[0])


class Actor(TempRepoCase):
    """E8: how the actor is derived from the payload."""

    def test_e8_actor_from_agent_type_agent_id_or_neither(self):
        for case, actor, expected in (
            ("agent_type", "backend-node", "backend-node"),
            ("agent_id only", "subagent", "subagent"),
            ("neither", "main", "main"),
        ):
            with self.subTest(case="E8", kind=case):
                res = call_main(payload("PostToolUse", "Bash", actor=actor, cwd=self.repo, tool_input={"command": "ls"}))
                self.assertEqual(res.records[0]["actor"], expected)


class BashRecords(TempRepoCase):
    """E9, E11 (cmd): suite_by_non_runner and the stored command."""

    def flags(self, actor, command):
        res = call_main(payload("PostToolUse", "Bash", actor=actor, cwd=self.repo, tool_input={"command": command}))
        return res.records[0]["flags"]

    def test_e9_actor_sets_match_the_literals_below(self):
        """Pins the hook's actor sets, so E9 and the write rules cannot silently follow a change."""
        self.assertEqual(audit.IMPLEMENTERS, set(IMPLEMENTERS))
        self.assertEqual(audit.READ_ONLY_AGENTS, set(READ_ONLY_AGENTS))

    def test_e9_suites_by_non_runners_are_flagged(self):
        actors = [*IMPLEMENTERS, "quality-fixer", "test-writer"]
        for actor in actors:
            for command in ("pytest", "pnpm --filter api test", "k6 run x.js"):
                with self.subTest(case="E9", actor=actor, command=command):
                    self.assertIn("suite_by_non_runner", self.flags(actor, command))
            with self.subTest(case="E9", actor=actor, command="pytest tests/test_a.py"):
                self.assertNotIn("suite_by_non_runner", self.flags(actor, "pytest tests/test_a.py"))

    def test_e9_runner_and_main_may_run_suites(self):
        for actor in ("test-runner", "main"):
            with self.subTest(case="E9", actor=actor):
                self.assertNotIn("suite_by_non_runner", self.flags(actor, "pytest"))

    def test_e11_command_is_truncated_to_max_cmd(self):
        command = "echo " + "a" * 995
        self.assertEqual(len(command), 1000)
        res = call_main(payload("PostToolUse", "Bash", cwd=self.repo, tool_input={"command": command}))
        self.assertEqual(len(res.records[0]["cmd"]), 300)
        self.assertEqual(res.records[0]["cmd"], command[:300])


class Visual(TempRepoCase):
    """E10: visual tools are flagged for everyone but ui-verifier."""

    def test_e10_visual_tool_flag_only_for_non_ui_verifier(self):
        for actor, flags in (("frontend-react", ["visual_tool"]), ("ui-verifier", [])):
            with self.subTest(case="E10", actor=actor):
                res = call_main(payload("PostToolUse", SCREENSHOT, actor=actor, cwd=self.repo))
                rec = res.records[0]
                self.assertEqual(rec["categories"], ["visual"])
                self.assertEqual(rec["flags"], flags)


class WriteRecords(TempRepoCase):
    """E11 (privacy): the record never carries file content or tool output."""

    def test_e11_write_record_has_no_content_or_response(self):
        secret = "TOP-SECRET-CONTENT"
        target = str(self.repo / "services" / "api" / "a.py")
        res = call_main(
            payload(
                "PostToolUse", "Write", cwd=self.repo,
                tool_input={"file_path": target, "content": secret, "new_string": secret},
                tool_response={"type": "create", "content": secret, "filePath": target},
            )
        )
        rec = res.records[0]
        for key in ("content", "new_string", "tool_input", "tool_response"):
            self.assertNotIn(key, rec)
        self.assertNotIn(secret, json.dumps(rec))
        self.assertEqual(rec["path"], target)


class WriteFlagOrder(TempRepoCase):
    """The record's flags are sorted and unique (`sorted(set(flags))` in main())."""

    def test_flags_are_recorded_sorted(self):
        pl = {"actor": "frontend-react", "tool_input": {"file_path": str(self.repo / "docs/backlog/x.md")}}
        pre = call_main(payload("PreToolUse", "Write", actor=pl["actor"], cwd=self.repo, tool_input=pl["tool_input"]))
        self.assertIn("backlog_write_by_other", pre.output["hookSpecificOutput"]["additionalContext"])
        post = call_main(payload("PostToolUse", "Write", actor=pl["actor"], cwd=self.repo, tool_input=pl["tool_input"]))
        self.assertEqual(post.records[0]["flags"], ["backlog_write_by_other", "docs_write_by_implementer"])


class ScratchpadPayload(TempRepoCase):
    """Spec audit-scratch-exemption, SC18-SC19: `scratchpad_dir` of the payload, through audit.main().

    Write by `backend-node` with an active run (ALLOWED services/api/**); three targets: inside the scratchpad,
    in another `claude-*` directory, and inside the scratchpad again but with the field absent.
    """

    def setUp(self):
        super().setUp()
        self.write_run()
        self.sp = self.make_scratchpad()
        self.inside = self.sp / "n.txt"
        self.other = self.sp.parents[3] / "claude-xyz" / "x"

    def cases(self):
        """(label, target, scratchpad) of the three payloads."""
        return (("inside", self.inside, self.sp), ("other", self.other, self.sp), ("absent", self.inside, None))

    def write(self, event, target, scratchpad, actor="backend-node"):
        return call_main(payload(event, "Write", actor=actor, cwd=self.repo, session="s1",
                                 tool_input={"file_path": str(target)}, scratchpad=scratchpad))

    def test_sc18_pre_tool_use_warns_only_outside_the_session_scratchpad(self):
        expected = {"inside": False, "other": True, "absent": True}
        for label, target, scratchpad in self.cases():
            with self.subTest(case=label):
                res = self.write("PreToolUse", target, scratchpad)
                if expected[label]:
                    spec = res.output["hookSpecificOutput"]
                    self.assertIn("Reminder from the agent workflow (out_of_scope_write)", spec["additionalContext"])
                    self.assertNotIn("permissionDecision", spec)
                else:
                    self.assertIsNone(res.output)

    def test_sc19_post_tool_use_records_the_scratch_state_and_never_the_path(self):
        expected = {"inside": "match", "other": "no-match", "absent": "unavailable"}
        for label, target, scratchpad in self.cases():
            with self.subTest(case=label):
                rec = self.write("PostToolUse", target, scratchpad).records[0]
                self.assertEqual(rec["scratch"], expected[label])
                self.assertEqual("out_of_scope_write" in rec["flags"], label != "inside")
                if scratchpad is not None:
                    self.assertNotIn(str(scratchpad), rec.values())  # the target's `rel`/`path` may contain it
                    self.assertNotIn("scratchpad_dir", rec)

    def test_sc19_subagent_uses_the_scratchpad_of_the_parent_session(self):
        rec = self.write("PostToolUse", self.inside, self.sp, actor="test-writer").records[0]
        self.assertEqual(rec["actor"], "test-writer")
        self.assertEqual(rec["agent_id"], "agent-1")
        self.assertEqual(rec["session"], "s1")
        self.assertEqual(rec["scratch"], "match")
        self.assertNotIn("out_of_scope_write", rec["flags"])
        self.assertNotIn("scratchpad_dir", rec)


class MdOutsideDocsPayload(TempRepoCase):
    """Spec audit-md-outside-docs, Testing MD16a-MD16c, MD18 and MD19: `md_outside_docs` through `main()`."""

    def pl(self, event, actor, rel, tool_response=None):
        return payload(event, "Write", actor=actor, cwd=self.repo, tool_input={"file_path": str(self.repo / rel)},
                       tool_response=tool_response)

    def post_flags(self, actor, rel, tool_response):
        result = call_main(self.pl("PostToolUse", actor, rel, tool_response))
        self.assertEqual(len(result.records), 1)
        return result.records[0]["flags"]

    def assert_md_warning(self, out):
        self.assertIsNotNone(out)
        hso = out["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", hso)
        self.assertIn("Reminder from the agent workflow (md_outside_docs)", hso["additionalContext"])
        self.assertIn("Files", hso["additionalContext"])

    def test_md16a_pretooluse_write(self):
        with self.subTest(case="main in PRD.md"):
            self.assertIsNone(call_main(self.pl("PreToolUse", "main", "PRD.md")).output)
        with self.subTest(case="planner in a missing NOTES.md"):
            self.assert_md_warning(call_main(self.pl("PreToolUse", "planner", "NOTES.md")).output)
        with self.subTest(case="planner in an existing NOTES.md"):
            (self.repo / "NOTES.md").write_text("x", encoding="utf-8")
            self.assertIsNone(call_main(self.pl("PreToolUse", "planner", "NOTES.md")).output)

    def test_md16b_posttooluse_write_type_decides(self):
        with self.subTest(type="update"):
            self.assertEqual(self.post_flags("planner", "NOTES.md", {"type": "update"}), [])
        with self.subTest(type="create"):
            self.assertEqual(self.post_flags("planner", "NOTES.md", {"type": "create"}), ["md_outside_docs"])

    def test_md16c_markdown_path_of_the_task_files(self):
        write_run_state(self.repo, {"1": [".claude/agents/x.md"]})
        rel = ".claude/agents/x.md"
        with self.subTest(event="PreToolUse"):
            self.assertIsNone(call_main(self.pl("PreToolUse", "frontend-react", rel, {"type": "create"})).output)
        with self.subTest(event="PostToolUse"):
            self.assertEqual(self.post_flags("frontend-react", rel, {"type": "create"}), [])

    def test_md18_docs_writer_is_free_and_planner_is_not(self):
        with self.subTest(actor="docs-writer", event="PreToolUse"):
            self.assertIsNone(call_main(self.pl("PreToolUse", "docs-writer", "NOTES.md")).output)
        with self.subTest(actor="docs-writer", event="PostToolUse"):
            self.assertEqual(self.post_flags("docs-writer", "NOTES.md", {"type": "create"}), [])
        with self.subTest(actor="planner", event="PreToolUse"):
            self.assert_md_warning(call_main(self.pl("PreToolUse", "planner", "NOTES.md")).output)
        with self.subTest(actor="planner", event="PostToolUse"):
            self.assertEqual(self.post_flags("planner", "NOTES.md", {"type": "create"}), ["md_outside_docs"])

    def test_md19_failed_write_creates_nothing(self):
        with self.subTest(event="PostToolUseFailure"):
            result = call_main(self.pl("PostToolUseFailure", "backend-node", "NOTES.md"))
            self.assertEqual(len(result.records), 1)
            self.assertTrue(result.records[0]["failed"])
            self.assertNotIn("md_outside_docs", result.records[0]["flags"])
        with self.subTest(event="PostToolUse"):
            self.assertIn("md_outside_docs", self.post_flags("backend-node", "NOTES.md", {"type": "create"}))


class MetricsFile(TempRepoCase):
    """E14: the metrics directory and the per-session file."""

    def run_main(self, metrics_dir, pl):
        call_main(pl, metrics_dir=metrics_dir)

    def test_e14_directory_created_and_events_share_one_file(self):
        with tempfile.TemporaryDirectory(prefix="agent-audit-tests-e14-") as tmp:
            metrics_dir = Path(tmp) / "not" / "yet" / "there"
            self.assertFalse(metrics_dir.exists())
            for command in ("ls", "pwd"):
                self.run_main(
                    metrics_dir,
                    payload("PostToolUse", "Bash", cwd=self.repo, session="s1", tool_input={"command": command}),
                )
            self.assertTrue(metrics_dir.is_dir())
            self.assertEqual([p.name for p in metrics_dir.iterdir()], ["s1.jsonl"])
            self.assertEqual([r["cmd"] for r in read_jsonl(metrics_dir / "s1.jsonl")], ["ls", "pwd"])

    def test_e14_payload_without_session_goes_to_unknown(self):
        with tempfile.TemporaryDirectory(prefix="agent-audit-tests-e14-") as tmp:
            metrics_dir = Path(tmp) / "m"
            pl = payload("PostToolUse", "Bash", cwd=self.repo, tool_input={"command": "ls"})
            del pl["session_id"]
            self.run_main(metrics_dir, pl)
            self.assertEqual([p.name for p in metrics_dir.iterdir()], ["unknown.jsonl"])
            self.assertEqual(len(read_jsonl(metrics_dir / "unknown.jsonl")), 1)


if __name__ == "__main__":
    unittest.main()
