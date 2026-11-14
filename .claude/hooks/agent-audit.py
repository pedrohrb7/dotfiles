#!/usr/bin/env python3
"""Agent audit and enforcement hook.

Wired in settings.json on PreToolUse (decide), PostToolUse, PostToolUseFailure, SubagentStart and
SubagentStop (record). Reads the hook payload (JSON) from stdin.

- Post* and Subagent* events append one line per event to ~/.claude/metrics/<session_id>.jsonl;
  agent-metrics.py turns those lines into a report.
- PreToolUse applies agent-audit.json: in mode "enforce", each flagged category gets its action -
  "block" (deny, with the scope-request protocol as the reason), "ask" (Claude Code asks the user),
  "warn" (allow, with a reminder injected into the agent's context) or "audit" (record only).
  Decisions other than allow/audit are recorded too. In mode "audit" PreToolUse does nothing.
- Fail-open: any error, a missing config or an unknown category lets the action through.

What it classifies (see agent-workflow.md, sections 13 and 14):
- Bash commands, by the classifier module `agent_audit_classify.py` (this file keeps the policy: the config, the
  decision texts, the run state, the watchdog and the metrics). The classifier reads every command through the shell
  parser of `agent_audit_shell.py` (every command position, quote, heredoc and here-string; text that does not
  parse is blocked, and so is every command when either module does not load): tests (narrow/full/load; Lua:
  busted, luarocks test, Neovim headless with plenary or mini.test, and the mise tasks that run them), lint,
  typecheck, docker (read/build/lifecycle, with its global options and the `container` / `compose` forms), git
  (commit/push, also behind `-c alias.*` and `GIT_CONFIG_*`), requests (local/external). The program is found
  behind wrappers and interpreter launchers (`sudo`, `env`, `xargs`, `uv run`, `poetry run`, `conda run`, ...);
  strings that run code (`bash -c`, `eval`, `trap`, here-strings and heredocs a shell or a function reads,
  functions that forward `"$@"`) are classified one level down with the values the text gave its variables. A
  value is known only when every source of the name is in the text: a name with another source, or a program or
  code string made by an expansion the text cannot resolve, is level B (`unclassified_command`, blocked); only a
  name the text never assigns (it comes from the environment) is level A (`dynamic_command`, recorded). Heredoc
  and here-string bodies are data for `cat`/`tee`/`git commit -F -`, for interpreters of other languages, SQL
  clients (unless the query asks to run a command) and, for here-strings, for known filters (`jq`, `grep`, ...);
  `NAME=$(cat <<'EOF' ...)` is data too;
- file writes: inside or outside the active run's allowed_paths (from .claude/runs/<slug>.json;
  outside the repo only inside the session scratchpad (`scratchpad_dir`) or an approved absolute glob),
  docs and backlog files (under the project's docs root: `- docs root:` in the root CLAUDE.md `## Workflow`, default `docs/`), new .md files
  created by agents outside the docs root (not by the main session or docs-writer, not the known doc names, not a markdown path in the
  task's Files), and the project's DESIGN_SYSTEM.md (written only by design-director and the main session);
- browser and screenshot tools.

Commands, file contents and tool outputs are not stored, only a truncated command line and paths.
Any error is swallowed: an audit hook must never break a session.
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import select
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

try:  # the C module: `socket` itself costs about 2 ms of imports on every hook call
    import _socket
except ImportError:  # no fork watchdog then (see `_fork_available`)
    _socket = None

METRICS_DIR = Path(os.environ.get("AGENT_AUDIT_DIR", str(Path.home() / ".claude" / "metrics")))
CONFIG_PATH = Path(__file__).resolve().with_name("agent-audit.json")
MAX_CMD = 300
# Wall-clock limit of the classification (seconds), kept under the 10 s hook timeout. When it expires the
# analysis is abandoned and the call is denied as analysis_timeout. Tests lower it through the env var
# AGENT_AUDIT_ANALYSIS_TIMEOUT (a positive number of seconds; read only by `_analysis_limit`).
ANALYSIS_TIMEOUT_S = 7.0
ANALYSIS_TIMEOUT_ENV = "AGENT_AUDIT_ANALYSIS_TIMEOUT"
# Bounded I/O (spec audit-hook-hardening, section 2): every file the hook reads or writes goes through
# `_read_bounded` / `_append_line`, so no input can be unbounded in size or block on a FIFO.
MAX_CONFIG_BYTES = 65536
MAX_RUN_STATE_BYTES = 262144  # the largest run state seen is 7.2 KB
MAX_RUN_ENTRIES = 256
MAX_RUN_READS = 16
RECORD_FLOOR_S = 0.25  # minimum budget of the recording step
# Fork watchdog (spec audit-hook-hardening, section 5): the analysis runs in a child process that sends the
# parent two JSON lines (the analysis, then the run tags). The parent reads at most this many bytes per line.
MAX_CHILD_MESSAGE = 1 << 20
CHILD_GRACE_S = 1.0  # a child that is still alive this long after the analysis limit ends itself (SIGALRM, default action)
REAP_TRIES = 40  # waitpid(WNOHANG) polls after the SIGKILL, 0.5 ms apart
REAP_STEP_S = 0.0005
WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class AnalysisTimeout(BaseException):
    """Raised by the SIGALRM handler. A BaseException so the `except Exception` blocks cannot swallow it."""


def _load_module(name: str):
    """`<name>.py` next to this file: (module, None) or (None, error name). Loaded by path from checked-hash bytecode
    (PEP 552): the `.pyc` in `__pycache__` is used only when it carries the hash of the source just read, so a
    same-size edit within the same second, or an edited or planted `.pyc`, is never served. On a miss the source is
    compiled and a checked-hash `.pyc` is written (atomically; a write error, as a read-only directory, is ignored).
    The hook runs as a script, which Python never caches. The module is registered in `sys.modules` while it runs, so
    the classifier finds the parser by name. Never raises, not even a BaseException (`SystemExit`,
    `KeyboardInterrupt`) raised by the module at import: a missing or broken module is kept as an error name."""
    try:
        try:  # the import machinery CPython always has loaded at startup: `importlib.util` would add about 0.7 ms
            from _frozen_importlib import module_from_spec
            from _frozen_importlib_external import MAGIC_NUMBER, SourceFileLoader, cache_from_source, spec_from_file_location
        except ImportError:
            from importlib.machinery import SourceFileLoader
            from importlib.util import MAGIC_NUMBER, cache_from_source, module_from_spec, spec_from_file_location
        import _imp
        import marshal

        header = MAGIC_NUMBER + b"\x03\x00\x00\x00"  # flags: hash-based, checked against the source
        raw_magic = int.from_bytes(MAGIC_NUMBER, "little")

        class CheckedHashLoader(SourceFileLoader):
            def get_code(self, fullname):
                path = self.get_filename(fullname)
                source = self.get_data(path)
                digest = _imp.source_hash(raw_magic, source)
                cache = cache_from_source(path)
                try:
                    data = self.get_data(cache)
                    if data[:16] == header + digest:  # marshal reads only bytecode that carries this source's hash
                        code = marshal.loads(memoryview(data)[16:])
                        if hasattr(code, "co_code"):
                            return code
                except Exception:  # no cache, a foreign or corrupt one: compile from the source
                    pass
                code = self.source_to_code(source, path)
                if not sys.dont_write_bytecode:
                    try:
                        self.set_data(cache, header + digest + marshal.dumps(code))
                    except Exception:
                        pass
                return code

        path = CONFIG_PATH.with_name(name + ".py")
        spec = spec_from_file_location(name, path, loader=CheckedHashLoader(name, str(path)))
        module = module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
        return module, None
    except BaseException as exc:  # ImportError, SyntaxError, OSError, SystemExit, KeyboardInterrupt, ...
        return None, type(exc).__name__


def _load_classifier():
    """The parser, then the classifier that reads its trees (spec audit-shell-lexer, section 4.1, review fix part C):
    (classifier module, None) or (None, error name of the first one that failed). A missing, broken or raising module
    leaves no classifier, and `_classifier` then raises: every Bash command is blocked (`classifier_error`) instead of
    being let through; the file-write and visual-tool checks do not use it."""
    for name in ("agent_audit_shell", "agent_audit_classify"):
        module, error = _load_module(name)
        if module is None:
            return None, error
    return module, None


classifier, _CLASSIFIER_ERROR = _load_classifier()  # before any fork, so the analysis child inherits it


def _classifier():
    """The classifier module; a load failure raises here (U4 turns it into `classifier_error`)."""
    if classifier is None:
        raise RuntimeError(f"classifier module: {_CLASSIFIER_ERROR}")
    return classifier


IMPLEMENTERS = {
    "backend-node", "backend-spring", "backend-go", "backend-rust", "backend-python",
    "frontend-react", "mobile-react-native", "lua",
}

# Agents that must never write files.
READ_ONLY_AGENTS = {"ui-verifier", "test-runner", "code-reviewer", "security-reviewer", "Explore", "Plan"}

# Documentation files outside the project's docs root that only docs-writer edits.
DOC_FILES = {"README.md", "CHANGELOG.md", ".env.example", "DEPLOY.md"}

# A project's DESIGN_SYSTEM.md: created by design-director, maintained by the main session following
# the design-system skill. Protected by file name (case-insensitive) anywhere in the repo, so a
# project root that is a subfolder of the git root (monorepo) is covered too.
DESIGN_SYSTEM_NAME = "design_system.md"
DESIGN_SYSTEM_WRITERS = {"design-director", "main"}


DOC_FILE_NAMES = frozenset(n.casefold() for n in DOC_FILES)
# md_outside_docs: known documentation names, exempt by exact file name (any case); their ownership
# is judged by other flags (docs_write_by_implementer; CLAUDE.md has none yet).
MD_DOC_NAMES = frozenset(n for n in DOC_FILE_NAMES if n.endswith(".md")) | {"claude.md"}
# Never md_outside_docs: the main session creates root project files with the user; docs-writer is where needs_docs go.
MD_FREE_ACTORS = frozenset({"main", "docs-writer"})


def file_name(path: str) -> str:
    """Case-folded last component of a path or glob (`\\` read as `/`)."""
    return PurePosixPath(str(path).replace("\\", "/")).name.casefold()


def write_creates(tool: str, response) -> bool | None:
    """Whether the write creates the file: True/False when the payload says so, None when only the
    target's existence can tell (a Write without tool_response, that is PreToolUse)."""
    if isinstance(response, dict) and response.get("type") in ("create", "update"):
        return response["type"] == "create"
    if tool != "Write":
        return False
    return None if response is None else True


