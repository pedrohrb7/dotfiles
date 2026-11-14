"""Command classifier of the agent-audit hook (spec audit-shell-lexer, review fix part C).

Turns a Bash command into categories, flags and the reasons of any uncertainty: `analyze_command` is the entry. The
command is read by the shell parser of the sibling module `agent_audit_shell.py` (every command position, quote,
heredoc and here-string), every simple command is read as the readings its wrappers and launchers allow, the
arguments that run code are analyzed one level deeper, and the values the text gives its variables resolve the
program names and code strings.

It is a part of the hook and holds no policy: which category is blocked, asked or only recorded is the config of
`agent-audit.py`, which loads this module by path (so the bytecode is cached) and calls `analyze_command`. The module
imports nothing from the hook: what it needs (the parser) is registered in `sys.modules` by the hook's loader, and a
module that does not load leaves the hook without a classifier, which blocks every Bash command (`classifier_error`).
Stdlib only, and no `typing` import (it costs the hook about 3 ms in every call), so the types are `collections`
named tuples.
"""

from __future__ import annotations

import functools
import re
from collections import namedtuple

import agent_audit_shell as shell

# A Bash command longer than this is never fed to the regex classifier: it is denied (command_too_long). The cap
# shrinks the input but does not bound the time (a quadratic path still costs seconds at 8-11 KB); the wall-clock
# guard of the hook is the structural bound, because a hook timeout (settings.json: 10 s) fails open.
MAX_COMMAND_LEN = 16384
# Heredocs on one simple command above this: none of its bodies is data (they are read as code).
MAX_HEREDOC_OPENERS = 32
# Command readings (spec audit-hook-hardening, section 3): distinct command starts per command above this, and
# code text (nvim `-c '!cmd'`, heredoc bodies) still present at the depth below, cannot be classified: blocked as
# unclassified_command.
MAX_READINGS = 8
MAX_CODE_DEPTH = 3
# Characters every parse of one analysis may read in total, nested texts included (spec audit-shell-lexer, S10).
MAX_LEX_CHARS = 8 * MAX_COMMAND_LEN

DIRECT_BINARIES = {"vitest", "jest", "mocha", "playwright", "eslint", "prettier", "tsc", "biome", "stylelint"}

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
LOCAL_HOST = re.compile(r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|[a-z0-9-]+)(:\d+)?(/|\s|$)")
URL = re.compile(r"https?://[^\s'\"]+")


class Readings(namedtuple("Readings", "texts reasons complete starts", defaults=((),))):
    """Every plausible reading of one simple command (spec audit-hook-hardening, section 3.2; audit-shell-lexer,
    section 4.2): read over the words of the parser.

    texts: normalized segments, primary first, deduplicated; reasons: a frozenset of "prefix_readings" and
    "readings_cap"; complete: False when readings_cap was hit (texts is then empty); starts: the word index where
    each reading starts, the same order as `texts`. (A `collections.namedtuple`, not a `typing.NamedTuple`: the
    `typing` import alone cost the hook about 3 ms in every call.)"""
    __slots__ = ()


def _wrapper(bs="", vs="", opt="", ns="", amb="", bl="", vl="", ol="", nl="", numeric=False, dash=False):
    """The flag grammar of one wrapper (spec audit-shell-lexer, section 4.2): short flags as strings of letters,
    long flags as space separated names. bs/bl boolean; vs/vl take a value (attached or the next word); opt/ol
    take an attached value only; ns/nl end the wrapper without a command (`sudo -l`); amb is a short flag that is
    both a no-command flag and a value flag (`sudo -h`); numeric: `-10` is a flag; dash: a lone `-` is a flag."""
    return (frozenset(bs), frozenset(vs), frozenset(opt), frozenset(ns), frozenset(amb), frozenset(bl.split()),
            frozenset(vl.split()), frozenset(ol.split()), frozenset(nl.split()), numeric, dash)


_WRAPPERS = {
    "sudo": _wrapper(
        bs="AbEHknPSsi", vs="CDgpRrTtUu", ns="elvKV", amb="h",
        bl="preserve-env login shell set-home non-interactive background stdin askpass preserve-groups "
           "reset-timestamp",
        vl="user group chdir chroot close-from host prompt role type command-timeout other-user",
        nl="edit list validate remove-timestamp version help"),
    # `env -S STRING` runs code: the wrapper stays the head (the string is the argument of task 4)
    "env": _wrapper(bs="i0v", vs="uCP", ns="S", bl="ignore-environment null debug", vl="unset chdir",
                    nl="split-string", dash=True),
    "nice": _wrapper(vs="n", vl="adjustment", nl="help version", numeric=True),
    "time": _wrapper(bs="pavq", vs="fo", bl="portability append verbose quiet", vl="format output"),
    "stdbuf": _wrapper(vs="ioe", vl="input output error"),
    "ionice": _wrapper(bs="t", vs="cn", ns="pPu", bl="ignore", vl="class classdata", nl="pid pgid uid"),
    "xargs": _wrapper(
        bs="0rtpxo", vs="adEILnPs", opt="eil",
        bl="null no-run-if-empty verbose interactive exit open-tty",
        vl="arg-file delimiter max-args max-procs max-chars process-slot-var",
        ol="replace max-lines eof", nl="show-limits version help"),
    "watch": _wrapper(bs="dtbegcpwx", vs="nq", ns="hv", bl="no-title beep errexit chgexit color precise no-wrap exec",
                      vl="interval equexit", ol="differences", nl="help version"),
    "command": _wrapper(bs="p", ns="vV"),
    "exec": _wrapper(bs="cl", vs="a"),
}
# Prefixes with no flags of their own: the next word is the command.
_PLAIN_PREFIXES = frozenset({"rtk", "proxy", "builtin", "noglob", "nocorrect", "-", "nohup"})
# Interpreter launchers (review fix B2, HD4): `NAME [global flags] run [flags] COMMAND`: COMMAND is the program that
# runs, so `uv run python - <<EOF` is a Python body and `uv run bash -c 'x'` a shell one. (global flags, `run` flags)
_LAUNCHERS = {
    "uv": (
        _wrapper(bs="qvnhV", vl="directory project config-file cache-dir python-preference color",
                 bl="quiet verbose no-cache offline no-progress no-config native-tls no-python-downloads help version "
                    "managed-python no-managed-python"),
        _wrapper(bs="qvnhsmU", vs="piPfCc",  # (`-p` is `--python`: it takes a value)
                 bl="all-extras no-dev only-dev no-editable exact no-env-file isolated active no-sync locked frozen "
                    "no-project all-packages upgrade reinstall refresh script gui-script module quiet verbose no-cache "
                    "offline no-progress no-config native-tls no-python-downloads no-default-groups all-groups "
                    "no-build no-binary no-build-isolation compile-bytecode no-install-project no-install-workspace "
                    "managed-python no-managed-python",
                 vl="extra no-extra group no-group only-group env-file with with-editable with-requirements package "
                    "python index default-index index-url extra-index-url find-links upgrade-package "
                    "reinstall-package config-setting constraint override resolution prerelease exclude-newer "
                    "link-mode refresh-package no-install-package index-strategy keyring-provider directory project "
                    "config-file cache-dir python-preference color")),
    "poetry": (
        _wrapper(bs="vqnhV", vs="CP", bl="verbose quiet no-interaction no-ansi ansi no-plugins no-cache help version",
                 vl="directory project"),
        _wrapper(bs="vqh", bl="verbose quiet help")),
    "pdm": (
        _wrapper(bs="vqIVh", vs="c", bl="verbose quiet ignore-python pep582 version help", vl="config"),
        _wrapper(bs="vqsjh", bl="verbose quiet site-packages json help", vl="venv", ns="l", nl="list")),
    "hatch": (
        _wrapper(bs="vqh", vs="e", bl="verbose quiet interactive no-interactive color no-color help",
                 vl="env project data-dir cache-dir config"),
        _wrapper(bs="h", vs="ix", bl="help ignore-compat", vl="include exclude"),
        # `hatch env run [-e ENV] -- COMMAND`: a second subcommand word before the same program
        ("env", "run", _wrapper(bs="h", vs="eix", bl="help ignore-compat", vl="env include exclude filter"))),
    "pipenv": (
        _wrapper(bs="qvh", bl="quiet verbose help bare clear site-packages", vl="python venv pypi-mirror"),
        _wrapper(bs="qvh", bl="quiet verbose help system deploy", vl="python")),
    "rye": (
        _wrapper(bs="qvh", bl="quiet verbose help version", vl="env-file"),
        _wrapper(bs="qvh", bl="quiet verbose help", vl="pyproject env-file", ns="l", nl="list")),
    "conda": (
        _wrapper(bs="qvyhV", bl="quiet verbose yes help version no-plugins"),
        _wrapper(bs="vh", vs="npa", bl="no-capture-output live-stream dev debug-wrapper-scripts verbose help",
                 vl="name prefix cwd attach")),
    "pixi": (
        _wrapper(bs="vqh", bl="verbose quiet help version color", vl="manifest-path"),
        _wrapper(bs="h", vs="e", bl="help frozen locked no-install as-is no-lockfile-update force-activate "
                                    "auto-install clean-env", vl="manifest-path environment tls-no-verify")),
}
_LAUNCHERS["mamba"] = _LAUNCHERS["micromamba"] = _LAUNCHERS["conda"]  # the same `run [-n NAME] COMMAND` grammar


def _flag_step(tokens: list[str], i: int, spec) -> "tuple[list[int], list[int], bool]":
    """One word of a wrapper's flags: (positions where the command starts, positions of the next flag word,
    whether the wrapper ends without a command). A flag the table does not know gives two next positions, with
    and without a value (N3)."""
    bs, vs, opt, ns, amb, bl, vl, ol, nl, numeric, dash = spec
    tok = tokens[i]
    if tok == "--":
        return [i + 1], [], False
    if tok == "-":
        return ([], [i + 1], False) if dash else ([i], [], False)
    if not tok.startswith("-"):
        return [i], [], False
    if tok.startswith("--"):
        name, eq, _ = tok[2:].partition("=")
        if name in nl:
            return [], [], True
        if name in bl or name in ol or (eq and name in vl):
            return [], [i + 1], False
        if name in vl:
            return [], [i + 2], False
        return [], ([i + 1] if eq else [i + 1, i + 2]), False
    if numeric and tok[1:].isdigit():
        return [], [i + 1], False
    for j in range(1, len(tok)):
        c = tok[j]
        if c in ns:
            return [], [], True
        if c in bs:
            continue
        if c in opt:
            return [], [i + 1], False
        if c in vs:
            return [], [i + 1 if j + 1 < len(tok) else i + 2], False
        if c in amb:
            return [], [i + 1 if j + 1 < len(tok) else i + 2], True
        return [], [i + 1, i + 2], False
    return [], [i + 1], False


def _wrapper_steps(tokens: list[str], p: int, spec) -> list[int]:
    """Positions where the command of the wrapper at `tokens[p]` can start, the strict reading first. `p` itself
    stands for "the wrapper is the command" (`sudo -l`, N5). Each word is visited once: linear."""
    n = len(tokens)
    ends: list[int] = []
    nocmd = False
    seen: set[int] = set()
    stack = [p + 1]
    while stack:
        i = min(stack.pop(), n)
        if i in seen:
            continue
        seen.add(i)
        if i >= n:
            ends.append(n)
            continue
        starts, nexts, none = _flag_step(tokens, i, spec)
        nocmd = nocmd or none
        for s in starts:
            ends.append(min(s, n))
        stack.extend(reversed(nexts))
    out: list[int] = []
    for e in ends + ([p] if nocmd else []):
        if e not in out:
            out.append(e)
    return out


def _launcher_steps(tokens: list[str], p: int, glob, run, sub=None) -> list[int]:
    """Positions where the command of the launcher at `tokens[p]` (`uv [flags] run [flags] COMMAND`) can start, the
    strict reading first, or `[]` when the launcher is the command (no `run` subcommand: `uv sync`). A flag the
    tables do not know gives two readings, like a wrapper's (N3). `sub`: `(word, word, flags)`, a two-word
    subcommand that runs a command too (`hatch env run`). Each (word, phase) is visited once."""
    n = len(tokens)
    ends: list[int] = []
    nocmd = False
    seen: set = set()
    stack = [(p + 1, 0)]
    while stack:
        i, phase = stack.pop()
        i = min(i, n)
        if (i, phase) in seen:
            continue
        seen.add((i, phase))
        if i >= n:
            if phase:
                ends.append(n)
            continue
        starts, nexts, none = _flag_step(tokens, i, (sub[2] if phase == 2 else run) if phase else glob)
        if phase:
            nocmd = nocmd or none
            ends.extend(min(s, n) for s in starts)
        else:
            stack.extend((s + 1, 1) for s in reversed(starts) if s < n and tokens[s] == "run")
            if sub is not None:
                stack.extend((s + 2, 2) for s in reversed(starts)
                             if s + 1 < n and tokens[s] == sub[0] and tokens[s + 1] == sub[1])
        stack.extend((q, phase) for q in reversed(nexts))
    out: list[int] = []
    for e in ends + ([p] if nocmd else []):
        if e not in out:
            out.append(e)
    return out


def _program_name(token: str) -> str:
    """N2: the name a word gives the program it names: the last component of a path whose last component is a
    known program (`/usr/bin/docker`, `~/.local/bin/mise`), and a zsh `=name` without its `=`. `./mvnw` stays."""
    if token[:1] == "=" and len(token) > 1 and "/" not in token:
        return token[1:]
    if "/" in token:
        last = token.rsplit("/", 1)[-1]
        if last in KNOWN_HEADS:
            return last
    return token


def _prefix_steps(tokens: list[str], p: int) -> list[int]:
    """Positions that can follow the prefix at `tokens[p]` (the words of one simple command, quotes removed), or
    `[]` when `p` starts the command; `p` in the result means the prefix is also the command itself.

    Prefixes: env assignments after a wrapper; the wrappers of `_WRAPPERS` with their flag grammar (an option the
    table does not know yields two readings, fail closed); the flagless prefixes of `_PLAIN_PREFIXES`; zsh
    `repeat N`; `timeout [options] DURATION` (every GNU form); `mise [global flags] exec|x [...] --` (cut up to
    the `--`). Program names go through `_program_name`. Every step moves forward, so a search over positions
    ends."""
    if p >= len(tokens):
        return []
    raw = tokens[p]
    if shell.ASSIGNMENT.match(raw):
        return [p + 1]
    tok = _program_name(raw)
    if tok in _PLAIN_PREFIXES:
        return [p + 1]
    spec = _WRAPPERS.get(tok)
    if spec is not None:
        return _wrapper_steps(tokens, p, spec)
    launcher = _LAUNCHERS.get(tok)
    if launcher is not None:
        return _launcher_steps(tokens, p, *launcher)
    if tok == "repeat":
        return [min(p + 2, len(tokens))]
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


def _command_starts(tokens: list[str]) -> tuple[list[int], bool]:
    """Token positions where a command can start after the prefixes, primary first then ascending, and whether
    more than MAX_READINGS distinct starts were found (then the list is empty). Each position is visited once:
    linear in the number of tokens, no recursion."""
    steps: dict[int, list[int]] = {}
    starts: set[int] = set()
    stack = [0]
    while stack:
        p = stack.pop()
        if p in steps:
            continue
        following = _prefix_steps(tokens, p)
        if p in following:  # a prefix that is also the command (`sudo -l docker ...`)
            starts.add(p)
            following = [q for q in following if q != p]
        steps[p] = following
        if following:
            stack.extend(reversed(following))
        else:
            starts.add(p)
        if len(starts) > MAX_READINGS:
            return [], True
    primary = 0
    while steps[primary]:
        primary = steps[primary][0]  # the first step of each position: the strict reading
    return [primary] + sorted(s for s in starts if s != primary), False


def _word_readings(words) -> Readings:
    """`_token_readings` of the words of a simple command (`Word.text`: quotes removed, expansions as written)."""
    return _token_readings([w.text for w in words])


def _token_readings(tokens: list[str]) -> Readings:
    """The readings of one simple command from its words: drops the prefixes of `_prefix_steps`; path-prefixed Lua
    tools (`./.luarocks/bin/busted` -> `busted`); `luarocks [global flags] test` -> `luarocks test`; and docker
    compose global flags (`docker compose -f x.yml up` -> `docker compose up`). When the prefix shape is ambiguous
    (`timeout -s KILL "$T" cmd`), every plausible reading is returned, the first is the primary one. More than
    MAX_READINGS distinct starts: incomplete."""
    starts, capped = _command_starts(tokens)
    if capped:
        return Readings([], frozenset({"readings_cap"}), False)
    try:
        texts, starts = _distinct_texts(tokens, starts)
    except _FormsCap:  # a docker command whose options read too many ways: not classified (level B)
        return Readings([], frozenset({"readings_cap"}), False)
    reasons = frozenset({"prefix_readings"}) if len(texts) > 1 else frozenset()
    return Readings(texts, reasons, True, tuple(starts))


def command_readings(segment: str) -> Readings:
    """The readings of the first simple command of `segment`, read with the shell parser (public entry for the
    tests and the heredoc rules). Text the parser rejects: no reading and the reason `lex_error`."""
    try:
        script = shell.parse(segment, shell.Budget(MAX_LEX_CHARS))
    except shell.ShellError:
        return Readings([], frozenset({"lex_error"}), False)
    for site in shell.iter_sites(script):
        return _word_readings(site.cmd.words)
    return _word_readings(())


def _distinct_texts(tokens: list[str], starts: list[int]) -> tuple[list[str], list[int]]:
    """The distinct normalized texts of the readings and the word index where each one starts (same order; a start
    that reads two ways, `docker --unknown-flag x`, appears twice)."""
    own: list[str] = []
    kept: list[int] = []
    for start in starts:
        for text in _finish_strip(list(tokens[start:])):
            if text not in own:
                own.append(text)
                kept.append(start)
    return own, kept


# docker(1) and docker compose: the options before the subcommand (B2 item 7). `value`: take a value (attached with
# `=` or as the next word); `boolean`: do not. An option that is in neither is read both ways (fail closed).
_DOCKER_OPTIONS = (
    frozenset({"--config", "-c", "--context", "-H", "--host", "-l", "--log-level", "--tlscacert", "--tlscert",
               "--tlskey"}),
    frozenset({"-D", "--debug", "--tls", "--tlsverify", "-v", "--version", "-h", "--help"}))
_COMPOSE_OPTIONS = (
    frozenset({"-f", "--file", "-p", "--project-name", "--profile", "--env-file", "--project-directory", "--ansi",
               "--parallel", "--progress", "-H", "--host", "--context", "-c", "-l", "--log-level", "--tlscacert",
               "--tlscert", "--tlskey"}),
    frozenset({"--compatibility", "--dry-run", "--all-resources", "--verbose", "--no-ansi", "--skip-hostname-check",
               "--tls", "--tlsverify", "-v", "--version", "-h", "--help", "-D", "--debug"}))
# `docker container VERB` is `docker VERB` (the management form of the lifecycle commands and of the reads)
_CONTAINER_VERBS = {"run": "run", "start": "start", "stop": "stop", "restart": "restart", "rm": "rm", "kill": "kill",
                    "exec": "exec", "create": "create", "ls": "ps", "ps": "ps", "logs": "logs", "inspect": "inspect",
                    "port": "port"}
MAX_DOCKER_FORMS = 8


class _FormsCap(Exception):
    """More readings of the options before the docker subcommand than MAX_DOCKER_FORMS: the real one may be among
    the dropped ones, so the command is not classified (`readings_cap`, level B)."""


def _option_ends(tokens: list[str], i: int, options) -> list[int]:
    """The positions where the first word that is not an option can be, after the options of `tokens` from `i`
    (`options`: `(value, boolean)`), in ascending order: more than one when an option is not known."""
    value, boolean = options
    ends: list[int] = []
    seen: set[int] = set()
    stack = [i]
    n = len(tokens)
    while stack:
        j = stack.pop()
        if j in seen:
            continue
        seen.add(j)
        if j >= n:
            ends.append(n)
            continue
        tok = tokens[j]
        if not tok.startswith("-") or tok == "-":
            ends.append(j)
            continue
        if tok == "--":
            ends.append(j + 1)
            continue
        name, eq, _ = tok.partition("=")
        if name in value:
            stack.append(j + 1 if eq else j + 2)
        elif name in boolean:
            stack.append(j + 1)
        elif not tok.startswith("--") and len(tok) > 2:
            # a cluster of short options, read the way pflag reads it: a boolean letter goes on, a value letter takes
            # the rest of the word (`-Hhost`, `-l=info`) or the next word (`-Dl info`), an unknown letter is read both ways
            for k in range(1, len(tok)):
                letter = "-" + tok[k]
                if letter in value:
                    stack.append(j + 1 if k + 1 < len(tok) else j + 2)
                    break
                if letter not in boolean:
                    stack.extend([j + 1, j + 2])
                    break
            else:
                stack.append(j + 1)
        else:
            stack.extend([j + 1] if eq else [j + 1, j + 2])
    if len(ends) > MAX_DOCKER_FORMS:
        raise _FormsCap()
    return sorted(ends)


