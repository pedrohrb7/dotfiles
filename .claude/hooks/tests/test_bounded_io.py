"""Bounded I/O of the agent-audit hook.

Source: spec audit-hook-hardening, section Testing, `test_bounded_io.py` (BIO1-BIO10), Task 1.
Every file the hook reads or writes is opened without blocking, only if regular, and with a size limit.
Nothing here starts a process; FIFOs, sparse files and links are made in temp directories.
"""
import ast
import json
import os
import shutil
import stat
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from ._support import ForkedSuite, TempRepoCase, audit, call_main, payload, write_run_state

HOOK_SOURCE = audit.__file__
FAST = 0.5  # seconds: a blocking open would hang, so any bound well under this proves it did not block


class TmpCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agent-audit-tests-bio-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def timed(self, fn, *args, **kwargs):
        start = time.monotonic()
        result = fn(*args, **kwargs)
        self.assertLess(time.monotonic() - start, FAST)
        return result


class ReadBounded(TmpCase):
    """BIO1 (spec audit-hook-hardening): `_read_bounded` never blocks, never raises, never over-reads."""

    def test_regular_file_below_at_and_above_the_limit(self):
        f = self.tmp / "f"
        f.write_bytes(b"abcdef")
        self.assertEqual(audit._read_bounded(f, 10), b"abcdef")
        self.assertEqual(audit._read_bounded(f, 6), b"abcdef")
        self.assertIsNone(audit._read_bounded(f, 5))
        self.assertEqual(audit._read_bounded(f, 5, truncate=True), b"abcde")

    def test_fifo_without_a_writer_is_rejected_fast(self):
        fifo = self.tmp / "fifo"
        os.mkfifo(fifo)
        self.assertIsNone(self.timed(audit._read_bounded, fifo, 100))

    def test_directory_missing_and_device_are_none(self):
        self.assertIsNone(audit._read_bounded(self.tmp, 100))
        self.assertIsNone(audit._read_bounded(self.tmp / "missing", 100))
        self.assertIsNone(audit._read_bounded(os.devnull, 100))

    def test_symlink_to_a_regular_file_is_followed_and_to_a_fifo_is_not_read(self):
        target = self.tmp / "t"
        target.write_bytes(b"xy")
        link = self.tmp / "link"
        link.symlink_to(target)
        self.assertEqual(audit._read_bounded(link, 10), b"xy")
        fifo = self.tmp / "fifo"
        os.mkfifo(fifo)
        flink = self.tmp / "flink"
        flink.symlink_to(fifo)
        self.assertIsNone(self.timed(audit._read_bounded, flink, 10))

    def test_sparse_file_is_rejected_by_the_limit(self):
        f = self.tmp / "sparse"
        with open(f, "wb") as fh:
            fh.truncate(50 * 1024 * 1024)
        self.assertIsNone(self.timed(audit._read_bounded, f, 1024))


class LoadConfig(TmpCase):
    """BIO2 (B1): the config is read bounded; any failure is the audit-mode config."""

    AUDIT = {"mode": "audit"}

    def load(self, path):
        with mock.patch.object(audit, "CONFIG_PATH", path):
            return self.timed(audit.load_config)

    def test_fifo_is_audit_mode(self):
        fifo = self.tmp / "agent-audit.json"
        os.mkfifo(fifo)
        self.assertEqual(self.load(fifo), self.AUDIT)

    def test_file_over_the_limit_is_audit_mode(self):
        f = self.tmp / "big.json"
        pad = " " * audit.MAX_CONFIG_BYTES
        f.write_text('{"mode": "enforce"}' + pad)
        self.assertEqual(self.load(f), self.AUDIT)

    def test_valid_config_is_read(self):
        f = self.tmp / "ok.json"
        f.write_text('{"mode": "enforce", "categories": {}}')
        self.assertEqual(self.load(f), {"mode": "enforce", "categories": {}})

    def test_invalid_and_missing_are_audit_mode(self):
        f = self.tmp / "bad.json"
        f.write_text("{nope")
        self.assertEqual(self.load(f), self.AUDIT)
        self.assertEqual(self.load(self.tmp / "missing.json"), self.AUDIT)