def is_design_system(path: str) -> bool:
    return file_name(path) == DESIGN_SYSTEM_NAME

# Paths an implementer may always write, whatever its task's Files say.
ALWAYS_ALLOWED = [
    "**/package-lock.json", "**/pnpm-lock.yaml", "**/yarn.lock", "**/bun.lockb", "**/bun.lock",
    "**/poetry.lock", "**/uv.lock", "**/Cargo.lock", "**/go.sum", "**/Gemfile.lock",
    "**/migrations/**", "**/migration/**", "**/db/migrate/**", "**/alembic/versions/**",
    "**/__snapshots__/**", "**/*.snap",
]

VISUAL_TOOL = re.compile(r"(?i)(screenshot|browser|playwright|chrome|computer|simulator|emulator|snapshot)")


def _read_bounded(path, limit: int, *, truncate: bool = False) -> bytes | None:
    """Read a regular file without ever blocking or reading more than `limit` bytes; None on any problem.

    O_NONBLOCK: opening a FIFO must not wait for a writer. fstat on the fd (after following any symlink)
    must say regular file, so a FIFO, directory or char device is never read, and a sparse 50 MB file is
    rejected by the limit before it is materialized. Over `limit` bytes: None, or the first `limit` bytes
    with `truncate=True`. Never raises."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | _O_CLOEXEC)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                return None
            chunks: list[bytes] = []
            remaining = limit + 1
            while remaining > 0:
                chunk = os.read(fd, remaining)
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
        finally:
            os.close(fd)
        data = b"".join(chunks)
        if len(data) > limit:
            return data[:limit] if truncate else None
        return data
    except Exception:
        return None


def _append_line(path, line: str) -> bool:
    """Append `line` to a regular file (created 0600) with one non-blocking, symlink-refusing open.

    A FIFO, symlink, directory or any error drops the line and returns False; it never blocks or raises."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NONBLOCK | _O_NOFOLLOW | _O_CLOEXEC, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                return False
            data = memoryview(line.encode("utf-8"))
            while data:
                written = os.write(fd, data)
                data = data[written:]
            return True
        finally:
            os.close(fd)
    except Exception:
        return False


