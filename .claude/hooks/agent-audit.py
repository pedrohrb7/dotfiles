#!/usr/bin/env python3
"""Agent audit hook - records what agents do, never blocks (audit mode).

Wired in settings.json on PostToolUse, PostToolUseFailure, SubagentStart and SubagentStop.
Reads the hook payload (JSON) from stdin and appends one line per event to
~/.claude/metrics/<session_id>.jsonl. agent-metrics.py turns those lines into a report.

What it classifies (see agent-workflow.md, sections 13 and 14):
- Bash commands: tests (narrow/full/load), lint, typecheck, docker (read/build/lifecycle),
  git (commit/push), requests (local/external);
- file writes: inside or outside the active run's allowed_paths (from .claude/runs/<slug>.json);
- browser and screenshot tools.

Commands, file contents and tool outputs are not stored, only a truncated command line and paths.
Any error is swallowed: an audit hook must never break a session.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

METRICS_DIR = Path(os.environ.get("AGENT_AUDIT_DIR", str(Path.home() / ".claude" / "metrics")))
CONFIG_PATH = Path(__file__).resolve().with_name("agent-audit.json")
MAX_CMD = 300

IMPLEMENTERS = {
    "backend-node", "backend-spring", "backend-go", "backend-rust", "backend-python",
    "frontend-react", "mobile-react-native",
}

# Agents that must never write files.
READ_ONLY_AGENTS = {"ui-verifier", "test-runner", "code-reviewer", "security-reviewer", "Explore", "Plan"}

# Documentation files outside docs/ that only docs-writer edits.
DOC_FILES = {"README.md", "CHANGELOG.md", ".env.example", "DEPLOY.md"}

# Paths an implementer may always write, whatever its task's Files say.
ALWAYS_ALLOWED = [
    "**/package-lock.json", "**/pnpm-lock.yaml", "**/yarn.lock", "**/bun.lockb", "**/bun.lock",
    "**/poetry.lock", "**/uv.lock", "**/Cargo.lock", "**/go.sum", "**/Gemfile.lock",
    "**/migrations/**", "**/migration/**", "**/db/migrate/**", "**/alembic/versions/**",
    "**/__snapshots__/**", "**/*.snap",
]

VISUAL_TOOL = re.compile(r"(?i)(screenshot|browser|playwright|chrome|computer|simulator|emulator|snapshot)")

DIRECT_BINARIES = {"vitest", "jest", "mocha", "playwright", "eslint", "prettier", "tsc", "biome", "stylelint"}

SEGMENT_SPLIT = re.compile(r"\s*(?:&&|\|\||;|\||\n)\s*")
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=\S*$")

TEST_RUNNERS = re.compile(
    r"^(pytest|py\.test|jest|vitest|mocha|ava|go test|cargo test|cargo nextest|"
    r"\./mvnw\b.*\btest\b|mvn\b.*\btest\b|\./gradlew\b.*\btest\b|gradle\b.*\btest\b|"
    r"(npm|pnpm|yarn|bun)( run)? test[\w:-]*|(npm|pnpm|yarn|bun) (-C \S+ |--filter \S+ |-r |--recursive )*(run )?test[\w:-]*|"
    r"make test[\w-]*|just test[\w-]*|playwright test|npx (jest|vitest|playwright test)|"
    r"(uv|poetry) run (pytest|py\.test)|python -m pytest|dotnet test|rspec|phpunit)\b"
)
LOAD_RUNNERS = re.compile(r"^(k6|artillery|locust|jmeter|vegeta|ab|wrk)\b")
# test-narrow: a file or a test name; test-package: one package/service; test-full: the whole repo.
NARROW_HINT = re.compile(
    r"(\s-run\s|\s-k\s|\s--tests?\s|-Dtest=|\s-t\s|--testNamePattern|::|"
    r"\S+\.(test|spec)\.[cm]?[jt]sx?\b|\S+_test\.(go|py)\b|\Stest_\S+\.py\b|\S+Tests?\.(java|kt)\b|\S+_spec\.rb\b)"
)
PACKAGE_HINT = re.compile(
    r"(\s-C\s|\s--filter\s|\s-pl\s|\s-p\s|\s--package\s|\s:[\w-]+(:[\w-]+)*:test\b|"
    r"\s(\./)?[\w@.-]+(/[\w@.-]+)+/?(\.\.\.)?(\s|$))"
)
FULL_HINT = re.compile(r"(\s\./\.\.\.(\s|$)|\s--all\b|\s--workspace\b|\s-r\s|\s--recursive\b)")
LINT = re.compile(
    r"^(eslint|ruff check|ruff format|golangci-lint|go vet|gofmt|goimports|cargo clippy|cargo fmt|"
    r"ktlint|detekt|checkstyle|prettier|biome|stylelint|"
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


def strip_prefixes(segment: str) -> str:
    """Drop env assignments, `rtk`/`rtk proxy`, `sudo`, `time` and normalize docker compose global flags."""
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        tokens = segment.split()
    while tokens and (ENV_ASSIGN.match(tokens[0]) or tokens[0] in {"rtk", "proxy", "sudo", "time", "command", "exec"}):
        tokens.pop(0)
    # npx vitest / pnpm exec eslint / pnpm vitest -> vitest / eslint
    if tokens and tokens[0] in {"npx", "bunx"}:
        tokens.pop(0)
    elif len(tokens) > 1 and tokens[0] in {"pnpm", "yarn", "bun"}:
        if tokens[1] in {"exec", "x", "dlx"}:
            del tokens[:2]
        elif tokens[1] in DIRECT_BINARIES:
            tokens.pop(0)
    text = " ".join(tokens)
    if text.startswith("docker-compose"):
        text = "docker compose" + text[len("docker-compose"):]
    m = DOCKER_COMPOSE_FLAGS.match(text)
    if m:  # docker compose -f x.yml up -> docker compose up
        text = "docker compose" + text[m.end():]
    return text


def classify_command(command: str) -> tuple[list[str], list[str]]:
    categories: list[str] = []
    flags: list[str] = []
    for raw in SEGMENT_SPLIT.split(command or ""):
        seg = strip_prefixes(raw.strip())
        if not seg or seg.startswith("cd "):
            continue
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
        elif LOAD_RUNNERS.match(seg):
            categories.append("test-load")
        elif TEST_RUNNERS.match(seg):
            if FULL_HINT.search(padded):
                categories.append("test-full")
            elif NARROW_HINT.search(padded):
                categories.append("test-narrow")
            elif PACKAGE_HINT.search(padded):
                categories.append("test-package")
            else:
                categories.append("test-full")
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
    return sorted(set(categories)) or ["other"], sorted(set(flags))


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


def evaluate_write(path_str: str, cwd: str, actor: str, tool: str, response) -> dict:
    out: dict = {"path": path_str}
    path = Path(path_str)
    if not path.is_absolute():
        path = Path(cwd or ".") / path
    root = git_root(path.parent if path.parent.exists() else Path(cwd or "."))
    if not root:
        out["in_run"] = False
        return out
    try:
        rel = str(path.resolve().relative_to(root.resolve()))
    except Exception:
        rel = str(path)
    out["rel"] = rel
    out["area"] = "docs" if rel.startswith("docs/") else "run-state" if rel.startswith(".claude/runs/") else "code"
    created = isinstance(response, dict) and response.get("type") == "create"
    flags = []
    if rel.endswith(".md") and out["area"] != "docs" and (created or tool == "Write") and not rel.endswith(("README.md", "CLAUDE.md", "CHANGELOG.md")):
        flags.append("md_outside_docs")
    if actor in IMPLEMENTERS and (out["area"] == "docs" or Path(rel).name in DOC_FILES):
        flags.append("docs_write_by_implementer")
    if actor in READ_ONLY_AGENTS:
        flags.append("write_by_readonly_agent")
    if rel.startswith("docs/backlog/") and actor not in {"backlog-keeper", "unknown"}:
        flags.append("backlog_write_by_other")

    run = active_run(root)
    out["in_run"] = bool(run)
    if run:
        task = str(run.get("current_task", ""))
        out["run"] = run.get("_slug")
        out["task"] = task
        if actor in IMPLEMENTERS or actor in {"quality-fixer", "test-writer"}:
            allowed = list((run.get("allowed_paths") or {}).get(task, []))
            allowed += [
                s.get("target", "") for s in run.get("approved_scope", [])
                if str(s.get("task")) == task and s.get("decision", "approved") == "approved"
            ]
            in_scope = matches(rel, allowed + ALWAYS_ALLOWED)
            out["in_scope"] = in_scope
            if not in_scope:
                flags.append("out_of_scope_write")
    out["flags"] = flags
    return out


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    config = load_config()
    if config.get("mode", "audit") == "off":
        return

    event = payload.get("hook_event_name", "")
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
        record["failed"] = event == "PostToolUseFailure"
        flags: list[str] = []
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
            record.update(evaluate_write(path, payload.get("cwd", ""), actor, tool, payload.get("tool_response")))
            flags = record.pop("flags", [])
        elif VISUAL_TOOL.search(tool):
            record["categories"] = ["visual"]
            flags = [] if actor == "ui-verifier" else ["visual_tool"]
        else:
            return  # reads, searches and other tools are not audited
        record["flags"] = sorted(set(flags))

    if "in_run" not in record:  # tag commands and lifecycle events with the active /implement run
        root = git_root(Path(payload.get("cwd") or "."))
        run = active_run(root) if root else None
        record["in_run"] = bool(run)
        if run:
            record["run"] = run.get("_slug")
            record["task"] = str(run.get("current_task", ""))

    session = record.get("session") or "unknown"
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    with open(METRICS_DIR / f"{session}.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
