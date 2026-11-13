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

import json
import math
import os
import re
import functools
import shlex
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

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
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=\S*$")

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


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
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
        # O_NONBLOCK: opening a FIFO must not wait for a writer. fstat on the fd (after following any
        # symlink) must say regular file, so a FIFO or a char device such as /dev/tty is never read.
        fd = os.open(Path(root) / "CLAUDE.md", os.O_RDONLY | os.O_NONBLOCK)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                return DEFAULT_DOCS_ROOT
            with os.fdopen(fd, "rb", closefd=False) as fh:
                text = fh.read(262144).decode("utf-8", errors="replace")
        finally:
            os.close(fd)
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


def strip_prefixes(segment: str) -> str:
    """Normalize a command segment so it can be classified by its real program.

    Drops env assignments, `rtk`/`rtk proxy`, `sudo`, `time`, `command`, `exec`; `timeout [options] DURATION`
    (every GNU form, and fail closed: an option shape not understood still drops the option-looking tokens and
    the duration, so the real command is classified); `mise [global flags] exec|x [...] --` (cut up to the
    `--`); path-prefixed Lua tools (`./.luarocks/bin/busted` -> `busted`); `luarocks [global flags] test`
    -> `luarocks test`; and docker compose global flags (`docker compose -f x.yml up` -> `docker compose up`)."""
    return strip_prefix_variants(segment)[0]


def strip_prefix_variants(segment: str) -> list[str]:
    """Like `strip_prefixes`, but a `timeout` whose shape is not understood yields every plausible reading
    (the first is the primary one), so a real command cannot hide behind a duration form the parser misses."""
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        tokens = segment.split()
    out: list[str] = []
    for variant in _strip_tokens(tokens, 0):
        if variant not in out:
            out.append(variant)
    return out[:8]


def _strip_tokens(tokens: list[str], depth: int) -> list[str]:
    while tokens:
        if ENV_ASSIGN.match(tokens[0]) or tokens[0] in {"rtk", "proxy", "sudo", "time", "command", "exec"}:
            tokens.pop(0)
        elif tokens[0] == "mise":
            j = _skip_mise_flags(tokens, 1)
            if j < len(tokens) and tokens[j] in {"exec", "x"} and "--" in tokens[j:]:
                del tokens[:tokens.index("--", j) + 1]  # mise -C d exec lua@5.4 -- busted x -> busted x
            else:
                break
        elif tokens[0] == "timeout":
            lengths = _timeout_prefix_lengths(tokens)
            if len(lengths) > 1 and depth < 3:
                results: list[str] = []
                for length in lengths:
                    results.extend(_strip_tokens(tokens[length:], depth + 1))
                return results
            del tokens[:lengths[0]]
        else:
            break
    return [_finish_strip(tokens)]


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


def _timeout_duration_index(tokens: list[str]) -> int | None:
    """Index where the DURATION of `timeout [GNU options] [--] DURATION` sits when every option is understood
    (value options -s/-k/--signal/--kill-after consume their next token), else None. The token there is not
    checked: it may be a variable or any other word the shell expands."""
    i = 1
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


def _timeout_prefix_lengths(tokens: list[str]) -> list[int]:
    """Token counts to drop for a leading `timeout ...` (each at least 1, so the wrapped command is classified).

    Strict parse first: when every option is understood and a duration follows, that is the only reading. When
    the shape is not fully understood (fail closed), drop the leading option-looking tokens and the
    duration-looking tokens after them (at most two: an option value and the duration); if the token after the
    options is not a duration, a second reading also takes it as the duration. When the options were understood
    but the token at the duration position is not a duration (`timeout -s KILL "$T" cmd`), readings that drop up
    to that position and up to the next one are added too."""
    n = len(tokens)
    at = _timeout_duration_index(tokens)
    if at is not None and at < n and _is_duration(tokens[at]):
        return [at + 1]
    i = 1
    while i < n and tokens[i].startswith("-"):
        i += 1
    unknown_duration = i < n and not _is_duration(tokens[i])
    for _ in range(2):
        if i < n and _is_duration(tokens[i]):
            i += 1
    lengths = [i]
    if unknown_duration and i + 1 <= n:
        lengths.append(i + 1)
    if at is not None:
        lengths.extend([at, at + 1])
    out: list[int] = []
    for length in lengths:
        length = max(1, min(length, n))
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