def load_config() -> dict:
    try:
        raw = _read_bounded(CONFIG_PATH, MAX_CONFIG_BYTES)
        if raw is None:
            return {"mode": "audit"}
        return json.loads(raw)
    except Exception:
        return {"mode": "audit"}


DEFAULT_DOCS_ROOT = "docs/"
WORKFLOW_HEADING = re.compile(r"^##[ \t]+workflow[ \t]*$", re.I)
SECTION_END = re.compile(r"^#{1,2}[ \t]")
DOCS_ROOT_LINE = re.compile(r"^[ \t]*[-*][ \t]+docs root:[ \t]*(.*?)[ \t]*$", re.I)
DRIVE_LETTER = re.compile(r"^[A-Za-z]:")
CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def normalize_docs_root(raw: object) -> str | None:
    """Normalize a declared docs root to `a/b/`, or None when invalid. Never raises.

    Spec skills-docs-root, section 2: strip spaces and one pair of backticks, `\\` -> `/`, drop empty and
    `.` segments, end with one `/`. Invalid: empty after that, starts with `/` or `~`, a drive letter,
    a `..` segment, a control character, or not a string."""
    try:
        if not isinstance(raw, str):
            return None
        value = raw.strip()
        if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
            value = value[1:-1].strip()
        value = value.replace("\\", "/")
        if value.startswith(("/", "~")) or DRIVE_LETTER.match(value) or CONTROL_CHARS.search(value):
            return None
        segments = [s for s in value.split("/") if s not in ("", ".")]
        if not segments or ".." in segments:
            return None
        return "/".join(segments) + "/"
    except Exception:
        return None


def project_docs_root(root: Path) -> str:
    """The docs root declared by a git root, as `a/b/`; `docs/` when none or invalid.

    Reads at most 256 KiB of `<root>/CLAUDE.md`: the first `- docs root: <path>/` line inside its
    `## Workflow` section decides (the section ends at the next `#` or `##` heading). Same rules as the
    project-docs skill (Layouts and path resolution, Docs root): R1 one declaration, default `docs/`;
    R3 an invalid value falls back to `docs/` (a hook never stops a session; skills ask instead);
    R5 only that section of that file counts; R10 a missing, unreadable, directory, binary or huge file
    is the same as no declaration, and nothing is raised."""
    try:
        raw = _read_bounded(Path(root) / "CLAUDE.md", 262144, truncate=True)
        if raw is None:
            return DEFAULT_DOCS_ROOT
        text = raw.decode("utf-8", errors="replace")
        in_section = False
        for line in text.splitlines():
            if in_section:
                if SECTION_END.match(line):
                    in_section = False
                    continue
                m = DOCS_ROOT_LINE.match(line)
                if m:
                    return normalize_docs_root(m.group(1)) or DEFAULT_DOCS_ROOT
            elif WORKFLOW_HEADING.match(line.strip()):
                in_section = True
        return DEFAULT_DOCS_ROOT
    except Exception:
        return DEFAULT_DOCS_ROOT


class GitRootUnknown(Exception):
    """git timed out or failed for a reason other than "not a repository": the root cannot be told."""


def git_toplevel(start: Path) -> Path | None:
    """The git root of `start`; None when it is not in a repository; GitRootUnknown when git timed out, could not
    run or failed in any other way (the caller decides what uncertainty means)."""
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=2, env={**os.environ, "LC_ALL": "C"},
        )
    except Exception as exc:  # TimeoutExpired, OSError (git missing, no memory), undecodable output
        raise GitRootUnknown(type(exc).__name__) from exc
    if out.returncode == 0:
        if not out.stdout.strip():
            raise GitRootUnknown("empty")
        return Path(out.stdout.strip())
    if out.returncode == 128 and "not a git repository" in out.stderr:
        return None
    raise GitRootUnknown(f"rc{out.returncode}")


def git_root(start: Path) -> Path | None:
    """`git_toplevel` where "cannot tell" reads as no repository (run tags, where nothing is judged)."""
    try:
        return git_toplevel(start)
    except GitRootUnknown:
        return None


def active_run(root: Path) -> dict | None:
    """Newest run state with phase != "done" (spec audit-hook-hardening, B2): at most MAX_RUN_ENTRIES directory
    entries listed (of any kind), regular `*.json` files only, newest first, at most MAX_RUN_READS read, each up to MAX_RUN_STATE_BYTES;
    invalid, oversized or non-object states are skipped. With MAX_RUN_READS newer finished states, an older
    active run is not seen (the active run is the file updated last during an /implement)."""
    entries: list[tuple[float, str]] = []
    seen = 0
    try:
        with os.scandir(root / ".claude" / "runs") as it:
            for entry in it:
                seen += 1  # every entry counts against the cap, stray files and directories included
                if seen > MAX_RUN_ENTRIES:
                    break
                if not entry.name.endswith(".json"):
                    continue
                try:
                    st = entry.stat()  # follows symlinks; a FIFO is only stat'ed, never opened here
                except OSError:
                    continue
                if not stat.S_ISREG(st.st_mode):
                    continue
                entries.append((st.st_mtime, entry.name))
    except OSError:
        return None
    entries.sort(reverse=True)
    for _, name in entries[:MAX_RUN_READS]:
        raw = _read_bounded(root / ".claude" / "runs" / name, MAX_RUN_STATE_BYTES)
        if raw is None:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, dict) and data.get("phase") != "done":
            data["_slug"] = name[: -len(".json")]
            return data
    return None


def run_task_keys(run: dict) -> list[str]:
    """Task ids (as strings) whose scope applies now: the valid `running_tasks` entries, then `current_task`.

    A stale or malformed `running_tasks` can only widen the scope, never replace `current_task`.
    An id is valid when it is an int or a non-empty string (not a bool).
    """
    candidates = list(run.get("running_tasks") or []) if isinstance(run.get("running_tasks"), (list, tuple)) else []
    candidates.append(run.get("current_task"))
    keys = [
        str(t).strip() for t in candidates
        if isinstance(t, (int, str)) and not isinstance(t, bool) and str(t).strip()
    ]
    return list(dict.fromkeys(keys))