class ActiveRun(TmpCase):
    """BIO3-BIO6 (B2): `active_run` is bounded in entries, reads and bytes, and ignores what is not a run state."""

    def setUp(self):
        super().setUp()
        self.runs = self.tmp / ".claude" / "runs"
        self.runs.mkdir(parents=True)
        self._clock = 1_000_000.0

    def add(self, name, content=None, *, raw=None):
        """Create a state file; each call is newer than the previous one."""
        f = self.runs / name
        f.write_text(raw if raw is not None else json.dumps(content))
        self._clock += 10
        os.utime(f, (self._clock, self._clock))
        return f

    def valid(self, name="good.json", **extra):
        return self.add(name, {"phase": "implement", "current_task": 1, **extra})

    def test_non_object_states_are_ignored_as_invalid_json(self):
        self.valid()
        for i, value in enumerate(([], "x", 3, None)):  # all newer than the valid state
            self.add(f"bad{i}.json", value)
        run = self.timed(audit.active_run, self.tmp)
        self.assertEqual(run["_slug"], "good")

    def test_only_non_objects_is_none(self):
        self.add("a.json", [])
        self.add("b.json", None)
        self.assertIsNone(audit.active_run(self.tmp))

    def test_sparse_state_is_skipped_fast(self):
        self.valid()
        big = self.add("big.json", {})
        os.truncate(big, 50 * 1024 * 1024)
        os.utime(big, (self._clock + 10, self._clock + 10))
        self.assertEqual(self.timed(audit.active_run, self.tmp)["_slug"], "good")

    def test_fifo_and_directory_entries_are_ignored(self):
        self.valid()
        os.mkfifo(self.runs / "x.json")
        (self.runs / "y.json").mkdir()
        self.assertEqual(self.timed(audit.active_run, self.tmp)["_slug"], "good")

    def test_at_most_max_run_entries_are_listed_and_max_run_reads_read(self):
        for i in range(audit.MAX_RUN_ENTRIES + 44):
            self.add(f"s{i:03d}.json", {"phase": "done"})
        real = audit._read_bounded
        with mock.patch.object(audit, "_read_bounded", wraps=real) as spy:
            self.assertIsNone(audit.active_run(self.tmp))
        self.assertLessEqual(spy.call_count, audit.MAX_RUN_READS)

    def test_an_active_run_older_than_the_read_limit_is_not_seen(self):
        self.valid("old.json")  # documented limit: MAX_RUN_READS newer finished states hide it
        for i in range(audit.MAX_RUN_READS):
            self.add(f"done{i:02d}.json", {"phase": "done"})
        self.assertIsNone(audit.active_run(self.tmp))

    def test_newest_active_state_wins_and_done_is_skipped(self):
        self.valid("old.json")
        self.valid("new.json")
        self.add("newest.json", {"phase": "done"})
        self.assertEqual(audit.active_run(self.tmp)["_slug"], "new")

    def test_missing_runs_dir_is_none(self):
        shutil.rmtree(self.runs)
        self.assertIsNone(audit.active_run(self.tmp))


class WriteScopeWithNonObjectState(TempRepoCase):
    """BIO3: a stray `[]` next to the run state no longer drops `evaluate_write` into its fallback."""

    def test_docs_write_by_implementer_survives_a_non_object_state(self):
        write_run_state(self.repo, {"1": ["services/api/**"]})
        stray = self.repo / ".claude" / "runs" / "stray.json"
        stray.write_text("[]")
        valid = self.repo / ".claude" / "runs" / "feat-x.json"
        os.utime(valid, (time.time() - 100, time.time() - 100))  # the stray one is newer
        res = self.evaluate("README.md", "backend-node")
        self.assertIn("docs_write_by_implementer", res["flags"])
        self.assertEqual(res["area"], "code")


class AppendLine(TmpCase):
    """BIO7 (B3): `_append_line` never blocks, never follows a link, and drops what it cannot write."""

    def test_new_file_is_0600_and_existing_file_is_appended(self):
        f = self.tmp / "m.jsonl"
        self.assertTrue(audit._append_line(f, "one\n"))
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
        self.assertTrue(audit._append_line(f, "two\n"))
        self.assertEqual(f.read_text(), "one\ntwo\n")

    def test_fifo_without_a_reader_is_dropped_fast(self):
        fifo = self.tmp / "t.jsonl"
        os.mkfifo(fifo)
        self.assertIs(self.timed(audit._append_line, fifo, "x\n"), False)

    def test_symlink_is_not_followed(self):
        target = self.tmp / "target"
        target.write_text("keep\n")
        link = self.tmp / "link.jsonl"
        link.symlink_to(target)
        self.assertIs(audit._append_line(link, "x\n"), False)
        self.assertEqual(target.read_text(), "keep\n")

    def test_directory_and_missing_parent_are_false(self):
        self.assertIs(audit._append_line(self.tmp, "x\n"), False)
        self.assertIs(audit._append_line(self.tmp / "nope" / "m.jsonl", "x\n"), False)

    def test_a_large_line_is_written_whole(self):
        f = self.tmp / "m.jsonl"
        line = "y" * 300_000 + "\n"
        self.assertTrue(audit._append_line(f, line))
        self.assertEqual(f.read_text(), line)


