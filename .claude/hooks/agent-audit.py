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
- Bash commands: tests (narrow/full/load; Lua: busted, luarocks test, Neovim headless with plenary or
  mini.test, and the mise tasks that run them), lint, typecheck, docker (read/build/lifecycle),
  git (commit/push), requests (local/external);
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
import functools
import select
import shlex
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath
from typing import NamedTuple

try:  # the C module: `socket` itself costs about 2 ms of imports on every hook call
    import _socket
except ImportError:  # no fork watchdog then (see `_fork_available`)
    _socket = None

METRICS_DIR = Path(os.environ.get("AGENT_AUDIT_DIR", str(Path.home() / ".claude" / "metrics")))
CONFIG_PATH = Path(__file__).resolve().with_name("agent-audit.json")
MAX_CMD = 300
# A Bash command longer than this is never fed to the regex classifier: it is denied (command_too_long). The cap
# shrinks the input but does not bound the time (a quadratic path still costs seconds at 8-11 KB); the wall-clock
# guard below is the structural bound, because a hook timeout (settings.json: 10 s) fails open.
MAX_COMMAND_LEN = 16384
# Wall-clock limit of the classification (seconds), kept under the 10 s hook timeout. When it expires the
# analysis is abandoned and the call is denied as analysis_timeout. Tests lower it through the env var
# AGENT_AUDIT_ANALYSIS_TIMEOUT (a positive number of seconds; read only by `_analysis_limit`).
ANALYSIS_TIMEOUT_S = 7.0
ANALYSIS_TIMEOUT_ENV = "AGENT_AUDIT_ANALYSIS_TIMEOUT"
# Heredoc openers in one command above this: nothing is stripped (the command is classified as it is).
MAX_HEREDOC_OPENERS = 32
# Command readings (spec audit-hook-hardening, section 3): distinct command starts per piece above this, and
# nvim `-c '!cmd'` shell text still present at this depth, cannot be classified: blocked as unclassified_command.
MAX_READINGS = 8
LOOSE_VALUE_TOKENS = 3  # raw-split assignment that opens a quote: the value may swallow up to this many next tokens
NVIM_MAX_DEPTH = 3
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

DIRECT_BINARIES = {"vitest", "jest", "mocha", "playwright", "eslint", "prettier", "tsc", "biome", "stylelint"}

SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")  # linear; the pieces are stripped after splitting
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\+?=")  # on shlex tokens: the value may hold spaces (A="x y"); `A+=x` appends

TEST_RUNNERS = re.compile(
    r"^(pytest|py\.test|jest|vitest|mocha|ava|go test|cargo test|cargo nextest|"
    r"\./mvnw\b.*\btest\b|mvn\b.*\btest\b|\./gradlew\b.*\btest\b|gradle\b.*\btest\b|"
    r"(npm|pnpm|yarn|bun)( run)? test[\w:-]*|(npm|pnpm|yarn|bun) (-C \S+ |--filter \S+ |-r |--recursive )*(run )?test[\w:-]*|"
    r"make test[\w-]*|just test[\w-]*|playwright test|npx (jest|vitest|playwright test)|"
    r"(uv|poetry) run (pytest|py\.test)|python -m pytest|dotnet test|rspec|phpunit|busted|luarocks test)\b"
)
LOAD_RUNNERS = re.compile(r"^(k6|artillery|locust|jmeter|vegeta|ab|wrk)\b")
# test-narrow: a file or a test name; test-package: one package/service; test-full: the whole repo.
NARROW_HINT = re.compile(r"(\s-run\s|\s-k\s|\s--tests?\s|-Dtest=|\s-t\s|--testNamePattern|::)")  # linear
# File-name hints, matched per whitespace token (`\S+X` is the same as `\SX`, so there is no backtracking over
# the token); a token longer than _NARROW_TOKEN_MAX is never a test file name and is skipped.
NARROW_TOKEN_HINT = re.compile(
    r"\S\.(?:test|spec)\.[cm]?[jt]sx?\b|\S_test\.(?:go|py)\b|\STests?\.(?:java|kt)\b|\S_spec\.rb\b|"
    r"\S_(?:spec|test)\.lua\b"
)
_NARROW_TOKEN_MAX = 512
_PY_SUFFIX = re.compile(r"\.py\b")


def _narrow_hint(padded: str) -> bool:
    """True when a test-runner line names a test file or a test name (see NARROW_HINT, NARROW_TOKEN_HINT)."""
    if NARROW_HINT.search(padded):
        return True
    for token in padded.split():
        if len(token) > _NARROW_TOKEN_MAX:
            continue
        if NARROW_TOKEN_HINT.search(token):
            return True
        at = token.find("test_", 1)  # `\Stest_\S+\.py\b`: the earliest test_ leaves the most room for `.py`
        if at >= 0 and _PY_SUFFIX.search(token, at + 6) is not None:
            return True
    return False
# busted only: a name filter or a tag selects a subset of the suite.
BUSTED_NARROW = re.compile(r"\s(--filter|--tags?)(=|\s)")
# busted flags whose next token is a value (a `.lua` value there is a helper or pattern, not a file to run).
_BUSTED_VALUE_FLAGS = {
    "-o", "--output", "-p", "--pattern", "-m", "--lpath", "--cpath", "-C", "--directory", "--helper",
    "--lua", "--loaders", "-r", "--run", "-f", "--config-file", "--exclude-pattern", "--exclude-tags",
}


def _busted_lua_file(padded: str) -> bool:
    """True when a busted command line names a `.lua` file argument (a single file run is narrow)."""
    skip = False
    for tok in padded.split():
        if skip:
            skip = False
        elif tok in _BUSTED_VALUE_FLAGS:
            skip = True
        elif not tok.startswith("-") and tok.endswith(".lua"):
            return True
    return False