def matches(rel: str, patterns: list[str]) -> bool:
    p = PurePosixPath(rel)
    for pat in patterns:
        pat = pat.strip().strip("`")
        if not pat:
            continue
        try:
            if p.full_match(pat) or p.full_match(pat.rstrip("/") + "/**"):
                return True
        except Exception:
            if rel == pat or rel.startswith(pat.rstrip("*").rstrip("/") + "/"):
                return True
    return False


def session_scratchpad(raw: object) -> Path | None:
    """The session scratchpad from the payload's `scratchpad_dir`, normalized, or None when unusable.

    Not a non-empty absolute `str` without NUL, or the filesystem root: None. Never raises. No realpath and no
    existence check: the value comes from Claude Code (an agent cannot change the payload) and the directory
    may not exist yet."""
    try:
        if not isinstance(raw, str) or not raw or "\0" in raw or not os.path.isabs(raw):
            return None
        p = Path(os.path.normpath(raw))
        return None if p == Path(p.anchor) else p
    except Exception:
        return None


def is_scratch(target: Path, scratchpad: Path | None) -> bool:
    """True when `target` is strictly inside the session scratchpad (B1).

    Compared by path component, so `<sp>x/` and `<sp>-other/` do not match, and other sessions' scratchpads and
    other `claude-*` directories are not scratch (B2). The scratchpad is never resolved (B5): if it is swapped
    for a symlink, the resolved target lands elsewhere, does not match, and is flagged."""
    if scratchpad is None:
        return False
    try:
        return bool(target.relative_to(scratchpad).parts)
    except ValueError:
        return False


def nearest_existing(path: Path) -> Path:
    while not path.exists() and path != path.parent:
        path = path.parent
    return path


def _under(target: Path, root: Path) -> str | None:
    """`target` relative to `root` (tried resolved, then as given), or None when it is outside."""
    for r in (root.resolve(), root):
        try:
            return str(target.relative_to(r))
        except ValueError:
            pass
    return None


def _creates(form: Path, created: bool | None) -> bool:
    """Whether the write creates `form`: the payload's verdict, else (None, PreToolUse) whether it is missing."""
    if created is not None:
        return created
    try:
        return not form.exists()
    except Exception:
        return True  # cannot tell: judge as a new file


def _assess_root(root: Path, forms: list[Path], actor: str, created: bool | None, roots: list[str],
                 scratch: Path | None = None) -> tuple[list[str], dict]:
    """Judge the target (each path form: resolved, and lexical when it has `..`) against one git root and its run.
    Returns the union of the flags (stricter wins) and the record fields of the first flagged form, else the first."""
    run = active_run(root)
    flags: list[str] = []
    rec: dict | None = None
    scoped_run = bool(run) and (actor in IMPLEMENTERS or actor in {"quality-fixer", "test-writer"})
    allowed: list[str] = []
    keys: list[str] = []
    if run:
        keys = run_task_keys(run)
    if run and scoped_run:
        by_task = run.get("allowed_paths") or {}
        allowed = [p for k in keys for p in by_task.get(k, [])]
        allowed += [
            s.get("target", "") for s in run.get("approved_scope", [])
            if str(s.get("task")) in keys and s.get("decision", "approved") == "approved"
            and not is_design_system(s.get("target", ""))  # never enters allowed paths
        ]
    # a markdown path the task declares (Files or approved scope); a broad glob (services/api/**) does not count
    declared_md = [p for p in allowed if file_name(str(p).strip().strip("`")).endswith(".md")]
    for form in forms:
        rel = _under(form, root)
        inside = rel is not None
        if not inside:
            rel = str(form)
            area = "outside"
        else:
            area = "docs" if rel.startswith(tuple(roots)) else "run-state" if rel.startswith(".claude/runs/") else "code"
        found: list[str] = []
        is_ds = is_design_system(rel)
        name = file_name(rel)
        if (inside and actor not in MD_FREE_ACTORS and area != "docs" and name.endswith(".md")
                and name not in MD_DOC_NAMES
                and not (is_ds and actor == "design-director")
                and not (declared_md and matches(rel, declared_md))
                and _creates(form, created)):
            found.append("md_outside_docs")
        if inside and actor in IMPLEMENTERS and (area == "docs" or name in DOC_FILE_NAMES):
            found.append("docs_write_by_implementer")
        if inside and rel.startswith(tuple(r + "backlog/" for r in roots)) and actor not in {"backlog-keeper", "unknown"}:
            found.append("backlog_write_by_other")
        cur: dict = {"rel": rel, "area": area, "in_run": bool(run)}
        if run:
            cur["run"] = run.get("_slug")
            cur["task"] = ",".join(keys)
            if scoped_run:
                if inside:
                    in_scope = matches(rel, allowed + ALWAYS_ALLOWED)
                else:  # ALWAYS_ALLOWED are repo conventions; outside, only approved ABSOLUTE globs
                    # (matched literally after ~ expansion, never realpath'd: a planted symlink must not widen a
                    # glob; relative ones never match) or the session scratchpad of the payload
                    absolute = [os.path.expanduser(a.strip().strip("`")) for a in allowed]
                    in_scratch = is_scratch(form, scratch)
                    cur["scratch"] = "unavailable" if scratch is None else "match" if in_scratch else "no-match"
                    in_scope = in_scratch or matches(rel, [a for a in absolute if a.startswith("/")])
                cur["in_scope"] = in_scope
                if not in_scope:
                    found.append("out_of_scope_write")
        flags += found
        if rec is None or (found and not rec.get("_flagged")):
            rec = {**cur, "_flagged": bool(found)}
    rec = rec or {}
    rec.pop("_flagged", None)
    return flags, rec