def _docker_forms(tokens: list[str]) -> list[list[str]]:
    """The normalized words of a `docker` or `docker-compose` reading (the options before the subcommand dropped,
    `docker-compose` as `docker compose`, `docker container restart` as `docker restart`), one form per reading of
    an option the table does not know."""
    n = len(tokens)
    forms: list[list[str]] = []
    options = _COMPOSE_OPTIONS if tokens[0] == "docker-compose" else _DOCKER_OPTIONS
    for e in _option_ends(tokens, 1, options):
        word = tokens[e] if e < n else ""
        if tokens[0] == "docker-compose":
            forms.append(["docker", "compose"] + tokens[e:])
        elif word == "compose":
            forms.extend(["docker", "compose"] + tokens[e2:] for e2 in _option_ends(tokens, e + 1, _COMPOSE_OPTIONS))
        elif word == "container" and e + 1 < n and tokens[e + 1] in _CONTAINER_VERBS:
            forms.append(["docker", _CONTAINER_VERBS[tokens[e + 1]]] + tokens[e + 2:])
        elif word in ("image", "builder") and e + 1 < n and tokens[e + 1] == "build":
            forms.append(["docker", "build"] + tokens[e + 2:])
        else:
            forms.append(["docker"] + tokens[e:])
    out: list[list[str]] = []
    for form in forms:
        if form not in out:
            out.append(form)
            if len(out) > MAX_DOCKER_FORMS:
                raise _FormsCap()
    return out


def _finish_strip(tokens: list[str]) -> list[str]:
    """The normalized texts of one reading (more than one when `docker` has an option this does not know)."""
    # npx vitest / pnpm exec eslint / pnpm vitest -> vitest / eslint
    if tokens:
        tokens[0] = _program_name(tokens[0])  # /usr/bin/docker -> docker, =docker -> docker (N2)
    if tokens and tokens[0] in {"npx", "bunx"}:
        tokens.pop(0)
    elif len(tokens) > 1 and tokens[0] in {"pnpm", "yarn", "bun"}:
        if tokens[1] in {"exec", "x", "dlx"}:
            del tokens[:2]
        elif tokens[1] in DIRECT_BINARIES:
            tokens.pop(0)
    if tokens:
        tokens[0] = _program_name(tokens[0])  # ./.luarocks/bin/busted -> busted
    if tokens and tokens[0] == "luarocks":
        j = _skip_luarocks_flags(tokens, 1)
        if j < len(tokens) and tokens[j] == "test":
            tokens = ["luarocks"] + tokens[j:]  # luarocks --lua-version 5.1 test -> luarocks test
    if tokens and tokens[0] in ("docker", "docker-compose"):  # docker -H h compose -f x.yml up -> docker compose up
        return [" ".join(form) for form in _docker_forms(tokens)]
    return [" ".join(tokens)]


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


# Global options of git(1) (spec audit-shell-lexer, A2): what is skipped before the subcommand.
_GIT_VALUE_LONG = frozenset({"git-dir", "work-tree", "namespace", "config-env", "attr-source"})
_GIT_BOOL_LONG = frozenset(
    "paginate no-pager bare no-replace-objects no-lazy-fetch no-optional-locks no-advice literal-pathspecs "
    "glob-pathspecs noglob-pathspecs icase-pathspecs exec-path list-cmds html-path man-path info-path version help"
    .split())
_GIT_BOOL_SHORT = frozenset({"-p", "-P", "-v", "-h"})


def _git_args(tokens: list[str]) -> list[str] | None:
    """The words after the `git` head of a reading (`tokens` start at the reading), or None when it has none."""
    for k, tok in enumerate(tokens):
        if _program_name(tok) == "git":
            return tokens[k + 1:]
        if k >= 2:  # a prefix of the normalization (`npx`, `pnpm exec`) is at most two words
            break
    return None


def _git_walk(args: list[str]) -> "tuple[list[int], list[tuple[int, bool, bool]]]":
    """The words after `git` read as global options and a subcommand: (the indices where the subcommand can be, the
    configurations given on the command line). The global options are skipped first, `--` ends them, and an option
    this does not know is read both ways, with and without a value (fail closed: every reading counts). A
    configuration is `(index, attached, from_env)`: `-c key=value` is the word at `index`; `--config-env=key=VAR`
    is the text after `--config-env=` of that word (`attached`), `--config-env key=VAR` the next word. Each word is
    visited once."""
    n = len(args)
    seen: set[int] = set()
    stack = [0]
    verbs: list[int] = []
    configs: list[tuple[int, bool, bool]] = []
    while stack:
        i = stack.pop()
        if i in seen or i >= n:
            continue
        seen.add(i)
        tok = args[i]
        if tok == "--":
            if i + 1 < n:
                verbs.append(i + 1)
        elif not tok.startswith("-"):
            verbs.append(i)
        elif tok in ("-C", "-c"):
            if tok == "-c" and i + 1 < n:
                configs.append((i + 1, False, False))
            stack.append(i + 2)
        elif tok.startswith("--"):
            option, eq, _ = tok[2:].partition("=")
            if option in _GIT_VALUE_LONG:
                if option == "config-env" and (eq or i + 1 < n):
                    configs.append((i, True, True) if eq else (i + 1, False, True))
                stack.append(i + 1 if eq else i + 2)
            elif option in _GIT_BOOL_LONG:
                stack.append(i + 1)
            else:
                stack.extend([i + 1] if eq else [i + 1, i + 2])
        elif tok in _GIT_BOOL_SHORT:
            stack.append(i + 1)
        else:
            stack.extend([i + 1, i + 2])
    return verbs, configs


def _git_has_subcommand(args: list[str], name: str) -> bool:
    """True when `name` can be the git subcommand of `args` (the words after `git`): one reading of the global
    options (`_git_walk`) with `name` as the subcommand is enough. `commit` as the value of `--grep` or as a
    config key is not the subcommand."""
    return any(args[i] == name for i in _git_walk(args)[0])


_GIT_ALIAS_DEPTH = 5


def _has_git_config_names(cmd, env) -> bool:
    """The command (prefix assignments) or the text (values) sets a `GIT_CONFIG_*` variable."""
    return any(w.text.startswith("GIT_CONFIG_") for w in cmd.assignments) or any(n.startswith("GIT_CONFIG_") for n in env)


def _sq_dequote(text: str, i: int) -> "tuple[str, int] | None":
    """One shell-quoted item of git's `GIT_CONFIG_PARAMETERS` (`sq_dequote_step`): `'...'`, where an embedded quote is
    written `'\\''` (and `'\\!'`), starting at `text[i]`. (the item, the index after it) or None."""
    if text[i:i + 1] != "'":
        return None
    out: list[str] = []
    i += 1
    n = len(text)
    while i < n:
        j = text.find("'", i)
        if j < 0:
            return None
        out.append(text[i:j])
        i = j + 1
        if text[i:i + 2] in ("\\'", "\\!") and text[i + 2:i + 3] == "'":
            out.append(text[i + 1])
            i += 3
            continue
        return "".join(out), i
    return None


def _config_parameters(text: str) -> "tuple[list[tuple[str, str]], bool]":
    """`GIT_CONFIG_PARAMETERS` as git reads it (`parse_config_env_list`): blank-separated items, each `'key=value'`
    (the old form) or `'key'='value'` / `'key'` (git 2.31 and later). (the pairs, whether something did not
    parse: then the configuration is not known)."""
    pairs: list[tuple[str, str]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] in " \t\n":
            i += 1
            continue
        item = _sq_dequote(text, i)
        if item is None:
            return pairs, True
        key, i = item
        if text[i:i + 1] == "=":
            value = _sq_dequote(text, i + 1)
            if value is None:
                return pairs, True
            pairs.append((key, value[0]))
            i = value[1]
        else:
            key, _, val = key.partition("=")
            pairs.append((key, val))
        if i < n and text[i] not in " \t\n":
            return pairs, True
    return pairs, False


def _split_cmdline(value: str) -> "list[str] | None":
    """An alias value split the way git does (`split_cmdline`): blanks separate words, `'...'`, `"..."` and a
    backslash quote, and the quotes are removed. None when a quote or an escape does not close."""
    words: list[str] = []
    current: list[str] = []
    started = False
    quote = ""
    i, n = 0, len(value)
    while i < n:
        c = value[i]
        i += 1
        if quote:
            if c == quote:
                quote = ""
            elif c == "\\":
                if quote == "'" or i >= n:  # (not sure how every git reads it inside single quotes: unresolved)
                    return None
                current.append(value[i])
                i += 1
            else:
                current.append(c)
        elif c in "'\"":
            quote = c
            started = True
        elif c == "\\":
            if i >= n:
                return None
            current.append(value[i])
            i += 1
            started = True
        elif c in " \t\n":
            if current or started:
                words.append("".join(current))
                current, started = [], False
        else:
            current.append(c)
    if quote:
        return None
    if current or started:
        words.append("".join(current))
    return words


def _git_env_config(cmd, env) -> "tuple[list[tuple[str, str]], bool]":
    """Configuration given to git through the environment, as (key, value) pairs, and whether some of it cannot be
    known: `GIT_CONFIG_COUNT` with `GIT_CONFIG_KEY_n` / `GIT_CONFIG_VALUE_n` and `GIT_CONFIG_PARAMETERS`
    (`'alias.p=push' 'k=v'`), from the prefix assignments of the command and the values the text gives its names."""
    values: dict = {}
    for word in cmd.assignments:
        first = word.parts[0]
        target = _assignment_target(first.text) if first.kind == "lit" else None
        if target is not None and target[0].startswith("GIT_CONFIG_") and target[1] == "=":
            values[target[0]] = None if word.dynamic else frozenset({word.text[target[2]:]})
    for name, known in env.items():
        if name.startswith("GIT_CONFIG_") and name not in values:
            values[name] = known
    pairs: list[tuple[str, str]] = []
    unresolved = False
    params = values.get("GIT_CONFIG_PARAMETERS", frozenset())
    if params is None:
        unresolved = True
    for value in params or ():
        if value is None:
            unresolved = True
            continue
        found, bad = _config_parameters(value)
        pairs.extend(found)
        unresolved = unresolved or bad
    counts = values.get("GIT_CONFIG_COUNT", frozenset())
    if counts is None:
        return pairs, True
    for count in counts:
        if count is None or not count.isdigit() or int(count) > MAX_VALUE_CANDIDATES:
            unresolved = True
            continue
        for i in range(int(count)):
            keys, vals = values.get(f"GIT_CONFIG_KEY_{i}"), values.get(f"GIT_CONFIG_VALUE_{i}")
            if not keys or not vals or None in keys or None in vals:
                unresolved = True
                continue
            pairs.extend((k, v) for k in keys for v in vals)
    return pairs, unresolved


def _git_aliases(cmd, args: list[str], env) -> "tuple[dict[str, list[str]], bool]":
    """The aliases a `git` reading defines for itself (`-c alias.p=push`, `--config-env=alias.p=VAR`, the
    `GIT_CONFIG_*` variables): lower-cased name -> values, and whether some configuration cannot be known (a
    key or value made by an expansion)."""
    verbs, configs = _git_walk(args)
    pairs: list[tuple[str, str]] = []
    unresolved = False
    for index, attached, from_env in configs:
        text = args[index].partition("=")[2] if attached else args[index]
        key, _, value = text.partition("=")
        if "$" in text or "`" in text:
            unresolved = True
            continue
        if from_env:  # the value is the name of an environment variable: its value from the command or the text
            known = None
            for word in cmd.assignments:
                first = word.parts[0]
                target = _assignment_target(first.text) if first.kind == "lit" else None
                if target is not None and target[0] == value and target[1] == "=" and not word.dynamic:
                    known = frozenset({word.text[target[2]:]})
            known = known if known is not None else env.get(value)
            if not known or None in known:
                if key.lower().startswith("alias."):
                    unresolved = True
                continue
            pairs.extend((key, v) for v in known)
        else:
            pairs.append((key, value))
    if _has_git_config_names(cmd, env):
        extra, more = _git_env_config(cmd, env)
        pairs.extend(extra)
        unresolved = unresolved or more
    aliases: dict[str, list[str]] = {}
    for key, value in pairs:
        if key.lower().startswith("alias."):
            aliases.setdefault(key[6:].lower(), []).append(value)
    return aliases, unresolved


class _AssignView:
    """What the git configuration readers need of a command: its `assignments` (the prefix assignments, and the
    `NAME=value` operands of `env`, `sudo` and `doas` before the program)."""

    __slots__ = ("assignments",)

    def __init__(self, assignments):
        self.assignments = assignments


def _wrapper_assignments(cmd, tokens: list[str], words: list, s: int) -> "tuple[object, bool]":
    """Part E, V4: `cmd` with the `NAME=value` words among `tokens[:s]` (the wrapper operands before the program at
    `s`) added to its prefix assignments, and whether some such word cannot be read (its name is made by an
    expansion): then the configuration is not known."""
    extra: list = []
    unreadable = False
    for i in range(min(s, len(tokens))):
        text = tokens[i]
        word = words[i] if i < len(words) else None
        if shell.ASSIGNMENT.match(text) and not text.startswith("-"):
            extra.append(word if word is not None else shell.Word((shell.Part("lit", text),), (0, 0), False))
        elif "=" in text and not text.startswith("-") and ("$" in text.partition("=")[0] or "`" in text.partition("=")[0]):
            unreadable = True
    if not extra:
        return cmd, unreadable
    return _AssignView(tuple(cmd.assignments) + tuple(extra)), unreadable


def _git_alias_variants(variants: list, cmd, env) -> "tuple[list, list[str], bool]":
    """B2 item 6: `git -c alias.p=push p` runs `git push`. For every variant that reads a `git` with aliases of its
    own: more variants with the alias name replaced by its value (an alias of an alias too, up to
    _GIT_ALIAS_DEPTH), the shell code of the `!` aliases (the value, then the rest of the words), and whether an
    alias could not be resolved or the chain goes on (level B)."""
    out = list(variants)
    code: list[str] = []
    seen: set = set()
    unresolved = False
    for tokens, words, readings in variants:
        if not readings.complete:
            continue
        for s in readings.starts:
            if s >= len(tokens) or _program_name(tokens[s]) != "git":
                continue
            args = tokens[s + 1:]
            cmd_s, unreadable = _wrapper_assignments(cmd, tokens, words, s)  # `env VAR=v git`, `sudo VAR=v git` (V4)
            if not (any(t == "-c" or t.startswith("--config-env") for t in args) or _has_git_config_names(cmd_s, env)):
                unresolved = unresolved or (unreadable and any(t.startswith("GIT_CONFIG") for t in tokens[:s]))
                continue
            aliases, more = _git_aliases(cmd_s, args, env)
            unresolved = unresolved or more or unreadable
            if not aliases:
                continue
            frontier = [(tokens, words)]
            for _ in range(_GIT_ALIAS_DEPTH):
                following = []
                for toks, wds in frontier:
                    for v in _git_walk(toks[s + 1:])[0]:
                        at = s + 1 + v
                        for value in aliases.get(toks[at].lower(), ()):
                            if value.startswith("!"):
                                code.append((value[1:] + " " + " ".join(_sh_quote(t) for t in toks[at + 1:])).strip())
                                continue
                            pieces = _split_cmdline(value)
                            if pieces is None:  # a quote that does not close: git refuses it or reads it its own way
                                unresolved = True
                                continue
                            new_tokens = toks[:at] + pieces + toks[at + 1:]
                            if not pieces or tuple(new_tokens) in seen:
                                continue
                            seen.add(tuple(new_tokens))
                            if len(seen) > MAX_VALUE_CANDIDATES:
                                return out, code, True
                            new_words = wds[:at] + [None] * len(pieces) + wds[at + 1:]
                            out.append((new_tokens, new_words, _token_readings(new_tokens)))
                            following.append((new_tokens, new_words))
                frontier = following
                if not frontier:
                    break
            else:
                unresolved = True  # an alias chain longer than the limit
    return out, code, unresolved


def _is_git_commit(tokens: list[str]) -> bool:
    """`tokens` (a reading, from its head) is a `git commit`: `commit` is the subcommand."""
    args = _git_args(tokens)
    return args is not None and _git_has_subcommand(args, "commit")


_STDIN_FILE_FLAGS = {"git": [["-F", "-"], ["--file", "-"], ["--file=-"]], "gh": [["--body-file", "-"], ["-F", "-"], ["--body-file=-"]]}
_GIT_CONFIG = re.compile(r"(?:^|\s)-c\s*\S*(?:alias|core)\.")  # -c alias.x=!cmd / core.pager=cmd run code
# `$(cat <<EOF ...)` is data only as the value of these options, right before the `$(` (and its `"`).
# (the reading must also be a `git commit`, `_is_git_commit`: `commit` as the subcommand, not as an argument)
_GIT_MESSAGE_VALUE = re.compile(r"^git\s.*(?:\s-[A-Za-z]*m|\s--message)(?:=|\s+)?\"?$")
_GH_MESSAGE_VALUE = re.compile(
    r"^gh\s+(?:pr|issue|release)\s+(?:create|edit|comment|review)\b.*(?:\s(?:--body|-b|--title|-t))(?:=|\s+)?\"?$"
)
_GH_MESSAGE_CMD = re.compile(r"^gh\s+(?:pr|issue|release)\s+(?:create|edit|comment|review)\b")


_SINK_HEADS = frozenset({"cat", "tee", "git", "gh"})
# Receivers whose heredoc body is a program of another language, never shell (spec audit-shell-lexer, HD4, X7).
_FOREIGN_INTERPRETERS = frozenset({"node", "ruby", "perl", "lua", "luajit", "php"})
# SQL / DSL clients: a heredoc or here-string body is a query, not shell (HD4, review fix B2), unless it asks the
# client to run a command (`_query_escape`).
_QUERY_CLIENTS = frozenset({"sqlite3", "psql", "mysql", "mariadb", "cypher-shell"})
_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh", "mksh", "ash"})
# The heads `_classify_segment` and its regexes (TEST_RUNNERS, LOAD_RUNNERS, LINT, TYPECHECK) look for. `mvnw` and
# `gradlew` are left out on purpose: `./mvnw` is matched with its `./`.
_CLASSIFIED_HEADS = frozenset(
    "docker docker-compose git gh mise nvim curl http wget pytest py.test jest vitest mocha ava go cargo mvn gradle "
    "npm pnpm yarn bun bunx npx make just playwright uv poetry python python3 dotnet rspec phpunit busted luarocks "
    "eslint ruff golangci-lint gofmt goimports ktlint detekt checkstyle prettier biome stylelint luacheck selene "
    "stylua treefmt tsc mypy pyright k6 artillery locust jmeter vegeta ab wrk".split())
# N2: every program name the hook's tables use, computed from them (wrappers, sinks, shells and interpreters,
# classified heads, direct binaries, path tools), so a path-prefixed program is recognized by its last component.
KNOWN_HEADS = frozenset(_WRAPPERS) | frozenset(_LAUNCHERS) | _PLAIN_PREFIXES | {"repeat", "timeout", "eval", "trap", "su"} | _SHELLS \
    | _SINK_HEADS | _FOREIGN_INTERPRETERS | _QUERY_CLIENTS | _CLASSIFIED_HEADS | DIRECT_BINARIES | _PATH_TOOLS


def _head_of(text: str) -> str:
    """The first word of a normalized reading ('' when it is empty)."""
    first = text.split(None, 1)
    return first[0] if first else ""


def _has_sink_head(readings: Readings) -> bool:
    """True when some reading starts with `cat`, `tee`, `git` or `gh`."""
    return any(_head_of(text) in _SINK_HEADS for text in readings.texts)


def _has_substitution(cmd) -> bool:
    """H1: a command, process or backtick substitution in the words, assignments or redirections of the command."""
    for word in (*cmd.assignments, *cmd.words):
        for _ in word.scripts():
            return True
    for redirect in cmd.redirects:
        if redirect.target is not None:
            for _ in redirect.target.scripts():
                return True
    return False


