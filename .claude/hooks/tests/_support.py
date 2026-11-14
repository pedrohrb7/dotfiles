"""Shared infrastructure for the agent-audit hook test suite.

Everything is stdlib. Commands such as `docker compose up` or `git push` appear only as strings;
the only processes started are `git init` (once, copied by `init_repo`), `git rev-parse` (by the hook itself) and
the hook copy run by `HookProcess`. `ForkedSuite` and `HookProcess.run_many` keep the suite inside its time budget.
"""
import atexit
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

from . import _loader
from ._loader import load_hook

audit = load_hook("agent-audit.py", "agent_audit")
# The command classifier is a module of its own, loaded by the hook (which registers it in `sys.modules`): this is the
# instance the hook calls, so a `mock.patch.object(classifier, ...)` reaches the hook too. `classifier.shell` is the parser.
classifier = load_hook("agent_audit_classify.py")
metrics = load_hook("agent-metrics.py", "agent_metrics")

HOOKS_DIR = _loader.HOOKS_DIR
CLAUDE_DIR = HOOKS_DIR.parent

_BLOCK = "block"
_ASK = "ask"
_WARN = "warn"
_AUDIT = "audit"

# Fixed config for the mechanism tests. Never read from the live agent-audit.json: a policy
# change there (for instance promoting a category from warn to block) must not break the suite.
TEST_CONFIG: dict = {
    "mode": "enforce",
    "categories": {
        "docker_lifecycle": _BLOCK,
        "write_by_readonly_agent": _BLOCK,
        "visual_tool": _BLOCK,
        "design_director_write_outside": _BLOCK,
        "command_too_long": _BLOCK,
        "analysis_timeout": _BLOCK,
        "unclassified_command": _BLOCK,
        "parse_uncertain": _AUDIT,
        "git_commit": _ASK,
        "git_push": _ASK,
        "docker_build": _AUDIT,
        "external_request": _WARN,
        "suite_by_non_runner": _WARN,
        "out_of_scope_write": _WARN,
        "md_outside_docs": _WARN,
        "docs_write_by_implementer": _WARN,
        "backlog_write_by_other": _WARN,
        "design_system_write_by_other": _WARN,
    },
}


def config(**overrides) -> dict:
    """Deep copy of TEST_CONFIG with top-level keys replaced by `overrides`."""
    out = copy.deepcopy(TEST_CONFIG)
    out.update(copy.deepcopy(overrides))
    return out


def _make_git_template() -> Path:
    """The real `git init` (no template: only HEAD, config, objects and refs) in a private temp dir, once, when
    this module is imported (before the forked workers of `ForkedSuite` exist, which skip `atexit`)."""
    base = Path(tempfile.mkdtemp(prefix="agent-audit-tests-gitdir-"))
    atexit.register(shutil.rmtree, base, ignore_errors=True)
    subprocess.run(["git", "init", "-q", "--template=", str(base)], check=True)
    return base / ".git"


_GIT_TEMPLATE = _make_git_template()


def init_repo(path) -> None:
    """Make `path` a git repository, like `git init -q <path>`, without starting a process each time: a copy of
    the `.git` of `_GIT_TEMPLATE`. The hook still runs the real `git rev-parse` against the result."""
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(_GIT_TEMPLATE, target / ".git")


def assert_no_git_root(path) -> None:
    """Fail unless `path` is outside any git repository."""
    root = audit.git_root(Path(path))
    if root is not None:
        raise AssertionError(f"premissa do ambiente: {path} esta dentro de um repo git ({root})")


def declare_docs_root(root, value, *, section="Workflow", extra="") -> None:
    """Write `<root>/CLAUDE.md` declaring `- docs root: <value>` under `## <section>`.

    `extra` is appended verbatim after the declaration."""
    text = f"# p\n\n## {section}\n\n- docs layout: features\n- docs root: {value}\n{extra}"
    (Path(root) / "CLAUDE.md").write_text(text, encoding="utf-8")


def write_run_state(root, allowed: dict, **extra) -> None:
    """Write an active /implement run state (`.claude/runs/feat-x.json`) under `root`."""
    runs = Path(root) / ".claude" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    state = {"phase": "implement", "current_task": 1, "allowed_paths": allowed}
    state.update(extra)
    (runs / "feat-x.json").write_text(json.dumps(state))