def evaluate_write(path_str: str, cwd: str, actor: str, tool: str, response, roots: list[str] | None = None,
                   scratchpad: object = None, failed: bool = False) -> dict:
    """Classify a write. `failed` (a PostToolUseFailure event): the write created nothing, so
    `md_outside_docs` never fires; the other flags are unchanged.

    Docs area = `roots` when given, else the governing root's declared docs root (`project_docs_root`).
    `md_outside_docs` is for agents creating a stray .md (see `_assess_root`).
    Actor-only flags (read-only agent, design-director, DESIGN_SYSTEM.md by file name) are computed first,
    before any filesystem call, so any error below degrades to area "outside" with just those flags.
    The target is `~`-expanded and resolved (symlinks, `..`); with a `..` component the lexical
    normpath form is judged too and the stricter result wins. The governing root is the git root of
    the session cwd (where the run lives); with no root there, the target's own. When the target's own
    root is a different repo nested in the cwd root (submodule), both are judged, flags are unioned and
    the record carries the nested (target) root's rel, area and run, unless only the other root flagged out_of_scope_write. A target outside every root has
    rel = its absolute path and area "outside": area flags do not apply, and fixed-scope actors with a
    run need an approved absolute glob (matched literally after ~ expansion, never realpath'd) or a path inside the session scratchpad (`scratchpad_dir` of the payload)."""
    out: dict = {"path": path_str}
    scoped = actor in IMPLEMENTERS or actor in {"quality-fixer", "test-writer"}

    def actor_flags(ds_names: list[bool]) -> list[str]:
        """`ds_names`: is each known name of the target (raw, resolved) a DESIGN_SYSTEM.md."""
        found = []
        if any(ds_names) and actor not in DESIGN_SYSTEM_WRITERS:
            found.append("design_system_write_by_other")
        if actor == "design-director" and not all(ds_names):
            found.append("design_director_write_outside")
        if actor in READ_ONLY_AGENTS:
            found.append("write_by_readonly_agent")
        return found

    flags = actor_flags([is_design_system(path_str)])
    try:
        sp = session_scratchpad(scratchpad)
        path = Path(os.path.expanduser(path_str))
        if not path.is_absolute():
            path = Path(cwd or ".") / path
        resolved = path.resolve()
        flags = actor_flags([is_design_system(path_str), is_design_system(str(resolved))])
        forms = [resolved]
        if ".." in path.parts:
            lexical = Path(os.path.normpath(path))
            if lexical != resolved:
                forms.append(lexical)
        cwd_root = git_toplevel(Path(cwd)) if cwd and Path(cwd).is_dir() else None
        target_root = git_toplevel(nearest_existing(resolved.parent))
        judged = [cwd_root] if cwd_root else [target_root] if target_root else []
        if cwd_root and target_root and target_root != cwd_root and _under(target_root, cwd_root) is not None:
            judged.append(target_root)  # nested repo / submodule: judged by its own root and run too
        created = False if failed else write_creates(tool, response)  # a failed write creates nothing
        rec = {"rel": str(resolved), "area": "outside", "in_run": False}
        rec_oos = False
        for root in judged:
            found, cur = _assess_root(root, forms, actor, created, roots or [project_docs_root(root)], scratch=sp)
            flags += found
            oos = "out_of_scope_write" in found
            if not (rec_oos and not oos):  # the nested root wins, unless an earlier root is the one that flagged
                rec, rec_oos = cur, oos
        out.update(rec)
    except Exception as exc:  # fail closed: unresolvable path -> outside, actor-only flags (+ out of scope in a run)
        out.update({"rel": path_str, "area": "outside", "in_run": False})
        unknown_root = isinstance(exc, GitRootUnknown)
        if unknown_root:  # git could not tell the root: nothing was judged, which is never an allow
            out["uncertainty"] = ["git_root_unknown"]
        if scoped:
            try:
                if unknown_root:
                    in_run = True  # the run lives under the git root, which cannot be found: assume one is active
                else:
                    root = git_root(Path(cwd)) if cwd else None
                    in_run = bool(active_run(root)) if root else False
            except Exception:
                in_run = True  # cannot tell: assume a run is active
            if in_run:
                flags.append("out_of_scope_write")
                out["in_run"] = True
    out["flags"] = list(dict.fromkeys(flags))
    return out


SEVERITY = {"audit": 0, "warn": 1, "ask": 2, "block": 3}

WHY = {
    "docker_lifecycle": "agents never start, stop, restart, recreate or exec into services or containers; the user owns the local environment",
    "write_by_readonly_agent": "this agent is read-only and must not write files",
    "visual_tool": "browser and screenshot tools are used only by ui-verifier, on an explicit request from the user",
    "git_commit": "commits need the user's explicit authorization in the current conversation, and never carry attribution lines",
    "git_push": "pushes need the user's explicit authorization in the current conversation",
    "out_of_scope_write": "this path is outside the task's allowed_paths and its approved scope",
    "suite_by_non_runner": "whole suites run only through test-runner; run only the tests of the files you touched",
    "md_outside_docs": "agents do not create new .md files (notes, summaries, reports) outside the project's docs root (docs/, or the \"- docs root:\" line of the root CLAUDE.md ## Workflow); documentation needs go to needs_docs, and a markdown file the task really needs must be in its Files or come through a scope_requests entry",
    "docs_write_by_implementer": "documentation files are written only by docs-writer; list the need in needs_docs",
    "backlog_write_by_other": "<docs root>/backlog/ (docs/backlog/ unless the root CLAUDE.md declares a docs root) is written only by backlog-keeper; report it in out_of_scope_issues",
    "design_director_write_outside": "design-director writes only the project's DESIGN_SYSTEM.md; for anything else finish with result: blocked and a scope_requests entry saying what and why, the caller will ask the user",
    "design_system_write_by_other": "a project's DESIGN_SYSTEM.md (any directory) is created only by design-director and maintained only by the main session following the design-system skill; propose the value (token, light and dark, usage) in scope_requests instead",
    "docker_build": "images are built only when the task changes a Dockerfile or its build context",
    "external_request": "requests go only to local hosts (localhost, 127.0.0.1, compose service names)",
    "command_too_long": "a Bash command over 16384 characters is not analyzed and is never run; write large content (files, scripts, heredoc bodies) with the Write tool and keep commands short",
    "analysis_timeout": "this tool call was too complex to analyze in time, so it is blocked and never run; simplify or split the command, and write large content (files, scripts, heredoc bodies) with the Write tool",
    "unclassified_command": "the hook could not classify this command with certainty (shell syntax it does not support or that does not parse, shell code built at run time, too many possible readings, nesting too deep, or an analysis error), so it is blocked and never run",
    "parse_uncertain": "the hook could only partly resolve this command (several plausible readings, a program name taken from a variable, an unclean heredoc prefix, or a blocked program outside a command position); every reading was classified and the strictest one applies",
}