def _is_data_sink(prefix: str, rest: str, outer: str | None, depth: int) -> bool:
    """True when the heredoc opened by `prefix` (the simple command before `<<`) is provably data.

    `rest` is the remainder of the opener's logical line; `outer` is the text before the enclosing
    `$(` when the heredoc is inside a command substitution (else None); `depth` is the nesting of
    groups/substitutions (1 = top level). Data sinks: top-level `cat`/`tee` that is not piped or fed
    to a `$(`; `git commit -F -` and `gh pr|issue|release create|edit|comment|review -F -` (no
    `-c alias.*`/`core.*`); and a lone `$(cat <<EOF ...)` that is the value of `git commit -m` or of
    a `gh` message option.
    """
    if _CODE_FEED.search(prefix + rest):
        return False
    tokens = strip_prefixes(prefix.strip()).split()
    if not tokens:
        return False
    text = " ".join(tokens)
    head = tokens[0]
    if head == "git" and _GIT_CONFIG.search(text):
        return False
    if outer is not None:
        if tokens != ["cat"]:
            return False
        outer_text = strip_prefixes(outer.strip())
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


def _scan_heredocs(command: str) -> str:
    """Single pass over `command` (see strip_heredoc_bodies); may raise, the caller falls back."""
    if _UNMODELED.search(command):
        return command
    n = len(command)
    out: list[str] = []
    # Context stack of (kind, outer): kind is cmd, sq, dq or arith; outer is the text before the
    # `$(` that opened a command substitution, else None.
    stack: list[tuple[str, str | None]] = [("cmd", None)]
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
                stack.append(("arith" if command.startswith("((", i) else "cmd", outer))
                seg_start = len(out) + 1
        elif c == "'":
            stack.append(("sq", None))
        elif c == '"':
            stack.append(("dq", None))
        elif c == "(":
            # `((` and `$((` open arithmetic, where `<<` is a shift; the second `(` sees ctx arith.
            if ctx == "arith" or command.startswith("((", i):
                stack.append(("arith", None))
            else:
                outer = "".join(out[seg_start:]) if out and out[-1] == "$" else None
                stack.append(("cmd", outer))
            seg_start = len(out) + 1
        elif c == ")":
            if len(stack) > 1:
                stack.pop()
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
                        "".join(out[seg_start:]), rest.replace("\\\n", ""), stack[-1][1], len(stack))
                is_data = sink_cache[seg_start]
                pending.append((delim, strip_tabs, is_data))
                out.extend(command[i:end].replace("\\\n", ""))
                i = end
                continue
        out.append(c)
        i += 1
    return "".join(out)


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
    try:
        return _scan_heredocs(command)
    except Exception:
        return command


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


def classify_command(command: str, _depth: int = 0) -> tuple[list[str], list[str]]:
    command = command or ""
    if len(command) > MAX_COMMAND_LEN:  # checked before any regex or parse touches the text
        return ["other"], ["command_too_long"]
    categories: list[str] = []
    flags: list[str] = []
    for piece in SEGMENT_SPLIT.split(strip_heredoc_bodies(command)):
        raw = piece.strip()
        nested: list[tuple[list[str], list[str]]] = []  # nvim shell texts, classified once per raw segment
        for n, seg in enumerate(strip_prefix_variants(raw)):
            seg_categories: list[str] = []
            _classify_segment(raw, seg, seg_categories, flags, _depth, nested)
            # an alternate reading only adds what it found, never its "other" (the primary reading owns that)
            categories.extend(seg_categories if n == 0 else [c for c in seg_categories if c != "other"])
    return sorted(set(categories)) or ["other"], sorted(set(flags))


def _nvim_nested(raw: str, _depth: int) -> tuple[list[str], list[str]]:
    """Categories and flags of the shell text an nvim invocation runs through `-c '!cmd'` (fail closed when
    nested too deep)."""
    categories: list[str] = []
    flags: list[str] = []
    texts = nvim_shell_texts(raw)
    if _depth < 3:  # shell text run by `-c '!cmd'` is classified as its own command
        for text in texts:
            sub_categories, sub_flags = classify_command(text, _depth + 1)
            categories.extend(sub_categories)
            flags.extend(sub_flags)
    elif texts:  # nested too deep to classify: fail closed with the strictest existing deny
        categories.append("docker-lifecycle")
        flags.extend(["docker_lifecycle", "nested_shell_unclassified"])
    return categories, flags


def _classify_segment(raw: str, seg: str, categories: list[str], flags: list[str], _depth: int,
                      nested: list[tuple[list[str], list[str]]] | None = None) -> None:
    """Classify one segment (already stripped of prefixes), appending to `categories` and `flags`.

    `nested` is a one-slot cache shared by the readings of one raw segment, so the nvim shell texts are
    classified once per raw segment however many readings start with nvim."""
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
            nested.append(_nvim_nested(raw, _depth))
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