class TempRepoCase(unittest.TestCase):
    """Temp git repo with an active /implement run state, and evaluate_write helpers.

    Nothing is scratch unless a test passes `scratchpad=` (see `make_scratchpad()`), so the suite does
    not depend on the TMPDIR it runs under.
    """

    ALLOWED = {"1": ["services/api/**"], "2": ["services/web/**"]}

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        init_repo(self.repo)
        (self.repo / ".claude" / "runs").mkdir(parents=True)

    def write_run(self, **extra):
        write_run_state(self.repo, self.ALLOWED, **extra)

    def declare(self, value, **kw):
        declare_docs_root(self.repo, value, **kw)

    def remove_run(self):
        (self.repo / ".claude" / "runs" / "feat-x.json").unlink(missing_ok=True)

    def make_dir(self, prefix="audit-", git=False):
        d = Path(tempfile.mkdtemp(prefix=prefix))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        if git:
            init_repo(d)
        else:
            assert_no_git_root(d)
        return d

    def make_scratchpad(self, session="s1", slug="-proj") -> Path:
        """`<temp dir>/claude-<uid>/<slug>/<session>/scratchpad` (mode 0700), outside any repo.

        Same shape as the Claude Code session scratchpad; the base is removed on cleanup."""
        uid = os.getuid() if hasattr(os, "getuid") else 0
        sp = self.make_dir().resolve() / f"claude-{uid}" / slug / session / "scratchpad"
        sp.mkdir(parents=True, mode=0o700)
        return sp

    def eval_at(self, target, actor, cwd=None, scratchpad=None):
        return audit.evaluate_write(str(target), str(cwd or self.repo), actor, "Write", None, scratchpad=scratchpad)

    def evaluate(self, rel, actor="frontend-react"):
        return audit.evaluate_write(str(self.repo / rel), str(self.repo), actor, "Write", None)


def payload(event, tool=None, *, actor="main", cwd, session="t", tool_input=None, tool_response=None,
            scratchpad=None) -> dict:
    """Build a hook stdin payload. actor: "main" (no agent keys), "subagent" (agent_id only) or an agent name."""
    out: dict = {"hook_event_name": event, "session_id": session, "cwd": str(cwd)}
    if actor == "subagent":
        out["agent_id"] = "agent-1"
    elif actor != "main":
        out["agent_type"] = actor
        out["agent_id"] = "agent-1"
    if tool is not None:
        out["tool_name"] = tool
        out["tool_input"] = tool_input if tool_input is not None else {}
    if tool_response is not None:
        out["tool_response"] = tool_response
    if scratchpad is not None:
        out["scratchpad_dir"] = str(scratchpad)
    return out


def read_jsonl(path) -> list[dict]:
    """Lines of a JSONL file as dicts; a missing file gives []."""
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


@dataclass
class HookResult:
    output: dict | None
    records: list[dict]


def call_main(payload: dict, config: dict | None = None, metrics_dir: Path | None = None) -> HookResult:
    """Run audit.main() in process with a fixed config and a metrics directory.

    The directory is fresh for each call unless `metrics_dir` is given (then calls can share it).
    `output` is the JSON the hook printed (None when silent); `records` are the lines found in the
    directory afterwards.
    """
    cfg = TEST_CONFIG if config is None else config
    with tempfile.TemporaryDirectory(prefix="agent-audit-tests-call-") as tmp:
        if metrics_dir is None:
            metrics_dir = Path(tmp) / "metrics"
        buf = io.StringIO()
        with (
            mock.patch.object(audit, "load_config", lambda: copy.deepcopy(cfg)),
            mock.patch.object(audit, "METRICS_DIR", metrics_dir),
            mock.patch.object(sys, "stdin", io.StringIO(json.dumps(payload))),
            redirect_stdout(buf),
        ):
            audit.main()
        text = buf.getvalue().strip()
        output = json.loads(text) if text else None
        records = []
        for f in sorted(metrics_dir.glob("*.jsonl")):
            records.extend(read_jsonl(f))
    return HookResult(output=output, records=records)


def _parallelism() -> int:
    return max(1, min(8, os.cpu_count() or 1))


class _Slots:
    """A counting semaphore that works across threads and across forked processes: tokens in a pipe.

    Bounds the hook processes alive at once, whichever worker or thread starts them (`run_many` and `ForkedSuite`
    nest): at most one per core, so the short deadlines of the watchdog cases keep a core each and do not flake."""

    def __init__(self, count: int):
        self.read_fd, self.write_fd = os.pipe()
        os.write(self.write_fd, b"x" * count)

    def __enter__(self):
        os.read(self.read_fd, 1)

    def __exit__(self, *exc):
        os.write(self.write_fd, b"x")


_PROCESS_SLOTS = _Slots(_parallelism())