PACKAGE_HINT = re.compile(
    r"(\s-C\s|\s--filter\s|\s-pl\s|\s-p\s|\s--package\s|\s:[\w-]+(:[\w-]+)*:test\b|"
    r"\s(\./)?[\w@.-]+(/[\w@.-]+)+/?(\.\.\.)?(\s|$))"
)
FULL_HINT = re.compile(r"(\s\./\.\.\.(\s|$)|\s--all\b|\s--workspace\b|\s-r\s|\s--recursive\b)")
LINT = re.compile(
    r"^(eslint|ruff check|ruff format|golangci-lint|go vet|gofmt|goimports|cargo clippy|cargo fmt|"
    r"ktlint|detekt|checkstyle|prettier|biome|stylelint|luacheck|selene|stylua|treefmt|"
    r"(npm|pnpm|yarn|bun) (-C \S+ |--filter \S+ |-r |--recursive )*(run )?(lint|format)[\w:-]*|make lint|just lint)\b"
)
TYPECHECK = re.compile(
    r"^(tsc|mypy|pyright|(npm|pnpm|yarn|bun) (-C \S+ |--filter \S+ |-r |--recursive )*(run )?(typecheck|type-check|tsc)[\w:-]*|"
    r"(uv|poetry) run (mypy|pyright))\b"
)

DOCKER_READ = re.compile(r"^docker (compose (ps|logs|port|config|images)|ps|logs|inspect|port|images)\b")
DOCKER_BUILD = re.compile(r"^docker (compose build|build|buildx build)\b")
DOCKER_LIFECYCLE = re.compile(
    r"^docker (compose (up|down|start|stop|restart|rm|kill|pull|create|run|exec)|"
    r"run|start|stop|restart|rm|kill|exec|create)\b"
)
DOCKER_COMPOSE_FLAGS = re.compile(r"^docker compose((\s+(-f|--file|-p|--project-name|--profile|--env-file)\s+\S+)|(\s+--\S+=\S+))+")
LOCAL_HOST = re.compile(r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|[a-z0-9-]+)(:\d+)?(/|\s|$)")
URL = re.compile(r"https?://[^\s'\"]+")


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


class Readings(NamedTuple):
    """Every plausible reading of a command piece (spec audit-hook-hardening, section 3.2)."""
    texts: list[str]  # normalized segments, primary first, deduplicated
    reasons: frozenset[str]  # "prefix_readings", "shlex_fallback", "readings_cap"
    complete: bool  # False when readings_cap was hit (texts is then empty)
    fallback: bool = False  # shlex failed: the piece was read as two token lists
    by_list: tuple[tuple[str, ...], ...] = ()  # the texts of each token list (two when `fallback`)
    truncated: bool = False  # a loose assignment window ended before the tokens did (`loose_assignment_truncated`)


_PLAIN_PREFIXES = frozenset({"rtk", "proxy", "sudo", "time", "command", "exec"})


def _opens_unclosed_quote(tok: str) -> bool:
    """True for a raw-split assignment whose value opens a quote that the token does not close (`A="x`)."""
    m = ENV_ASSIGN.match(tok)
    value = tok[m.end():] if m else ""
    return value.count('"') % 2 == 1 or value.count("'") % 2 == 1


def _prefix_steps(tokens: list[str], p: int, loose: bool = False) -> list[int]:
    """Positions that can follow the prefix at `tokens[p]`, or `[]` when `p` starts the command.

    Prefixes: env assignments, `rtk`/`proxy`/`sudo`/`time`/`command`/`exec`; `timeout [options] DURATION` (every
    GNU form; an option shape not understood yields several readings, fail closed); `mise [global flags]
    exec|x [...] --` (cut up to the `--`). Every step moves forward, so a search over positions ends."""
    if p >= len(tokens):
        return []
    tok = tokens[p]
    if ENV_ASSIGN.match(tok):
        if loose and _opens_unclosed_quote(tok):  # `A="x y cmd`: the value may swallow a few of the next tokens
            return list(range(p + 1, min(p + 1 + LOOSE_VALUE_TOKENS, len(tokens)) + 1))
        return [p + 1]
    if tok in _PLAIN_PREFIXES:
        return [p + 1]
    if tok == "mise":
        j = _skip_mise_flags(tokens, p + 1)
        if j < len(tokens) and tokens[j] in {"exec", "x"}:
            try:
                return [tokens.index("--", j) + 1]  # mise -C d exec lua@5.4 -- busted x -> busted x
            except ValueError:
                return []
        return []
    if tok == "timeout":
        return [p + length for length in _timeout_prefix_lengths(tokens, p)]
    return []


def _command_starts(tokens: list[str], loose: bool = False) -> tuple[list[int], bool, bool]:
    """Token positions where a command can start after the prefixes, primary first then ascending, whether
    more than MAX_READINGS distinct starts were found (then the list is empty), and whether a loose assignment
    window ended before the token list did (the value may swallow more tokens than the window covers). Each
    position is visited once: linear in the number of tokens, no recursion."""
    steps: dict[int, list[int]] = {}
    starts: set[int] = set()
    truncated = False
    stack = [0]
    while stack:
        p = stack.pop()
        if p in steps:
            continue
        following = _prefix_steps(tokens, p, loose)
        if loose and p < len(tokens) and ENV_ASSIGN.match(tokens[p]) and _opens_unclosed_quote(tokens[p]) \
                and p + 2 + LOOSE_VALUE_TOKENS < len(tokens):  # a longer value would still leave a command token
            truncated = True
        steps[p] = following
        if following:
            stack.extend(reversed(following))
        else:
            starts.add(p)
            if len(starts) > MAX_READINGS:
                return [], True, truncated
    primary = 0
    while steps[primary]:
        primary = steps[primary][0]  # the first step of each position: the strict reading
    return [primary] + sorted(s for s in starts if s != primary), False, truncated