class SlowTagging(TempRepoCase):
    """BIO8 (R1), in-process path: a run tagging that overruns the budget no longer loses the record."""

    def setUp(self):
        super().setUp()
        # The in-process path (SIGALRM) is the one under test; the fork path is covered by WD7. Without this the
        # tagging would run in a forked child, whose start-up eats the margin of a short deadline under load.
        patcher = mock.patch.object(audit, "_fork_available", lambda: False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def slow(self, start):
        time.sleep(30)

    def call(self, event, command):
        # 0.1 s: the in-process analysis of a one-line command takes milliseconds, the tagging never ends
        with mock.patch.object(audit, "ANALYSIS_TIMEOUT_S", 0.1), mock.patch.object(audit, "RECORD_FLOOR_S", 0.1), \
                mock.patch.object(audit, "git_root", self.slow):
            start = time.monotonic()
            res = call_main(payload(event, "Bash", actor="backend-python", cwd=self.repo,
                                    tool_input={"command": command}))
        self.assertLess(time.monotonic() - start, 2.0)
        return res

    def test_post_is_recorded_without_the_run_tags(self):
        res = self.call("PostToolUse", "pytest tests/test_a.py")
        self.assertIsNone(res.output)
        [record] = res.records
        self.assertIs(record["in_run"], False)
        self.assertEqual(record["run_tags"], "timeout")

    def test_pre_deny_is_printed_and_the_same_record_is_written(self):
        res = self.call("PreToolUse", "docker compose up")
        self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], "deny")
        [record] = res.records
        self.assertIs(record["in_run"], False)
        self.assertEqual(record["run_tags"], "timeout")
        self.assertEqual(record["decision_category"], "docker_lifecycle")

    def test_tagged_normally_when_fast(self):
        write_run_state(self.repo, {"1": ["services/api/**"]})
        res = call_main(payload("PostToolUse", "Bash", cwd=self.repo, tool_input={"command": "pytest tests/test_a.py"}))
        [record] = res.records
        self.assertIs(record["in_run"], True)
        self.assertEqual(record["run"], "feat-x")
        self.assertNotIn("run_tags", record)


class FileAccessInvariant(unittest.TestCase):
    """BIO9 (B5): no file read or write in the hook outside `_read_bounded`, `_append_line` and the stdin payload."""

    ALLOWED_FUNCTIONS = {"_read_bounded", "_append_line"}
    FILE_ATTRS = {"fdopen", "read_text", "read_bytes", "read", "write", "load", "open"}

    def offenders(self, source: str) -> list[str]:
        tree = ast.parse(source)
        found: list[str] = []

        def visit(node, function):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function = node.name
            if isinstance(node, ast.Call):
                name = None
                if isinstance(node.func, ast.Name) and node.func.id == "open":
                    name = "open"
                elif isinstance(node.func, ast.Attribute) and node.func.attr in self.FILE_ATTRS:
                    name = node.func.attr
                if name and function not in self.ALLOWED_FUNCTIONS and not self.is_stdin_load(node, function):
                    found.append(f"{function or '<module>'}: {name}() at line {node.lineno}")
            for child in ast.iter_child_nodes(node):
                visit(child, function)

        visit(tree, None)
        return found

    @staticmethod
    def is_stdin_load(node: ast.Call, function) -> bool:
        return (function == "main" and isinstance(node.func, ast.Attribute) and node.func.attr == "load"
                and bool(node.args) and ast.unparse(node.args[0]) == "sys.stdin")

    def test_the_hook_has_no_unbounded_file_access(self):
        source = Path(HOOK_SOURCE).read_text(encoding="utf-8")
        self.assertEqual(self.offenders(source), [])

    def test_the_check_flags_a_new_unbounded_read(self):
        bad = "def helper(p):\n    return open(p).read()\n\ndef other(p):\n    return p.read_text()\n"
        self.assertEqual(len(self.offenders(bad)), 3)  # open, read, read_text, by function name
        self.assertTrue(all("helper" in o or "other" in o for o in self.offenders(bad)))


class DocsRootStillBounded(TmpCase):
    """BIO10: `project_docs_root` keeps its behavior on top of `_read_bounded(..., truncate=True)`."""

    def test_declaration_beyond_the_limit_is_not_read_and_one_inside_is(self):
        (self.tmp / "CLAUDE.md").write_text("## Workflow\n\n- docs root: .claude/docs/\n")
        self.assertEqual(audit.project_docs_root(self.tmp), ".claude/docs/")
        (self.tmp / "CLAUDE.md").write_text("x" * 262144 + "\n## Workflow\n\n- docs root: late/\n")
        self.assertEqual(audit.project_docs_root(self.tmp), "docs/")

    def test_fifo_is_the_default(self):
        os.mkfifo(self.tmp / "CLAUDE.md")
        self.assertEqual(self.timed(audit.project_docs_root, self.tmp), "docs/")


def load_tests(loader, tests, pattern):
    """Independent cases: run them in forked workers (see `ForkedSuite`)."""
    return ForkedSuite(tests)


if __name__ == "__main__":
    unittest.main()