class HookProcess:
    """The hook as a real process, run from a private copy with its own config, metrics and HOME."""

    TIMEOUT = 10  # same as the settings.json hook timeout

    def __init__(self, tmp: Path, config: "dict | str | None" = TEST_CONFIG):
        self.tmp = Path(tmp)
        self.dir = self.tmp / "hook"
        self.metrics_dir = self.tmp / "metrics"
        self.home = self.tmp / "home"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.home.mkdir(parents=True, exist_ok=True)
        self.script = self.dir / "agent-audit.py"
        shutil.copy2(HOOKS_DIR / "agent-audit.py", self.script)
        shutil.copy2(HOOKS_DIR / "agent-metrics.py", self.dir / "agent-metrics.py")
        for module in ("agent_audit_shell.py", "agent_audit_classify.py"):  # the hook loads them by path
            shutil.copy2(HOOKS_DIR / module, self.dir / module)
        if isinstance(config, str):
            (self.dir / "agent-audit.json").write_text(config, encoding="utf-8")
        elif config is not None:
            (self.dir / "agent-audit.json").write_text(json.dumps(config), encoding="utf-8")

    def patch_source(self, old: str, new: str, file: str = "agent-audit.py") -> None:
        """Replace a snippet of a file of the private copy of the hook (never the versioned file): the hook itself,
        or a module it loads (`file="agent_audit_shell.py"`, `file="agent_audit_classify.py"`).

        Fails when `old` does not appear exactly once, so a refactor cannot turn the patch into a no-op."""
        path = self.dir / file
        text = path.read_text(encoding="utf-8")
        found = text.count(old)
        if found != 1:
            raise AssertionError(f"patch_source: {old!r} appears {found} times in {file} of the hook copy, expected exactly 1")
        path.write_text(text.replace(old, new), encoding="utf-8")

    def run(self, stdin: "dict | str", cwd, extra_env: "dict[str, str] | None" = None,
            bytecode: bool = False) -> CompletedProcess:
        """Run the hook copy once. `bytecode=True` leaves out `-B`, so the interpreter writes and reads the
        `__pycache__` of the module the hook loads (the live hook runs that way)."""
        data = stdin if isinstance(stdin, str) else json.dumps(stdin)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "AGENT_AUDIT_DIR": str(self.metrics_dir),
            "LANG": "C.UTF-8",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        env.update(extra_env or {})
        flags = ["-I"] if bytecode else ["-I", "-B"]
        with _PROCESS_SLOTS:
            return subprocess.run(
                [sys.executable, *flags, str(self.script)],
                input=data, capture_output=True, text=True, cwd=str(cwd), env=env, timeout=self.TIMEOUT,
            )

    def records(self, session: str = "t") -> list[dict]:
        return read_jsonl(self.metrics_dir / f"{session}.jsonl")

    @staticmethod
    def run_many(items: "list[tuple[HookProcess, list[tuple]]]") -> "list[list[CompletedProcess]]":
        """Run independent sessions in parallel; the runs of one session stay in order.

        Each item is `(hook, steps)`, with `hook` its own `HookProcess` (own private copy, metrics and HOME, so the
        order of its records is not mixed with another session's) and `steps` a list of `(stdin, cwd[, extra_env])`
        run one after the other. Returns, per item and in the same order, the `CompletedProcess` of each step.
        Nothing is asserted here: the caller checks the results in the test thread (so `subTest` stays usable). A
        failing run (for instance `TimeoutExpired`) is raised when the results are collected."""
        def session(item):
            hook, steps = item
            return [hook.run(*step) for step in steps]

        if not items:
            return []
        with ThreadPoolExecutor(max_workers=min(_parallelism(), len(items))) as pool:
            return list(pool.map(session, items))


class RemoteFailure(Exception):
    """A failure or error that happened in a `ForkedSuite` worker: its message is the worker's formatted traceback."""


class _Recorder(unittest.TestResult):
    """The result a `ForkedSuite` worker runs a test against: keeps plain, picklable events (the traceback already
    formatted as text) to be replayed on the real result by the parent."""

    def __init__(self):
        super().__init__()
        self.events: list[tuple] = []

    def addSuccess(self, test):
        self.events.append(("addSuccess",))

    def addSkip(self, test, reason):
        self.events.append(("addSkip", reason))

    def addFailure(self, test, err):
        self.events.append(("addFailure", self._exc_info_to_string(err, test)))

    def addError(self, test, err):
        self.events.append(("addError", self._exc_info_to_string(err, test)))

    def addSubTest(self, test, subtest, err):
        if err is not None:  # a passing subtest reports nothing; the test's own outcome follows
            kind = "addFailure" if issubclass(err[0], test.failureException) else "addError"
            self.events.append((kind, f"{subtest}\n{self._exc_info_to_string(err, test)}"))

    def addExpectedFailure(self, test, err):
        self.events.append(("addExpectedFailure", self._exc_info_to_string(err, test)))

    def addUnexpectedSuccess(self, test):
        self.events.append(("addUnexpectedSuccess",))