def _clean_sink_words(site, readings: Readings | None = None, *, any_dynamic: bool = False) -> list[str] | None:
    """Words of the single clean reading of a command, or None (H2): exactly one complete reading, and no
    expansion in the assignments, in the words up to the head (inclusive) or in a redirection before the head
    (in any word or redirection when `any_dynamic`)."""
    cmd = site.cmd
    if readings is None:
        readings = _word_readings(cmd.words)
    if not readings.complete or len(readings.texts) != 1:
        return None
    words = readings.texts[0].split()
    if not words:
        return None
    head = cmd.words[readings.starts[0]]  # the head word: the reading is not empty, so a word starts it
    if any(w.dynamic for w in cmd.assignments) or any(w.dynamic for w in cmd.words[:readings.starts[0] + 1]):
        return None
    for redirect in cmd.redirects:
        if redirect.target is not None and redirect.target.dynamic and (any_dynamic or redirect.target.span[0] < head.span[0]):
            return None
    if any_dynamic and any(w.dynamic for w in cmd.words):
        return None
    return words


def _sole_substitution(word):
    """(literal text before it, the `$(...)` part) when the word is nothing but one command substitution,
    optionally inside double quotes and after literal text (`$(..)`, `"$(..)"`, `--message="$(..)"`), else None."""
    *head, last = word.parts
    if any(p.kind not in ("lit", "sq") for p in head):
        return None
    prefix = "".join(p.text for p in head)
    if last.kind == "cmdsub":
        return prefix, last
    if last.kind == "dq" and len(last.inner) == 1 and last.inner[0].kind == "cmdsub" \
            and last.text.endswith(last.inner[0].text):
        return prefix + last.text[:len(last.text) - len(last.inner[0].text)], last.inner[0]
    return None


def _message_value_of(site, reasons: set[str]) -> bool:
    """H3: the site is a lone `cat <<EOF` that makes up the whole value (after its option) of a `git commit -m` or
    of a `gh` message option; the outer command has to read one clean way, like any heredoc prefix."""
    cmd, outer, word = site.cmd, site.substitution, site.sub_word
    if outer is None or word is None or not all(r.heredoc is not None for r in cmd.redirects):
        return False
    sole = _sole_substitution(word)
    if sole is None:
        return False
    prefix, part = sole
    pipelines = part.script.pipelines if part.script is not None else ()
    if len(pipelines) != 1 or len(pipelines[0].commands) != 1 or pipelines[0].commands[0] is not cmd:
        return False
    outer_words = outer.cmd.words
    index = next((k for k, w in enumerate(outer_words) if w is word), None)
    if index is None:
        return False
    tokens = [w.text for w in outer_words[:index]]
    if prefix:
        tokens.append(prefix)
    readings = _token_readings(tokens)
    clean = readings.complete and len(readings.texts) == 1 and not any(
        w.dynamic for w in (*outer.cmd.assignments, *outer_words[:index])) and not any(
        r.target is not None and r.target.dynamic and r.target.span[0] < word.span[0] for r in outer.cmd.redirects)
    if not clean:
        if _has_sink_head(readings):
            reasons.add("heredoc_unclean_prefix")
        return False
    text = readings.texts[0]
    if _GIT_CONFIG.search(text):
        return False
    if _GIT_MESSAGE_VALUE.match(text) and _is_git_commit(tokens[readings.starts[0]:]):
        return True
    return bool(_GH_MESSAGE_VALUE.match(text))


def _lone_cat(part, quoted: bool = True):
    """The `Simple` of a substitution that is nothing but `cat` with one heredoc (quoted delimiter when `quoted`):
    no argument, no assignment, no other redirection. Else None."""
    pipelines = part.script.pipelines if part.script is not None else ()
    if len(pipelines) != 1 or len(pipelines[0].commands) != 1:
        return None
    cmd = pipelines[0].commands[0]
    if not isinstance(cmd, shell.Simple) or cmd.assignments or [w.text for w in cmd.words] != ["cat"] \
            or any(w.dynamic for w in cmd.words):
        return None
    if len(cmd.redirects) != 1 or cmd.redirects[0].heredoc is None or (quoted and not cmd.redirects[0].heredoc.quoted):
        return None
    return cmd


def _assignment_value_of(site) -> bool:
    """B2 item 4: the site is a lone `cat <<'EOF'` that makes up the whole value of an assignment (`BODY=$(cat <<'EOF'
    ... EOF)`, also in quotes, after `local` / `export` / `declare`): its output only goes into the variable, so the
    body is text. What the variable is used for later is seen by the values (`_known_values`): a head or a code
    string made of it is classified with this text."""
    cmd, outer, word = site.cmd, site.substitution, site.sub_word
    if outer is None or word is None:
        return False
    sole = _sole_substitution(word)
    if sole is None or _lone_cat(sole[1]) is not cmd:
        return False
    target = _assignment_target(sole[0])
    if target is None or target[1] != "=" or target[2] != len(sole[0]):
        return False
    if any(w is word for w in outer.cmd.assignments):
        return True
    head = outer.cmd.words[0] if outer.cmd.words else None
    return head is not None and not head.dynamic and head.text in _DECLARE_BUILTINS \
        and any(w is word for w in outer.cmd.words[1:])


def _heredoc_is_data(site, readings: Readings, disqualified: bool, reasons: set[str], grouped: bool = False) -> bool:
    """True when the heredocs of this simple command are provably data (spec audit-shell-lexer, section 5).

    Data sinks: top-level, unpiped `cat`/`tee`; `git commit -F -` and `gh pr|issue|release create|edit|comment|
    review -F -` (no `-c alias.*`/`core.*`); and a lone `$(cat <<EOF ...)` that is the value of `git commit -m` or
    of a `gh` message option. Only a clean prefix counts (`_clean_sink_words`) and no substitution may sit in the
    command itself. A body kept because the prefix is not clean, while some reading is a sink head, adds
    `heredoc_unclean_prefix` to `reasons`."""
    cmd = site.cmd
    if disqualified or sum(1 for r in cmd.redirects if r.heredoc is not None) > MAX_HEREDOC_OPENERS:
        return False
    words = _clean_sink_words(site, readings)
    if words and words[0] in ("git", "gh"):
        words = _clean_sink_words(site, readings, any_dynamic=True)
    if words is None:
        if _has_sink_head(readings):
            reasons.add("heredoc_unclean_prefix")
        return False
    if _has_substitution(cmd):
        return False
    text = " ".join(words)
    head = words[0]
    if head == "git" and _GIT_CONFIG.search(text):
        return False
    if site.substitution is not None:
        return words == ["cat"] and (_message_value_of(site, reasons) or _assignment_value_of(site))
    if head in ("git", "gh"):
        pairs = _STDIN_FILE_FLAGS[head]
        has_flag = any(words[k:k + len(p)] == p for p in pairs for k in range(len(words)))
        if head == "git":
            return has_flag and _is_git_commit([w.text for w in cmd.words][readings.starts[0]:])
        return has_flag and bool(_GH_MESSAGE_CMD.match(text))
    if head not in ("cat", "tee") or site.stages != 1:
        return False
    # top level, or (HD3, revised by the user) inside a function body or `{ }` group that is no pipeline stage, with
    # its own output redirection: `mk() { cat > "$1/f" <<EOF ... }`. A subshell, a substitution and a pipeline stay code.
    return site.top_level or (grouped and any(r.op in _OUTPUT_OPS and r.heredoc is None for r in cmd.redirects))


_OUTPUT_OPS = frozenset({">", ">>", ">|", "&>", "&>>"})


def _grouped_commands(script) -> set:
    """The ids of the simple commands that sit, one pipeline stage each, in function bodies and `{ }` groups that are
    themselves a whole pipeline of the top-level script (nested groups included)."""
    found: set = set()
    stack = [(script, False)]
    while stack:
        current, inside = stack.pop()
        for pipeline in current.pipelines:
            if len(pipeline.commands) != 1:
                continue
            cmd = pipeline.commands[0]
            if isinstance(cmd, shell.Compound):
                if cmd.kind in ("group", "function"):
                    stack.extend((body, True) for body in cmd.bodies)
            elif inside:
                found.add(id(cmd))
    return found


def _high_fd(redirect) -> bool:
    """A redirection with a file descriptor of 3 or more (or a named one), as source or as `>&N` target."""
    if redirect.fd is not None and not (redirect.fd.isdigit() and redirect.fd.lstrip("0") in ("", "1", "2")):
        return True
    if redirect.op in (">&", "<&") and redirect.target is not None:
        text = redirect.target.text
        return text.isdigit() and text.lstrip("0") not in ("", "1", "2")
    return False


def _heredocs_disqualified(script, items) -> bool:
    """The whole-script reasons to read every heredoc body as code (spec audit-shell-lexer, section 5): a head
    `mkfifo`, a `coproc`, an `exec` with redirections only, a function named like a data sink, a descriptor of 3 or
    more. Each one can route a body somewhere the data rules did not look."""
    for site, tokens, readings in items:
        cmd = site.cmd
        if any(_head_of(text).rsplit("/", 1)[-1] == "mkfifo" for text in readings.texts):
            return True
        if cmd.redirects and tokens and tokens[-1] == "exec" and all(
                t in _PLAIN_PREFIXES or t in _WRAPPERS or t.startswith("-") for t in tokens):
            return True
        if any(_high_fd(r) for r in cmd.redirects):
            return True
    for comp in shell.iter_compounds(script):
        if comp.kind == "coproc" or (comp.kind == "function" and comp.name in _SINK_HEADS):
            return True
        if any(_high_fd(r) for r in comp.redirects):
            return True
    return False


def _receiver_name(name: str) -> bool:
    """A program name the data rules trust: a data sink, a data reader, an interpreter of another language or a
    SQL / DSL client."""
    return name in _SINK_HEADS or name in _STDIN_DATA or name in _FOREIGN_INTERPRETERS or name in _QUERY_CLIENTS \
        or name.startswith("python")


_LOOPS = frozenset({"for", "while", "until", "select"})
_FOREVER = 1 << 62


def _rebound_spans(script, items) -> list:
    """Review fix D1, H2 and H3: where the text rebinds the name of a program the data rules trust (a heredoc sink, a
    here-string data reader, a foreign interpreter or SQL client), so the name no longer says what runs: a function
    of that name, `hash -p PATH NAME` / zsh `hash NAME=PATH`, bash `enable -f`, or an assignment to `PATH` / zsh
    `path`. The result is the `(start, end)` source spans in which a command reads every body and here-string as
    code. A prefix assignment (`PATH=x cmd`) covers its own command; a rebinding in the shell itself covers the text
    after it, from the start of the text when a loop holds it (the loop may run it before the commands that come
    first), and up to the end of the subshell, the substitution or the pipeline stage that holds it."""
    spans: list = []
    compounds = list(shell.iter_compounds(script))
    for comp in compounds:
        if comp.kind == "function" and comp.name and _receiver_name(comp.name.rsplit("/", 1)[-1]):
            spans.append((comp.span[0], _FOREVER))
    for site, tokens, readings in items:
        cmd = site.cmd
        prefix = any(_name_prefix(word.text) in ("PATH", "path") for word in cmd.assignments)
        pure = False
        for start in readings.starts:
            head = _program_name(tokens[start]) if start < len(tokens) else ""
            rest = tokens[start + 1:]
            if head == "hash" and any(t.startswith("-") and "p" in t[1:] or "=" in t for t in rest):
                pure = True
            elif head == "enable" and any(t.startswith("-") and "f" in t[1:] for t in rest):
                pure = True
            elif head in _DECLARE_BUILTINS and any(  # `export PATH=...`, `typeset -x path=(...)`
                    _name_prefix(t) in ("PATH", "path") and t[len(_name_prefix(t)):][:1] in ("=", "+") for t in rest):
                pure = True
        if prefix and cmd.words:
            spans.append(cmd.span)
        elif prefix or pure:
            lo, hi = cmd.span[0], _FOREVER
            for comp in compounds:
                if comp.span[0] <= cmd.span[0] < comp.span[1]:
                    if comp.kind in _LOOPS:
                        lo = 0
                    elif comp.kind == "subshell":
                        hi = min(hi, comp.span[1])
            if site.stages > 1:
                hi = min(hi, cmd.span[1])
            if site.substitution is not None:
                hi = min(hi, site.substitution.cmd.span[1])
            spans.append((lo, hi))
    return spans


# Values of variables assigned in the text itself (spec audit-shell-lexer, V1-V4, section 4.4). They name the
# receiver of a heredoc (`PY=python3; $PY - <<EOF`), the program of a command (`D=docker; $D restart x`) and fill
# the variables of a code string (`T="docker compose"; zsh -c "$T down"`).
MAX_VALUE_CANDIDATES = 16
# Budget characters charged, besides the length the parser charges, for every text analyzed and for every value
# combination read, so the fan-out of values and code strings stays inside the CPU budget (fails closed).
TEXT_COST = 128
VARIANT_COST = 64
_NAME_READERS = frozenset({"read", "getopts", "mapfile", "readarray", "printf", "print", "vared", "let", "unset"})
_CODE_LOADERS = frozenset({"eval", "source", "."})
_OPTION_SETTERS = frozenset({"setopt", "unsetopt", "emulate", "set"})
_DECLARE_BUILTINS = shell.DECLARE_BUILTINS
_VALUE_HEADS = _DECLARE_BUILTINS | _NAME_READERS | _CODE_LOADERS | _OPTION_SETTERS
_SPLIT_OPTION = "shwordsplit"
_UNKNOWN = frozenset({None})  # `None` inside a set of values: the environment (or another source) may give another


def _is_name(text: str) -> bool:
    """A shell variable name (no regex: this module compiles its patterns at import, in every hook call)."""
    return text.isascii() and text.isidentifier()


def _name_prefix(text: str) -> str:
    """The variable name `text` starts with (`NAME`, `NAME=v`, `NAME[i]`, zsh `NAME?prompt`), else ''."""
    n = 0
    for ch in text:
        if ch == "_" or (ch.isascii() and ch.isalnum()):
            n += 1
        else:
            break
    name = text[:n]
    return name if _is_name(name) else ""


class _Values(dict):
    """`name -> frozenset of values | None` (see `_known_values`), and what is known about the text as a whole.
    `opaque`: the text runs code that may assign anything (`eval`, `source`); `split_unknown`: the splitting of
    unquoted values is not the default one (`IFS`, `setopt shwordsplit`, `emulate sh`); `here`: the names this text
    assigns; `firsts`: name -> offset of its first unconditional top-level assignment; `loops`: (name, start, end)
    where a name is set for sure: the bodies of the `for` / `select` loops that set it and the `&&` chains that
    follow an assignment. A `None` among the values of a name is the environment: a use before the first
    unconditional assignment keeps it as a possible value (`at`)."""

    __slots__ = ("opaque", "split_unknown", "here", "firsts", "loops", "soft", "_index", "_late_values")

    def __init__(self):
        super().__init__()
        self.opaque = False
        self.split_unknown = False
        self.here = frozenset()
        self.firsts = {}
        self.loops = ()
        self.soft = frozenset()  # names whose only unknown value (the `None`) is a command substitution (`R=$(x)`)
        self._index = None  # (names with no unconditional assignment, [(offset, name)] sorted): built by `at`
        self._late_values = None  # name -> its values with the environment's one added (None stays None)

    def copy_flags(self, other: "_Values") -> None:
        self.opaque = other.opaque
        self.split_unknown = other.split_unknown
        self.soft = other.soft

    def defined(self, name: str, pos: int) -> bool:
        first = self.firsts.get(name)
        if first is not None and first < pos:
            return True
        return any(n == name and lo <= pos <= hi for n, lo, hi in self.loops)

    def at(self, pos: int) -> "_Values":
        """The values at a site that starts at offset `pos`: a name of this text that is not (unconditionally)
        assigned before that point may still hold what the environment gave it."""
        if self._index is None:  # built once: the names are found by offset, not tested one by one at every site
            never = [n for n in self.here if n not in self.firsts]
            ordered = sorted((first, n) for n, first in self.firsts.items() if n in self.here)
            self._index = (never, ordered, [first for first, _ in ordered])
            self._late_values = {n: None if self[n] is None else self[n] | _UNKNOWN for n in self.here}
        never, ordered, offsets = self._index
        lo, hi = 0, len(offsets)  # (a binary search: the first assignment at or after `pos`)
        while lo < hi:
            mid = (lo + hi) // 2
            if offsets[mid] < pos:
                lo = mid + 1
            else:
                hi = mid
        late = never + [n for _, n in ordered[lo:]]
        if self.loops:
            covered = {n for n, lo, hi in self.loops if lo <= pos <= hi}
            if covered:
                late = [n for n in late if n not in covered]
        if not late:
            return self
        view = _Values()
        view.update(self)
        view.copy_flags(self)
        view.soft = self.soft - frozenset(late)  # the environment's value is not a substitution's
        view.update({n: self._late_values[n] for n in late})
        return view


_NO_VALUES = _Values()


def _walk_parts(parts):
    """Every part of `parts`, the ones inside double quotes, expansions and arrays included (not the scripts)."""
    stack = list(parts)
    while stack:
        part = stack.pop()
        yield part
        stack.extend(part.inner)
        for word in part.elements:
            stack.extend(word.parts)


def _tree_words(script):
    """Every word of the tree (assignments, words, redirection targets, the words of compound commands), nested
    scripts included, and the expansion parts of the heredoc bodies as one pseudo word list each (`None`, parts)."""
    for site in shell.iter_sites(script):
        cmd = site.cmd
        for word in (*cmd.assignments, *cmd.words):
            yield word, word.parts
        for redirect in cmd.redirects:
            if redirect.target is not None:
                yield redirect.target, redirect.target.parts
            if redirect.heredoc is not None:
                yield None, redirect.heredoc.expansions
    for comp in shell.iter_compounds(script):
        for word in comp.words:
            yield word, word.parts
        for redirect in comp.redirects:
            if redirect.target is not None:
                yield redirect.target, redirect.target.parts
            if redirect.heredoc is not None:
                yield None, redirect.heredoc.expansions


def _tree_parts(script):
    """Every part of every word of the tree and of the expansions of heredoc bodies (see `_tree_words`)."""
    for _, parts in _tree_words(script):
        yield from _walk_parts(parts)


def _single_quoted_substitution(parts) -> bool:
    """The quoted or escaped text of `parts` (siblings: the parts of a word or of an expansion) holds `$(` or a
    backquote: `'a$(b)'`, `\\$\\(b\\)`, `"\\$(b)"`. (A backslash makes one part per escaped character.)"""
    text = "".join(p.text for p in parts if p.kind in ("sq", "ansi", "lit"))
    if "$(" in text or "`" in text:
        return True
    for part in parts:
        if part.kind == "dq" and not part.inner and ("$(" in part.text or "`" in part.text):
            return True
        if part.inner and _single_quoted_substitution(part.inner):
            return True
        if any(_single_quoted_substitution(word.parts) for word in part.elements):
            return True
    return False


def _param_assigned(text: str) -> "str | None":
    """The name `${N:=v}`, `${N=v}` (zsh `${N::=v}`) assigns, else None."""
    if not text.startswith("${"):
        return None
    i = 2
    if text[i:i + 1] == "(":  # zsh flags
        close = text.find(")", i)
        if close < 0:
            return None
        i = close + 1
    name = _name_prefix(text[i:])
    if not name:
        return None
    return name if text[i + len(name):].startswith(("=", ":=", "::=")) else None


def _assignment_target(text: str) -> "tuple[str, str, int] | None":
    """(name, operator, index where the value starts) of `NAME=`, `NAME+=` (operator `+=`) and `NAME[...]=`
    (operator `[`) at the start of `text`, else None."""
    eq = text.find("=")
    if eq <= 0:
        return None
    head = text[:eq]
    if head.endswith("+") and _is_name(head[:-1]):
        return head[:-1], "+=", eq + 1
    if _is_name(head):
        return head, "=", eq + 1
    bracket = head.find("[")
    if bracket > 0 and _is_name(head[:bracket]):
        return head[:bracket], "[", eq + 1
    return None


def _variable_of(text: str) -> "str | None":
    """The name when `text` is exactly `$NAME` or `${NAME}`, else None."""
    if text.startswith("${") and text.endswith("}") and _is_name(text[2:-1]):
        return text[2:-1]
    if text.startswith("$") and _is_name(text[1:]):
        return text[1:]
    return None