def command_readings(segment: str) -> Readings:
    """Normalize a command piece so it can be classified by its real program, as a set of readings.

    Drops the prefixes of `_prefix_steps`; path-prefixed Lua tools (`./.luarocks/bin/busted` -> `busted`);
    `luarocks [global flags] test` -> `luarocks test`; and docker compose global flags (`docker compose -f x.yml
    up` -> `docker compose up`). When the prefix shape is ambiguous (`timeout -s KILL "$T" cmd`), every
    plausible reading is returned, the first is the primary one. A `shlex` failure reads the piece twice (raw
    split, and the same without quote characters). More than MAX_READINGS distinct starts: incomplete."""
    reasons: set[str] = set()
    try:
        token_lists = [shlex.split(segment, posix=True)]
    except ValueError:
        raw = segment.split()
        token_lists = [raw, [t.replace("'", "").replace('"', "") for t in raw]]
    fallback = len(token_lists) > 1  # the reason itself is added by `analyze_command`, only when the lists differ
    texts: list[str] = []
    by_list: list[tuple[str, ...]] = []
    truncated = False
    for n, tokens in enumerate(token_lists):
        loose = fallback and n == 0  # the raw split reads an assignment that opens a quote as a possible prefix
        starts, capped, cut = _command_starts(tokens, loose)
        if capped:
            return Readings([], frozenset(reasons | {"readings_cap"}), False, fallback)
        truncated = truncated or cut
        own = _distinct_texts(tokens, starts)
        # the extra readings of a loose assignment are the fallback's own (see `_fallback_lists_differ`)
        strict = _distinct_texts(tokens, _command_starts(tokens)[0]) if loose else own
        if len(strict) > 1:
            reasons.add("prefix_readings")
        by_list.append(tuple(own))
        texts.extend(t for t in own if t not in texts)
    return Readings(texts, frozenset(reasons), True, fallback, tuple(by_list), truncated)


def _distinct_texts(tokens: list[str], starts: list[int]) -> list[str]:
    own: list[str] = []
    for start in starts:
        text = _finish_strip(list(tokens[start:]))
        if text not in own:
            own.append(text)
    return own


def _finish_strip(tokens: list[str]) -> str:
    # npx vitest / pnpm exec eslint / pnpm vitest -> vitest / eslint
    if tokens and tokens[0] in {"npx", "bunx"}:
        tokens.pop(0)
    elif len(tokens) > 1 and tokens[0] in {"pnpm", "yarn", "bun"}:
        if tokens[1] in {"exec", "x", "dlx"}:
            del tokens[:2]
        elif tokens[1] in DIRECT_BINARIES:
            tokens.pop(0)
    if tokens and "/" in tokens[0] and tokens[0].rsplit("/", 1)[-1] in _PATH_TOOLS:
        tokens[0] = tokens[0].rsplit("/", 1)[-1]  # ./.luarocks/bin/busted -> busted
    if tokens and tokens[0] == "luarocks":
        j = _skip_luarocks_flags(tokens, 1)
        if j < len(tokens) and tokens[j] == "test":
            tokens = ["luarocks"] + tokens[j:]  # luarocks --lua-version 5.1 test -> luarocks test
    text = " ".join(tokens)
    if text.startswith("docker-compose"):
        text = "docker compose" + text[len("docker-compose"):]
    m = DOCKER_COMPOSE_FLAGS.match(text)
    if m:  # docker compose -f x.yml up -> docker compose up
        text = "docker compose" + text[m.end():]
    return text


_LUAROCKS_VALUE_FLAGS = {
    "--lua-version", "--lua-dir", "--tree", "--server", "--only-server", "--timeout", "--deps-mode",
    "--project-tree", "--lr-bin", "--lr-path", "--lr-cpath", "--variables", "--namespace",
}


def _skip_luarocks_flags(tokens: list[str], i: int) -> int:
    while i < len(tokens) and tokens[i].startswith("-") and tokens[i] != "--":
        i += 2 if tokens[i] in _LUAROCKS_VALUE_FLAGS else 1
    return i


_NUM = r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"  # unambiguous: linear on any digit run
_HEX = r"0[xX](?:[0-9a-fA-F]+(?:\.[0-9a-fA-F]*)?|\.[0-9a-fA-F]+)(?:[pP][+-]?\d+)?"
_TIMEOUT_DURATION = re.compile(rf"^[+]?(?:{_NUM}|{_HEX}|inf(?:inity)?|nan)[smhd]?$", re.I)
_STRTOD_SPACE = " \t\n\v\f\r"  # strtod skips these before a number
_DURATION_MAX_LEN = 64  # a longer token is never a duration (and never reaches a regex)


def _is_duration(token: str) -> bool:
    token = token.lstrip(_STRTOD_SPACE)
    return len(token) <= _DURATION_MAX_LEN and _TIMEOUT_DURATION.match(token) is not None


_TIMEOUT_LONG = {
    "foreground": False, "kill-after": True, "preserve-status": False, "signal": True,
    "verbose": False, "help": False, "version": False,
}  # GNU long options -> takes a value
_TIMEOUT_SHORT_BOOL = set("fpv")
_TIMEOUT_SHORT_VALUE = set("ks")
_PATH_TOOLS = {"busted", "luacheck", "selene", "stylua", "nvim"}


def _timeout_duration_index(tokens: list[str], start: int = 0) -> int | None:
    """Index where the DURATION of `timeout [GNU options] [--] DURATION` sits (the `timeout` token is at `start`)
    when every option is understood (value options -s/-k/--signal/--kill-after consume their next token), else
    None. The token there is not checked: it may be a variable or any other word the shell expands."""
    i = start + 1
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok == "--":
            i += 1
            break
        if tok.startswith("--"):
            name, eq, _ = tok[2:].partition("=")
            hits = [k for k in _TIMEOUT_LONG if name and k.startswith(name)]  # getopt allows abbreviations
            if name in _TIMEOUT_LONG:
                hits = [name]
            if len(hits) != 1:
                return None
            i += 1 if (eq or not _TIMEOUT_LONG[hits[0]]) else 2
        elif tok.startswith("-") and len(tok) > 1:
            i += 1
            for pos, ch in enumerate(tok[1:], start=1):
                if ch in _TIMEOUT_SHORT_BOOL:
                    continue
                if ch in _TIMEOUT_SHORT_VALUE:
                    if pos == len(tok) - 1:
                        i += 1  # the value is the next token; otherwise the rest of the cluster is
                    break
                return None
        else:
            break
    return i