class ForkedSuite(unittest.TestSuite):
    """Runs the tests of a module in forked worker processes and reports them in order, in the process that ran it.

    For modules whose tests are independent of each other (own temp dirs; patches and signals stay inside a worker,
    which is a separate process): no class or module fixtures. A module that has any is not forked: the suite
    falls back to the normal runner, which runs the fixtures. The workers take the
    next test from a shared queue (a pipe of indexes), run it against a `_Recorder` and send the events back in a file;
    the parent replays them on the real result test by test, so the counts, names and tracebacks are the usual ones
    (a traceback is the worker's text inside a `RemoteFailure`). A worker that dies leaves its tests as errors.

    The parent is single-threaded when it forks (the hook forks as well, in `call_main` tests)."""

    def run(self, result, debug=False):
        tests = list(_leaves(self))
        if any(_has_fixtures(test) for test in tests):
            return super().run(result, debug)  # the normal runner runs the class and module fixtures
        if not tests:
            return result
        workers = min(_parallelism(), len(tests))
        out_dir = Path(tempfile.mkdtemp(prefix="agent-audit-tests-forked-"))
        try:
            queue_r, queue_w = os.pipe()
            os.write(queue_w, b"".join(i.to_bytes(2, "big") for i in range(len(tests))))
            os.close(queue_w)
            sys.stdout.flush()
            sys.stderr.flush()
            pids = []
            for k in range(workers):
                pid = os.fork()
                if pid == 0:  # worker: never returns, and skips the parent's atexit handlers
                    code = 1
                    try:
                        _work(tests, queue_r, out_dir / f"{k}.json")
                        code = 0
                    finally:
                        for stream in (sys.stdout, sys.stderr):  # os._exit skips the interpreter's flush
                            try:
                                stream.flush()
                            except Exception:
                                pass
                        os._exit(code)
                pids.append(pid)
            os.close(queue_r)
            for pid in pids:
                os.waitpid(pid, 0)
            events: dict[int, list] = {}
            for k in range(workers):
                try:
                    with open(out_dir / f"{k}.json", encoding="utf-8") as fh:
                        events.update({int(i): ev for i, ev in json.load(fh).items()})
                except (OSError, ValueError):
                    pass  # that worker's tests are reported as missing below
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)
        for i, test in enumerate(tests):
            result.startTest(test)
            try:
                for name, *args in events.get(i, [("addError", "the forked worker died before reporting this test")]):
                    if name in ("addFailure", "addError", "addExpectedFailure"):
                        err = RemoteFailure(args[0])
                        getattr(result, name)(test, (RemoteFailure, err, None))
                    else:
                        getattr(result, name)(test, *args)
            finally:
                result.stopTest(test)
        return result


def package_suite(loader, package: str, package_file: str, pattern: str):
    """The tests of every module of the package as one suite, for `load_tests` of the package `__init__`.

    Each module is loaded through its own `load_tests`. The independent cases of the modules that return a
    `ForkedSuite` (and have no fixtures) share one `ForkedSuite`, queued with the modules that start the most
    hook processes first so a long test never runs alone at the end; the other modules run as usual, first."""
    import fnmatch
    names = sorted(f[:-3] for f in os.listdir(Path(package_file).parent) if f.endswith(".py") and fnmatch.fnmatch(f, pattern))
    heavy = [n for n in _HEAVY_FIRST if n in names]
    names = heavy + [n for n in names if n not in heavy]
    plain, forked = unittest.TestSuite(), []
    for name in names:
        suite = loader.loadTestsFromName(f"{package}.{name}")
        leaves = list(_leaves(suite))
        if isinstance(suite, ForkedSuite) and leaves and not any(_has_fixtures(t) for t in leaves):
            forked.extend(leaves)
        else:
            plain.addTest(suite)
    return unittest.TestSuite([plain, ForkedSuite(forked)])


# Modules whose cases start hook processes (the long ones), queued first by `package_suite`.
_HEAVY_FIRST = ("test_hook_process", "test_watchdog", "test_shell_properties", "test_uncertainty", "test_hook_main")


def _has_fixtures(test) -> bool:
    """True when the test's class has class fixtures or its module has `setUpModule` / `tearDownModule`."""
    cls = type(test)
    if cls.setUpClass.__func__ is not unittest.TestCase.setUpClass.__func__ or \
            cls.tearDownClass.__func__ is not unittest.TestCase.tearDownClass.__func__:
        return True
    module = sys.modules.get(cls.__module__)
    return module is not None and (hasattr(module, "setUpModule") or hasattr(module, "tearDownModule"))


def _work(tests, queue_fd: int, out_path: Path) -> None:
    """Body of a `ForkedSuite` worker: take indexes until the queue is empty, run them, save the events."""
    events: dict[int, list] = {}
    try:
        while len(raw := os.read(queue_fd, 2)) == 2:
            index = int.from_bytes(raw, "big")
            recorder = _Recorder()
            tests[index].run(recorder)
            events[index] = recorder.events  # plain strings only: JSON
    finally:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(events, fh)


def _leaves(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _leaves(item)
        else:
            yield item