def git_root(start: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0:
            return Path(out.stdout.strip())
    except Exception:
        pass
    return None


def active_run(root: Path) -> dict | None:
    runs_dir = root / ".claude" / "runs"
    if not runs_dir.is_dir():
        return None
    candidates = []
    for f in runs_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        if data.get("phase") != "done":
            candidates.append((f.stat().st_mtime, f.stem, data))
    if not candidates:
        return None
    _, slug, data = max(candidates, key=lambda c: c[0])
    data["_slug"] = slug
    return data


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
        cwd_root = git_root(Path(cwd)) if cwd and Path(cwd).is_dir() else None
        target_root = git_root(nearest_existing(resolved.parent))
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
    except Exception:  # fail closed: unresolvable path -> outside, actor-only flags (+ out of scope in a run)
        out.update({"rel": path_str, "area": "outside", "in_run": False})
        if scoped:
            try:
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
}


def what_to_do(actor: str, category: str) -> str:
    if category == "docker_lifecycle":
        return "Put the command in manual_checks for the user instead."
    if category == "command_too_long":
        return "Write the content to a file with the Write tool and run a short command that uses the file."
    if category == "analysis_timeout":
        return ("Simplify the command or split it into several short commands, and write large content to a file "
                "with the Write tool instead of putting it in the command.")
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

    if event in {"SubagentStart", "SubagentStop"}:
        record["agent_type"] = payload.get("agent_type")
    else:
        tool = payload.get("tool_name", "")
        tinput = payload.get("tool_input") or {}
        record["tool"] = tool
        if event != "PreToolUse":
            record["failed"] = event == "PostToolUseFailure"
        flags: list[str] = []
        timed_out = False
        previous = None
        try:
            try:  # the classification runs under a wall-clock limit (a hook timeout fails open)
                previous = _arm_analysis_timer()
                if tool == "Bash":
                    cmd = tinput.get("command", "")
                    record["cmd"] = cmd[:MAX_CMD]
                    record["categories"], flags = classify_command(cmd)
                    suites = {"test-full", "test-package", "test-load"} & set(record["categories"])
                    if suites and actor in IMPLEMENTERS | {"quality-fixer", "test-writer"}:
                        flags.append("suite_by_non_runner")
                elif tool in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
                    path = tinput.get("file_path") or tinput.get("notebook_path") or ""
                    record["categories"] = ["write"]
                    record.update(evaluate_write(path, payload.get("cwd", ""), actor, tool,
                                                  payload.get("tool_response"),
                                                  scratchpad=payload.get("scratchpad_dir"),
                                                  failed=event == "PostToolUseFailure"))
                    flags = record.pop("flags", [])
                elif VISUAL_TOOL.search(tool):
                    record["categories"] = ["visual"]
                    flags = [] if actor == "ui-verifier" else ["visual_tool"]
                else:
                    return  # reads, searches and other tools are not audited
            finally:
                _disarm_analysis_timer(previous)
        except AnalysisTimeout:  # also when it fires inside the arm or disarm calls (the timer is one shot)
            timed_out = True
        if timed_out:  # too complex to analyze in time: PreToolUse denies it, PostToolUse records it
            if "cmd" not in record and tool == "Bash":
                record["cmd"] = str(tinput.get("command", ""))[:MAX_CMD]
            record["categories"] = ["other"]
            flags = ["analysis_timeout"]
        record["flags"] = sorted(set(flags))

    if event == "PreToolUse":
        decision = decide(record, config)
        if decision is None:
            return  # allowed silently; PostToolUse records the action itself
        print(json.dumps(decision))
        sys.stdout.flush()  # the decision is out before any slow recording step can delay or lose it
        if record.get("decision") == "warn":
            return  # the action still runs and PostToolUse records it with its flags

    # The recording runs under what is left of the analysis budget, so it can never push the hook past its timeout.
    remaining = max(0.25, _analysis_limit() - (time.monotonic() - started))
    previous = None
    try:
        try:
            previous = _arm_analysis_timer(remaining)
            _write_record(payload, record)
        finally:
            _disarm_analysis_timer(previous)
    except AnalysisTimeout:  # the record is lost, the decision (if any) was already printed
        pass


def _write_record(payload: dict, record: dict) -> None:
    if "in_run" not in record:  # tag commands and lifecycle events with the active /implement run
        root = git_root(Path(payload.get("cwd") or "."))
        run = active_run(root) if root else None
        record["in_run"] = bool(run)
        if run:
            record["run"] = run.get("_slug")
            record["task"] = ",".join(run_task_keys(run))

    session = record.get("session") or "unknown"
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    with open(METRICS_DIR / f"{session}.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except (Exception, AnalysisTimeout):  # never a stack trace, always exit 0
        pass
    sys.exit(0)