def _timeout_prefix_lengths(tokens: list[str], start: int = 0) -> list[int]:
    """Token counts to drop for the `timeout ...` at `tokens[start]` (each at least 1, so the wrapped command is
    classified).

    Strict parse first: when every option is understood and a duration follows, that is the only reading. When
    the shape is not fully understood (fail closed), drop the leading option-looking tokens and the
    duration-looking tokens after them (at most two: an option value and the duration); if the token after the
    options is not a duration, a second reading also takes it as the duration. When the options were understood
    but the token at the duration position is not a duration (`timeout -s KILL "$T" cmd`), readings that drop up
    to that position and up to the next one are added too."""
    n = len(tokens)
    at = _timeout_duration_index(tokens, start)
    if at is not None and at < n and _is_duration(tokens[at]):
        return [at + 1 - start]
    i = start + 1
    while i < n and tokens[i].startswith("-"):
        i += 1
    unknown_duration = i < n and not _is_duration(tokens[i])
    for _ in range(2):
        if i < n and _is_duration(tokens[i]):
            i += 1
    lengths = [i - start]
    if unknown_duration and i + 1 <= n:
        lengths.append(i + 1 - start)
    if at is not None:
        lengths.extend([at - start, at + 1 - start])
    out: list[int] = []
    for length in lengths:
        length = max(1, min(length, n - start))
        if length not in out:
            out.append(length)
    return out


_SEPARATORS = ";&|\n"
_WORD_END = set(" \t\n;&|<>()")
# Constructs the scanner does not model: with any of them present nothing is stripped (fail closed).
_UNMODELED = re.compile(
    r"\$\{|\$'|\$\[|`|\r|[<>]\(|\bmkfifo\b|\bcoproc\b|\bexec\s+\d*[<>]"
    r"|\b(?:cat|tee)\s*\(\s*\)|\bfunction\s+(?:cat|tee)\b|>&(?:[3-9]|\d{2,})|(?<![\w])(?:[3-9]|\d{2,})>"
)
# On the opener's logical line these can feed the body (or anything else) to code: not a data sink.
_CODE_FEED = re.compile(r"(?<!\|)\|(?!\|)|<\(|>\(|\$\(")
_STDIN_FILE_FLAGS = {"git": [["-F", "-"], ["--file", "-"], ["--file=-"]], "gh": [["--body-file", "-"], ["-F", "-"], ["--body-file=-"]]}
_GIT_CONFIG = re.compile(r"(?:^|\s)-c\s*\S*(?:alias|core)\.")  # -c alias.x=!cmd / core.pager=cmd run code
# `$(cat <<EOF ...)` is data only as the value of these options, right before the `$(` (and its `"`).
_GIT_MESSAGE_VALUE = re.compile(r"^git\s.*\bcommit\b.*(?:\s-[A-Za-z]*m|\s--message)(?:=|\s+)?\"?$")
_GH_MESSAGE_VALUE = re.compile(
    r"^gh\s+(?:pr|issue|release)\s+(?:create|edit|comment|review)\b.*(?:\s(?:--body|-b|--title|-t))(?:=|\s+)?\"?$"
)
_GH_MESSAGE_CMD = re.compile(r"^gh\s+(?:pr|issue|release)\s+(?:create|edit|comment|review)\b")


def _read_delimiter(text: str, i: int) -> tuple[str, int] | None:
    """Parse a heredoc delimiter word at `text[i:]`; return (unquoted delimiter, end index) or None.

    A backslash-newline inside the word is a line continuation and is skipped.
    """
    n = len(text)
    if i >= n or not (text[i].isalpha() or text[i] in "_'\"\\"):
        return None
    delim: list[str] = []
    while i < n and text[i] not in _WORD_END:
        c = text[i]
        if c in "'\"":
            j = text.find(c, i + 1)
            if j < 0:
                return None
            delim.append(text[i + 1:j])
            i = j + 1
        elif c == "\\" and text.startswith("\\\n", i):
            i += 2
        elif c == "\\" and i + 1 < n:
            delim.append(text[i + 1])
            i += 2
        else:
            delim.append(c)
            i += 1
    return "".join(delim), i


_SINK_HEADS = frozenset({"cat", "tee", "git", "gh"})


def _clean_sink_tokens(prefix: str, *, any_dollar: bool = False) -> list[str] | None:
    """Tokens of the single clean reading of a heredoc prefix, or None (H2): exactly one reading, complete, no
    shlex fallback, and no `$` in the tokens up to the head (in any token when `any_dollar`)."""
    text = prefix.strip()
    readings = command_readings(text)
    if not readings.complete or len(readings.texts) != 1 or readings.fallback:
        return None
    tokens = readings.texts[0].split()
    if not tokens:
        return None
    try:
        original = shlex.split(text, posix=True)
    except ValueError:
        return None
    if any_dollar:
        checked = original
    else:
        try:
            checked = original[:original.index(tokens[0]) + 1]  # up to the head: the prefix tokens never repeat it
        except ValueError:
            return None  # the head is not a token of the text (normalized away): not understood
    if any("$" in tok for tok in checked):
        return None
    return tokens


def _has_sink_head(text: str) -> bool:
    """True when some reading of the piece starts with `cat`, `tee`, `git` or `gh`."""
    return any(t.split()[:1] and t.split()[0] in _SINK_HEADS for t in command_readings(text.strip()).texts)


