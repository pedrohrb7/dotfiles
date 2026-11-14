"""The fork watchdog of the analysis, through `call_main` (spec audit-hook-hardening, Task 4, WD1-WD10).

The analysis (and the run tagging) of an audited tool runs in a forked child under a hard deadline; the parent
reads two JSON lines, decides, prints and records. Mocks set in the test process are inherited by the child, so a
classifier that sleeps, crashes or prints behaves the same as a real defect would. The no-fork fallback (W5) is
covered by WD5 and WD9 and by `AnalysisLimitAndArming` / `DecisionBeforeRecording` in `test_hook_main.py`.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock

from ._support import ForkedSuite, HookProcess, TempRepoCase, audit, call_main, classifier, payload, write_run_state

DOCKER_UP = "docker compose up"
SHORT = 0.05  # analysis limit of the deadline cases: the analysis never ends there, so a short limit cannot flake
TAGGING_STUCK = 0.15  # limit where the analysis must finish and only the run tagging never ends (margin under load)


class ForkSpy:
    """Wraps `os.fork`: counts the parent's forks and remembers the child pids (the child never records)."""

    def __init__(self):
        self.real = os.fork
        self.pids: list[int] = []

    def __call__(self):
        pid = self.real()
        if pid:
            self.pids.append(pid)
        return pid


