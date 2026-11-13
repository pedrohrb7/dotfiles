"""Shared infrastructure for the agent-audit hook test suite.

Everything is stdlib. Commands such as `docker compose up` or `git push` appear only as strings;
the only processes started are `git init`, `git rev-parse` (by the hook itself) and the hook copy
run by `HookProcess`.
"""
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

from . import _loader
from ._loader import load_hook

audit = load_hook("agent-audit.py", "agent_audit")
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
    "docs_roots": ["docs/", ".claude/docs/"],
    "categories": {
        "docker_lifecycle": _BLOCK,
        "write_by_readonly_agent": _BLOCK,
        "visual_tool": _BLOCK,
        "design_director_write_outside": _BLOCK,
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


def assert_not_scratch(path) -> None:
    """Fail unless `path` is not an agent scratchpad according to the hook (under the current patches)."""
    if audit.is_scratch(Path(path).resolve()):
        raise AssertionError(f"premissa do ambiente: {path} e tratado como scratchpad (TMPDIR sob claude-*?)")


def assert_no_git_root(path) -> None:
    """Fail unless `path` is outside any git repository."""
    root = audit.git_root(Path(path))
    if root is not None:
        raise AssertionError(f"premissa do ambiente: {path} esta dentro de um repo git ({root})")


def write_run_state(root, allowed: dict, **extra) -> None:
    """Write an active /implement run state (`.claude/runs/feat-x.json`) under `root`."""
    runs = Path(root) / ".claude" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    state = {"phase": "implement", "current_task": 1, "allowed_paths": allowed}
    state.update(extra)
    (runs / "feat-x.json").write_text(json.dumps(state))


class TempRepoCase(unittest.TestCase):
    """Temp git repo with an active /implement run state, and evaluate_write helpers.

    SCRATCH_BASES is patched to () so a directory under /tmp/claude-* (the TMPDIR of an agent run)
    is not treated as a scratchpad by accident. Tests of the scratch exemption itself call
    `use_real_scratch_bases()` or set `REAL_SCRATCH_BASES = True`.
    """

    ALLOWED = {"1": ["services/api/**"], "2": ["services/web/**"]}
    REAL_SCRATCH_BASES = False

    def setUp(self):
        self._scratch_patch = None
        if not self.REAL_SCRATCH_BASES:
            self._scratch_patch = mock.patch.object(audit, "SCRATCH_BASES", ())
            self._scratch_patch.start()
            self.addCleanup(self.use_real_scratch_bases)
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        assert_not_scratch(self.repo)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / ".claude" / "runs").mkdir(parents=True)

    def use_real_scratch_bases(self):
        """Undo the SCRATCH_BASES patch (idempotent)."""
        if self._scratch_patch is not None:
            self._scratch_patch.stop()
            self._scratch_patch = None

    def write_run(self, **extra):
        write_run_state(self.repo, self.ALLOWED, **extra)

    def remove_run(self):
        (self.repo / ".claude" / "runs" / "feat-x.json").unlink(missing_ok=True)

    def make_dir(self, prefix="audit-", git=False):
        d = Path(tempfile.mkdtemp(prefix=prefix))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        assert_not_scratch(d)
        if git:
            subprocess.run(["git", "init", "-q", str(d)], check=True)
        else:
            assert_no_git_root(d)
        return d

    def eval_at(self, target, actor, cwd=None):
        return audit.evaluate_write(str(target), str(cwd or self.repo), actor, "Write", None)

    def evaluate(self, rel, actor="frontend-react"):
        return audit.evaluate_write(str(self.repo / rel), str(self.repo), actor, "Write", None)


def payload(event, tool=None, *, actor="main", cwd, session="t", tool_input=None, tool_response=None) -> dict:
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
        if isinstance(config, str):
            (self.dir / "agent-audit.json").write_text(config, encoding="utf-8")
        elif config is not None:
            (self.dir / "agent-audit.json").write_text(json.dumps(config), encoding="utf-8")

    def run(self, stdin: "dict | str", cwd) -> CompletedProcess:
        data = stdin if isinstance(stdin, str) else json.dumps(stdin)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(self.home),
            "AGENT_AUDIT_DIR": str(self.metrics_dir),
            "LANG": "C.UTF-8",
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        return subprocess.run(
            [sys.executable, "-I", "-B", str(self.script)],
            input=data, capture_output=True, text=True, cwd=str(cwd), env=env, timeout=self.TIMEOUT,
        )

    def records(self, session: str = "t") -> list[dict]:
        return read_jsonl(self.metrics_dir / f"{session}.jsonl")