class _ValueScan:
    """The working state of `_known_values`: what each kind of command or compound adds to the values, one method
    per source of values, and `finish`, which merges them with the outer text's."""

    __slots__ = ("source", "values", "unknown", "firsts", "chains", "var_heads", "soft", "result")

    def __init__(self, source):
        self.source = source
        self.values: dict[str, set[str]] = {}
        self.unknown: set[str] = set()
        self.firsts: dict[str, int] = {}
        self.chains: list = []  # (name, start, end) of the assignments that hold up to the end of their `&&` chain
        self.var_heads: list[str] = []
        self.soft: set[str] = set()  # names given a command substitution as their whole value
        self.result = _Values()

    def add(self, name: str, text: "str | None") -> None:
        if text is None:
            self.unknown.add(name)
        else:
            self.values.setdefault(name, set()).add(text)

    def effective(self, site) -> "tuple[int, int | None] | None":
        """Where the assignments of a simple command reach the shell itself: a top-level command that is no
        pipeline stage and not in the background. `(offset, None)`: from the offset on, whatever the flow; after
        `&&` they run only when the left side succeeded, so `(offset, end)`: up to `end`, the end of the chain of
        `&&` that follows (the next `;`, newline, `|`, `||` or `&`). After `||` they may not run at all: None."""
        source = self.source
        if source is None or not site.top_level or site.stages != 1:
            return None
        start, end = site.cmd.span
        i = start
        while i > 0 and source[i - 1] in " \t\n\\":
            i -= 1
        before = source[max(i - 2, 0):i]
        if before == "||":
            return None
        n = len(source)
        j = end
        while j < n and source[j] in " \t":
            j += 1
        if source[j:j + 1] == "&" and source[j:j + 2] != "&&":
            return None
        if before != "&&":
            return start, None
        while j < n:  # the chain of `&&` the assignment starts
            c = source[j]
            if c in ";\n|" or (c == "&" and source[j + 1:j + 2] != "&"):
                break
            j += 2 if c == "&" else 1
        return start, j

    def take(self, word, reach, own: bool) -> None:
        first = word.parts[0]
        target = _assignment_target(first.text) if first.kind == "lit" else None
        if target is None:
            return
        name, operator, start = target
        if name == "IFS" and own:  # (a prefix assignment of a command only changes that command)
            self.result.split_unknown = True
        if operator != "=":  # `N+=v` appends and `N[i]=v` is an element: not a value this reads
            self.unknown.add(name)
            return
        if reach is not None:
            if reach[1] is None:
                self.firsts[name] = min(reach[0], self.firsts.get(name, reach[0]))
            else:
                self.chains.append((name, reach[0], reach[1]))
        if len(word.parts) == 2 and word.parts[1].kind == "array" and start == len(first.text):
            texts = []
            for element in word.parts[1].elements:
                text = None if any(True for _ in element.scripts()) else element.text
                self.add(name, text)
                texts.append(text)
            if None not in texts:  # zsh expands an unquoted array to all its elements: `$D` is the joined words
                self.add(name, " ".join(texts))
        elif any(True for _ in word.scripts()):
            # `NAME=$(cat <<'EOF' ... EOF)`: the value is the body (a substitution drops the trailing newlines)
            sole = _sole_substitution(word)
            cat = _lone_cat(sole[1]) if sole is not None and sole[0] == first.text[:start] else None
            if cat is None and _whole_substitution(word, len(first.text) == start):
                self.soft.add(name)  # `R=$(which x)`: unknown, but only because of a command substitution
            else:
                self.add(name, cat.redirects[0].heredoc.body.rstrip("\n") if cat is not None else None)
        else:
            self.add(name, first.text[start:] + "".join(p.text for p in word.parts[1:]))

    def scan_sites(self, script) -> None:
        """The prefix assignments, and the builtins and variable heads that give a name a value."""
        for site in shell.iter_sites(script):
            cmd = site.cmd
            pure = not cmd.words
            for word in cmd.assignments:
                self.take(word, self.effective(site) if pure else None, pure)
            if pure:
                continue
            name = _plain_variable(cmd.words[0])
            if name is not None:
                self.var_heads.append(name)
            tokens = [w.text for w in cmd.words]
            if _VALUE_HEADS.isdisjoint(tokens):
                continue
            readings = _token_readings(tokens)
            for s in readings.starts:
                self.builtin(site, _program_name(tokens[s]), cmd.words[s + 1:])

    def builtin(self, site, head: str, args) -> None:
        """What the builtin `head` of a reading does to the values, with its arguments `args` (words)."""
        if head in _DECLARE_BUILTINS:
            self.declare(site, args)
        elif head in _NAME_READERS:
            for w in args:
                n = _name_prefix(w.text)
                if n:
                    self.unknown.add(n)
                    if n == "IFS":
                        self.result.split_unknown = True
        elif head in _CODE_LOADERS:
            self.result.opaque = True
        elif head == "emulate":
            if any(w.text in ("sh", "ksh", "bash") for w in args):
                self.result.split_unknown = True
        elif head in _OPTION_SETTERS:  # set, setopt, unsetopt
            self.option_setter(head, args)

    def declare(self, site, args) -> None:
        """`declare` / `typeset` / `local` / `export` / `readonly`: the assignments in the arguments, and the names
        a name reference (`-n`) makes unknown."""
        pos = self.effective(site)
        for word in args:
            self.take(word, pos, True)
        if any(w.text.startswith("-") and "n" in w.text for w in args):  # a name reference
            for w in args:
                if not w.text.startswith("-"):
                    target, _, ref = w.text.partition("=")
                    self.unknown.update(n for n in (_name_prefix(target), _name_prefix(ref)) if n)

    def option_setter(self, head: str, args) -> None:
        """`set`, `setopt`, `unsetopt`: the word splitting option, and `set -A NAME` (an array)."""
        texts = [w.text for w in args]
        for k, text in enumerate(texts):
            if _SPLIT_OPTION in text.lower().replace("_", "").replace("-", ""):
                self.result.split_unknown = True
            if head == "set" and text in ("-A", "+A") and k + 1 < len(texts):  # an array: `set -A D x y`
                n = _name_prefix(texts[k + 1])
                if n:
                    self.unknown.add(n)

    def scan_loops(self, script) -> list:
        """The `for` / `select` variables: their lists are values, and the body of a loop sets its name for sure."""
        loops: list = []
        for comp in shell.iter_compounds(script):
            if comp.kind in ("for", "select") and comp.name:
                if not comp.words:  # `for x; do` walks the positional parameters
                    self.unknown.add(comp.name)
                for word in comp.words:
                    self.add(comp.name, None if any(True for _ in word.scripts()) else word.text)
                for body in comp.bodies:
                    if body.pipelines:
                        loops.append((comp.name, body.span[0], body.span[1]))
        return loops

    def scan_param_assignments(self, script) -> None:
        """`${N:=v}` and `${N=v}` assign: the name is unknown."""
        if self.source is None or "${" in self.source:
            for part in _tree_parts(script):
                if part.kind == "param":
                    name = _param_assigned(part.text)
                    if name is not None:
                        self.unknown.add(name)
                        if name == "IFS":
                            self.result.split_unknown = True

    def finish(self, inherited, loops: list) -> "_Values":
        """The `_Values` of the scan, merged with the `inherited` ones of the outer text."""
        result = self.result
        values, unknown, soft = self.values, self.unknown, self.soft
        result.here = frozenset(values) | frozenset(unknown) | frozenset(soft)
        for name, vals in values.items():
            result[name] = frozenset(vals)
        soft_only = {n for n in soft if n not in unknown}
        for name in soft_only:  # the values it has, and the unknown one that a substitution gives
            result[name] = frozenset(values.get(name, ())) | _UNKNOWN
        for name in unknown:
            result[name] = None
        for name, outer in (inherited or {}).items():  # (what the outer text could not know stays unknown, not soft)
            mine = result.get(name, False)
            if mine is False:
                result[name] = outer
            elif mine is not None:
                result[name] = None if outer is None else mine | outer
                if outer is None or None in outer:
                    soft_only.discard(name)
        result.soft = frozenset(soft_only)
        result.opaque = result.opaque or bool(getattr(inherited, "opaque", False))
        result.split_unknown = result.split_unknown or bool(getattr(inherited, "split_unknown", False))
        for name in self.var_heads:  # a head that may be a builtin that assigns (`R=read; $R X`) makes any name unknown
            known = result.get(name, False)
            if known is None or (known is not False and any(v is not None and _head_of(v) in _VALUE_HEADS for v in known)):
                result.opaque = True
        if result.opaque:
            for name in result:
                result[name] = None
            result.soft = frozenset()
        result.firsts = self.firsts
        result.loops = tuple(loops + self.chains)
        return result


def _known_values(script, inherited=None, source=None) -> "_Values":
    """Every value assigned to each variable anywhere in `script` (V3: the union, whatever the flow), merged with
    the `inherited` ones of the text that holds this one (a name unknown on either side is unknown). A name that
    gets a value from anywhere else (a substitution, `read`, `mapfile`, `printf -v`, zsh `print -v` and `vared`,
    `+=`, a subscript, `${N:=v}`, `set -A`, a name reference, a `for` over a substitution) maps to None, and a name
    never assigned is absent: both are unknown (V1). The builtins are matched against the normalized heads of the
    readings of each command (`command read`, `builtin export`). A text that runs `eval`, `source` or `.` is
    `opaque`: every name it assigns is unknown. `source`, the text itself, gives the offsets of the first
    unconditional top-level assignments (`_Values.at`)."""
    scan = _ValueScan(source)
    scan.scan_sites(script)
    loops = scan.scan_loops(script)
    scan.scan_param_assignments(script)
    return scan.finish(inherited, loops)


def _values_of(script, inherited, cache: list, source=None) -> "_Values":
    """The values of the names of `script` for the program-name and code-string uses (V1-V4), computed once per
    analysis (`cache` holds the result of `_known_values`; `source` is the text of `script`)."""
    if not cache:
        cache.append(_known_values(script, inherited, source))
    return cache[0]


def _whole_substitution(word, plain_start: bool) -> bool:
    """The value of an assignment word is one command substitution and nothing else (`R=$(x)`, `R="$(x)"`,
    ``R=`x` ``), after a first part that is just `NAME=` (`plain_start`)."""
    if not plain_start or len(word.parts) != 2:
        return False
    part = word.parts[1]
    if part.kind in ("cmdsub", "backtick"):
        return True
    return part.kind == "dq" and len(part.inner) == 1 and part.inner[0].kind in ("cmdsub", "backtick") \
        and part.inner[0].text == part.text


def _is_dynamic_text(text: str) -> bool:
    """A word that names a program through an expansion or a pattern (`$1/x`, `` `which x` ``, `dock?r`)."""
    return "$" in text or "`" in text or "*" in text or "?" in text or "[" in text


def _plain_variable(word) -> "str | None":
    """The name when `word` is exactly `$NAME`, `${NAME}` or `"$NAME"` (no single quotes, no other part)."""
    if len(word.parts) != 1:
        return None
    part = word.parts[0]
    if part.kind == "dq" and len(part.inner) == 1 and part.inner[0].kind == "param" and part.inner[0].text == part.text:
        return _variable_of(part.text)
    return _variable_of(part.text) if part.kind == "param" else None


def _head_variants(tokens: list[str], words: list, readings: Readings, env: "_Values") -> "tuple[list, bool]":
    """N6/V1/V2/V4: when the program of the strict reading is a plain variable, one `(tokens, words, readings)` per
    known value, the value split at blanks in its place (an empty value leaves no word); `words` hold None where a
    word was made of a value. Only the program position counts (never an argument of a wrapper: `timeout "$T"
    docker ...` stays as it is). Also whether the program is unresolved: the name is assigned in the text (or the
    text runs `eval` / `source`) and its value is unknown, may also be the environment's, has more than
    MAX_VALUE_CANDIDATES values, or the splitting is not the default one; that is level B. A name that is only
    in the environment is not (N6, level A)."""
    if not readings.complete or not readings.starts:
        return [], False
    start = readings.starts[0]
    if start >= len(words) or words[start] is None:
        return [], False
    name = _plain_variable(words[start])
    if name is None:
        return [], False
    known = env.get(name, False)
    if known is False:
        return [], env.opaque
    if known is None:
        return [], True
    strings = sorted(v for v in known if v is not None)
    # an unknown value that only a command substitution gives (`R=$(which x)`) is N6: level A, not unresolved
    unresolved = (None in known and name not in env.soft) or env.split_unknown
    if len(strings) > MAX_VALUE_CANDIDATES:
        return [], True
    out = []
    for value in strings:
        pieces = value.split()
        new_tokens = tokens[:start] + pieces + tokens[start + 1:]
        new_words = words[:start] + [None] * len(pieces) + words[start + 1:]
        out.append((new_tokens, new_words, _token_readings(new_tokens)))
    return out, unresolved


_SPECIAL_PARAMS = "0123456789@*#?$!-"
_PARAM_UNSAFE_CHARS = frozenset("$`\\'\"{}()")
_GLOB_CHARS = frozenset("*?[")


def _param_candidates(body: str, env: "_Values") -> "list[str] | None":
    """The texts the parameter expansion `${body}` can give besides the value its name has in the environment
    (D1, H4): the word of `-`, `:-`, `=`, `:=`, `+`, `:+` (and `""` for the `+` forms and an empty word: the
    expansion may vanish), the replacement of `/pat/rep`, `//`, `/#`, `/%`, and the known values of the name (changed
    by the replacement when the pattern is literal). `[]` for a plain expansion or `?` / `:?`; None when it cannot be
    known (zsh flags, an indirection, a subscript, another operator, an expansion or a quote in the word)."""
    if body[:1] == "#":  # `${#X}` is a length, never a program
        return []
    if not body or body[0] in "!(":  # an indirection, zsh flags
        return None
    name = _name_prefix(body) or (body[0] if body[0] in _SPECIAL_PARAMS else "")
    if not name:
        return None
    rest = body[len(name):]
    if not rest:
        return []
    known = env.get(name) or ()
    values = sorted(v for v in known if v is not None)
    for op in (":-", ":=", "-", "="):
        if rest.startswith(op):
            word = rest[len(op):]
            return None if _PARAM_UNSAFE_CHARS & set(word) else [word, *values]
    for op in (":+", "+"):
        if rest.startswith(op):
            word = rest[len(op):]
            return None if _PARAM_UNSAFE_CHARS & set(word) else [word, ""]
    if rest[:1] == "?" or rest.startswith(":?"):
        return []
    if rest.startswith("/"):
        mode = rest[1:2] if rest[1:2] in ("/", "#", "%") else ""
        pattern, _, replacement = rest[1 + len(mode):].partition("/")
        if _PARAM_UNSAFE_CHARS & set(pattern + replacement):
            return None
        found = [replacement, *values]
        if pattern and not _GLOB_CHARS & set(pattern):
            for v in values:
                if mode == "#":
                    found.append(replacement + v[len(pattern):] if v.startswith(pattern) else v)
                elif mode == "%":
                    found.append(v[:len(v) - len(pattern)] + replacement if v.endswith(pattern) else v)
                else:
                    found.append(v.replace(pattern, replacement, -1 if mode == "/" else 1))
        return found
    return None


def _operator_texts(text: str, env: "_Values") -> "list[str] | None":
    """D1, H4: the texts a word made of expansions with an operator can become (`${PWD:+docker}`, `${X/ls/d}`,
    `/usr/bin/${B:-docker}`), the candidates of every `${...}` in it crossed, at most MAX_VALUE_CANDIDATES. `[]`
    when the text has no such expansion; None when some expansion cannot be known (level B for a program name)."""
    pieces: list = []
    last = i = 0
    while True:
        j = text.find("${", i)
        if j < 0:
            break
        k = text.find("}", j)
        if k < 0:
            return None
        body = text[j + 2:k]
        if "${" in body or "$(" in body or "`" in body:
            return None
        found = _param_candidates(body, env)
        if found is None:
            return None
        if found:
            pieces.append(text[last:j])
            pieces.append(found)
            last = k + 1
        i = k + 1
    if not pieces:
        return []
    pieces.append(text[last:])
    combos = [""]
    for n, piece in enumerate(pieces):
        combos = [c + o for c in combos for o in ([piece] if n % 2 == 0 else piece)]
        if len(combos) > MAX_VALUE_CANDIDATES:
            return None
    return combos


_SENTINEL = ("", "", "")  # stand-ins for the `{`, `}` and `,` of a quoted part of a word


def _has_brace_text(text: str) -> bool:
    """A brace expansion in the text of a word made of a value (`{a,b}`, `{1..3}`)."""
    return "{" in text and "}" in text and ("," in text or ".." in text)