def _is_data_sink(prefix: str, rest: str, outer: str | None, depth: int,
                  reasons: set[str] | None = None) -> bool:
    """True when the heredoc opened by `prefix` (the simple command before `<<`) is provably data.

    `rest` is the remainder of the opener's logical line; `outer` is the text before the enclosing
    `$(` when the heredoc is inside a command substitution (else None); `depth` is the nesting of
    groups/substitutions (1 = top level). Data sinks: top-level `cat`/`tee` that is not piped or fed
    to a `$(`; `git commit -F -` and `gh pr|issue|release create|edit|comment|review -F -` (no
    `-c alias.*`/`core.*`); and a lone `$(cat <<EOF ...)` that is the value of `git commit -m` or of
    a `gh` message option. Only a clean prefix counts (`_clean_sink_tokens`); a body kept because the
    prefix is not clean, while some reading is a sink head, adds `heredoc_unclean_prefix` to `reasons`.
    """
    tokens = _clean_sink_tokens(prefix)
    if tokens and tokens[0] in ("git", "gh"):
        tokens = _clean_sink_tokens(prefix, any_dollar=True)
    if tokens is None:
        if reasons is not None and _has_sink_head(prefix):
            reasons.add("heredoc_unclean_prefix")
        return False
    if _CODE_FEED.search(prefix + rest):
        return False
    text = " ".join(tokens)
    head = tokens[0]
    if head == "git" and _GIT_CONFIG.search(text):
        return False
    if outer is not None:
        if tokens != ["cat"]:
            return False
        outer_tokens = _clean_sink_tokens(outer.rstrip().rstrip('"').rstrip(), any_dollar=True)
        if outer_tokens is None:
            if reasons is not None and _has_sink_head(outer):
                reasons.add("heredoc_unclean_prefix")
            return False
        outer_text = " ".join(outer_tokens)
        if _GIT_CONFIG.search(outer_text):
            return False
        return bool(_GIT_MESSAGE_VALUE.match(outer_text) or _GH_MESSAGE_VALUE.match(outer_text))
    if head in ("git", "gh"):
        pairs = _STDIN_FILE_FLAGS[head]
        has_flag = any(tokens[k:k + len(p)] == p for p in pairs for k in range(len(tokens)))
        if head == "git":
            return has_flag and "commit" in tokens
        return has_flag and bool(_GH_MESSAGE_CMD.match(text))
    return depth == 1 and head in ("cat", "tee")


def _scan_heredocs(command: str, reasons: set[str] | None = None) -> str:
    """Single pass over `command` (see strip_heredoc_bodies); may raise, the caller falls back.
    Uncertainty reasons found on the way are added to `reasons`."""
    if _UNMODELED.search(command):
        return command
    n = len(command)
    out: list[str] = []
    # Context stack of (kind, outer, saved_seg_start): kind is cmd, sq, dq or arith; outer is the text before
    # the `$(` that opened a command substitution, else None; saved_seg_start is the start of the enclosing
    # simple command, restored when the group closes (H1).
    stack: list[tuple[str, str | None, int]] = [("cmd", None, 0)]
    pending: list[tuple[str, bool, bool]] = []  # (delimiter, strip leading tabs, body is data)
    seg_start = 0  # index in `out` where the current simple command starts
    sink_cache: dict[int, bool] = {}  # seg_start -> data-sink verdict of the simple command that starts there
    openers = 0
    i = 0
    while i < n:
        c = command[i]
        ctx = stack[-1][0]
        if c == "\n" and pending:
            if ctx in ("sq", "dq"):  # bash starts the body after the newline that ends the command line
                return command
            out.append(c)
            i += 1
            for delim, strip_tabs, is_data in pending:
                while i < n:
                    j = command.find("\n", i)
                    end = n if j < 0 else j
                    line = command[i:end]
                    i = end + 1 if j >= 0 else n
                    if (line.lstrip("\t") if strip_tabs else line) == delim:
                        break
                    if not is_data:
                        out.extend(line + "\n")
            pending = []
            seg_start = len(out)
            continue
        if ctx == "sq":
            if c == "'":
                stack.pop()
        elif c == "\\" and i + 1 < n:
            if command[i + 1] == "\n":  # line continuation
                i += 2
                continue
            out.append(c)
            i += 1
            c = command[i]
        elif ctx == "dq":
            if c == '"':
                stack.pop()
            elif c == "$" and command.startswith("$(", i):
                outer = "".join(out[seg_start:])
                out.append(c)
                i += 1
                c = "("
                stack.append(("arith" if command.startswith("((", i) else "cmd", outer, seg_start))
                seg_start = len(out) + 1
        elif c == "'":
            stack.append(("sq", None, seg_start))
        elif c == '"':
            stack.append(("dq", None, seg_start))
        elif c == "(":
            # `((` and `$((` open arithmetic, where `<<` is a shift; the second `(` sees ctx arith.
            if ctx == "arith" or command.startswith("((", i):
                stack.append(("arith", None, seg_start))
            else:
                outer = "".join(out[seg_start:]) if out and out[-1] == "$" else None
                stack.append(("cmd", outer, seg_start))
            seg_start = len(out) + 1
        elif c == ")":
            if len(stack) > 1:
                seg_start = stack.pop()[2]  # the enclosing command goes on (`sh -s $(true) cat <<EOF`)
            else:
                seg_start = len(out) + 1
        elif ctx == "arith":
            pass
        elif c == "#" and (not out or out[-1] in " \t\n;&|()"):
            j = command.find("\n", i)
            end = n if j < 0 else j
            out.extend(command[i:end])
            i = end
            continue
        elif c in _SEPARATORS:
            seg_start = len(out) + 1
        elif c == "<" and command.startswith("<<<", i):
            out.extend("<<<")
            i += 3
            continue
        elif c == "<" and command.startswith("<<", i):
            j = i + 2
            strip_tabs = command.startswith("-", j)
            if strip_tabs:
                j += 1
            while j < n and command[j] in " \t":
                j += 1
            parsed = _read_delimiter(command, j)
            if parsed is not None:
                delim, end = parsed
                openers += 1
                if openers > MAX_HEREDOC_OPENERS:  # fail closed: classify the command as it is
                    return command
                if seg_start not in sink_cache:  # decided once per simple command (the first opener's view of it)
                    eol = re.search(r"(?<!\\)\n", command[end:])
                    rest = command[i:end + eol.start()] if eol else command[i:]
                    sink_cache[seg_start] = _is_data_sink(
                        "".join(out[seg_start:]), rest.replace("\\\n", ""), stack[-1][1], len(stack),
                        reasons)
                is_data = sink_cache[seg_start]
                pending.append((delim, strip_tabs, is_data))
                out.extend(command[i:end].replace("\\\n", ""))
                i = end
                continue
        out.append(c)
        i += 1
    return "".join(out)