class WatchdogCase(TempRepoCase):
    def call(self, event="PreToolUse", command=DOCKER_UP, actor="backend-python", tool="Bash", tool_input=None, **kw):
        tinput = tool_input if tool_input is not None else {"command": command}
        return call_main(payload(event, tool, actor=actor, cwd=self.repo, tool_input=tinput), **kw)

    def spy_fork(self):
        spy = ForkSpy()
        patcher = mock.patch.object(audit.os, "fork", spy)
        patcher.start()
        self.addCleanup(patcher.stop)
        return spy

    def assert_all_reaped(self, spy):
        for pid in spy.pids:
            with self.assertRaises(ChildProcessError, msg=f"child {pid} was not reaped"):
                os.waitpid(pid, os.WNOHANG)

    def patch(self, name, value, module=audit):
        patcher = mock.patch.object(module, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def patch_classifier(self, name, value):
        self.patch(name, value, classifier)

    def no_fork(self):
        self.patch("_fork_available", lambda: False)


class ForkPerAuditedTool(WatchdogCase):
    """WD1 (W1): one fork per audited tool call, none for the others."""

    def test_wd1_one_fork_for_bash_and_write_pre_and_post(self):
        spy = self.spy_fork()
        target = str(self.repo / "src" / "a.py")
        for event in ("PreToolUse", "PostToolUse"):
            with self.subTest(event=event, tool="Bash"):
                before = len(spy.pids)
                self.call(event, "pytest tests/test_a.py")
                self.assertEqual(len(spy.pids), before + 1)
            with self.subTest(event=event, tool="Write"):
                before = len(spy.pids)
                self.call(event, tool="Write", tool_input={"file_path": target})
                self.assertEqual(len(spy.pids), before + 1)
        self.assert_all_reaped(spy)

    def test_wd1_no_fork_for_other_tools_modes_and_events(self):
        spy = self.spy_fork()
        self.call("PostToolUse", tool="Read", tool_input={"file_path": "/etc/hostname"})
        self.call("PreToolUse", tool="Grep", tool_input={"pattern": "x"})
        self.call("SubagentStart", tool=None)
        self.assertEqual(spy.pids, [])
        for cfg in ({"mode": "off"}, {"mode": "audit"}):
            with self.subTest(mode=cfg["mode"]):
                call_main(payload("PreToolUse", "Bash", cwd=self.repo, tool_input={"command": DOCKER_UP}), cfg)
                self.assertEqual(spy.pids, [])

    def test_the_visual_tools_are_audited_too(self):
        spy = self.spy_fork()
        res = self.call("PostToolUse", tool="mcp__playwright__browser_take_screenshot", tool_input={})
        self.assertEqual(len(spy.pids), 1)
        self.assertEqual(res.records[0]["flags"], ["visual_tool"])


class DeadlineAndKill(WatchdogCase):
    """WD2, WD3 (W1): the child is killed at the deadline, whatever it is doing."""

    def slow_analysis(self, command, _depth=0):
        time.sleep(30)

    def run_with(self, analysis, event):
        spy = self.spy_fork()
        self.patch("ANALYSIS_TIMEOUT_S", SHORT)
        self.patch_classifier("analyze_command", analysis)
        with mock.patch.object(audit.os, "killpg", wraps=os.killpg) as kill:  # the child's whole process group
            start = time.monotonic()
            res = self.call(event)
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertIn(mock.call(spy.pids[0], signal.SIGKILL), kill.call_args_list)
        self.assert_all_reaped(spy)
        return res

    def test_wd2_pre_denies_with_analysis_timeout(self):
        res = self.run_with(self.slow_analysis, "PreToolUse")
        out = res.output["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("Agent workflow (analysis_timeout)", out["permissionDecisionReason"])
        [record] = res.records
        self.assertEqual(record["flags"], ["analysis_timeout"])
        self.assertEqual(record["categories"], ["other"])
        self.assertEqual(record["cmd"], DOCKER_UP)
        self.assertEqual(record["decision_category"], "analysis_timeout")

    def test_wd2_post_records_without_output(self):
        res = self.run_with(self.slow_analysis, "PostToolUse")
        self.assertIsNone(res.output)
        [record] = res.records
        self.assertEqual(record["flags"], ["analysis_timeout"])
        self.assertIs(record["in_run"], False)  # the child is gone: the record is written untagged
        self.assertEqual(record["run_tags"], "timeout")

    def test_wd3_a_long_c_call_is_cut_off_too(self):
        def stuck(command, _depth=0):
            sum(range(10**12))  # one C call: a signal handler alone would not interrupt it
        res = self.run_with(stuck, "PreToolUse")
        self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(res.records[0]["flags"], ["analysis_timeout"])


class CrashAndError(WatchdogCase):
    """WD4-WD6 (W2, W3): a child that dies, fails or speaks nonsense is blocked, never allowed."""

    def assert_unclassified(self, res, uncertainty, error=None):
        out = res.output["hookSpecificOutput"]
        self.assertEqual(out["permissionDecision"], "deny")
        self.assertIn("Agent workflow (unclassified_command)", out["permissionDecisionReason"])
        [record] = res.records
        self.assertEqual(record["uncertainty"], [uncertainty])
        self.assertEqual(record["flags"], ["parse_uncertain", "unclassified_command"])
        self.assertEqual(record["categories"], ["unclassified"])
        self.assertEqual(record["cmd"], DOCKER_UP)
        if error:
            self.assertEqual(record["error"], error)
        else:
            self.assertNotIn("error", record)

    def test_wd4_a_child_that_exits_without_a_message_is_a_crash(self):
        for name, die in (("os._exit", lambda: os._exit(3)),
                          ("SIGKILL", lambda: os.kill(os.getpid(), signal.SIGKILL))):
            with self.subTest(how=name):
                spy = self.spy_fork()
                with mock.patch.object(classifier, "analyze_command", lambda command, _depth=0: die()):
                    start = time.monotonic()
                    res = self.call()
                self.assertLess(time.monotonic() - start, 2.0)
                self.assert_unclassified(res, "analysis_crash")
                self.assert_all_reaped(spy)

    def test_wd4_the_crash_is_recorded_on_post_without_output(self):
        with mock.patch.object(classifier, "analyze_command", lambda command, _depth=0: os._exit(3)):
            res = self.call("PostToolUse")
        self.assertIsNone(res.output)
        self.assertEqual(res.records[0]["uncertainty"], ["analysis_crash"])

    def test_wd5_an_exception_in_the_child_and_in_process_give_the_same_record(self):
        def boom(command, _depth=0):
            raise RecursionError("probe")
        records = {}
        for path in ("fork", "in-process"):
            with self.subTest(path=path):
                if path == "in-process":
                    self.no_fork()
                spy = self.spy_fork()
                with mock.patch.object(classifier, "analyze_command", boom):
                    res = self.call()
                self.assertEqual(len(spy.pids), 1 if path == "fork" else 0)
                self.assert_unclassified(res, "classifier_error", "RecursionError")
                records[path] = {k: v for k, v in res.records[0].items() if k != "ts"}
        self.assertEqual(records["fork"], records["in-process"])

    def test_wd6_an_invalid_first_line_is_a_crash(self):
        def garbage(payload, event, actor, sock):
            sock.sendall(b"xx\n")
        with mock.patch.object(audit, "_run_child", garbage):
            self.assert_unclassified(self.call(), "analysis_crash")

    def test_wd6_a_first_line_above_the_cap_is_a_crash(self):
        def huge(payload, event, actor, sock):
            sock.sendall(b'{"analysis": {"cmd": "' + b"a" * audit.MAX_CHILD_MESSAGE + b'"}}\n')
        with mock.patch.object(audit, "_run_child", huge):
            start = time.monotonic()
            res = self.call()
        self.assertLess(time.monotonic() - start, 2.0)
        self.assert_unclassified(res, "analysis_crash")

    def test_a_first_line_of_the_wrong_shape_is_a_crash(self):
        for body in (b"[]", b'{"nothing": 1}', b'{"analysis": 3}', b'"x"'):
            with self.subTest(body=body):
                def wrong(payload, event, actor, sock, body=body):
                    sock.sendall(body + b"\n")
                with mock.patch.object(audit, "_run_child", wrong):
                    self.assert_unclassified(self.call(), "analysis_crash")


class RunTagsFromTheChild(WatchdogCase):
    """WD7, WD10 (W4): the decision is printed before the tagging is awaited; tags are read only when needed."""

    def test_the_run_tags_come_from_the_child(self):
        write_run_state(self.repo, {"1": ["services/api/**"]})
        spy = self.spy_fork()
        res = self.call("PostToolUse", "pytest tests/test_a.py")
        self.assertEqual(len(spy.pids), 1)
        [record] = res.records
        self.assertIs(record["in_run"], True)
        self.assertEqual(record["run"], "feat-x")
        self.assertEqual(record["task"], "1")
        self.assertNotIn("run_tags", record)

    def test_a_pre_with_a_decision_gets_the_tags_too(self):
        write_run_state(self.repo, {"1": ["services/api/**"]})
        res = self.call("PreToolUse", DOCKER_UP)
        self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(res.records[0]["run"], "feat-x")

    def test_a_write_already_tagged_by_the_analysis_does_not_wait_for_a_second_line(self):
        calls = []
        real = audit._Child.tags
        self.patch("_run_tags", lambda payload: time.sleep(30))
        with mock.patch.object(audit._Child, "tags", lambda self, *a, **k: calls.append(1) or real(self, *a, **k)):
            start = time.monotonic()
            res = self.call("PostToolUse", tool="Write", tool_input={"file_path": str(self.repo / "a.py")})
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertEqual(calls, [])
        self.assertIn("in_run", res.records[0])

    def test_wd7_a_slow_tagging_keeps_the_decision_and_the_record(self):
        seen = []
        real = audit._Child.tags

        def spy(child, *args, **kwargs):  # runs in the parent right before it waits for the tagging line
            seen.append(sys.stdout.getvalue())
            return real(child, *args, **kwargs)

        self.patch("ANALYSIS_TIMEOUT_S", TAGGING_STUCK)
        self.patch("RECORD_FLOOR_S", 0.1)
        self.patch("git_root", lambda start: time.sleep(30))
        with mock.patch.object(audit._Child, "tags", spy):
            start = time.monotonic()
            res = self.call("PreToolUse", DOCKER_UP)
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertEqual(len(seen), 1)
        self.assertIn('"permissionDecision": "deny"', seen[0])  # already on stdout (W4)
        self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], "deny")
        [record] = res.records
        self.assertIs(record["in_run"], False)
        self.assertEqual(record["run_tags"], "timeout")
        self.assertEqual(record["decision_category"], "docker_lifecycle")

    def test_wd10_a_pre_without_a_decision_never_waits_for_the_tagging(self):
        spy = self.spy_fork()
        calls = []
        real = audit._Child.tags
        self.patch("git_root", lambda start: time.sleep(30))
        with mock.patch.object(audit._Child, "tags", lambda self, *a, **k: calls.append(1) or real(self, *a, **k)):
            start = time.monotonic()
            res = self.call("PreToolUse", "echo hi")
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertIsNone(res.output)
        self.assertEqual(res.records, [])
        self.assertEqual(calls, [])
        self.assert_all_reaped(spy)

    def test_a_warn_decision_does_not_wait_either(self):
        self.patch("git_root", lambda start: time.sleep(30))
        start = time.monotonic()
        res = self.call("PreToolUse", "curl https://example.com/x")
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertEqual(res.output["hookSpecificOutput"].get("permissionDecision"), None)  # a warn
        self.assertEqual(res.records, [])