def what_to_do(actor: str, category: str) -> str:
    if category == "docker_lifecycle":
        return "Put the command in manual_checks for the user instead."
    if category == "command_too_long":
        return "Write the content to a file with the Write tool and run a short command that uses the file."
    if category == "analysis_timeout":
        return ("Simplify the command or split it into several short commands, and write large content to a file "
                "with the Write tool instead of putting it in the command.")
    if category == "unclassified_command":
        return ("Run each program as its own plain command: no stacked wrappers, no shell code built from variables "
                "or substitutions (bash -c \"$X\", eval), no nested shells, and only common POSIX/bash syntax; "
                "write scripts and large content to a file with the Write tool and run the file.")
    if category == "visual_tool":
        return "List the states to check in manual_checks; the user can ask for a ui-verifier check."
    if actor == "main":
        return "Explain to the user why this is needed and ask for authorization before trying again."
    return (
        "Do not retry this action or a variation of it. If the task really needs it, stop here and finish "
        "with result: blocked and a scope_requests entry saying why; the caller will ask the user."
    )


def decide(record: dict, config: dict) -> dict | None:
    """Return the PreToolUse hook output for the strictest flagged category, or None to allow silently."""
    actions = config.get("categories") or {}
    worst, worst_cat = "audit", None
    for flag in record.get("flags") or []:
        action = actions.get(flag, "audit")
        if SEVERITY.get(action, 0) > SEVERITY[worst]:
            worst, worst_cat = action, flag
    if worst_cat is None:
        return None
    record["decision"], record["decision_category"] = worst, worst_cat
    actor = record.get("actor", "main")
    reason = f"Agent workflow ({worst_cat}): {WHY.get(worst_cat, worst_cat)}."
    out: dict = {"hookEventName": "PreToolUse"}
    if worst == "block":
        out["permissionDecision"] = "deny"
        out["permissionDecisionReason"] = f"{reason} {what_to_do(actor, worst_cat)}"
    elif worst == "ask":
        out["permissionDecision"] = "ask"
        out["permissionDecisionReason"] = reason
    else:  # warn: allow, remind the agent
        out["additionalContext"] = (
            f"Reminder from the agent workflow ({worst_cat}): {WHY.get(worst_cat, worst_cat)}. "
            "This action was allowed but recorded as a deviation; follow the scope-request protocol "
            "instead of repeating it."
        )
    return {"hookSpecificOutput": out}


def _analysis_limit() -> float:
    """Wall-clock limit of the classification: ANALYSIS_TIMEOUT_S, or the test-only env override."""
    try:
        value = float(os.environ.get(ANALYSIS_TIMEOUT_ENV, ""))
        if math.isfinite(value) and value > 0:
            return min(value, ANALYSIS_TIMEOUT_S)  # the override can only lower the limit
    except ValueError:
        pass
    return ANALYSIS_TIMEOUT_S


def _on_alarm(signum, frame) -> None:
    raise AnalysisTimeout()


def _arm_analysis_timer(seconds: float | None = None):
    """Start the wall-clock limit (SIGALRM, one shot); returns the previous handler, or None when the platform
    has no setitimer or the hook does not run in the main thread (then there is no guard).
    A timer that cannot be armed raises AnalysisTimeout: the caller treats it as a timeout (PreToolUse denies)."""
    if not hasattr(signal, "setitimer"):
        return None
    try:
        previous = signal.signal(signal.SIGALRM, _on_alarm)
    except ValueError:  # not the main thread
        return None
    try:
        signal.setitimer(signal.ITIMER_REAL, _analysis_limit() if seconds is None else seconds)
    except Exception:  # OverflowError, OSError, ...: never continue unguarded
        try:
            signal.signal(signal.SIGALRM, previous if previous is not None else signal.SIG_DFL)
        except Exception:
            pass
        raise AnalysisTimeout()
    return previous if previous is not None else signal.SIG_DFL


def _disarm_analysis_timer(previous) -> None:
    if previous is None:
        return
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, previous)


def main() -> None:
    started = time.monotonic()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    config = load_config()
    mode = config.get("mode", "audit")
    if mode == "off":
        return

    event = payload.get("hook_event_name", "")
    if event == "PreToolUse" and mode != "enforce":
        return
    actor = payload.get("agent_type") or ("subagent" if payload.get("agent_id") else "main")
    record: dict = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "session": payload.get("session_id"),
        "event": event,
        "actor": actor,
        "agent_id": payload.get("agent_id"),
        "cwd": payload.get("cwd"),
    }

    child: _Child | None = None
    try:  # the finally kills and reaps the analysis child on every path (return, decision, exception)
        if event in {"SubagentStart", "SubagentStop"}:
            record["agent_type"] = payload.get("agent_type")
        else:
            tool = payload.get("tool_name", "")
            if not _audited_tool(tool):
                return  # reads, searches and other tools are not audited
            record["tool"] = tool
            if event != "PreToolUse":
                record["failed"] = event == "PostToolUseFailure"
            # The analysis runs in a forked child under a hard deadline (W1-W6); without fork, in this process
            # under the SIGALRM guard (W5). Either way a classifier defect or overrun is never an allow.
            if _fork_available():
                child = _start_child(payload, event, actor)
            if child is not None:
                outcome = child.analysis(started + _analysis_limit())
            else:
                outcome = _analyze_in_process(payload, event, actor)
            _apply_outcome(record, payload, outcome)

        if event == "PreToolUse":
            decision = decide(record, config)
            if decision is None:
                return  # allowed silently; PostToolUse records the action itself
            print(json.dumps(decision))
            sys.stdout.flush()  # the decision is out before any slow recording step can delay or lose it
            if record.get("decision") == "warn":
                return  # the action still runs and PostToolUse records it with its flags

        # The run tagging runs under what is left of the analysis budget; when it overruns, the record is still
        # written (R1), untagged: in_run false and run_tags "timeout". The write has its own short guard.
        if "in_run" not in record:  # tag commands and lifecycle events with the active /implement run
            remaining = max(RECORD_FLOOR_S, _analysis_limit() - (time.monotonic() - started))
            tags: dict | None = None
            if child is not None:
                tags = child.tags(time.monotonic() + remaining, go=event == "PreToolUse")
            else:
                box: dict = {}
                if _run_guarded(remaining, lambda: box.update(_run_tags(payload))):
                    tags = box
            if tags is not None:
                record.update(tags)
            else:
                record["in_run"] = False
                record["run_tags"] = "timeout"
        _run_guarded(RECORD_FLOOR_S, lambda: _write_record(record))  # a lost record never affects the decision
    finally:
        if child is not None:
            child.close()


