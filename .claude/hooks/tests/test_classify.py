"""Command classification of agent-audit.py: classify_command and strip_prefixes.

Source: docs/features/design-director/spec.md (Testing, cases C1-C37) and
docs/features/audit-hook-test-suite/spec.md (Testing, cases X1-X14).
All commands below are string literals only; nothing is executed.
"""
import unittest

from ._support import audit

classify = audit.classify_command

# (case id, command, categories, flags)
COMMAND_TABLE = [
    ("C1", "pytest tests/test_orders.py", ["test-narrow"], []),
    ("C2", "pytest -k export", ["test-narrow"], []),
    ("C3", "pytest", ["test-full"], []),
    ("C4", "go test ./internal/orders/", ["test-package"], []),
    ("C5", "go test ./...", ["test-full"], []),
    ("C6", "go test -run TestExport ./internal/orders", ["test-narrow"], []),
    ("C7", "cargo test", ["test-full"], []),
    ("C8", "cargo test -p orders", ["test-package"], []),
    ("C9", "npx vitest run src/a.test.ts", ["test-narrow"], []),
    ("C10", "pnpm exec vitest run src/a.test.ts", ["test-narrow"], []),
    ("C11", "pnpm vitest run", ["test-full"], []),
    ("C12", "pnpm --filter api test", ["test-package"], []),
    ("C13", "pnpm -r test", ["test-full"], []),
    ("C14", "npm test", ["test-full"], []),
    ("C15", "rtk pnpm test", ["test-full"], []),
    ("C16", "./mvnw test -Dtest=OrderTest", ["test-narrow"], []),
    ("C17", "./gradlew :api:test", ["test-package"], []),
    ("C18", "uv run pytest tests/test_x.py::test_y", ["test-narrow"], []),
    ("C19", "k6 run load.js", ["test-load"], []),
    ("C20", "eslint src/a.ts", ["lint"], []),
    ("C21", "pnpm lint", ["lint"], []),
    ("C22", "ruff check .", ["lint"], []),
    ("C23", "tsc --noEmit", ["typecheck"], []),
    ("C24", "pnpm typecheck", ["typecheck"], []),
    ("C25", "uv run mypy src", ["typecheck"], []),
    ("C26", "docker compose ps", ["docker-read"], []),
    ("C27", "docker compose -f x.yml up -d", ["docker-lifecycle"], ["docker_lifecycle"]),
    ("C28", "rtk docker compose restart api", ["docker-lifecycle"], ["docker_lifecycle"]),
    ("C29", "docker build -t x .", ["docker-build"], ["docker_build"]),
    ("C30", "docker logs api --since 2m", ["docker-read"], []),
    ("C31", "git status", ["git-other"], []),
    ("C32", "git commit -m x", ["git-commit"], ["git_commit"]),
    ("C33", "git push origin main", ["git-push"], ["git_push"]),
    ("C34", "curl -s http://localhost:3000/health", ["request-local"], []),
    ("C35", "curl -s http://api:3000/orders", ["request-local"], []),
    ("C36", "curl https://example.com/x", ["request-external"], ["external_request"]),
    ("C37", "cd /tmp && ls", ["other"], []),
]

# (case id, commands, categories, flags); every command of a row has the same expectation.
PREFIX_TABLE = [
    ("X1", ["sudo docker restart api"], ["docker-lifecycle"], ["docker_lifecycle"]),
    ("X2", ["docker-compose up"], ["docker-lifecycle"], ["docker_lifecycle"]),
    ("X3", ["docker compose -p p --profile dev up"], ["docker-lifecycle"], ["docker_lifecycle"]),
    ("X4", ["docker compose --env-file .env logs api"], ["docker-read"], []),
    ("X5", ["docker compose build api", "docker buildx build ."], ["docker-build"], ["docker_build"]),
    ("X6", ["docker compose exec api sh"], ["docker-lifecycle"], ["docker_lifecycle"]),
    ("X7", ["docker version"], ["docker-other"], []),
    ("X8", ["git -C repo commit -m x"], ["git-commit"], ["git_commit"]),
    (
        "X9",
        ["git add . && git commit -m x && git push"],
        ["git-commit", "git-other", "git-push"],
        ["git_commit", "git_push"],
    ),
    ("X10", ["curl http://localhost:3000 https://example.com"], ["request-external"], ["external_request"]),
    (
        "X11",
        ["curl -s http://[::1]:8080/x", "wget http://0.0.0.0/", "http :3000/x", "curl -s"],
        ["request-local"],
        [],
    ),
    # the full-repo hint wins over the narrow one
    ("X12", ["go test ./... -run X"], ["test-full"], []),
    (
        "X13",
        ["time FOO=1 rtk proxy pytest tests/test_a.py", "yarn jest src/a.test.ts"],
        ["test-narrow"],
        [],
    ),
    ("X14", ["", None], ["other"], []),
]


class CommandTable(unittest.TestCase):
    """Spec design-director, Testing, cases C1-C37: one subTest per command."""

    def test_command_classification(self):
        for case, command, categories, flags in COMMAND_TABLE:
            with self.subTest(case=case, command=command):
                self.assertEqual(classify(command), (categories, flags))


class PrefixesAndSegments(unittest.TestCase):
    """Spec audit-hook-test-suite, Testing, cases X1-X14: prefixes, global options and segments."""

    def test_prefixes_and_segments(self):
        for case, commands, categories, flags in PREFIX_TABLE:
            for command in commands:
                with self.subTest(case=case, command=command):
                    self.assertEqual(classify(command), (categories, flags))


if __name__ == "__main__":
    unittest.main()