def _strip_heredocs(command: str) -> tuple[str, frozenset[str]]:
    """`strip_heredoc_bodies` plus the uncertainty reasons found while scanning (`heredoc_unclean_prefix`).
    A scanner error returns the original command."""
    try:
        reasons: set[str] = set()
        return _scan_heredocs(command, reasons), frozenset(reasons)
    except Exception:
        return command, frozenset()


def strip_heredoc_bodies(command: str) -> str:
    """Return `command` without the bodies (and terminator lines) of heredocs that are provably data.

    Fail closed: a body is stripped only for a data sink (see `_is_data_sink`): top-level `cat`/`tee`
    not piped or fed to `$(`, `git commit -F -`, `gh pr|issue|release ... -F -`, or a lone
    `$(cat <<EOF ...)` as the value of `git commit -m` or a `gh` message option. Every other heredoc
    (bash, python, `| bash`, eval, xargs, ...) keeps its body so it is classified as commands; only its
    terminator line is dropped. The opener line and everything after the terminator are kept.
    Handles `<<`, `<<-` (tab-stripped terminator), quoted and escaped delimiters, several heredocs on
    one line and backslash-newline continuations; ignores `<<<`, `$((1<<2))`, quoted text and comments.
    An unterminated body runs to the end. Nothing is stripped (the command is returned unchanged) when
    it has constructs the scanner does not model (`${`, `$'`, `$[`, backticks, `\\r`, process
    substitution, mkfifo, coproc, exec redirections, cat/tee functions, fds >= 3), or a newline inside
    quotes while a heredoc is pending. A scanner error also returns the original.
    """
    return _strip_heredocs(command)[0]


@functools.lru_cache(maxsize=64)
def test_scope(padded: str, busted: bool = False) -> str:
    """Category of a test-runner segment (space-padded): full, narrow (a file, a name) or package.

    Pure, and cached per distinct padded reading (the prefix readings of one command share most of their text)."""
    if FULL_HINT.search(padded):
        return "test-full"
    if _narrow_hint(padded) or (busted and (BUSTED_NARROW.search(padded) or _busted_lua_file(padded))):
        return "test-narrow"
    if PACKAGE_HINT.search(padded):
        return "test-package"
    return "test-full"


_MISE_VALUE_FLAGS = {
    "-C", "--cd", "-E", "--env", "-P", "--profile", "--log-level", "-j", "--jobs", "-o", "--output",
    "-t", "--tool", "-s", "--shell", "--timeout", "--secrets", "--allow-env", "--allow-net", "--allow-read",
    "--allow-write", "--affected-base", "--affected-head", "--task-cache",
}
_MISE_BOOL_SHORT = set("qvyhfnrcS")
_MISE_VALUE_SHORT = set("CEPjots")
_MISE_TEST = re.compile(r"^test(?!-tool$)[\w:*-]*$")
_MISE_LINT = re.compile(r"^(lint|format|fmt)[\w:*-]*$")
_MISE_SUITE = {"all", "check", "ci"}


def _skip_mise_flags(tokens: list[str], i: int) -> int:
    """Index of the first token after mise flags; value flags consume their value, `--` stops the scan."""
    while i < len(tokens) and tokens[i].startswith("-") and tokens[i] != "--":
        tok = tokens[i]
        takes_value = tok in _MISE_VALUE_FLAGS or (
            len(tok) > 2 and tok[1] != "-" and tok[-1] in _MISE_VALUE_SHORT
            and all(c in _MISE_BOOL_SHORT for c in tok[1:-1])
        )  # -vC dir: boolean short flags ending in a value flag
        i += 2 if takes_value else 1
    return i


def mise_categories(seg: str) -> list[str]:
    """Categories of a `mise run <task> [args] [::: <task> ...]` segment (or the `mise <task>` shortcut)."""
    tokens = seg.split()[1:]
    i = _skip_mise_flags(tokens, 0)
    if i < len(tokens) and tokens[i] in {"run", "r"}:
        i += 1
    elif i + 1 < len(tokens) and tokens[i] == "tasks" and tokens[i + 1] == "run":
        i += 2
    groups: list[list[str]] = [[]]
    for tok in tokens[i:]:
        if tok == ":::":
            groups.append([])
        else:
            groups[-1].append(tok)
    categories: list[str] = []
    for group in groups:
        j = _skip_mise_flags(group, 0)
        if j >= len(group):
            continue
        name, args = group[j], group[j + 1:]
        if _MISE_TEST.match(name):
            categories.append(test_scope(" " + " ".join(args) + " "))
        elif _MISE_LINT.match(name):
            categories.append("lint")
        elif name in _MISE_SUITE:
            categories.append("test-full")
        else:
            categories.append("other")
    return categories or ["other"]