def _audited_tool(tool) -> bool:
    """Bash, the file-writing tools and the browser/screenshot tools are analyzed; everything else is not."""
    return isinstance(tool, str) and (tool == "Bash" or tool in WRITE_TOOLS or bool(VISUAL_TOOL.search(tool)))


def _analysis(payload: dict, event: str, actor: str) -> dict:
    """The audited-tool analysis, as record fields: `categories`, `flags`, `uncertainty` and, for Bash, `cmd`,
    plus the fields of `evaluate_write` for a file write. JSON-serializable; may raise (U4 handles it)."""
    tool = payload.get("tool_name", "")
    tinput = payload.get("tool_input") or {}
    out: dict = {}
    flags: list[str] = []
    uncertainty: list[str] = []
    if tool == "Bash":
        cmd = tinput.get("command", "")
        out["cmd"] = cmd[:MAX_CMD]
        out["categories"], flags, uncertainty = _classifier().analyze_command(cmd)
        suites = {"test-full", "test-package", "test-load"} & set(out["categories"])
        if suites and actor in IMPLEMENTERS | {"quality-fixer", "test-writer"}:
            flags.append("suite_by_non_runner")
    elif tool in WRITE_TOOLS:
        path = tinput.get("file_path") or tinput.get("notebook_path") or ""
        out["categories"] = ["write"]
        out.update(evaluate_write(path, payload.get("cwd", ""), actor, tool,
                                  payload.get("tool_response"),
                                  scratchpad=payload.get("scratchpad_dir"),
                                  failed=event == "PostToolUseFailure"))
        flags = out.pop("flags", [])
        uncertainty = out.pop("uncertainty", [])  # git_root_unknown
    else:
        out["categories"] = ["visual"]
        flags = [] if actor == "ui-verifier" else ["visual_tool"]
    out["flags"] = list(flags)
    out["uncertainty"] = list(uncertainty)
    return out


def _analyze_in_process(payload: dict, event: str, actor: str) -> tuple[str, object]:
    """The analysis in this process under the SIGALRM guard: ("ok", fields), ("error", exception name) or
    ("timeout", None). The limit also fires inside the arm and disarm calls (the timer is one shot)."""
    box: list = []

    def run() -> None:
        try:
            box.append(("ok", _analysis(payload, event, actor)))
        except Exception as exc:  # a defect of the classifier is never an allow (U4): blocked, with the error name
            box.append(("error", type(exc).__name__))

    if not _run_guarded(_analysis_limit(), run) or not box:
        return ("timeout", None)
    return box[0]


def _apply_outcome(record: dict, payload: dict, outcome: tuple[str, object]) -> None:
    """Fold an analysis outcome ("ok", "error", "timeout" or "crash") into the record: categories, flags and
    the uncertainty reasons. Everything but "ok" is fail closed (analysis_timeout or unclassified_command)."""
    kind, data = outcome
    flags: list[str] = []
    uncertainty: list[str] = []
    if kind == "ok" and isinstance(data, dict):
        fields = dict(data)
        flags = list(fields.pop("flags", []))
        uncertainty = list(fields.pop("uncertainty", []))
        record.update(fields)
    else:
        if "cmd" not in record and payload.get("tool_name") == "Bash":
            tinput = payload.get("tool_input")
            record["cmd"] = str(tinput.get("command", "") if isinstance(tinput, dict) else "")[:MAX_CMD]
        if kind == "timeout":  # too complex to analyze in time: PreToolUse denies it, PostToolUse records it
            record["categories"] = ["other"]
            flags = ["analysis_timeout"]
        else:  # "error" (U4, W3) or "crash" (W2): level B, blocked as unclassified_command
            record["categories"] = ["unclassified"]
            flags = ["unclassified_command"]
            if kind == "error":
                record["error"] = str(data)[:100]
                uncertainty = ["classifier_error"]
            else:
                uncertainty = ["analysis_crash"]
    if uncertainty:
        record["uncertainty"] = sorted(set(uncertainty))
        flags = [*flags, "parse_uncertain"]
    record["flags"] = sorted(set(flags))


def _fork_available() -> bool:
    return hasattr(os, "fork") and _socket is not None


class _ChildTimeout(Exception):
    """The deadline passed before the child's next line."""


class _ChildCrash(Exception):
    """The child ended without a valid line (EOF, an oversized line)."""


