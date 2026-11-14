"""The hook as a real process (stdin -> stdout/exit code), run from a private copy.

Source: audit-hook-test-suite spec, section Testing, `test_hook_process.py` (G1-G11, P1-P6). The
process runs `HookProcess`'s copy of the hook with its own `agent-audit.json`, metrics directory and
HOME: the live hook and the live config are never executed or read here. Every case also asserts
exit code 0 and an empty stderr.
"""
import json
import os
import shlex
import shutil
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from ._support import ForkedSuite, HookProcess, config, declare_docs_root, init_repo, payload, write_run_state

MCP_SCREENSHOT = "mcp__playwright__browser_take_screenshot"
RUN_ALLOWED = {"1": ["services/web/src/**"]}
_DEFAULT = object()  # `hook()` default: the standard test config (None and str are meaningful values)


def load_tests(loader, tests, pattern):
    """Every case here is independent (own temp dir and private hook copy, only processes started): run them in
    parallel. The report is the usual one, in order; see `ForkedSuite`."""
    return ForkedSuite(tests)


class ProcessCase(unittest.TestCase):
    """Temp dir with a git repo and helpers that run the hook copy and check the process contract."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-audit-tests-proc-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        init_repo(self.repo)

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

    def session(self, name: str, cfg: "dict | str | None | object" = _DEFAULT) -> "tuple[HookProcess, Path]":
        """An independent hook copy (own metrics and HOME) and its own git repo, for `HookProcess.run_many`."""
        base = self.tmp / name
        repo = base / "repo"
        repo.mkdir(parents=True)
        init_repo(repo)
        return HookProcess(base, config() if cfg is _DEFAULT else cfg), repo  # type: ignore[arg-type]

    def parsed(self, proc: subprocess.CompletedProcess) -> dict | None:
        """The contract every case shares (exit 0, empty stderr) and the hook's one JSON line, for a run that
        `HookProcess.run_many` already made."""
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        return self.output(proc)

    @staticmethod
    def edit_step(repo, actor, rel, tool="Edit", event="PreToolUse") -> tuple:
        """A `run_many` step: the payload of an edit of `<repo>/<rel>` and the cwd."""
        return payload(event, tool, actor=actor, cwd=repo, tool_input={"file_path": str(repo / rel)}), repo

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
        (h1, r1), (h3, r3), (h5, r5) = self.session("h1"), self.session("h3"), self.session("h5")
        write_run_state(r5, RUN_ALLOWED)  # H5 runs inside an /implement run; H1 and H3 do not
        a1 = ("design-director", "DESIGN_SYSTEM.md")
        a3 = ("design-director", "NOTES.md")
        a5 = ("frontend-react", "DESIGN_SYSTEM.md")
        res1, res3, res5 = HookProcess.run_many([
            (h1, [self.edit_step(r1, *a1, tool="Write"), self.edit_step(r1, *a1, tool="Write", event="PostToolUse")]),
            (h3, [self.edit_step(r3, *a3, tool="Write"), self.edit_step(r3, *a3, tool="Write", event="PostToolUse")]),
            (h5, [self.edit_step(r5, *a5), self.edit_step(r5, *a5, event="PostToolUse")]),
        ])
        with self.subTest(case="H1"):
            self.assertIsNone(self.parsed(res1[0]))
            self.parsed(res1[1])
            self.assertEqual(self.post_flags(h1), [[]])
        with self.subTest(case="H3"):
            self.assert_decision(self.parsed(res3[0]), "deny", "design_director_write_outside")
            self.parsed(res3[1])
            self.assertEqual(self.post_flags(h3)[-1], ["design_director_write_outside", "md_outside_docs"])
        with self.subTest(case="H5"):
            self.assert_warn(self.parsed(res5[0]), "design_system_write_by_other")
            self.parsed(res5[1])
            self.assertEqual(self.post_flags(h5)[-1], ["design_system_write_by_other", "out_of_scope_write"])

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

    @staticmethod
    def bash_step(repo, event, command, extra_env=None, actor="backend-node") -> tuple:
        """A `run_many` step of `run_bash`."""
        return payload(event, "Bash", actor=actor, cwd=repo, tool_input={"command": command}), repo, extra_env

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
        values = ("abc", "0", "-1", "")
        sessions = [self.session(f"v{i}") for i in range(len(values))]
        results = HookProcess.run_many([
            (hp, [self.bash_step(repo, "PreToolUse", "pytest tests/test_a.py", {"AGENT_AUDIT_ANALYSIS_TIMEOUT": value})])
            for value, (hp, repo) in zip(values, sessions)])
        for value, [proc] in zip(values, results):
            with self.subTest(value=value):
                self.assertIsNone(self.parsed(proc))

    def test_huge_or_non_finite_overrides_are_clamped_never_a_silent_allow(self):
        """Round 5: inf / 1e300 / 1e10 made setitimer raise OverflowError and the hook allowed everything."""
        self.assert_clamped(("inf", "-inf", "nan"))

    def test_huge_finite_overrides_are_clamped_never_a_silent_allow(self):
        """Same, for the finite values (split in two tests so that no single test takes longer than 0.5 s)."""
        self.assert_clamped(("1e300", "1e10"))

    def assert_clamped(self, values):
        sessions = [self.session(f"v{i}") for i in range(len(values))]
        results = HookProcess.run_many([
            (hp, [self.bash_step(repo, event, command, {"AGENT_AUDIT_ANALYSIS_TIMEOUT": value})
                  for event, command in (("PreToolUse", "docker compose restart api"),
                                         ("PreToolUse", "pytest tests/test_a.py"),
                                         ("PostToolUse", "pytest tests/test_a.py"))])
            for value, (hp, repo) in zip(values, sessions)])
        for value, (hp, _), (deny, allow, post) in zip(values, sessions, results):
            with self.subTest(value=value):
                self.assert_decision(self.parsed(deny), "deny", "docker_lifecycle")
                self.assertIsNone(self.parsed(allow))
                self.assertIsNone(self.parsed(post))
                self.assertEqual(self.post_flags(hp)[-1], [])


class HardeningProcess(ProcessCase):
    """Spec audit-hook-hardening: bounded I/O (Task 1: P-HH1, P-HH2) and uncertainty (Task 2: P-HH3-P-HH6)
    through the real process."""

    def timed_hook(self, hp, stdin):
        start = time.monotonic()
        proc = self.run_hook(hp, stdin)
        self.assertLess(time.monotonic() - start, 2.0)
        return proc

    def test_p_hh1_a_fifo_as_the_metrics_file_blocks_nothing(self):
        hp = self.hook()
        hp.metrics_dir.mkdir(parents=True)
        os.mkfifo(hp.metrics_dir / "t.jsonl")
        pre = self.timed_hook(hp, payload("PreToolUse", "Bash", actor="backend-python", cwd=self.repo,
                                          tool_input={"command": "docker compose restart api"}))
        self.assert_decision(self.output(pre), "deny", "docker_lifecycle")
        post = self.timed_hook(hp, payload("PostToolUse", "Bash", actor="backend-python", cwd=self.repo,
                                           tool_input={"command": "pytest tests/test_a.py"}))
        self.assertEqual(post.stdout, "")
        # No record: the path is still the FIFO (reading it would block, so it is only stat'ed).
        self.assertTrue(stat.S_ISFIFO(os.stat(hp.metrics_dir / "t.jsonl").st_mode))

    def test_p_hh2_stray_and_huge_run_states_do_not_break_the_run_tags(self):
        self.write_run()  # the valid state, feat-x.json
        runs = self.repo / ".claude" / "runs"
        (runs / "a.json").write_text("[]")
        with open(runs / "b.json", "wb") as fh:
            fh.truncate(50 * 1024 * 1024)
        now = time.time() + 10
        for name in ("a.json", "b.json"):
            os.utime(runs / name, (now, now))  # both newer than the valid state
        hp = self.hook()
        for event in ("PreToolUse", "PostToolUse"):
            stdin = payload(event, "Write", actor="frontend-react", cwd=self.repo,
                            tool_input={"file_path": str(self.repo / "README.md")})
            self.timed_hook(hp, stdin)
        [record] = [r for r in hp.records() if r["event"] == "PostToolUse"]
        self.assertIn("docs_write_by_implementer", record["flags"])
        self.assertIn("out_of_scope_write", record["flags"])
        self.assertEqual(record["area"], "code")
        self.assertEqual(record["run"], "feat-x")

    def bash_pre(self, hp, command):
        return self.output(self.timed_hook(hp, payload("PreToolUse", "Bash", actor="backend-python", cwd=self.repo,
                                                       tool_input={"command": command})))

    def test_p_hh3_more_readings_than_the_cap_is_denied_as_unclassified(self):
        hp = self.hook()
        out = self.bash_pre(hp, "timeout a " * 9 + "docker restart x")
        self.assert_decision(out, "deny", "unclassified_command")
        [record] = hp.records()
        self.assertEqual(record["uncertainty"], ["readings_cap"])
        self.assertEqual(record["decision_category"], "unclassified_command")

    def test_p_hh4_nvim_nested_four_levels_is_denied_as_unclassified(self):
        command = "docker ps"
        for _ in range(4):
            command = "nvim -c " + shlex.quote("!" + command)
        hp = self.hook()
        self.assert_decision(self.bash_pre(hp, command), "deny", "unclassified_command")
        [record] = hp.records()
        self.assertEqual(record["uncertainty"], ["nested_shell_depth"])

    def test_p_hh5_an_exception_in_the_classifier_is_denied_as_unclassified(self):
        hp = self.hook()
        hp.patch_source('    if not seg or seg.startswith("cd "):\n        return\n',
                        '    raise RecursionError("probe")\n', file="agent_audit_classify.py")
        self.assert_decision(self.bash_pre(hp, "echo hi"), "deny", "unclassified_command")
        [record] = hp.records()
        self.assertEqual(record["uncertainty"], ["classifier_error"])
        self.assertEqual(record["error"], "RecursionError")

    def test_p_hh6_stacked_timeouts_no_longer_hide_the_command(self):
        hp = self.hook()
        self.assert_decision(self.bash_pre(hp, "timeout a " * 4 + "docker restart x"), "deny", "docker_lifecycle")

    def test_p_hh7_a_substitution_in_the_prefix_does_not_hide_the_body(self):
        hp = self.hook()
        command = "sh -s $(true) cat <<'EOF'\ndocker restart x\nEOF"
        self.assert_decision(self.bash_pre(hp, command), "deny", "docker_lifecycle")


class ShellParserProcess(ProcessCase):
    """Spec audit-shell-lexer, Task 2 (P-SL1, P-SL2, P-SL4): the forms the parser reads, through the real process.
    Blocked forms are built from pieces, so the live hook does not deny this file's own text."""

    LIFECYCLE = "docker re" + "start x"
    CHECKED_HASH_FLAGS = b"\x03\x00\x00\x00"  # PEP 552: hash-based and checked against the source
    PLAIN = "pytest tests/test_a.py"

    def warm(self, hp):
        """Run once with bytecode on, so the modules are cached; returns the cache file of the classifier."""
        stdin = payload("PreToolUse", "Bash", actor="backend-python", cwd=self.repo, tool_input={"command": self.PLAIN})
        proc = hp.run(stdin, self.repo, bytecode=True)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))
        [cached] = (hp.dir / "__pycache__").glob("agent_audit_classify.*.pyc")
        return cached

    def run_plain(self, hp):
        proc = hp.run(payload("PreToolUse", "Bash", actor="backend-python", cwd=self.repo,
                              tool_input={"command": self.PLAIN}), self.repo, bytecode=True)
        self.assertEqual((proc.returncode, proc.stderr), (0, ""))
        return proc

    def bash_pre(self, hp, command, actor="backend-python"):
        return self.output(self.run_hook(hp, payload("PreToolUse", "Bash", actor=actor, cwd=self.repo,
                                                     tool_input={"command": command})))

    def test_p_sl1_forms_that_were_not_seen_are_denied(self):
        hp = self.hook()
        for command in (f"true & {self.LIFECYCLE}", f"cat <<EOF\n$({self.LIFECYCLE})\nEOF",
                        f'A="x y z w v" {self.LIFECYCLE.replace("x", "api")} # "', f"( {self.LIFECYCLE} )",
                        f"x=$({self.LIFECYCLE})"):
            for actor in ("backend-python", "main"):
                with self.subTest(command=command, actor=actor):
                    self.assert_decision(self.bash_pre(hp, command, actor), "deny", "docker_lifecycle")

    def test_p_sl1_text_that_only_looks_like_a_command_is_silent(self):
        hp = self.hook()
        for command in (f"python3 - <<'EOF'\n{self.LIFECYCLE}\nEOF", f'echo "a\n{self.LIFECYCLE}"',
                        f"cat > f <<'EOF'\n$({self.LIFECYCLE})\nEOF", "pytest tests/test_a.py"):
            with self.subTest(command=command):
                self.assertIsNone(self.bash_pre(hp, command))

    def test_p_sl2_a_text_that_does_not_close_is_denied_as_unclassified(self):
        hp = self.hook()
        self.assert_decision(self.bash_pre(hp, 'echo "a'), "deny", "unclassified_command")
        [record] = hp.records()
        self.assertEqual(record["uncertainty"], ["lex_error"])
        self.assertEqual(record["categories"], ["unclassified"])

    def test_p_sl3_code_built_from_a_variable_is_denied_as_unclassified(self):
        hp = self.hook()
        self.assert_decision(self.bash_pre(hp, 'bash -c "$X"'), "deny", "unclassified_command")
        [record] = hp.records()
        self.assertEqual(record["uncertainty"], ["dynamic_code"])
        self.assertEqual(record["categories"], ["other", "unclassified"])

    def test_p_sl3_code_in_an_argument_is_classified(self):
        hp = self.hook()
        for command in (f"bash -c '{self.LIFECYCLE}'", f"eval {self.LIFECYCLE}", f"nvim -c '!{self.LIFECYCLE}'"):
            with self.subTest(command=command):
                self.assert_decision(self.bash_pre(hp, command), "deny", "docker_lifecycle")

    def test_p_sl4_the_modules_are_cached_as_bytecode_and_give_the_same_decision(self):
        hp = self.hook()
        cache = hp.dir / "__pycache__"
        self.assertFalse(cache.exists())
        stdin = payload("PreToolUse", "Bash", actor="backend-python", cwd=self.repo,
                        tool_input={"command": f"true & {self.LIFECYCLE}"})
        first = hp.run(stdin, self.repo, bytecode=True)
        for module in ("agent_audit_shell", "agent_audit_classify"):
            compiled = sorted(cache.glob(f"{module}.*.pyc"))
            self.assertEqual(len(compiled), 1, compiled)  # the modules only: the hook is a script, never cached
            self.assertEqual(compiled[0].read_bytes()[4:8], self.CHECKED_HASH_FLAGS, module)  # PEP 552, checked
        self.assertEqual(list(cache.glob("agent-audit*.pyc")), [])
        second = hp.run(stdin, self.repo, bytecode=True)
        for proc in (first, second):
            self.assertEqual((proc.returncode, proc.stderr), (0, ""))
        self.assertEqual(first.stdout, second.stdout)
        self.assert_decision(json.loads(second.stdout), "deny", "docker_lifecycle")
        normal = hp.run(payload("PreToolUse", "Bash", actor="backend-python", cwd=self.repo,
                                tool_input={"command": "pytest tests/test_a.py"}), self.repo, bytecode=True)
        self.assertEqual((normal.returncode, normal.stdout, normal.stderr), (0, "", ""))

    def test_p_sl4_a_stale_bytecode_is_recompiled_after_the_source_changes(self):
        hp = self.hook()
        stdin = payload("PreToolUse", "Bash", actor="backend-python", cwd=self.repo,
                        tool_input={"command": "pytest tests/test_a.py"})
        self.assertEqual(hp.run(stdin, self.repo, bytecode=True).stdout, "")
        for name in ("agent_audit_shell.py", "agent_audit_classify.py"):
            module = hp.dir / name
            module.write_text(module.read_text(encoding="utf-8") + "\n" + "x" * 7 + " = 1\n", encoding="utf-8")  # size changes
        proc = hp.run(stdin, self.repo, bytecode=True)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))
        for module in ("agent_audit_shell", "agent_audit_classify"):  # the cache was rewritten, still checked-hash
            [cached] = (hp.dir / "__pycache__").glob(f"{module}.*.pyc")
            self.assertEqual(cached.read_bytes()[4:8], self.CHECKED_HASH_FLAGS)

    def test_p_sl4_a_same_size_edit_with_the_same_mtime_is_not_served_from_the_cache(self):
        """The case a timestamp `.pyc` gets wrong: the source changes but its size and mtime do not."""
        hp = self.hook()
        self.warm(hp)
        source = hp.dir / "agent_audit_classify.py"
        before = source.stat()
        hp.patch_source("\nimport re\nfrom collections", "\nimport xx\nfrom collections", file="agent_audit_classify.py")
        os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
        after = source.stat()
        self.assertEqual((after.st_size, after.st_mtime_ns), (before.st_size, before.st_mtime_ns))
        proc = self.run_plain(hp)  # the edited source does not import: the classifier is gone, not the old bytecode
        self.assert_decision(json.loads(proc.stdout), "deny", "unclassified_command")
        [first, *_] = hp.records()
        self.assertEqual(first["uncertainty"], ["classifier_error"])

    def test_p_sl4_a_planted_bytecode_is_not_used(self):
        """A `.pyc` that claims the source's mtime and size, or carries a wrong hash, never runs."""
        import marshal
        from importlib.util import MAGIC_NUMBER
        hp = self.hook()
        cached = self.warm(hp)
        stat_ = (hp.dir / "agent_audit_classify.py").stat()
        planted = marshal.dumps(compile("raise ImportError('planted')", "planted", "exec"))
        timestamp = MAGIC_NUMBER + b"\x00\x00\x00\x00" + (int(stat_.st_mtime) & 0xFFFFFFFF).to_bytes(4, "little") \
            + (stat_.st_size & 0xFFFFFFFF).to_bytes(4, "little") + planted
        wrong_hash = MAGIC_NUMBER + self.CHECKED_HASH_FLAGS + b"\x00" * 8 + planted
        unchecked = MAGIC_NUMBER + b"\x01\x00\x00\x00" + b"\x00" * 8 + planted
        for name, data in (("timestamp", timestamp), ("wrong hash", wrong_hash), ("unchecked hash", unchecked),
                           ("garbage", b"not bytecode")):
            with self.subTest(name):
                cached.write_bytes(data)
                proc = self.run_plain(hp)
                self.assertEqual((proc.stdout, proc.stderr), ("", ""))  # the real classifier ran: the command is plain
                self.assertEqual(hp.records(), [])
                self.assertEqual(cached.read_bytes()[4:8], self.CHECKED_HASH_FLAGS)  # and the cache is repaired

    def test_p_sl4_a_module_that_exits_at_import_denies_bash_and_the_hook_still_decides(self):
        """`SystemExit` (a BaseException) raised by a tampered module is caught by the loader: fail closed."""
        for file, anchor in (("agent_audit_shell.py", "MAX_NESTING = 32\n"), ("agent_audit_classify.py", "MAX_CODE_DEPTH = 3\n")):
            for exc in ("SystemExit(3)", "KeyboardInterrupt()"):
                with self.subTest(file=file, exc=exc):
                    hp = self.hook()
                    hp.patch_source(anchor, f"{anchor}raise {exc}\n", file=file)
                    proc = self.run_plain(hp)
                    self.assert_decision(json.loads(proc.stdout), "deny", "unclassified_command")
                    [first, *_] = hp.records()
                    self.assertEqual((first["uncertainty"], first["error"]), (["classifier_error"], "RuntimeError"))
                    write = hp.run(payload("PreToolUse", "Write", actor="main", cwd=self.repo,
                                           tool_input={"file_path": str(self.repo / "a.txt")}), self.repo)
                    self.assertEqual((write.returncode, write.stdout, write.stderr), (0, "", ""))