class ChildOutputIsolation(WatchdogCase):
    """WD8 (W6): the real-process check that nothing the child prints reaches the hook's output lives in
    `test_hook_process.py` (WatchdogProcess, real stdout isolation): an in-process `call_main` captures stdout in
    the test, so it cannot see a leak to the real descriptors."""

    def test_only_the_parent_writes_the_record(self):
        marks = self.repo / "writers.txt"

        def mark(record):  # runs wherever `_write_record` is called: the file tells which process did
            with open(marks, "a", encoding="utf-8") as fh:
                fh.write(f"{os.getpid()}\n")
        self.patch("_write_record", mark)
        for event, command in (("PostToolUse", "pytest tests/test_a.py"), ("PreToolUse", DOCKER_UP)):
            self.call(event, command)
        self.assertEqual(marks.read_text().split(), [str(os.getpid())] * 2)


class Fallback(WatchdogCase):
    """WD9 (W5): without a working fork the analysis runs in process under SIGALRM, with the same rules."""

    def run_both(self, **kw):
        out = {}
        with mock.patch.object(audit.os, "fork", side_effect=OSError("no processes")):
            out["fork-fails"] = self.call(**kw)
        with mock.patch.object(audit, "_fork_available", lambda: False):
            out["unavailable"] = self.call(**kw)
        return out

    def test_wd9_the_classification_still_decides(self):
        for name, res in self.run_both().items():
            with self.subTest(path=name):
                self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], "deny")
                self.assertEqual(res.records[0]["decision_category"], "docker_lifecycle")

    def test_wd9_a_slow_classifier_is_still_an_analysis_timeout(self):
        def slow(command, _depth=0):
            time.sleep(30)
        self.patch("ANALYSIS_TIMEOUT_S", SHORT)
        self.patch_classifier("analyze_command", slow)
        start = time.monotonic()
        results = self.run_both()
        self.assertLess(time.monotonic() - start, 5.0)
        for name, res in results.items():
            with self.subTest(path=name):
                self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], "deny")
                self.assertEqual(res.records[0]["flags"], ["analysis_timeout"])
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))

    def test_a_socketpair_failure_falls_back_too(self):
        with mock.patch.object(audit._socket, "socketpair", side_effect=OSError("no fds")):
            res = self.call()
        self.assertEqual(res.records[0]["decision_category"], "docker_lifecycle")

    def test_fork_is_available_here(self):
        self.assertTrue(audit._fork_available())