class _Child:
    """The parent's end of the analysis child: a socket carrying newline-terminated JSON lines, read with a
    hard deadline and a size cap. `close` always kills and reaps the child."""

    def __init__(self, pid: int, sock) -> None:
        self.pid = pid
        self.sock = sock
        self.buf = b""
        self.alive = True
        self.closed = False

    def _line(self, deadline: float) -> bytes:
        while True:
            end = self.buf.find(b"\n")
            if end >= 0:
                line, self.buf = self.buf[:end], self.buf[end + 1:]
                if len(line) > MAX_CHILD_MESSAGE:
                    raise _ChildCrash()
                return line
            if len(self.buf) > MAX_CHILD_MESSAGE:
                raise _ChildCrash()
            left = deadline - time.monotonic()
            if left <= 0:
                raise _ChildTimeout()
            ready, _, _ = select.select([self.sock], [], [], left)
            if not ready:
                raise _ChildTimeout()
            chunk = self.sock.recv(65536)
            if not chunk:
                raise _ChildCrash()
            self.buf += chunk

    def analysis(self, deadline: float) -> tuple[str, object]:
        """Line 1: ("ok", fields), ("error", name), ("timeout", None) or ("crash", None)."""
        try:
            message = json.loads(self._line(deadline))
        except _ChildTimeout:
            self.alive = False
            return ("timeout", None)
        except Exception:  # _ChildCrash, OSError, or a line that is not JSON
            self.alive = False
            return ("crash", None)
        if isinstance(message, dict):
            if isinstance(message.get("analysis"), dict):
                return ("ok", message["analysis"])
            if isinstance(message.get("error"), str):
                return ("error", message["error"])
        self.alive = False
        return ("crash", None)

    def tags(self, deadline: float, go: bool) -> dict | None:
        """Line 2, the run tags (None when the child is gone, late or sent something else). `go` releases a child
        that waits for the parent to say the record is needed (PreToolUse)."""
        if not self.alive:
            return None
        try:
            if go:
                self.sock.sendall(b"g")
            message = json.loads(self._line(deadline))
        except Exception:  # timeout, crash, closed socket, invalid JSON
            self.alive = False
            return None
        tags = message.get("tags") if isinstance(message, dict) else None
        if not isinstance(tags, dict) or not isinstance(tags.get("in_run"), bool):
            return None
        return {key: tags[key] for key in ("in_run", "run", "task") if key in tags}

    def close(self) -> None:
        """SIGKILL, then a short bounded reap; a child stuck in state D is collected by init when this exits."""
        if self.closed:
            return
        self.closed = True
        try:
            os.killpg(self.pid, signal.SIGKILL)  # the child and its git grandchildren (it leads its own group)
        except OSError:  # no such group (the child never became its leader) or already gone
            try:
                os.kill(self.pid, signal.SIGKILL)
            except OSError:
                pass
        try:
            self.sock.close()
        except Exception:
            pass
        for _ in range(REAP_TRIES):
            try:
                done, _status = os.waitpid(self.pid, os.WNOHANG)
            except OSError:
                return
            if done:
                return
            time.sleep(REAP_STEP_S)


def _start_child(payload: dict, event: str, actor: str) -> _Child | None:
    """Fork the analysis child; None when the pipe or the fork fails (the caller falls back to the SIGALRM path)."""
    try:
        parent_end, child_end = _socket.socketpair()
    except Exception:
        return None
    try:
        sys.stdout.flush()  # nothing buffered may be written a second time from the child
        sys.stderr.flush()
    except Exception:
        pass
    try:
        pid = os.fork()
    except Exception:  # OSError: out of processes or memory
        parent_end.close()
        child_end.close()
        return None
    try:  # the child leads its own process group, so `_Child.close` reaches its git grandchildren too
        os.setpgid(pid, pid)
    except OSError:  # the child did it first, or is already gone
        pass
    if pid == 0:  # the child never returns to the caller of main()
        try:
            parent_end.close()
            _run_child(payload, event, actor, child_end)
        except BaseException:
            pass
        finally:
            os._exit(0)
    child_end.close()
    return _Child(pid, parent_end)


def _kill_own_group(_signum, _frame) -> None:
    """Child self-destruct (SIGALRM): SIGKILL to the child's own process group, which it leads."""
    try:
        if os.getpgrp() == os.getpid():  # never the hook's own group, should the setpgid have failed
            os.killpg(0, signal.SIGKILL)
    except Exception:
        pass
    os._exit(0)  # not a group leader (or the kill failed): end the child alone


def _run_child(payload: dict, event: str, actor: str, sock) -> None:
    """Child body (W1-W6): only the analysis and the run tags; never prints, never touches the metrics."""
    try:  # stdout and stderr go nowhere (W6): the parent alone writes the decision
        sys.stdout = sys.stderr = io.StringIO()
        dead, nowhere = _socket.socketpair()
        dead.close()  # a write to the other end fails at once instead of reaching the hook's pipes
        os.dup2(nowhere.fileno(), 1)
        os.dup2(nowhere.fileno(), 2)
    except Exception:
        pass
    try:  # if the parent died before killing this child, it ends its whole group (itself and its git processes)
        signal.signal(signal.SIGALRM, _kill_own_group)
        signal.setitimer(signal.ITIMER_REAL, _analysis_limit() + CHILD_GRACE_S)
    except Exception:
        pass
    fields: dict | None
    try:
        fields = _analysis(payload, event, actor)
        line = json.dumps({"analysis": fields})
    except Exception as exc:  # W3: the parent applies U4
        fields = None
        line = json.dumps({"error": type(exc).__name__})
    sock.sendall(line.encode("utf-8") + b"\n")
    if fields is not None and "in_run" in fields:
        return  # the write analysis already tagged the record
    if event == "PreToolUse" and sock.recv(1) != b"g":
        return  # no decision to record: the parent does not need the tags
    sock.sendall(json.dumps({"tags": _run_tags(payload)}).encode("utf-8") + b"\n")


def _run_guarded(seconds: float, fn) -> bool:
    """Run `fn` under the SIGALRM wall-clock limit; False when it timed out (the limit also fires inside the
    arm and disarm calls, the timer is one shot)."""
    previous = None
    try:
        try:
            previous = _arm_analysis_timer(seconds)
            fn()
        finally:
            _disarm_analysis_timer(previous)
    except AnalysisTimeout:
        return False
    return True


def _run_tags(payload: dict) -> dict:
    """Tags of the active /implement run for a record: `in_run`, and `run` and `task` when there is one."""
    root = git_root(Path(payload.get("cwd") or "."))
    run = active_run(root) if root else None
    tags: dict = {"in_run": bool(run)}
    if run:
        tags["run"] = run.get("_slug")
        tags["task"] = ",".join(run_task_keys(run))
    return tags


def _write_record(record: dict) -> None:
    session = record.get("session") or "unknown"
    METRICS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    _append_line(METRICS_DIR / f"{session}.jsonl", json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except (Exception, AnalysisTimeout):  # never a stack trace, always exit 0
        pass
    # Leave without the interpreter teardown: after the analysis fork every heap page is copy-on-write, and
    # tearing the objects down costs about 5 ms of page faults (more than the fork itself). All output is flushed.
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(0)