class WatchdogProcess(ProcessCase):
    """Spec audit-hook-hardening, Task 4 (P-HH8-P-HH11): the fork watchdog through the real process. A failure is
    patched into the private copy of the hook, at the first line of `_classify_segment`."""

    SEGMENT_HEAD = '    if not seg or seg.startswith("cd "):\n        return\n'
    # The classifier never ends (HH8): any limit gives the same result, so the smallest. The tagging never ends
    # (HH10) but the analysis must finish in time: a margin over the fork and the analysis under load.
    SHORT = {"AGENT_AUDIT_ANALYSIS_TIMEOUT": "0.05"}
    TAGGING_STUCK = {"AGENT_AUDIT_ANALYSIS_TIMEOUT": "0.15"}

    def run_timed(self, hp, event, command, env=None, actor="backend-python"):
        stdin = payload(event, "Bash", actor=actor, cwd=self.repo, tool_input={"command": command})
        start = time.monotonic()
        proc = hp.run(stdin, self.repo, env)
        elapsed = time.monotonic() - start
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        return self.output(proc), elapsed

    def test_p_hh8_a_long_c_call_in_the_classifier_is_an_analysis_timeout(self):
        hp = self.hook()
        hp.patch_source(self.SEGMENT_HEAD, "    sum(range(10**12))\n" + self.SEGMENT_HEAD, file="agent_audit_classify.py")
        out, elapsed = self.run_timed(hp, "PreToolUse", "echo hi", self.SHORT)
        self.assert_decision(out, "deny", "analysis_timeout")
        self.assertLess(elapsed, 2.0)
        [record] = hp.records()
        self.assertEqual(record["flags"], ["analysis_timeout"])

    def test_p_hh9_a_classifier_that_kills_the_process_is_an_analysis_crash(self):
        hp = self.hook()
        hp.patch_source(self.SEGMENT_HEAD, "    import os\n    os._exit(3)\n" + self.SEGMENT_HEAD,
                        file="agent_audit_classify.py")
        out, elapsed = self.run_timed(hp, "PreToolUse", "echo hi")
        self.assert_decision(out, "deny", "unclassified_command")
        self.assertLess(elapsed, 2.0)
        [record] = hp.records()
        self.assertEqual(record["uncertainty"], ["analysis_crash"])
        self.assertEqual(record["decision_category"], "unclassified_command")

    def test_p_hh10_a_stuck_git_in_the_tagging_still_records(self):
        fake = self.tmp / "fakebin"
        fake.mkdir()
        (fake / "git").write_text("#!/bin/sh\nexec sleep 3\n", encoding="utf-8")
        (fake / "git").chmod(0o755)
        hp = self.hook()
        env = {**self.TAGGING_STUCK, "PATH": f"{fake}:{os.environ.get('PATH', '/usr/bin:/bin')}"}
        out, elapsed = self.run_timed(hp, "PostToolUse", "pytest tests/test_a.py", env)
        self.assertIsNone(out)
        self.assertLess(elapsed, 2.0)
        [record] = hp.records()
        self.assertIs(record["in_run"], False)
        self.assertEqual(record["run_tags"], "timeout")
        self.assertEqual(record["flags"], [])

    def test_p_hh11_the_normal_path_keeps_its_contract(self):
        hp = self.hook()
        out, _ = self.run_timed(hp, "PreToolUse", "pytest tests/test_a.py")
        self.assertIsNone(out)
        out, _ = self.run_timed(hp, "PreToolUse", "docker compose restart api")
        self.assert_decision(out, "deny", "docker_lifecycle")
        self.assertIsNone(self.run_timed(hp, "PostToolUse", "pytest tests/test_a.py")[0])
        self.assertEqual([r["event"] for r in hp.records()], ["PreToolUse", "PostToolUse"])

    def test_wd8_whatever_the_child_writes_never_reaches_the_hook_output(self):
        hp = self.hook()
        hp.patch_source(self.SEGMENT_HEAD, (
            '    import os\n    print("noise")\n    try:\n        os.write(1, b"raw\\n")\n        os.write(2, b"raw\\n")\n'
            "    except OSError:\n        pass\n") + self.SEGMENT_HEAD, file="agent_audit_classify.py")
        self.assertIsNone(self.run_timed(hp, "PreToolUse", "echo hi")[0])  # stdout empty and stderr empty
        out, _ = self.run_timed(hp, "PreToolUse", "docker compose restart api")
        self.assert_decision(out, "deny", "docker_lifecycle")  # exactly one JSON line, no noise around it

if __name__ == "__main__":
    unittest.main()