# Unambiguous after `require` (no `\s*` next to another `\s*` or an optional that can match nothing), so a long
# whitespace run costs linear time: require("mini.test") / require'mini.test'
_MINI_TEST = r"(?:MiniTest|require\s*(?:\(\s*)?['\"]mini\.test['\"]\s*\)?)"
_PLENARY_HARNESS = r"require\s*(?:\(\s*)?['\"]plenary\.test_harness['\"]\s*(?:\)\s*)?\."
_NVIM_FILE = re.compile(rf"(PlenaryBustedFile\b|{_MINI_TEST}\.run_(file|at_location)\b|{_PLENARY_HARNESS}test_file\b)")
_NVIM_DIRECTORY = re.compile(
    rf"(?:PlenaryBustedDirectory\b\s*|{_PLENARY_HARNESS}test_directory\s*\(\s*)(?:['\"]?([^\s'\"),]+))?"
)
_NVIM_RUN = re.compile(rf"{_MINI_TEST}\.run\(")
_TEST_DIR_NAMES = {"test", "tests", "spec", "specs"}
# Shell text in an ex command: `!cmd`, `:!cmd`, `:silent !cmd`, `:w !cmd`, `:r !cmd`.
_NVIM_SHELL = re.compile(r"(?:^|[:|])\s*(?:sil(?:ent)?!?\s+|w(?:rite)?\s+|r(?:ead)?\s*)?!(.+)$", re.S)


@functools.lru_cache(maxsize=64)
def nvim_category(seg: str) -> str:
    """Category of an `nvim` segment: only `--headless` runs of a Lua test runner count as tests.

    Pure, and cached per distinct segment text."""
    if "--headless" not in seg.split():
        return "other"
    if _NVIM_FILE.search(seg):
        return "test-narrow"
    m = _NVIM_DIRECTORY.search(seg)
    if m:
        folder = (m.group(1) or "").strip("\"'")
        if folder.startswith(("{", "}")):
            folder = ""
        folder = folder[2:] if folder.startswith("./") else folder
        parts = folder.strip("/").split("/")
        if folder.startswith("/") and parts[-1] in _TEST_DIR_NAMES:
            return "test-full"  # an absolute path ending in the test folder is the whole suite
        return "test-package" if "/" in folder.strip("/") else "test-full"
    if _NVIM_RUN.search(seg):
        return "test-full"
    return "other"


def nvim_shell_texts(raw: str) -> list[str]:
    """Shell commands an nvim invocation runs through `-c`/`--cmd`/`+cmd` ex commands (`!cmd`, `:!cmd`)."""
    try:
        tokens = shlex.split(raw, posix=True)
    except ValueError:
        tokens = raw.split()
    start = next((k for k, t in enumerate(tokens) if t.rsplit("/", 1)[-1] == "nvim"), None)
    if start is None:
        return []
    texts: list[str] = []
    k = start + 1
    while k < len(tokens):
        tok = tokens[k]
        cmd = None
        if tok in {"-c", "--cmd"} and k + 1 < len(tokens):
            cmd = tokens[k + 1]
            k += 1
        elif tok.startswith("--cmd="):
            cmd = tok[6:]
        elif tok.startswith("+") and len(tok) > 1:
            cmd = tok[1:]
        if cmd is not None:
            m = _NVIM_SHELL.search(cmd)
            if m and m.group(1).strip():
                texts.append(m.group(1).strip())
        k += 1
    return texts


class Analysis(NamedTuple):
    """Result of `analyze_command`: what `classify_command` returns, plus why the parser was not certain."""
    categories: list[str]
    flags: list[str]  # never contains "parse_uncertain" (main adds it from `uncertainty`)
    uncertainty: list[str]  # sorted reasons


# Docker and git forms the canary (U7) looks for outside the command head.
_CANARY_SPLIT = re.compile(r"[\s'\"`(){};&|=$]+")
_DOCKER_VERBS = frozenset({"up", "down", "start", "stop", "restart", "rm", "kill", "pull", "create", "run", "exec"})
_CANARY_GIT_FLAGS = (("push", "git_push"), ("commit", "git_commit"))


def _deny_token_unmatched(raw: str, flags: set[str]) -> bool:
    """U7: a blocked program shows up outside the head of the piece, followed by its verb, and no rule flagged
    the command. Only a record: it makes the forms the parser does not model visible in the metrics."""
    if "docker" not in raw and "git" not in raw:
        return False
    tokens = [t for t in _CANARY_SPLIT.split(raw) if t]
    for i, tok in enumerate(tokens):
        if i == 0:
            continue
        name = tok.rsplit("/", 1)[-1]
        if name in {"docker", "docker-compose"} and "docker_lifecycle" not in flags:
            if any(t in _DOCKER_VERBS for t in tokens[i + 1:]):
                return True
        elif name == "git":
            rest = tokens[i + 1:]
            if any(verb in rest and flag not in flags for verb, flag in _CANARY_GIT_FLAGS):
                return True
    return False


def _fallback_lists_differ(raw: str, readings: Readings, _depth: int) -> bool:
    """True when the two token lists of a shlex failure read the piece differently: their texts differ and the
    categories or flags found by classifying them differ too (`grep -E "a` reads the same either way)."""
    if len(readings.by_list) != 2 or set(readings.by_list[0]) == set(readings.by_list[1]):
        return False
    found: list[tuple[set[str], set[str]]] = []
    for texts in readings.by_list:
        categories: list[str] = []
        flags: list[str] = []
        for seg in texts:
            _classify_segment(raw, seg, categories, flags, _depth, [], set())
        found.append((set(categories), set(flags)))
    return found[0] != found[1]