def _brace_group(text: str) -> "tuple[int, int, list[str]] | None":
    """The first (outermost, leftmost) brace group of `text` that has a comma at its own level: (start, end,
    alternatives). A group without one (`{x}`, `{}`) stays literal."""
    i = text.find("{")
    while i >= 0:
        depth, commas, j = 0, [], i
        while j < len(text):
            c = text[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    break
            elif c == "," and depth == 1:
                commas.append(j)
            j += 1
        if j < len(text) and commas:
            cuts = [i, *commas, j]
            return i, j, [text[cuts[k] + 1:cuts[k + 1]] for k in range(len(cuts) - 1)]
        i = text.find("{", i + 1)
    return None


def _brace_words(word) -> "list[str] | None":
    """The words the brace expansion of an unquoted word makes (`{docker,restart}` is `docker` and `restart`), in
    the order bash gives them, or None when they cannot be known with certainty: an expanded part (or a `$'...'`
    that cannot be decoded), a range (`{1..3}`), or more than MAX_VALUE_CANDIDATES words. A quoted part (`{'git',
    push}`, `""{git,push}`, `{$'\\x67it',push}`) is text: the brace expansion runs before the quotes go, so its own
    braces and commas are not the expansion's (D1, M2)."""
    pieces: list[str] = []
    for p in word.parts:
        if p.kind == "lit":
            pieces.append(p.text)
        elif p.kind in ("sq", "ansi", "dq") and not p.dyn and not p.inner:
            pieces.append(p.text.replace("{", _SENTINEL[0]).replace("}", _SENTINEL[1]).replace(",", _SENTINEL[2]))
        else:
            return None
    text = "".join(pieces)
    if len(text) > 256:
        return None
    out: list[str] = []
    stack = [text]
    while stack:
        current = stack.pop()
        group = _brace_group(current)
        if group is None:
            if _has_brace_text(current):
                return None
            out.append(current)
        else:
            start, end, alternatives = group
            stack.extend(current[:start] + a + current[end + 1:] for a in reversed(alternatives))
        if len(out) + len(stack) > MAX_VALUE_CANDIDATES:
            return None
    return [w.replace(_SENTINEL[0], "{").replace(_SENTINEL[1], "}").replace(_SENTINEL[2], ",") for w in out]


def _param_unsafe(text: str, env: "_Values") -> bool:
    """A parameter expansion (`$X`, `${X:-y}`, `$1`, `${a[@]}`, `${!x}`) whose value is not the environment alone:
    positional or special parameters, arrays, indirections, a name this text assigns, or any name when the text
    runs `eval` / `source`."""
    body = text[2:-1] if text.startswith("${") and text.endswith("}") else text[1:]
    body = body.lstrip("#")
    name = _name_prefix(body)
    if not name or body[len(name):len(name) + 1] == "[":
        return True
    return env.opaque or (name in env and name not in env.soft)


def _head_unsafe(word, env: "_Values") -> bool:
    """A dynamic program name that cannot be left as level A: a part that cannot be decoded with certainty
    (`$'\\q'`), or an expansion that is not the environment alone (`_param_unsafe`)."""
    for part in _walk_parts(word.parts):
        if part.dyn or (part.kind == "param" and _param_unsafe(part.text, env)):
            return True
    return False


# The verb of git, docker and gh: the first word that is not an option nor the value of one. The names the hook
# blocks are the subcommands of git and the verbs of docker, so a word that may be one is level B when unresolved.
_VERB_PROGRAMS = frozenset({"git", "gh", "docker", "docker-compose"})
_BLOCKED_VERB_PROGRAMS = frozenset({"git", "docker", "docker-compose"})
_DOCKER_VALUE_OPTIONS = frozenset({
    "-f", "--file", "-p", "--project-name", "--profile", "--env-file", "--context", "-c", "--config", "-H", "--host",
    "-l", "--log-level", "--project-directory", "--ansi", "--parallel", "--progress", "--tlscacert", "--tlscert",
    "--tlskey"})


def _dynamic_at(tokens: list[str], words: list, i: int) -> bool:
    """The word at `i` is not a literal: an expansion, a pattern or a brace expansion (`words[i]` is None for a word
    made of a value: its text is checked)."""
    word = words[i] if i < len(words) else None
    if word is None:
        return _is_dynamic_text(tokens[i]) or _has_brace_text(tokens[i])
    return word.dynamic or word.has_glob or word.has_brace


def _verb_region(tokens: list[str], words: list, start: int) -> list[int]:
    """The positions of the words where the subcommand / verb of the `git`, `docker` or `gh` at `tokens[start]` can
    be: the words after the options (an option takes the next word as its value when it is a known value option),
    up to and including the first literal word (`compose` of docker goes on to the next one)."""
    program = _program_name(tokens[start])
    git = program == "git"
    out: list[int] = []
    n = len(tokens)
    i = start + 1
    while i < n:
        tok = tokens[i]
        if tok.startswith("-") and len(tok) > 1:
            if git:
                takes = tok in ("-C", "-c") or (tok.startswith("--") and tok[2:] in _GIT_VALUE_LONG)
            else:
                takes = tok in _DOCKER_VALUE_OPTIONS
            i += 2 if takes else 1
            continue
        out.append(i)
        if not _dynamic_at(tokens, words, i) and not (program == "docker" and tok in ("compose", "container")):
            break
        i += 1
    return out


def _region_dynamic(tokens: list[str], words: list, readings: Readings) -> bool:
    """Some word where the verb of a blocked program could be is not a literal."""
    for start in readings.starts:
        if start < len(tokens) and _program_name(tokens[start]) in _BLOCKED_VERB_PROGRAMS:
            if any(_dynamic_at(tokens, words, i) for i in _verb_region(tokens, words, start)):
                return True
    return False


def _verb_positions(tokens: list[str], words: list, readings: Readings) -> list[int]:
    """The dynamic words, in ascending order, where the verb of a git, docker or gh reading can be."""
    positions: list[int] = []
    for start in readings.starts:
        if start < len(tokens) and _program_name(tokens[start]) in _VERB_PROGRAMS:
            for i in _verb_region(tokens, words, start):
                if i not in positions and _dynamic_at(tokens, words, i):
                    positions.append(i)
    positions.sort()
    return positions


def _position_options(tokens: list[str], words: list, positions: list[int], env: "_Values") -> "list | None":
    """For each dynamic verb position, the texts it can have (its known values, the words of its brace expansion,
    or itself), or None when one cannot be known or the combinations pass MAX_VALUE_CANDIDATES."""
    options: list = []
    total = 1
    for i in positions:
        word = words[i] if i < len(words) else None
        if word is not None and word.has_brace:  # all the words of the expansion take the place of the word
            expanded = _brace_words(word)
            found = [" ".join(expanded)] if expanded is not None else [tokens[i]]
        else:
            found = _expand_values(tokens[i], env) if "$" in tokens[i] else [tokens[i]]
        if found is None:
            return None
        total *= len(found)
        if total > MAX_VALUE_CANDIDATES:
            return None
        options.append(found)
    return options


def _combination_words(tokens: list[str], words: list, positions: list[int], combo: list) -> "tuple[list, list, bool]":
    """The words of one combination of options: each position replaced by its option, split at blanks (the new words
    hold None). Also whether some position changed."""
    new_tokens: list[str] = []
    new_words: list = []
    changed = False
    prev = 0
    for i, option in zip(positions, combo):
        new_tokens.extend(tokens[prev:i])
        new_words.extend(words[prev:i])
        if option == tokens[i]:
            new_tokens.append(option)
            new_words.append(words[i] if i < len(words) else None)
        else:
            changed = True
            pieces = option.split()
            new_tokens.extend(pieces)
            new_words.extend([None] * len(pieces))
        prev = i + 1
    new_tokens.extend(tokens[prev:])
    new_words.extend(words[prev:])
    return new_tokens, new_words, changed


def _arg_variants(tokens: list[str], words: list, readings: Readings, env: "_Values") -> "tuple[list, bool]":
    """Item 2: the known values of the variables in the verb positions of git, docker and gh (`c=push; git $c`,
    `git ${c}sh`, `for a in stop start; do docker compose $a x; done`): one `(tokens, words, readings)` per
    combination. Also whether a dynamic word is still left where the verb of git or docker could be (a name
    without a known value, a pattern, a brace expansion, more than MAX_VALUE_CANDIDATES combinations, a
    non-default splitting): that is level B."""
    base = [(tokens, words, readings)]
    if not readings.complete:
        return base, False
    positions = _verb_positions(tokens, words, readings)
    if not positions:
        return base, False
    options = _position_options(tokens, words, positions, env)
    if options is None:
        return base, True
    combos: list = [[]]
    for found in options:
        combos = [c + [o] for c in combos for o in found]
    out = []
    unresolved = False
    substituted = False
    for combo in combos:
        new_tokens, new_words, changed = _combination_words(tokens, words, positions, combo)
        substituted = substituted or changed
        new_readings = _token_readings(new_tokens)
        if new_readings.complete and _region_dynamic(new_tokens, new_words, new_readings):
            unresolved = True
        out.append((new_tokens, new_words, new_readings))
    return out, unresolved or (substituted and env.split_unknown)


def _expand_values(text: str, env: dict) -> "list[str] | None":
    """V2/V4: a code string with the variables of known value (`$N`, `${N}`) replaced, one text per combination
    of values of the names in it (the shell that holds the string expands them before the inner one reads it).
    A name that may also hold something unknown (a `None` among its values) keeps its own text as one more
    candidate, which the text read next finds dynamic. None when there are more than MAX_VALUE_CANDIDATES
    combinations: the string is unknown."""
    if "$" not in text or not env:
        return [text]
    names: list[str] = []
    pieces: list = []  # literal text, or (name, source text) to replace
    i, last, n = 0, 0, len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "$":
            j = i + 1
            braced = j < n and text[j] == "{"
            if braced:
                j += 1
            k = j
            while k < n and (text[k].isalnum() or text[k] == "_") and text[k].isascii():
                k += 1
            name = text[j:k]
            end = k + 1 if braced and k < n and text[k] == "}" else k
            if (not braced or end > k) and _is_name(name) and env.get(name):
                pieces.append(text[last:i])
                pieces.append((name, text[i:end]))
                if name not in names:
                    names.append(name)
                last = i = end
                continue
        i += 1
    if not names:
        return [text]
    pieces.append(text[last:])
    options = {name: sorted(v for v in env[name] if v is not None) + ([None] if None in env[name] else [])
               for name in names}
    combos = 1
    for name in names:
        combos *= len(options[name])
        if combos > MAX_VALUE_CANDIDATES:
            return None
    chosen: list[dict] = [{}]
    for name in names:
        chosen = [{**c, name: v} for c in chosen for v in options[name]]
    return ["".join(p if k % 2 == 0 else (c[p[0]] if c[p[0]] is not None else p[1]) for k, p in enumerate(pieces))
            for c in chosen]


_QUERY_SHELL_LINES = ("system ", "pager ", "edit ", "\\p ", "\\system")
# psql meta-commands (and the mysql ones) that run a program: the shell (`\!`), the editor (`\e`, `\ef`, `\ev`, which
# `\setenv` can point at any program), mysql `edit`; and the ones that send their output to a pipe when the argument
# starts with `|` (`\g |cmd`, `\g (format=csv) |cmd`, `\o '|cmd'`, `\w |cmd`).
_QUERY_RUNNERS = frozenset({"!", "e", "edit", "ef", "ev", "setenv", "system"})
_QUERY_PIPERS = frozenset({"g", "gx", "o", "out", "w", "|"})


def _foreign_kind(text: str) -> "str | None":
    """`interpreter` when the first word of `text` names an interpreter of another language (`python`,
    `python3.12`, `node`, ...), `query` for a SQL / DSL client (`sqlite3`, `psql`, ...), else None."""
    name = _head_of(text).rsplit("/", 1)[-1]
    if name.startswith("python"):
        # python, python3, python3.12; not python-config or pythonic
        return None if name[6:].strip("0123456789.") else "interpreter"
    if name in _FOREIGN_INTERPRETERS:
        return "interpreter"
    return "query" if name in _QUERY_CLIENTS else None


def _query_escape(text: str) -> bool:
    """A text a SQL / DSL client reads (a body, a here-string, an argument of `psql -c`) that asks the client to run
    a program (review fix D1, M4): sqlite3 dot-commands `.shell` and `.system` (any prefix of at least `.sys` /
    `.she`, as the sqlite shell reads them), a `|` in any dot-command, and the SQL function `edit(`; psql `\\!`,
    `\\e`, `\\ef`, `\\ev`, `\\setenv`, a backquote in a meta-command line, `\\g` / `\\gx` / `\\o` / `\\w` with a `|`
    (also `\\g (format=csv) |cmd`, `\\o '|cmd'`), `COPY ... PROGRAM`; mysql `system`, `pager`, `edit`, `\\!`.
    Over-approximated."""
    low = text.lower()
    if "copy" in low and "program" in low:
        return True
    at = low.find("edit")
    while at >= 0:
        # the sqlite function `edit(text, editor)` runs the editor, and SQL spells the name in many ways
        # (`"edit"(`, `[edit](`, `` `edit`( ``, `edit/**/(`): any `edit` that is a word of its own is level B (not `credit`)
        after = low[at + 4:at + 5]
        if (at == 0 or not (low[at - 1].isalnum() or low[at - 1] == "_")) and not (after.isalnum() or after == "_"):
            return True
        at = low.find("edit", at + 1)
    for line in low.splitlines() or [low]:
        s = line.strip()
        if s.startswith("."):
            word = s[1:].split(None, 1)[:1]
            word = word[0] if word else ""
            if "|" in s or (len(word) >= 2 and "system".startswith(word)) or (len(word) >= 3 and "shell".startswith(word)):
                return True
        if s.startswith(_QUERY_SHELL_LINES) or s == "edit":
            return True
        names = _backslash_commands(s)
        if any(n in _QUERY_RUNNERS for n in names):
            return True
        if "`" in s and (s.startswith("\\") or any(n not in ("g", "gx") for n in names)):
            return True
        if "|" in s and any("|" in s[max(s.find("\\" + n), 0):] for n in names if n in _QUERY_PIPERS):
            return True  # (a `||` of the SQL before the command does not count)
    return False


def _backslash_commands(line: str) -> list[str]:
    """The names after each backslash of a line (a run of letters, digits and `_`, or the one other character):
    the meta-commands of psql and the client commands of mysql."""
    names: list[str] = []
    i = line.find("\\")
    n = len(line)
    while i >= 0:
        j = i + 1
        if j < n and (line[j].isalpha()):
            k = j + 1
            while k < n and (line[k].isalnum() or line[k] == "_"):
                k += 1
            names.append(line[j:k])
            j = k
        elif j < n:
            names.append(line[j])
            j += 1
        i = line.find("\\", j)
    return names


def _stdin_texts(cmd) -> "list[tuple[str, bool]]":
    """What the redirections of a simple command put on its stdin as text, as (text, is a here-string): heredoc
    bodies and here-strings."""
    return [(r.heredoc.body, False) if r.heredoc is not None else (r.target.text, True) for r in cmd.redirects
            if r.heredoc is not None or (r.op == "<<<" and r.target is not None)]


# Programs that read a here-string as data (B2 item 1): a here-string is a short value handed to a filter far more
# often than a program, and `jq . <<< "$x"` must not be read as shell. A heredoc keeps the strict HD4 rule.
_STDIN_DATA = frozenset(
    "jq yq grep egrep fgrep rg sed awk gawk cut sort uniq wc head tail tr bc base64 xxd od cmp diff comm join "
    "paste column fmt fold nl rev tac sha1sum sha256sum md5sum cksum read mapfile readarray expand unexpand".split())
_STDIN_PROGRAM_READERS = frozenset({"sed", "awk", "gawk"})  # with `-f` / `--file` their stdin may be the program
# What may run the text of a here-string handed to a compound (`{ bash; } <<< x`, `f() { sh; }; f <<< x`).
_STDIN_CODE_READERS = _SHELLS | frozenset({"source", ".", "eval", "xargs", "su", "sudo", "env", "at", "batch", "parallel",
                                           "exec", "ssh", "script", "coproc"})


def _data_reader(readings: Readings) -> bool:
    """Every reading of the receiver is a program of `_STDIN_DATA` (`sed -f -` and `awk -f -` read a program)."""
    if not readings.texts:
        return False
    for text in readings.texts:
        words = text.split()
        name = words[0].rsplit("/", 1)[-1] if words else ""
        if name not in _STDIN_DATA:
            return False
        if name in _STDIN_PROGRAM_READERS and any(
                w.startswith(("-f", "--file")) or w in ("-", "/dev/stdin") for w in words[1:]):
            return False
    return True


def _compound_reads_code(compound, functions: frozenset) -> bool:
    """Some command inside the compound may read code from the stdin the compound is given: a shell, a loader
    (`source`, `eval`), a program that runs its input (`xargs`, `at`), a function of the text, a program name made
    by an expansion, or a command whose readings are not complete."""
    for body in compound.bodies:
        for site in shell.iter_sites(body):
            words = site.cmd.words
            readings = _word_readings(words)
            if not readings.complete:
                return True
            for start, text in zip(readings.starts, readings.texts):
                head = _head_of(text).rsplit("/", 1)[-1]
                if head in _STDIN_CODE_READERS or head in functions or (
                        start < len(words) and _head_is_dynamic(words[start])):
                    return True
    return False


def _foreign_receiver(readings: Readings, values_view) -> "str | None":
    """HD4: the program that receives the heredoc or here-string is not shell: an interpreter of another language
    (`interpreter`) or a SQL / DSL client (`query`), by its name or through the variable that holds it (`PY=
    .venv/bin/python; $PY - <<EOF`) when every value the text gives that variable is one (`values_view()` gives the
    values at this command). It has to hold for every reading (the strictest wins: `sudo -x python3 bash <<EOF`
    may run `bash`). An unknown variable, one that may also hold the environment's value, or one with too many
    values, is not. The result is `query` when some reading is a client."""
    if not readings.texts:
        return None
    kinds: set = set()
    for text in readings.texts:
        head = _head_of(text)
        name = _variable_of(head)
        if name is None:
            kinds.add(_foreign_kind(head))
            continue
        values = values_view().get(name)
        if not values or None in values or len(values) > MAX_VALUE_CANDIDATES:
            return None
        kinds.update(_foreign_kind(v) for v in values)
    if None in kinds:
        return None
    return "query" if "query" in kinds else "interpreter"


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


# X6: the other ways an ex command or Lua/Vim script runs a program. Every pattern is anchored or made of negated
# classes, and runs only over the text of one nvim argument (bounded by the command).
_NVIM_EXECUTE = re.compile(r"(?:^|[:|\s])exe(?:c(?:u(?:t(?:e)?)?)?)?\s+")
_NVIM_TERMINAL = re.compile(r"(?:^|[:|])\s*te(?:r(?:m(?:i(?:n(?:a(?:l)?)?)?)?)?)?!?\s+(\S.*)$", re.S)
_NVIM_CALL = re.compile(
    r"(?<![\w.])(?:vim\.(?:fn\.)?)?(?:system|systemlist|jobstart|termopen)\s*\(|(?<![\w.])(?:os\.execute|io\.popen)\s*\("
)
_NVIM_EXECUTE_SHELL = re.compile(r"\s*(?:sil(?:ent)?!?\s+)?!")
_SAFE_WORD = re.compile(r"^[\w@%+=:,./-]+$")


def _sh_quote(text: str) -> str:
    """A word that the shell parser reads back as `text` (the list forms of X6 keep their elements apart)."""
    return text if _SAFE_WORD.match(text) else "'" + text.replace("'", "'\\''") + "'"


def _nvim_literal(text: str, i: int) -> tuple[str, int] | None:
    """The string literal that starts at `text[i]` (a quote) and the index after it; None when it does not close."""
    quote = text[i]
    out: list[str] = []
    i += 1
    while i < len(text):
        c = text[i]
        if c == "\\" and quote == '"' and i + 1 < len(text):
            out.append(text[i + 1])
            i += 2
        elif c == quote:
            if quote == "'" and text[i + 1:i + 2] == "'":  # Vim script: '' is a quote inside '...'
                out.append("'")
                i += 2
                continue
            return "".join(out), i + 1
        else:
            out.append(c)
            i += 1
    return None


def _nvim_call_argument(text: str, i: int) -> str | None:
    """The program text of the first argument of a call whose `(` ends just before `text[i]`: a plain string
    literal, or a list/table of plain string literals (quoted and joined by spaces). Anything else (a variable, a
    concatenation, a Lua long string) is None: the program is not known."""
    n = len(text)
    while i < n and text[i].isspace():
        i += 1
    if i >= n:
        return None
    if text[i] in "\"'":
        got = _nvim_literal(text, i)
        if got is None:
            return None
        value, j = got
        while j < n and text[j].isspace():
            j += 1
        return value if j < n and text[j] in ")," else None
    if text[i] not in "[{":
        return None
    items: list[str] = []
    i += 1
    while True:
        while i < n and text[i].isspace():
            i += 1
        if i < n and text[i] in "]}":
            return " ".join(_sh_quote(v) for v in items) if items else None
        if i >= n or text[i] not in "\"'":
            return None
        got = _nvim_literal(text, i)
        if got is None:
            return None
        items.append(got[0])
        i = got[1]
        while i < n and text[i].isspace():
            i += 1
        if i < n and text[i] == ",":
            i += 1
        elif not (i < n and text[i] in "]}"):
            return None


def _nvim_ex_texts(cmd: str, texts: list[str | None]) -> None:
    """The shell texts of one ex command or Lua/Vim script argument (X6): `None` is a call whose program is not a
    plain literal."""
    m = _NVIM_SHELL.search(cmd)
    if m and m.group(1).strip():
        texts.append(m.group(1).strip())
    for m in _NVIM_EXECUTE.finditer(cmd):
        i = m.end()
        if i < len(cmd) and cmd[i] in "\"'":
            got = _nvim_literal(cmd, i)
            if got is None:
                continue
            head = _NVIM_EXECUTE_SHELL.match(got[0])
            if head is None:  # not a shell escape (`exe "normal x"`)
                continue
            body = got[0][head.end():].strip()
            if cmd[got[1]:].lstrip().startswith("."):  # `exe "!" . cmd`: the program is not a literal
                texts.append(None)
            elif body:
                texts.append(body)
    m = _NVIM_TERMINAL.search(cmd)
    if m and m.group(1).strip():
        texts.append(m.group(1).strip())
    for m in _NVIM_CALL.finditer(cmd):
        texts.append(_nvim_call_argument(cmd, m.end()))


def nvim_shell_texts(tokens: list[str]) -> list[str | None]:
    """Shell commands an nvim invocation runs through `-c`/`--cmd`/`+cmd` (spec audit-shell-lexer, X6): the `!cmd`
    forms (`:!cmd`, `:silent !cmd`, `:w !cmd`, `:r !cmd`), `exe "!cmd"`, `terminal cmd`, and the calls
    `system()`, `systemlist()`, `jobstart()`, `termopen()` (also `vim.fn.` and `vim.`), `vim.system()`,
    `os.execute()` and `io.popen()` with a plain literal argument. A call whose program is not a plain literal
    gives `None`. `tokens` are the words of the simple command."""
    start = next((k for k, t in enumerate(tokens) if t.rsplit("/", 1)[-1] == "nvim"), None)
    if start is None:
        return []
    texts: list[str | None] = []
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
            _nvim_ex_texts(cmd, texts)
        k += 1
    return texts


class Analysis(namedtuple("Analysis", "categories flags uncertainty")):
    """Result of `analyze_command`: what `classify_command` returns, plus why the parser was not certain.

    categories and flags: lists of names (flags never contains "parse_uncertain": main adds it from
    `uncertainty`); uncertainty: the sorted reasons."""
    __slots__ = ()


# Docker and git forms the canary (U7) looks for outside the command head.
_CANARY_SPLIT = re.compile(r"[\s'\"`(){};&|=$]+")
_DOCKER_VERBS = frozenset({"up", "down", "start", "stop", "restart", "rm", "kill", "pull", "create", "run", "exec"})
_CANARY_GIT_FLAGS = (("push", "git_push"), ("commit", "git_commit"))
_CANARY_FEEDERS = frozenset({"xargs", "parallel", "-exec", "-execdir", "-ok", "-okdir"})


def _deny_token_unmatched(raw: str, flags: set[str]) -> bool:
    """U7: a blocked program shows up outside the head of the piece, followed by its verb, and no rule flagged
    the command. Only a record: it makes the forms the parser does not model visible in the metrics."""
    if "docker" not in raw and "git" not in raw:
        return False
    tokens = [t for t in _CANARY_SPLIT.split(raw) if t]
    fed = False  # an `xargs`, `find -exec` or `parallel` before: the verb may come from the data it reads
    for i, tok in enumerate(tokens):
        if i == 0 and "/" not in tok:  # the head is classified by its own rules (a path head is `_program_name`'s)
            fed = tok in _CANARY_FEEDERS
            continue
        name = tok.rsplit("/", 1)[-1]
        if name in {"docker", "docker-compose"} and "docker_lifecycle" not in flags:
            if fed or any(t in _DOCKER_VERBS for t in tokens[i + 1:]):
                return True
        elif name == "git":
            rest = tokens[i + 1:]
            if any(verb in rest and flag not in flags for verb, flag in _CANARY_GIT_FLAGS) \
                    or (fed and not flags & {"git_push", "git_commit"}):
                return True
        fed = fed or name in _CANARY_FEEDERS
    return False


def _level_b(reason: str) -> Analysis:
    """A text that cannot be classified with certainty (U4): level B, the whole text is unclassified."""
    return Analysis(["unclassified"], ["unclassified_command"], [reason])


def _code_text(text: str, categories: list[str], flags: list[str], reasons: set[str], _depth: int,
               budget, code: bool = False, env=None) -> None:
    """Classify a text the command runs as shell (a heredoc body, a code argument) as a command of its own, one
    level deeper; what it finds joins the outer result. More than MAX_CODE_DEPTH levels deep (X2): level B.
    `code`: the text is a code argument, so a command name made by an expansion is level B (X3). `env`: the
    values of the variables of the outer text, which go down (V3)."""
    if not text.strip():
        return
    if _depth >= MAX_CODE_DEPTH:
        categories.append("unclassified")
        flags.append("unclassified_command")
        reasons.add("nested_shell_depth")
        return
    sub = analyze_command(text, _depth + 1, env, budget, code)
    categories.extend(sub.categories)
    flags.extend(sub.flags)
    reasons.update(sub.uncertainty)


# X1-X6: arguments that run code. `CodeArg.text` is the shell text to classify one level deeper; `None` is a
# form whose code cannot be known, level B with `reason`.
CodeArg = namedtuple("CodeArg", "text reason")
MAX_CODE_ARGS = 16  # code arguments of one simple command; more is level B (`analysis_budget`)
_SHELL_VALUE_LONG = frozenset({"--rcfile", "--init-file"})
_STDIN_FILES = frozenset({"/dev/stdin", "/dev/fd/0", "/proc/self/fd/0"})
_DYNAMIC_PART_KINDS = shell.DYNAMIC_KINDS
_EXPANSION = re.compile(r"[$`]")


def _path_tail(text: str) -> str:
    """The text after the last `/` that separates path components: a `/` inside `${...}` or `$(...)` is the
    expansion's own (`${X/ls/d}`, `${X%/*}`), never a separator."""
    depth = 0
    last = -1
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "$" and text[i + 1:i + 2] in ("{", "("):
            depth += 1
            i += 2
            continue
        if depth and c in "{(":
            depth += 1
        elif depth and c in "})":
            depth -= 1
        elif c == "/" and not depth:
            last = i
        i += 1
    return text[last + 1:]


def _head_is_dynamic(word) -> bool:
    """X3: the program name of a command word is made by an expansion (`$X`, `$(which docker)`): its last path
    component is not literal. `$S/sync.sh` and `"$D"/x` are not dynamic. A brace expansion (`{a,b}`) or a `$'...'`
    part that cannot be decoded with certainty (`Part.dyn`) makes the name dynamic too."""
    if word.has_brace:
        return True
    if not word.dynamic:
        return False
    tail = False
    for part in word.parts:
        if part.dyn or part.kind in _DYNAMIC_PART_KINDS:
            tail = True
        elif part.kind == "dq" and part.inner:
            tail = "/" not in part.text or _EXPANSION.search(_path_tail(part.text)) is not None
        elif "/" in part.text:
            tail = False
    return tail


def _head_kind(words: list, tokens: list[str], start: int) -> "str | None":
    """How the program name at `tokens[start]` is dynamic: `expansion` (X3: made by an expansion), `glob` (N6: an
    unquoted pattern) or None. `words[start]` is None for a word made of a value: its text is checked instead
    (a value with `$` or a backquote still holds an expansion)."""
    if start >= len(tokens):
        return None
    word = words[start] if start < len(words) else None
    if word is not None:
        if _head_is_dynamic(word):
            return "expansion"
        return "glob" if word.has_glob and word.text not in {"[", "]"} else None
    text = tokens[start]
    tail = _path_tail(text)  # as for a word: `$S/sync.sh` names the program `sync.sh`
    if "$" in tail or "`" in tail or _has_brace_text(tail):
        return "expansion"
    return "glob" if any(c in text for c in "*?[") and text not in {"[", "]"} else None


def _shell_operands(tokens: list[str], i: int) -> tuple[str, int]:
    """Options of a shell after its name: which of `c` (code string), `s` (stdin) and `n` (parse only) are among
    them, and the index of the first word that is not an option. `-o`, `+o`, `-O`, `+O` (also last in a cluster)
    and `--rcfile`/`--init-file` take the next word; other long options are boolean; `--` and a lone `-` end the
    options (a shell with no operand then reads its program from stdin)."""
    n = len(tokens)
    seen = ""
    while i < n:
        tok = tokens[i]
        if tok == "--" or tok == "-":
            return seen, i + 1
        if tok.startswith("--"):
            i += 2 if tok in _SHELL_VALUE_LONG else 1
        elif tok[:1] in "-+" and len(tok) > 1:
            if tok[0] == "-":
                seen += "".join(c for c in "csn" if c in tok)
            i += 2 if tok[-1] in "oO" else 1
        else:
            break
    return seen, i


def _stdin_code(site) -> list[CodeArg]:
    """A shell that reads its program from stdin: the here-string is the code (X1); a heredoc is read by the
    heredoc rules; a process substitution is code of unknown reach (X5); the stage of a pipeline that is not the
    first reads what the others write (X4)."""
    for redirect in site.cmd.redirects:
        if redirect.op == "<<<" and redirect.target is not None:
            return [CodeArg(redirect.target.text, None)]
        if redirect.op == "<" and redirect.target is not None \
                and any(part.kind == "procsub_in" for part in redirect.target.parts):
            return [CodeArg(None, "dynamic_code")]
        if redirect.heredoc is not None:
            return []
    return [CodeArg(None, "piped_shell")] if site.stage > 0 else []


def _first_operand_code(site, tokens: list[str], i: int, words: list) -> list[CodeArg]:
    """A shell reader (`source`, `.`) whose operand is the program: `<(...)` is X5, a stdin file is X4. `words`
    are the words of the command (None for one made of a value)."""
    if i >= len(tokens):
        return []
    if i < len(words) and words[i] is not None and any(part.kind == "procsub_in" for part in words[i].parts):
        return [CodeArg(None, "dynamic_code")]
    return _stdin_code(site) if tokens[i] in _STDIN_FILES else []


def _shell_code(site, tokens: list[str], p: int, words: list, fed: bool = False) -> list[CodeArg]:
    """`bash/sh/zsh/...` at `tokens[p]`: with `-c` the first word that is not an option is the code; without it
    that word is a script file (not analyzed; `<(...)` is X5) and no word means stdin. With `-n` and no `-c`
    nothing runs (`zsh -n`, `bash -n` only parse). `fed`: an `xargs` runs it, so a `-c` with no operand gets the
    code from the words xargs reads: unknown (X5)."""
    seen, i = _shell_operands(tokens, p + 1)
    if "c" in seen:
        if i < len(tokens):
            return [CodeArg(tokens[i], None)]
        return [CodeArg(None, "dynamic_code")] if fed else []
    if "n" in seen:
        return []
    if i < len(tokens) and "s" not in seen:
        return _first_operand_code(site, tokens, i, words)
    return _stdin_code(site)


def _env_code(tokens: list[str], p: int) -> list[CodeArg]:
    """`env -S STRING` / `--split-string=STRING`: the string and the words after it are the command."""
    n = len(tokens)
    i = p + 1
    while i < n:
        tok = tokens[i]
        if tok == "--" or not tok.startswith("-") or tok == "-":
            break
        if tok.startswith("--"):
            name, eq, value = tok[2:].partition("=")
            if name == "split-string":
                if not eq:
                    i += 1
                    value = tokens[i] if i < n else ""
                return [CodeArg(" ".join([value] + tokens[i + 1:]), None)]
            i += 2 if name in {"unset", "chdir"} and not eq else 1
            continue
        for j in range(1, len(tok)):
            if tok[j] == "S":
                value = tok[j + 1:]
                rest = i + 1
                if not value and rest < n:
                    value, rest = tokens[rest], rest + 1
                return [CodeArg(" ".join([value] + tokens[rest:]), None)]
            if tok[j] in "uCP":
                i += 0 if j + 1 < len(tok) else 1
                break
        i += 1
    return []


def _su_code(tokens: list[str], p: int) -> list[CodeArg]:
    """`su -c STRING`, `--command STRING`, `--command=STRING`."""
    out: list[CodeArg] = []
    n = len(tokens)
    for i in range(p + 1, n):
        tok = tokens[i]
        if tok == "--":
            break
        if tok.startswith("--command"):
            name, eq, value = tok[2:].partition("=")
            if name == "command":
                if eq:
                    out.append(CodeArg(value, None))
                elif i + 1 < n:
                    out.append(CodeArg(tokens[i + 1], None))
        elif tok.startswith("-") and not tok.startswith("--") and "c" in tok[1:]:
            tail = tok[tok.index("c") + 1:]
            if tail:
                out.append(CodeArg(tail, None))
            elif i + 1 < n:
                out.append(CodeArg(tokens[i + 1], None))
    return out


def _trap_code(tokens: list[str], p: int) -> list[CodeArg]:
    """`trap ACTION SIGNAL...`: ACTION is code, except for `-l`, `-p` and `-` (reset)."""
    i = p + 1
    if i < len(tokens) and tokens[i] in {"-l", "-p", "-"}:
        return []
    if i < len(tokens) and tokens[i] == "--":
        i += 1
    return [CodeArg(tokens[i], None)] if i < len(tokens) else []


def _mise_code(tokens: list[str], p: int) -> list[CodeArg]:
    """`mise [flags] exec|x [flags] -c STRING` (or `--command`): the string runs through a shell."""
    j = _skip_mise_flags(tokens, p + 1)
    if j >= len(tokens) or tokens[j] not in {"exec", "x"}:
        return []
    out: list[CodeArg] = []
    n = len(tokens)
    for i in range(j + 1, n):
        tok = tokens[i]
        if tok == "--":
            break
        if tok in {"-c", "--command"}:
            if i + 1 < n:
                out.append(CodeArg(tokens[i + 1], None))
        elif tok.startswith("--command="):
            out.append(CodeArg(tok[10:], None))
        elif tok.startswith("-c") and not tok.startswith("--"):
            out.append(CodeArg(tok[2:], None))
    return out


def _emulate_code(tokens: list[str], p: int) -> list[CodeArg]:
    """zsh `emulate [-LR] [mode] -c STRING`: the string runs as a command line."""
    out: list[CodeArg] = []
    n = len(tokens)
    i = p + 1
    while i < n:
        tok = tokens[i]
        if tok == "--":
            break
        if tok.startswith("-") and not tok.startswith("--") and "c" in tok[1:]:
            tail = tok[tok.index("c") + 1:]
            if tail:
                out.append(CodeArg(tail, None))
            elif i + 1 < n:
                out.append(CodeArg(tokens[i + 1], None))
                i += 1
        i += 1
    return out


def _mapfile_code(tokens: list[str], p: int) -> list[CodeArg]:
    """`mapfile` / `readarray -C CALLBACK`: bash evaluates the callback as a command each time it reads lines."""
    out: list[CodeArg] = []
    n = len(tokens)
    for i in range(p + 1, n):
        tok = tokens[i]
        if tok == "--":
            break
        if tok.startswith("-") and not tok.startswith("--") and "C" in tok[1:]:
            tail = tok[tok.index("C") + 1:]
            if tail:
                out.append(CodeArg(tail, None))
            elif i + 1 < n:
                out.append(CodeArg(tokens[i + 1], None))
    return out


def _flag_cluster(flags: list[str], letters: str) -> bool:
    """Some short option of `flags` (words between a wrapper and its command) has one of `letters`."""
    return any(f.startswith("-") and not f.startswith("--") and any(c in letters for c in f[1:]) for f in flags)


def _xargs_replace(flags: list[str]) -> frozenset:
    """The replacement strings of an xargs: `-I R`, `-IR`, `-i`, `-iR`, `--replace`, `--replace=R`."""
    out: set[str] = set()
    for k, tok in enumerate(flags):
        if tok == "-I" and k + 1 < len(flags):
            out.add(flags[k + 1])
        elif tok.startswith("-I") and not tok.startswith("--"):
            out.add(tok[2:])
        elif tok.startswith("-i") and not tok.startswith("--"):
            out.add(tok[2:] or "{}")
        elif tok == "--replace":
            out.add("{}")
        elif tok.startswith("--replace="):
            out.add(tok[10:])
    return frozenset(r for r in out if r)


def _position_code(site, tokens: list[str], p: int, name: str, starts: list[int], words: list,
                   fed: bool = False) -> list[CodeArg]:
    """The code arguments of the program named `name` at `tokens[p]`; `starts` are the positions where its
    wrapped command can start (when it is a wrapper); `fed`: an `xargs` of the prefix chain runs it."""
    n = len(tokens)
    if name in _SHELLS:
        return _shell_code(site, tokens, p, words, fed)
    if name == "emulate":
        return _emulate_code(tokens, p)
    if name in {"mapfile", "readarray"}:
        return _mapfile_code(tokens, p)
    if name in {"source", "."}:
        return _first_operand_code(site, tokens, p + 1, words)
    if name == "eval":
        rest = tokens[p + 1:]
        return [CodeArg(" ".join(rest[1:] if rest[:1] == ["--"] else rest), None)] if rest else []
    if name == "trap":
        return _trap_code(tokens, p)
    if name == "su":
        return _su_code(tokens, p)
    if name == "env":
        return _env_code(tokens, p)
    if name == "mise":
        return _mise_code(tokens, p)
    if name == "nvim":
        return [CodeArg(text, None if text is not None else "nvim_shell_exec") for text in nvim_shell_texts(tokens[p:])]
    out: list[CodeArg] = []
    if name == "sudo":  # -s / -i with words: the words are a command line for the user's shell
        for s in starts:
            if s < n and _flag_cluster(tokens[p + 1:s], "si"):
                out.append(CodeArg(" ".join(tokens[s:]), None))
    elif name == "watch":  # without -x / --exec the words are run by `sh -c`
        for s in starts:
            flags = tokens[p + 1:s]
            if s < n and not _flag_cluster(flags, "x") and "--exec" not in flags:
                out.append(CodeArg(" ".join(tokens[s:]), None))
    return out


def _code_args(site, tokens: list[str], words: "list | None" = None) -> list[CodeArg]:
    """X1-X6: every argument of the simple command that runs code, at every program of its prefix chain
    (`sudo -u x bash -c ...`), once each. A code string that holds a replacement string of an enclosing `xargs`
    is made at run time (X3). More than MAX_CODE_ARGS: one level B entry and no more. `words`: the words of
    `tokens` when a value took the place of one (None entries), else those of the site."""
    n = len(tokens)
    if words is None:
        words = site.cmd.words
    found: list[CodeArg] = []
    keys: set = set()
    seen: set[int] = set()
    stack: list[tuple[int, frozenset, bool]] = [(0, frozenset(), False)]
    while stack:
        p, replace, fed = stack.pop()
        if p >= n or p in seen:
            continue
        seen.add(p)
        name = _program_name(tokens[p])
        starts = [s for s in _prefix_steps(tokens, p) if s != p]
        for text, reason in _position_code(site, tokens, p, name, starts, words, fed):
            if text is not None and any(r in text for r in replace):
                text, reason = None, "dynamic_code"
            if (text, reason) not in keys:
                keys.add((text, reason))
                found.append(CodeArg(text, reason))
        if len(found) > MAX_CODE_ARGS:
            return found[:MAX_CODE_ARGS] + [CodeArg(None, "analysis_budget")]
        for s in reversed(starts):
            stack.append((s, replace | _xargs_replace(tokens[p + 1:s]) if name == "xargs" else replace,
                          fed or name == "xargs"))
    return found


def _function_names(script) -> frozenset:
    """The names of the functions the text defines."""
    return frozenset(c.name for c in shell.iter_compounds(script) if c.kind == "function" and c.name)


def _receiver_reads_code(readings: Readings, functions: frozenset) -> bool:
    """Some reading of the receiver of a heredoc or here-string runs its input (a shell, `source`, `eval`, `xargs`,
    `at`, ...) or is a function of the text: the body is code, so a program name made by an expansion in it is level
    B (X3)."""
    return any(_head_of(t).rsplit("/", 1)[-1] in _STDIN_CODE_READERS or _head_of(t) in functions
               for t in readings.texts)


def _heredoc_code(site, readings: Readings, categories: list[str], flags: list[str], reasons: set[str],
                  disqualified: bool, _depth: int, budget, view_at, grouped: bool, functions,
                  rebound: bool = False) -> None:
    """The bodies of the heredocs of one simple command (spec audit-shell-lexer, HD3-HD5): data is not read; the
    program of another language (`python`, `node`, ...) is not shell either; any other receiver gets its body
    classified as a script of its own. The expansions of an unquoted body are commands too (HD2), but they are
    sites of the walk, not handled here. The values of the variables go down into the body (V3); `view_at(pos)`
    gives the values at an offset of the text. `rebound`: the text gives a trusted program name another meaning (a
    function, `hash -p`, a `PATH` assignment, `_rebinds`): no body is data and no receiver is foreign."""
    bodies = _stdin_texts(site.cmd)
    if not bodies or _heredoc_is_data(site, readings, disqualified or rebound, reasons, grouped):
        return
    pos = site.cmd.span[0]
    names = functions()
    kind = None if rebound or any(_head_of(t).rsplit("/", 1)[-1] in names for t in readings.texts) \
        else _foreign_receiver(readings, lambda: view_at(pos))
    if kind:
        if kind == "query" and any(_query_escape(body) for body, _ in bodies):
            _block(categories, flags, reasons, "dynamic_code")  # `.shell`, `\!`: the client runs a command
        return
    data = not rebound and _data_reader(readings)
    code = _receiver_reads_code(readings, functions())
    for body, here in bodies:
        if here and data:
            continue
        env = view_at(pos) if "$" in body else None
        _code_text(body, categories, flags, reasons, _depth, budget, code, env)


_BAD = "bad"  # a positional form the substitution does not model: the call is level B (part E, V1)


def _digits(text: str) -> bool:
    return text.isdigit() and text.isascii() and text.strip("0") != ""


def _braced_positional(inner: str):
    """The spec of the positional parameter `${inner}` (see `_positional`), or None when it is not positional."""
    head = inner[:1]
    if head in ("#",) and inner[1:2] not in ("@", "*"):
        return None  # `${#1}`, `${#}`: a length
    if head in ("!", "#") and (inner[1:2] in ("@", "*", "1", "2", "3", "4", "5", "6", "7", "8", "9") or inner[1:5] == "argv"):
        return _BAD
    name = "@" if head in ("@", "*") else inner[:4] if inner[:4] == "argv" and not (inner[4:5].isalnum() or inner[4:5] == "_") \
        else ""
    if name:
        rest = inner[len(name):] if name == "argv" else inner[1:]
        if rest == "" or (name == "argv" and rest in ("[@]", "[*]")):
            return "all"
        if name == "argv" and rest[:1] == "[" and rest[-1:] == "]" and _digits(rest[1:-1]):
            return int(rest[1:-1])
        if name == "@" and rest[:1] == ":":
            offset, _, length = rest[1:].partition(":")
            if _digits(offset) and (length == "" and ":" not in rest[1:] or _digits(length) or length == "0"):
                return ("slice", int(offset), int(length) if length else None)
        return _BAD
    digits = 0
    while digits < len(inner) and inner[digits].isdigit():
        digits += 1
    if digits and head != "0":
        return int(inner[:digits]) if digits == len(inner) else _BAD  # `${1:-x}`: a default the substitution drops
    return None


def _positional(text: str):
    """The positional parameter `text` starts with: `(its text, spec)`, or None when it is not one. spec: `"all"`
    (`$@`, `$*`, `${@}`, zsh `$argv`, `${argv[@]}`), an argument number (`$1`, `${2}`, `$argv[1]`), `("slice", N,
    M or None)` (`${@:N}`, `${*:N:M}`), or `_BAD` for a form that is not modeled (`${@:$n}`, `${1:-x}`, `${!1}`,
    `$@[i]`, `${@[i]}`): a call of a function that uses one is level B."""
    if text[:1] != "$" or len(text) < 2:
        return None
    c = text[1]
    if c in "@*":
        return (text[:3], _BAD) if text[2:3] == "[" else (text[:2], "all")
    if c.isdigit() and c != "0":
        return text[:2], int(c)
    if text[1:5] == "argv" and not (text[5:6].isalnum() or text[5:6] == "_"):
        if text[5:6] == "[":
            close = text.find("]", 5)
            inner = text[6:close] if close > 0 else ""
            if close > 0 and _digits(inner):
                return text[:close + 1], int(inner)
            return (text[:close + 1] if close > 0 else text[:6]), ("all" if inner in ("@", "*") else _BAD)
        return text[:5], "all"
    if c == "{":
        close = text.find("}")
        if close < 0:
            return None
        spec = _braced_positional(text[2:close])
        return None if spec is None else (text[:close + 1], spec)
    return None


def _positional_refs(text: str):
    """Every positional parameter of the source `text` that the shell expands (not inside single quotes, not
    escaped), as `(offset, token, spec)`."""
    i, n = 0, len(text)
    in_sq = in_dq = False
    while i < n:
        c = text[i]
        if c == "\\" and not in_sq:
            i += 2
            continue
        if c == "'" and not in_dq:
            in_sq = not in_sq
        elif c == '"' and not in_sq:
            in_dq = not in_dq
        elif c == "$" and not in_sq:
            found = _positional(text[i:])
            if found is not None:
                yield i, found[0], found[1]
                i += len(found[0])
                continue
        i += 1


def _positional_model(body: str) -> "list | None":
    """Part E, V1: the `shift`s of a forwarding function's body, as `[(offset after the command, arguments dropped
    so far)]` in source order (a parameter used after one sees the later arguments), or None when the body does
    something with its parameters that the substitution does not model: a parameter form of `_positional` that is
    `_BAD`, a `shift` that is not a plain command of the body itself (inside an `if`, a loop, after `&&`, in a
    pipeline, with an argument that is not a number), or `set` that changes them."""
    refs = list(_positional_refs(body))
    if any(spec == _BAD for _, _, spec in refs):
        return None
    try:
        script = shell.parse(body, shell.Budget(MAX_LEX_CHARS))
    except shell.ShellError:
        return None
    inner = script
    if len(script.pipelines) == 1 and len(script.pipelines[0].commands) == 1:
        only = script.pipelines[0].commands[0]
        if isinstance(only, shell.Compound) and only.kind in ("group", "subshell") and only.bodies:
            inner = only.bodies[0]
    straight = {id(p.commands[0]) for p in inner.pipelines if len(p.commands) == 1 and isinstance(p.commands[0], shell.Simple)}
    count = 0
    marks: list = []
    for site in shell.iter_sites(script):
        cmd = site.cmd
        texts = [w.text for w in cmd.words[:3]]
        if "set" in texts[:2] and any(not t.startswith(("-", "+")) or t == "--" for t in [w.text for w in cmd.words[1:]]):
            return None
        if "shift" not in texts:
            continue
        start, end = cmd.span
        before = body[:start].rstrip(" \t")
        after = body[end:].lstrip(" \t")
        if (id(cmd) not in straight or len(cmd.words) > 2 or cmd.words[0].text != "shift" or cmd.redirects
                or before[-1:] not in ("", ";", "\n", "{", "(") or after[:1] not in ("", ";", "\n", "}", ")")
                or (len(cmd.words) == 2 and not _digits(cmd.words[1].text))):
            return None
        count += int(cmd.words[1].text) if len(cmd.words) == 2 else 1
        marks.append((end, count))
    return sorted(marks)


def _forwarding_functions(script, command: str) -> "dict[str, list[str]]":
    """B2 item 2: the functions the text defines whose body uses positional parameters (`f() { "$@"; }`,
    `g() { git -C r "$@"; }`): name -> the source text of each body. A call of one is classified with its
    arguments in place of the parameters (`_positional_text`)."""
    found: dict[str, list[str]] = {}
    for comp in shell.iter_compounds(script):
        if comp.kind != "function" or not comp.name or not comp.bodies:
            continue
        uses = False
        for body in comp.bodies:
            for site in shell.iter_sites(body):
                for word in (*site.cmd.assignments, *site.cmd.words):
                    uses = uses or any(p.kind == "param" and _positional(p.text) is not None
                                       for p in _walk_parts(word.parts))
        if uses:
            found.setdefault(comp.name, []).extend(command[body.span[0]:body.span[1]] for body in comp.bodies)
    return found


# Programs that take the name of a function as plain text (or are classified on their own, so `docker run` is not a
# use of a function named `run`): the name next to them is no call.
_NAME_ONLY_HEADS = frozenset({"echo", "printf", "type", "whence", "which", "unset", "declare", "typeset", "command",
                              "cd", "ls", "cat", "grep", "rg", "tail", "head", "rm", "cp", "mv", "mkdir", "touch",
                              "wc", "sort", "diff", "stat", "file"})


def _forwarding_spans(script, funcs: dict) -> list:
    """The `(start, end)` source spans of the bodies of the forwarding functions `funcs`."""
    return [body.span for comp in shell.iter_compounds(script)
            if comp.kind == "function" and comp.name in funcs for body in comp.bodies]


def _positional_params(word) -> "list[str] | None":
    """The positional parameters (`$@`, `"$1"`, `${2:-a}`, in double quotes too) a word expands, as written, when
    they are all it expands (no other parameter, substitution or arithmetic), else None."""
    found: list[str] = []
    for part in _walk_parts(word.parts):
        if part.kind == "param":
            if _positional(part.text) is None:
                return None
            found.append(part.text)
        elif part.kind in _DYNAMIC_PART_KINDS or part.dyn:
            return None
    return found


def _neutral_positionals(tokens: list[str], words: list) -> "tuple[list[str], list]":
    """The words of a command inside a forwarding function with each positional parameter replaced by a plain word
    (`ARG`) in the words that expand nothing else: the calls decide what they are, and each call is classified with
    its arguments."""
    new_tokens = list(tokens)
    new_words = list(words)
    for i, word in enumerate(words):
        params = _positional_params(word) if word is not None and word.dynamic else None
        if params:
            for param in params:
                new_tokens[i] = new_tokens[i].replace(param, "ARG")
            new_words[i] = None
    return new_tokens, new_words


def _mentions(text: str, names) -> bool:
    """Some name of `names` appears in `text` as a word of its own (not inside a longer identifier)."""
    for name in names:
        at = text.find(name)
        while at >= 0:
            before = text[at - 1:at] if at else ""
            after = text[at + len(name):at + len(name) + 1]
            if not (before.isalnum() or before in ("_", "-", ".", "/")) and not (after.isalnum() or after in ("_", "-", ".")):
                return True
            at = text.find(name, at + 1)
    return False


def _positional_text(text: str, args: list[str], plain: "list[str] | None" = None, marks=()) -> str:
    """`text` (the source of a function) with its positional parameters replaced by the call's arguments (their
    source text, quotes kept): `$@` and `$*` by all of them, `$N` by the Nth (empty when there is none). Single
    quotes keep a `$` as it is; a parameter that makes up a whole double-quoted word loses its quotes. An
    unquoted parameter is split into words by the shell, so it takes the arguments without their quotes
    (`plain`, the words of the call; the quotes of `f 'docker restart'` do not keep `$1` one word)."""
    plain = args if plain is None else plain
    out: list[str] = []
    i, n = 0, len(text)
    in_sq = in_dq = False
    while i < n:
        c = text[i]
        if c == "\\" and not in_sq:
            out.append(text[i:i + 2])
            i += 2
            continue
        if c == "'" and not in_dq:
            in_sq = not in_sq
        elif c == '"' and not in_sq:
            in_dq = not in_dq
        elif c == "$" and not in_sq:
            found = _positional(text[i:])
            if found is not None:
                token, number = found
                dropped = 0  # the arguments a `shift` before this point took away (`marks`)
                for mark_end, total in marks:
                    if mark_end <= i:
                        dropped = total
                words = (args if in_dq else plain)[dropped:]
                if number == "all":
                    value = " ".join(words)
                elif isinstance(number, tuple):  # `${@:N}` / `${@:N:M}`: the words from the Nth on (M of them)
                    _, offset, length = number
                    chosen = words[offset - 1:] if length is None else words[offset - 1:offset - 1 + length]
                    value = " ".join(chosen)
                else:
                    value = words[number - 1] if isinstance(number, int) and number <= len(words) else ""
                end = i + len(token)
                if in_dq and out and out[-1] == '"' and text[end:end + 1] == '"':
                    out.pop()  # `"$@"`: the arguments are words of their own
                    in_dq = False
                    end += 1
                out.append(value)
                i = end
                continue
        out.append(c)
        i += 1
    return "".join(out)


def _block(categories: list[str], flags: list[str], reasons: set[str], reason: str) -> None:
    """Level B for the command being read: it cannot be classified with certainty (`reason`)."""
    categories.append("unclassified")
    flags.append("unclassified_command")
    reasons.add(reason)


def _with_prefix(env: "_Values", full: "_Values", cmd) -> "_Values":
    """The values a code string of `cmd` sees: the environment of the command holds its prefix assignments
    (`T=docker bash -c '$T ps'`), whatever their position in the text."""
    names = []
    for word in cmd.assignments:
        first = word.parts[0]
        target = _assignment_target(first.text) if first.kind == "lit" else None
        if target is not None and target[0] in full:
            names.append(target[0])
    if not names:
        return env
    view = _Values()
    view.update(env)
    view.copy_flags(env)
    view.soft = (env.soft - frozenset(names)) | (full.soft & frozenset(names))
    for name in names:
        view[name] = full[name]
    return view


_NUMERIC_TESTS = frozenset({"-eq", "-ne", "-lt", "-le", "-gt", "-ge"})
_EVALUATING_TESTS = _NUMERIC_TESTS | {"-v", "-R"}  # the operand of a numeric test and of `-v NAME[sub]` is evaluated


def _arithmetic_hint(command: str) -> bool:
    """The raw text (strings that run as code in a nested shell included) evaluates arithmetic somewhere: `$((`,
    `(( ))`, `$[`, `let`, `declare -i`, or a numeric test (`-eq` ... as a word)."""
    if "((" in command or "$[" in command:
        return True
    previous = ""
    for word in command.replace(";", " ").replace("&", " ").replace("|", " ").replace("(", " ").split():
        word = word.strip("'\"")
        if word in _NUMERIC_TESTS or word == "let" or (word == "-i" and previous in ("declare", "typeset", "local")):
            return True
        previous = word
    return False


def _xtrace_evidence(command: str) -> bool:
    """Some word of the raw text turns tracing on: a short option cluster with `x` (`-x`, `-ex`, `-xe`) or the
    option name `xtrace` (`set -o xtrace`, `setopt xtrace`). A deliberate over-approximation."""
    if "xtrace" in command.lower():
        return True
    for token in command.split():
        t = token.strip("'\";&|()`")
        if len(t) > 1 and t[0] in "-+" and t[1] != "-" and "x" in t[1:] and t[1:].isalpha():
            return True
    return False


def _param_arithmetic(text: str) -> bool:
    """`${a[i]}` (a subscript is evaluated as arithmetic) and `${x:off:len}` (so are the offsets)."""
    if not text.startswith("${"):
        return False
    body = text[2:].lstrip("#!")
    name = _name_prefix(body)
    rest = body[len(name):]
    return rest.startswith("[") or (rest.startswith(":") and rest[1:2] not in ("", "-", "=", "+", "?", ":"))


def _ps4_traced(script) -> bool:
    """A `PS4` and a tracing option among the words of the text (assignments included). The arguments of a program of
    another language (`python3 -c '...PS4=... -xc...'`) are text of that language, not shell, so they do not count."""
    texts: list[str] = []
    for site in shell.iter_sites(script):
        cmd = site.cmd
        words = [w.text for w in cmd.words]
        keep = len(words)
        if words:
            for s in _token_readings(words).starts:
                if s < len(words) and _foreign_kind(words[s]):
                    keep = min(keep, s + 1)
        texts.extend(w.text for w in cmd.assignments)
        texts.extend(words[:keep])
    joined = " ".join(texts)
    return "PS4" in joined and _xtrace_evidence(joined)


def _code_evaluation(command: str, script, values=None) -> bool:
    """Item 1 and 4: contexts in which the shell evaluates a text as code where no command is written, so it is
    `dynamic_code` (level B): a parameter expansion that evaluates its value (`${(e)X}`, `${X@P}`, zsh `(%)`); a
    `PS4` in the shell words of a text that turns on tracing (`PS4` is expanded, command substitutions included, for
    each traced command); and a `$(` or a backquote that reaches a context where the shell evaluates a subscript
    and runs the substitution of `a[$(cmd)]`: the text comes from single quotes (or is escaped), from a known value
    after the substitution of the names in it, or from what `read` / `mapfile` takes from a heredoc or a
    here-string; the contexts are `$(( ))`, `(( ))`, `let`, `declare -i`, a numeric or `-v` test, an array subscript,
    `${x:off}`, an indirection (`${!x}`, zsh `${(P)x}`), and the names tainted through other names. `values()`
    gives the `_Values` of the text."""
    if "PS4" in command and _ps4_traced(script):
        return True
    if "$" not in command and "`" not in command:
        return False
    quoted = False
    for _, parts in _tree_words(script):
        if not quoted and _single_quoted_substitution(parts):
            quoted = True
        for part in _walk_parts(parts):
            if part.code:
                return True
    if not (quoted or _arithmetic_hint(command) or _indirect_hint(command)):
        return False
    return _quoted_reaches_arithmetic(script, values)


def _indirect_hint(command: str) -> bool:
    """The text may evaluate a name or a subscript without arithmetic syntax: `${!x}`, zsh `${(P)x}`, `-v` / `-R`."""
    return "${!" in command or "(P" in command or " -v" in command or " -R" in command


_SUBSCRIPT_HEADS = frozenset({"unset", "read", "printf", "test", "[", "declare", "typeset", "local", "export",
                              "readonly", "mapfile", "readarray", "getopts", "wait", "let"})


def _identifiers(text: str) -> set:
    """The names (identifier-shaped runs) in `text`: in an arithmetic expression a bare name is a variable."""
    out: set = set()
    n, i = len(text), 0
    while i < n:
        c = text[i]
        if c == "_" or (c.isascii() and c.isalpha()):
            j = i + 1
            while j < n and (text[j] == "_" or (text[j].isascii() and text[j].isalnum())):
                j += 1
            out.add(text[i:j])
            i = j
        else:
            i += 1
    return out


def _subscript_shaped(text: str) -> bool:
    """`a[$(x)]`: a name, a bracket, and a substitution before the last `]`."""
    i = text.find("[")
    close = text.rfind("]")
    while 0 < i < close:
        if (text[i - 1].isalnum() or text[i - 1] == "_") and ("$(" in text[i:close] or "`" in text[i:close]):
            return True
        i = text.find("[", i + 1)
    return False


def _names_in(word) -> set:
    """The variable names a word expands (`$x`, `${x[i]}`) or names in an arithmetic expansion."""
    names: set = set()
    for part in _walk_parts(word.parts):
        if part.kind == "param":
            body = part.text[2:] if part.text.startswith("${") else part.text[1:]
            names.add(_name_prefix(body.lstrip("#!")))
        elif part.kind == "arith":
            names |= _identifiers(part.text)
    return names


class _Reach:
    """Whether a word carries a quoted substitution into an arithmetic context: it holds one itself, or expands a
    tainted name (and, `bare`, names one the way an arithmetic expression does)."""

    __slots__ = ("tainted",)

    def __init__(self, tainted: set):
        self.tainted = tainted

    def __call__(self, word, bare: bool) -> bool:
        if _single_quoted_substitution(word.parts) or _names_in(word) & self.tainted:
            return True
        return bare and bool(_identifiers(word.text) & self.tainted)


_READERS = frozenset({"read", "mapfile", "readarray"})


def _substitution_text(text: str) -> bool:
    """`text` holds a command substitution: a backquote or a `$(` that is not the `$((` of an arithmetic expansion
    (`n=$((n+1))` is a value that holds no command)."""
    at = text.find("$(")
    while at >= 0:
        if text[at + 2:at + 3] != "(":
            return True
        at = text.find("$(", at + 1)
    return "`" in text


def _tainted_names(sites: list, extra=()) -> set:
    """The names that may hold text with `$(` or a backquote: assigned from quoted text that has one, from a heredoc
    or here-string that `read` / `mapfile` takes it from, the `extra` names (a known value that has one), and, through
    the names a word expands, every name assigned from a tainted one. One worklist pass: linear in the text (D1, L2)."""
    seeds = set(extra)
    users: dict[str, list[str]] = {}  # name -> the names assigned from words that expand it
    for site in sites:
        cmd = site.cmd
        words = list(cmd.assignments)
        if cmd.words and any(w.text in _DECLARE_BUILTINS for w in cmd.words[:3]):
            words += cmd.words[1:]
        for word in words:
            first = word.parts[0]
            target = _assignment_target(first.text) if first.kind == "lit" else None
            if target is None:
                continue
            if _single_quoted_substitution(word.parts):
                seeds.add(target[0])
            else:
                for ref in _names_in(word):
                    users.setdefault(ref, []).append(target[0])
        if cmd.words and cmd.words[0].text in ("declare", "typeset", "local") \
                and any(w.text.startswith("-") and "n" in w.text for w in cmd.words[1:]):
            for w in cmd.words[1:]:  # `declare -n r=x`: r reads (and evaluates) what x holds (part E, V2)
                target, _, ref = w.text.partition("=")
                if not w.text.startswith("-") and ref and _name_prefix(target) and _name_prefix(ref):
                    users.setdefault(_name_prefix(ref), []).append(_name_prefix(target))
        if cmd.words and cmd.words[0].text in _READERS:  # `read -r x <<< 'a[$(c)]'` / `mapfile a <<EOF ... EOF`
            names = [_name_prefix(w.text) for w in cmd.words[1:] if not w.text.startswith("-")] or ["REPLY", "MAPFILE"]
            names = [n for n in names if n] + ["REPLY", "MAPFILE"]
            for redirect in cmd.redirects:
                if redirect.heredoc is not None and _substitution_text(redirect.heredoc.body):
                    seeds.update(names)
                elif redirect.op == "<<<" and redirect.target is not None:
                    if _single_quoted_substitution(redirect.target.parts) or _substitution_text(redirect.target.text):
                        seeds.update(names)
                    else:
                        for ref in _names_in(redirect.target):
                            users.setdefault(ref, []).extend(names)
    tainted = set(seeds)
    queue = list(seeds)
    while queue:
        for user in users.get(queue.pop(), ()):
            if user not in tainted:
                tainted.add(user)
                queue.append(user)
    return tainted


def _command_reaches_arithmetic(cmd, reaches: _Reach) -> bool:
    """One simple command: a prefix assignment with a subscript, `let`, `declare -i`, a numeric `[` / `test`, or
    a builtin that evaluates a subscript-shaped argument, with the quoted text (or a tainted name) as operand."""
    heads = {w.text for w in cmd.words[:3]}
    for word in cmd.assignments:  # `A[$x]=v`: the subscript is evaluated
        first = word.parts[0]
        name = _name_prefix(first.text) if first.kind == "lit" else ""
        if name and first.text[len(name):len(name) + 1] == "[" and reaches(word, False):
            return True
    if "let" in heads and any(reaches(w, True) for w in cmd.words[1:]):
        return True
    if heads & {"declare", "typeset", "local"} and any(
            w.text.startswith("-") and "i" in w.text for w in cmd.words) and any(
            reaches(w, True) for w in cmd.words[1:] if not w.text.startswith("-")):
        return True
    if heads & {"[", "test"} and any(w.text in _EVALUATING_TESTS for w in cmd.words) \
            and any(reaches(w, False) for w in cmd.words):
        return True
    return bool(heads & _SUBSCRIPT_HEADS) and any(
        _subscript_shaped("".join(p.text for p in w.parts if p.kind in ("sq", "ansi", "lit", "dq")))
        or (_names_in(w) & reaches.tainted) for w in cmd.words[1:])


def _compound_reaches_arithmetic(script, reaches: _Reach) -> bool:
    """`(( ))` and a numeric test in `[[ ]]` with the quoted text (or a tainted name) as operand."""
    for comp in shell.iter_compounds(script):
        if comp.kind == "arith" and any(reaches(w, True) for w in comp.words):
            return True
        if comp.kind == "cond" and any(w.text in _EVALUATING_TESTS for w in comp.words) \
                and any(reaches(w, True) for w in comp.words):
            return True
    return False


def _expansion_reaches_arithmetic(script, tainted: set) -> bool:
    """`$(( ))`, `${x:off}` and `${a[i]}` expansions, and a nested shell string that evaluates a tainted name."""
    for _, parts in _tree_words(script):
        for part in _walk_parts(parts):
            if part.kind == "param" and tainted and _indirection_of(part.text) in tainted:
                return True  # `${!x}`, `${!x:-}`, zsh `${(P)x}`: the value of x is read as a name with a subscript
            if part.kind == "arith" and (_identifiers(part.text) & tainted or _single_quoted_substitution(part.inner)):
                return True
            if part.kind == "param" and _param_arithmetic(part.text) and (
                    _identifiers(part.text) & tainted or _single_quoted_substitution(part.inner)
                    or any(n in tainted for n in (_name_prefix(p.text[1:]) for p in part.inner if p.kind == "param"))):
                return True
            if tainted and part.kind in ("sq", "dq") and _arithmetic_hint(part.text) \
                    and _identifiers(part.text) & tainted:  # a nested shell that evaluates the name
                return True
    return False


def _indirection_of(text: str) -> str:
    """The name an indirect expansion reads as a name: `${!x}`, `${!x:-d}`, `${!x[@]}` is not (a list of keys), zsh
    `${(P)x}` and `${(PU)x}`; '' for any other expansion."""
    if text.startswith("${!"):
        name = _name_prefix(text[3:])
        return "" if text[3 + len(name):4 + len(name)] == "[" else name
    if text.startswith("${("):
        close = text.find(")")
        if close > 0 and "P" in text[3:close]:
            return _name_prefix(text[close + 1:])
    return ""


def _known_taint(values) -> set:
    """The names of the known values that hold `$(` or a backquote once the names in them are replaced
    (`d=$; x="a[${d}(c)]"`)."""
    out: set = set()
    if not values:
        return out
    for name, known in values.items():
        for value in known or ():
            if value is None:
                continue
            for text in _expand_values(value, values) or (value,):
                if _substitution_text(text):
                    out.add(name)
    return out


def _quoted_reaches_arithmetic(script, values=None) -> bool:
    """B1b: a `$(` or backquote that is quoted (or escaped), or that a known value or a `read` brings, is level B
    only when the text reaches a context that evaluates a subscript on it, where bash runs the substitution of
    `a[$(cmd)]`: an array subscript, `(( ))`, `$(( ))`, `$[ ]`, `${x:off}`, `let`, `declare -i`, a numeric or `-v`
    test, an indirection, whose operand is the quoted text itself or a variable that holds it (a name assigned from
    it, directly or through other names)."""
    sites = list(shell.iter_sites(script))
    tainted = _tainted_names(sites, _known_taint(values() if values is not None else None))
    reaches = _Reach(tainted)
    return (any(_command_reaches_arithmetic(site.cmd, reaches) for site in sites)
            or _compound_reaches_arithmetic(script, reaches)
            or _expansion_reaches_arithmetic(script, tainted))


class _Run:
    """The state of one `analyze_command` call: the text and its tree, what the commands found so far, and the
    values of its variables (computed when one is needed). One method per step of the reading of a simple command;
    each of them only adds to `categories`, `flags` and `reasons`."""

    __slots__ = ("command", "depth", "outer_env", "budget", "code", "script", "categories", "flags", "reasons",
                 "has_dollar", "funcs", "forwarded", "raws", "_values", "_views", "_names", "fwd_spans", "in_fwd")

    def __init__(self, command: str, depth: int, outer_env, budget, code: bool, script):
        self.command = command
        self.depth = depth
        self.outer_env = outer_env  # the values of the variables of the outer text (V3)
        self.budget = budget
        self.code = code
        self.script = script
        self.categories: list[str] = []
        self.flags: list[str] = []
        self.reasons: set[str] = set()
        # no expansion in the text: no value to resolve, none to pass down (the `GIT_CONFIG_*` names are values too)
        self.has_dollar = "$" in command or "GIT_CONFIG_" in command
        self.funcs = _forwarding_functions(script, command) if self.has_dollar and (
            "function" in command or "()" in command.replace(" ", "")) else {}
        self.forwarded: set = set()
        # the source spans of the bodies of the forwarding functions: what runs there is what the calls pass (D1)
        self.fwd_spans: list = _forwarding_spans(script, self.funcs) if self.funcs else []
        self.in_fwd = False  # the simple command being read sits in one of those bodies
        self.raws: list[str] = []
        self._values: list = []  # `_known_values` of the script, computed when a value is needed (V1-V4)
        self._views: dict[int, "_Values"] = {}
        self._names: list = []  # `_function_names` of the script, computed when a heredoc or here-string needs it

    def block(self, reason: str) -> None:
        _block(self.categories, self.flags, self.reasons, reason)

    def unclassified(self) -> None:
        self.categories.append("unclassified")
        self.flags.append("unclassified_command")

    def functions(self) -> frozenset:
        if not self._names:
            self._names.append(_function_names(self.script))
        return self._names[0]

    def values(self) -> "_Values":
        return _values_of(self.script, self.outer_env, self._values, self.command)

    def view_at(self, pos: int) -> "_Values":
        """The values of the variables at the offset `pos` of the text (a name not yet assigned there may hold the
        environment's value)."""
        view = self._views.get(pos)
        if view is None:
            view = self._views[pos] = self.values().at(pos)
        return view

    def code_text(self, text: str, env, code: bool = True, named: bool = True) -> None:
        """`named`: the text is a string a nested shell reads (not the source of a function body, which is in this
        text with its quotes)."""
        if named and self.funcs and _mentions(text, self.funcs):
            self.block("dynamic_code")  # a nested shell that names a forwarding function: `export -f f; bash -c 'f x'`
        _code_text(text, self.categories, self.flags, self.reasons, self.depth, self.budget, code, env)

    def forwarded_misuse(self, tokens: list[str], readings: Readings) -> None:
        """D1: a forwarding function named where it is not called with its arguments in view (`xargs f`, `eval f x`,
        `watch f`, `find -exec f`): what it runs is whatever that program passes, level B. Printing or inspecting
        its name is not a use."""
        starts = set(readings.starts)
        for i, token in enumerate(tokens):
            if token in self.funcs and i not in starts:
                if not any(_program_name(tokens[s]) in _NAME_ONLY_HEADS or tokens[s] in _CLASSIFIED_HEADS
                           for s in readings.starts if s < len(tokens)):
                    self.block("dynamic_code")
                    return

    def charge(self, cost: int) -> bool:
        """Charge the budget; False (and level B) when it is spent."""
        try:
            self.budget.charge(cost)
        except shell.BudgetExceeded:
            self.block("analysis_budget")
            return False
        return True

    def simple(self, site, tokens: list[str], readings: Readings) -> None:
        """One simple command of the tree with its readings."""
        self.reasons.update(readings.reasons)
        if not readings.complete:  # too many possible readings: not classified, blocked (no canary: already denied)
            self.unclassified()
            return
        cmd = site.cmd
        start, end = cmd.span
        self.raws.append(self.command[start:end])
        decoded = " ".join(tokens)  # the words as the shell sees them (`pu''sh`, `$'\x70ush'`): the canary reads them too
        if decoded != self.raws[-1]:
            self.raws.append(decoded)
        words = list(cmd.words)
        self.in_fwd = bool(self.fwd_spans) and any(lo <= start < hi for lo, hi in self.fwd_spans)
        if self.in_fwd:  # D1: a parameter of a forwarding function stands for what the calls pass: they are classified
            tokens, words = _neutral_positionals(tokens, words)
            readings = _token_readings(tokens)
            self.reasons.update(readings.reasons)
            if not readings.complete:
                self.unclassified()
                return
        if self.funcs:
            self.forwarded_misuse(tokens, readings)
        env = self.view_at(start) if self.has_dollar else _NO_VALUES
        variants, head_unresolved, from_variant = self.head_variants(tokens, words, readings, env)
        if head_unresolved:
            self.block("dynamic_code")
        for v_tokens, v_words, v_readings in variants:
            self.variant(site, v_tokens, v_words, v_readings, env, from_variant)

    def head_variants(self, tokens: list[str], words: list, readings: Readings, env: "_Values") -> "tuple[list, bool, bool]":
        """N6/V2: the readings of the command with its program made by a brace expansion or by a variable of known
        values, one per value: (variants, whether the program stays unresolved (level B), whether they come from
        values). A name the text assigns, with no value we can enumerate, is level B (a name from the environment
        alone is A)."""
        variants, head_unresolved, from_variant = [(tokens, words, readings)], False, False
        head = words[readings.starts[0]] if readings.starts and readings.starts[0] < len(words) else None
        # `{docker,restart} x`: the words the brace expansion makes, when known
        expanded = _brace_words(head) if head is not None and head.has_brace else None
        if expanded:
            s = readings.starts[0]
            new_tokens = tokens[:s] + expanded + tokens[s + 1:]
            variants = [(new_tokens, words[:s] + [None] * len(expanded) + words[s + 1:], _token_readings(new_tokens))]
        elif head is not None and head.has_brace:  # a brace expansion that cannot be known: level B (D1, M2)
            head_unresolved = len(readings.starts) == 1
        elif self.has_dollar and head is not None and "${" in head.text \
                and _head_kind(words, tokens, readings.starts[0]) == "expansion" and not _plain_variable(head):
            # D1, H4: `${PWD:+docker} restart x`, `"${X/ls/d}" restart y`: the word of the operator, or the
            # replacement, can be the program; each candidate is classified, and an operator that cannot be known is B
            s = readings.starts[0]
            texts = _operator_texts(tokens[s], env)
            if texts is None:
                head_unresolved = len(readings.starts) == 1
            for text in texts or ():
                pieces = text.split()
                new_tokens = tokens[:s] + pieces + tokens[s + 1:]
                variants.append((new_tokens, words[:s] + [None] * len(pieces) + words[s + 1:],
                                 _token_readings(new_tokens)))
        elif self.has_dollar and head is not None and _plain_variable(head):
            found, head_unresolved = _head_variants(tokens, words, readings, env)
            if found:
                variants, from_variant = found, True
                if _plain_variable(head) in env.soft:
                    if self.code:  # (in a code argument every expansion is level B, X3)
                        self.block("dynamic_code")
                    else:  # also a value from a command substitution: level A
                        self.reasons.add("dynamic_command")
            # (a variable that may be a wrapper argument, `timeout $a true`, is the ambiguity of
            # `prefix_readings`, level A: only a program in every reading is level B)
            head_unresolved = head_unresolved and len(readings.starts) == 1
        return variants, head_unresolved, from_variant

    def variant(self, site, tokens: list[str], words: list, readings: Readings, env: "_Values",
                from_variant: bool) -> None:
        """One reading of the command after the program's values: the known values of the verb positions of git,
        docker and gh (item 2), the aliases of git (item 6), then each resulting form."""
        cmd = site.cmd
        self.reasons.update(readings.reasons)
        if not readings.complete:
            self.unclassified()
            return
        arg_variants, args_unresolved = _arg_variants(tokens, words, readings, env)
        if args_unresolved:
            self.block("dynamic_code")
        # item 6: `git -c alias.p=push p` and the `GIT_CONFIG_*` variables: the alias as the command it is
        arg_variants, alias_code, alias_unresolved = _git_alias_variants(arg_variants, cmd, env)
        if alias_unresolved:
            self.block("dynamic_code")
        for code in alias_code:
            self.code_text(code, env if "$" in code else None)
        for a_tokens, a_words, a_readings in arg_variants:
            if (from_variant or len(arg_variants) > 1) and not self.charge(VARIANT_COST):
                break
            self.reading(site, a_tokens, a_words, a_readings, env, from_variant)

    def reading(self, site, tokens: list[str], words: list, readings: Readings, env: "_Values",
                from_variant: bool) -> None:
        """One final form of the command: its categories, then what the program being dynamic, a function it calls
        and the code in its arguments add."""
        self.reasons.update(readings.reasons)
        if not readings.complete:
            self.unclassified()
            return
        for n, seg in enumerate(readings.texts):
            seg_categories: list[str] = []
            _classify_segment(tokens, seg, seg_categories, self.flags, readings.starts[n])
            # an alternate reading only adds what it found, never its "other" (the primary owns that)
            self.categories.extend(seg_categories if n == 0 else [c for c in seg_categories if c != "other"])
        for s in readings.starts:  # `psql -c '\! cmd'`, `sqlite3 db '.shell cmd'`: the client runs a command
            if s < len(tokens) and _foreign_kind(tokens[s]) == "query" \
                    and any(_query_escape(t) for t in tokens[s + 1:]):
                self.block("dynamic_code")
        self.dynamic_program(words, tokens, readings, env, from_variant)
        self.forwarded_calls(site, tokens, words, readings, env)
        self.code_arguments(site, tokens, words, env)

    def dynamic_program(self, words: list, tokens: list[str], readings: Readings, env: "_Values",
                        from_variant: bool) -> None:
        """X3: the program that runs is made by an expansion in every reading (a reading that takes a wrapper
        argument as the program, `timeout "$T" docker ...`, is the ambiguity of `prefix_readings`, level A); N6: a
        single reading with a program that is a pattern or an expansion of no known value is level A,
        `dynamic_command`, unless the name comes from the text (a value that is itself dynamic), is a positional
        parameter, an array or may be set by `eval` / `source`: then it is level B. In a code argument every
        expansion is level B."""
        kinds = [_head_kind(words, tokens, s) for s in readings.starts]
        primary = words[readings.starts[0]] if readings.starts[0] < len(words) else None
        if kinds and kinds[0] is not None and (
                from_variant or (all(k == "expansion" for k in kinds) and primary is not None
                                 and _head_unsafe(primary, env))):
            self.block("dynamic_code")
        elif self.code and kinds and all(k == "expansion" for k in kinds):
            self.block("dynamic_code")
        elif len(kinds) == 1 and kinds[0] is not None:
            self.reasons.add("dynamic_command")

    def forwarded_calls(self, site, tokens: list[str], words: list, readings: Readings, env: "_Values") -> None:
        """B2 item 2: a call of a function of this text that forwards its arguments is classified with them."""
        for s in readings.starts:
            word = words[s] if s < len(words) else None
            bodies = self.funcs.get(tokens[s]) if s < len(tokens) and (word is None or not word.dynamic) else None
            if not bodies:
                continue
            if self.in_fwd:  # a forwarding function called from another one (or itself): a chain, not followed
                self.block("dynamic_code")
                continue
            # (an argument that is an expansion goes into the body as written: where it lands in the place of a
            # program or a verb the text is level B, `f $X` with `"$@"`; as the argument of `curl` it is not)
            args = [self.command[w.span[0]:w.span[1]] if w is not None else t
                    for w, t in zip(words[s + 1:], tokens[s + 1:])]
            for body in bodies:
                key = (id(site.cmd), body, tuple(args))
                if key in self.forwarded:
                    continue
                self.forwarded.add(key)
                if len(self.forwarded) > MAX_CODE_ARGS:
                    self.block("analysis_budget")
                    break
                marks = _positional_model(body)
                if marks is None:  # a use of the parameters the substitution does not model (V1): not resolved
                    self.block("dynamic_code")
                    continue
                text = _positional_text(body, args, tokens[s + 1:], marks)
                self.code_text(text, env if "$" in text else None, named=False)

    def code_arguments(self, site, tokens: list[str], words: list, env: "_Values") -> None:
        """X1-X6: the code the arguments of the command run, classified one level deeper."""
        cmd = site.cmd
        for text, reason in _code_args(site, tokens, words):
            texts = None if text is None else (_expand_values(text, env) if self.has_dollar else [text])
            if texts is None:  # unknown code (X3/X5), or more than MAX_VALUE_CANDIDATES values (V4)
                self.block(reason or "dynamic_code")
                continue
            inner = _with_prefix(env, self.values(), cmd) if cmd.assignments and self.has_dollar else env
            for code in texts:
                if len(texts) > 1 and not self.charge(VARIANT_COST):
                    break
                self.code_text(code, inner if "$" in code else None)

    def compound_heredocs(self) -> None:
        """A heredoc or here-string on a compound command (`{ bash; } <<EOF`) feeds code of unknown reach."""
        for compound in shell.iter_compounds(self.script):
            for redirect in compound.redirects:
                if redirect.heredoc is None and not (redirect.op == "<<<" and redirect.target is not None):
                    continue
                # a here-string is code only for a compound that may read code; a heredoc always is (HD4)
                reads = _compound_reads_code(compound, self.functions())
                if redirect.heredoc is None and not reads:
                    continue
                body = redirect.heredoc.body if redirect.heredoc is not None else redirect.target.text
                env = self.view_at(compound.span[0]) if "$" in body else None
                self.code_text(body, env, reads)

    def result(self) -> Analysis:
        flag_set = set(self.flags)  # the flag may come from another command of the same text
        if any(_deny_token_unmatched(raw, flag_set) for raw in self.raws):
            self.reasons.add("deny_token_unmatched")
        return Analysis(sorted(set(self.categories)) or ["other"], sorted(set(self.flags)), sorted(self.reasons))


def analyze_command(command: str, _depth: int = 0, _env=None, _budget=None, _code: bool = False) -> Analysis:
    """Classify a Bash command: categories, flags and the reasons of any parser uncertainty (spec
    audit-hook-hardening, section 3; audit-shell-lexer, section 4.1). The command is read by the shell parser, and
    every simple command of the tree is classified by its readings. Uncertainty never becomes an allow:
    alternative readings are all classified (level A), and what cannot be enumerated, does not parse or goes past
    a limit is `unclassified` / `unclassified_command` (level B). The arguments that run code (X1-X6) are analyzed
    one level deeper, through this same function. `_env` holds the values of the variables of the outer text
    (V3); the values assigned in this text resolve the program of a command (N6) and the variables of a code
    string (V2). `_budget` is the character budget shared by every parse of one analysis (nested texts);
    `_code`: the text is a code argument, where a command name made by an expansion is level B
    (`dynamic_code`, X3); outside one, it is level A (`dynamic_command`, N6) only for a name the text does not
    assign (the environment's); a name the text assigns whose value it cannot give is level B (B1)."""
    command = command or ""
    if len(command) > MAX_COMMAND_LEN:  # checked before any regex or parse touches the text
        return Analysis(["other"], ["command_too_long"], [])
    budget = _budget if _budget is not None else shell.Budget(MAX_LEX_CHARS)
    try:
        budget.charge(TEXT_COST)  # besides its length, which the parser charges: every text analyzed has a cost
        script = shell.parse(command, budget)
    except shell.NestingTooDeep:
        return _level_b("nesting_depth")
    except shell.BudgetExceeded:
        return _level_b("analysis_budget")
    except shell.ShellError:  # does not close, or is outside the subset: never read as a guess (S3)
        return _level_b("lex_error")
    run = _Run(command, _depth, _env, budget, _code, script)
    items = []
    for site in shell.iter_sites(script):
        tokens = [w.text for w in site.cmd.words]
        items.append((site, tokens, _token_readings(tokens)))
    if _code_evaluation(command, script, run.values):  # the shell evaluates text as code where no command is written
        run.block("dynamic_code")
    has_heredoc = "<<" in command
    disqualified = has_heredoc and _heredocs_disqualified(script, items)
    rebound_spans = _rebound_spans(script, items) if has_heredoc else ()
    grouped = _grouped_commands(script) if has_heredoc and not disqualified else ()
    for site, tokens, readings in items:
        run.simple(site, tokens, readings)
        if has_heredoc:
            _heredoc_code(site, readings, run.categories, run.flags, run.reasons, disqualified, _depth, budget,
                          run.view_at, id(site.cmd) in grouped, run.functions,
                          any(lo <= site.cmd.span[0] < hi for lo, hi in rebound_spans))
    if has_heredoc:
        run.compound_heredocs()
    return run.result()


def classify_command(command: str, _depth: int = 0) -> tuple[list[str], list[str]]:
    analysis = analyze_command(command, _depth)
    return analysis.categories, analysis.flags


def _classify_segment(tokens: list[str], seg: str, categories: list[str], flags: list[str], start: int = 0) -> None:
    """Classify one segment (already stripped of prefixes), appending to `categories` and `flags`.

    `tokens` are the words of the simple command and `start` is the index of the word where this reading begins
    (`Readings.starts`). The code the segment runs (`bash -c`, nvim `-c '!cmd'`) is read by `_code_args`."""
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
        if _is_git_commit(tokens[start:]):  # `commit` as the subcommand only (A2): not `config --get commit.x`
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