class ChildLifetime(WatchdogCase):
    """No zombies, no leaked descriptors, a child that cannot outlive its parent."""

    def open_fds(self):
        return len(os.listdir("/proc/self/fd")) if os.path.isdir("/proc/self/fd") else None

    def test_every_path_reaps_the_child_and_closes_the_sockets(self):
        spy = self.spy_fork()
        before = self.open_fds()
        self.call("PostToolUse", "pytest tests/test_a.py")
        self.call("PreToolUse", DOCKER_UP)
        self.call("PreToolUse", "echo hi")
        with mock.patch.object(classifier, "analyze_command", lambda command, _depth=0: os._exit(3)):
            self.call("PreToolUse")
        self.assertEqual(len(spy.pids), 4)
        self.assert_all_reaped(spy)
        if before is not None:
            self.assertLessEqual(self.open_fds(), before)

    def test_the_child_arms_a_self_destruct_alarm(self):
        seen = []

        def probe(command, _depth=0):
            seen.append(signal.getitimer(signal.ITIMER_REAL)[0])  # in the child: lost with it, so ship it as the cmd
            return classifier.Analysis(["other"], [f"remaining={seen[-1]:.1f}"], [])
        with mock.patch.object(classifier, "analyze_command", probe):
            res = self.call("PostToolUse", "echo hi")
        [flag] = res.records[0]["flags"]
        remaining = float(flag.split("=")[1])
        self.assertGreater(remaining, 0.0)
        self.assertLessEqual(remaining, audit.ANALYSIS_TIMEOUT_S + audit.CHILD_GRACE_S)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL), (0.0, 0.0))  # nothing armed in the parent