def analyze_command(command: str, _depth: int = 0) -> Analysis:
    """Classify a Bash command: categories, flags and the reasons of any parser uncertainty (spec
    audit-hook-hardening, section 3). Uncertainty never becomes an allow: alternative readings are all
    classified (level A), and what cannot be enumerated is `unclassified` / `unclassified_command` (level B)."""
    command = command or ""
    if len(command) > MAX_COMMAND_LEN:  # checked before any regex or parse touches the text
        return Analysis(["other"], ["command_too_long"], [])
    categories: list[str] = []
    flags: list[str] = []
    reasons: set[str] = set()
    text, heredoc_reasons = _strip_heredocs(command)
    reasons.update(heredoc_reasons)
    raws: list[str] = []
    for piece in SEGMENT_SPLIT.split(text):
        raw = piece.strip()
        readings = command_readings(raw)
        reasons.update(readings.reasons)
        if not readings.complete:  # too many possible readings: not classified, blocked (no canary: already denied)
            categories.append("unclassified")
            flags.append("unclassified_command")
            continue
        if readings.truncated:  # level A only: the value may extend past the window (91 real python heredoc
            reasons.add("loose_assignment_truncated")  # bodies with stray quotes would be denied if this failed closed)
        if readings.fallback and _fallback_lists_differ(raw, readings, _depth):
            reasons.add("shlex_fallback")
        raws.append(raw)
        nested: list[tuple[list[str], list[str]]] = []  # nvim shell texts, classified once per raw segment
        for n, seg in enumerate(readings.texts):
            seg_categories: list[str] = []
            _classify_segment(raw, seg, seg_categories, flags, _depth, nested, reasons)
            # an alternate reading only adds what it found, never its "other" (the primary reading owns that)
            categories.extend(seg_categories if n == 0 else [c for c in seg_categories if c != "other"])
    flag_set = set(flags)  # the flag may come from another piece of the same command
    if any(_deny_token_unmatched(raw, flag_set) for raw in raws):
        reasons.add("deny_token_unmatched")
    return Analysis(sorted(set(categories)) or ["other"], sorted(set(flags)), sorted(reasons))


def classify_command(command: str, _depth: int = 0) -> tuple[list[str], list[str]]:
    analysis = analyze_command(command, _depth)
    return analysis.categories, analysis.flags


def _nvim_nested(raw: str, _depth: int) -> tuple[list[str], list[str], set[str]]:
    """Categories, flags and uncertainty reasons of the shell text an nvim invocation runs through
    `-c '!cmd'` (blocked as unclassified_command when nested NVIM_MAX_DEPTH levels deep)."""
    categories: list[str] = []
    flags: list[str] = []
    reasons: set[str] = set()
    texts = nvim_shell_texts(raw)
    if _depth < NVIM_MAX_DEPTH:  # shell text run by `-c '!cmd'` is classified as its own command
        for text in texts:
            sub = analyze_command(text, _depth + 1)
            categories.extend(sub.categories)
            flags.extend(sub.flags)
            reasons.update(sub.uncertainty)
    elif texts:  # nested too deep to classify: level B
        categories.append("unclassified")
        flags.append("unclassified_command")
        reasons.add("nested_shell_depth")
    return categories, flags, reasons


def _classify_segment(raw: str, seg: str, categories: list[str], flags: list[str], _depth: int,
                      nested: list[tuple[list[str], list[str]]] | None = None,
                      reasons: set[str] | None = None) -> None:
    """Classify one segment (already stripped of prefixes), appending to `categories` and `flags`.

    `nested` is a one-slot cache shared by the readings of one raw segment, so the nvim shell texts are
    classified once per raw segment however many readings start with nvim; `reasons` collects the
    uncertainty reasons of those nested texts."""
    if not seg or seg.startswith("cd "):
        return
    padded = " " + seg + " "
    if seg.startswith("docker"):
        if DOCKER_LIFECYCLE.match(seg):
            categories.append("docker-lifecycle")
            flags.append("docker_lifecycle")
        elif DOCKER_BUILD.match(seg):
            categories.append("docker-build")
            flags.append("docker_build")
        elif DOCKER_READ.match(seg):
            categories.append("docker-read")
        else:
            categories.append("docker-other")
    elif seg.startswith("git "):
        if re.match(r"^git (\S+ )*commit\b", seg):
            categories.append("git-commit")
            flags.append("git_commit")
        elif re.match(r"^git (\S+ )*push\b", seg):
            categories.append("git-push")
            flags.append("git_push")
        else:
            categories.append("git-other")
    elif seg == "mise" or seg.startswith("mise "):
        categories.extend(mise_categories(seg))
    elif seg == "nvim" or seg.startswith("nvim "):
        categories.append(nvim_category(seg))
        if nested is None:
            nested = []
        if not nested:
            sub_categories, sub_flags, sub_reasons = _nvim_nested(raw, _depth)
            nested.append((sub_categories, sub_flags))
            if reasons is not None:
                reasons.update(sub_reasons)
        categories.extend(nested[0][0])
        flags.extend(nested[0][1])
    elif LOAD_RUNNERS.match(seg):
        categories.append("test-load")
    elif TEST_RUNNERS.match(seg):
        categories.append(test_scope(padded, busted=seg.startswith("busted")))
    elif LINT.match(seg):
        categories.append("lint")
    elif TYPECHECK.match(seg):
        categories.append("typecheck")
    elif seg.startswith(("curl ", "http ", "wget ")):
        urls = URL.findall(seg)
        if urls and all(LOCAL_HOST.match(u + " ") for u in urls):
            categories.append("request-local")
        elif urls:
            categories.append("request-external")
            flags.append("external_request")
        else:
            categories.append("request-local")
    else:
        categories.append("other")


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
    "unclassified_command": "the hook could not classify this command with certainty (too many possible readings, shell text nested too deep, or an analysis error), so it is blocked and never run",
    "parse_uncertain": "the command had more than one plausible reading; every reading was classified and the strictest one applies",
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
        return ("Run each program as its own short command, without stacked wrappers (timeout, sudo, mise exec) "
                "or nested shells, and write large content to a file with the Write tool.")
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
        out["categories"], flags, uncertainty = analyze_command(cmd)
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