class GrandchildDiesWithTheChild(WatchdogCase):
    """Review fix (security low): a git process the killed child was running is not orphaned."""

    def hanging_git(self, repo):
        """Makes `git -C repo rev-parse` block forever: its config includes a FIFO nobody writes to."""
        fifo = repo / "blocking-fifo"
        os.mkfifo(fifo)
        with open(repo / ".git" / "config", "a", encoding="utf-8") as fh:
            fh.write(f"\n[include]\n\tpath = {fifo}\n")
        return fifo

    @staticmethod
    def git_processes(repo):
        found = []
        for name in os.listdir("/proc"):
            if not name.isdigit():
                continue
            try:
                with open(f"/proc/{name}/cmdline", "rb") as fh:
                    argv = fh.read().split(b"\0")
            except OSError:
                continue
            if b"rev-parse" in argv and str(repo).encode() in argv:
                found.append(int(name))
        return found

    @unittest.skipUnless(os.path.isdir("/proc/self"), "needs /proc")
    def test_no_git_grandchild_outlives_a_killed_child(self):
        self.hanging_git(self.repo)
        self.patch("ANALYSIS_TIMEOUT_S", 0.3)  # the child gets time to start git, then it is killed
        target = str(self.repo / "src" / "a.py")
        try:
            res = self.call("PreToolUse", tool="Write", tool_input={"file_path": target})
            self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertEqual(res.records[0]["flags"], ["analysis_timeout"])
            deadline = time.monotonic() + 2.0
            while self.git_processes(self.repo) and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(self.git_processes(self.repo), [])
        finally:
            for pid in self.git_processes(self.repo):  # a failed run must not leave the blocked git behind
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass

    @unittest.skipUnless(os.path.isdir("/proc/self"), "needs /proc")
    def test_self_destruct_takes_the_whole_group(self):
        """Review fix (security low): the hook is group-killed from outside (the child leads its own group, so it
        survives that); its self-destruct alarm then ends the child AND its git process, with no orphan left."""
        self.hanging_git(self.repo)
        hook = HookProcess(self.repo.parent / (self.repo.name + "-hook"))
        self.addCleanup(shutil.rmtree, hook.tmp, ignore_errors=True)
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(hook.home), "LANG": "C.UTF-8",
               "AGENT_AUDIT_DIR": str(hook.metrics_dir), "GIT_CONFIG_NOSYSTEM": "1",
               audit.ANALYSIS_TIMEOUT_ENV: "0.5"}
        event = payload("PreToolUse", "Write", actor="backend-python", cwd=self.repo,
                        tool_input={"file_path": str(self.repo / "src" / "a.py")})
        proc = subprocess.Popen([sys.executable, "-I", "-B", str(hook.script)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(self.repo), env=env,
                                start_new_session=True)  # the hook leads a group of its own, as under Claude Code
        try:
            proc.stdin.write(json.dumps(event).encode())
            proc.stdin.close()
            deadline = time.monotonic() + 3.0
            while not self.git_processes(self.repo) and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertNotEqual(self.git_processes(self.repo), [], "git never started: the test would be vacuous")
            os.killpg(proc.pid, signal.SIGKILL)  # the hook dies; the child, in its own group, does not
            proc.wait(timeout=5)
            deadline = time.monotonic() + 4.0  # limit 0.5 s + grace 1.0 s from the start of the child
            while self.git_processes(self.repo) and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(self.git_processes(self.repo), [])
        finally:
            for pid in self.git_processes(self.repo):
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            for stream in (proc.stdout, proc.stderr):
                stream.close()

    def test_the_self_destruct_handler_spares_a_foreign_group(self):
        """If the child is not its own group leader (setpgid failed), the alarm never kills the hook's group."""
        with mock.patch.object(audit.os, "killpg") as killpg, mock.patch.object(audit.os, "_exit") as leave:
            audit._kill_own_group(signal.SIGALRM, None)  # the test process leads no group of its own here
        if os.getpgrp() == os.getpid():
            killpg.assert_called_once_with(0, signal.SIGKILL)
        else:
            killpg.assert_not_called()
        leave.assert_called_once_with(0)

    def test_the_child_leads_its_own_process_group(self):
        groups = []
        real = audit._Child.close

        def spy(child):
            try:
                groups.append(os.getpgid(child.pid))
            except OSError:
                groups.append(None)
            return real(child)
        with mock.patch.object(audit._Child, "close", spy):
            spy_fork = self.spy_fork()
            self.call("PostToolUse", "pytest tests/test_a.py")
        self.assertEqual(groups, [spy_fork.pids[0]])
        self.assertNotEqual(groups[0], os.getpgid(0))

    def test_close_falls_back_to_killing_the_child_alone(self):
        spy = self.spy_fork()
        with mock.patch.object(audit.os, "killpg", side_effect=ProcessLookupError()):
            with mock.patch.object(audit.os, "kill", wraps=os.kill) as kill:
                self.call("PreToolUse", "echo hi")
        self.assertIn(mock.call(spy.pids[0], signal.SIGKILL), kill.call_args_list)
        self.assert_all_reaped(spy)


def load_tests(loader, tests, pattern):
    """Independent cases: run them in forked workers (see `ForkedSuite`)."""
    return ForkedSuite(tests)


if __name__ == "__main__":
    unittest.main()
