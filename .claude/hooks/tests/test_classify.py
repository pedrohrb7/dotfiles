"""Command classification of agent-audit.py: classify_command (and the readings behind it).

Source: docs/features/design-director/spec.md (Testing, cases C1-C37) and
docs/features/audit-hook-test-suite/spec.md (Testing, cases X1-X14) and
docs/features/lua-agent/spec.md (Testing, cases L1-L25 and the review-fix cases LR1-LR7: timeout option forms,
mise global flags, nvim shell escapes, busted `.lua` files, luarocks global flags, Neovim runner forms,
cross-stack effect of `timeout`).
All commands below are string literals only; nothing is executed.
"""
import shlex
import time
import unittest
from unittest import mock

from ._support import ForkedSuite, classifier

classify = classifier.classify_command

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


class GitCommitSubcommand(unittest.TestCase):
    """GC1 (audit-shell-lexer, A2): `commit` counts only as the git subcommand, after git's global options."""

    def test_gc1_commit_as_an_argument_is_not_a_commit(self):
        for command in ("git config --get commit.gpgsign", "S=$(git config --get commit.gpgsign)",
                        "echo $(git config --get commit.gpgsign)", "git log --grep commit", "git -C repo show commit"):
            with self.subTest(command=command):
                categories, flags = classify(command)
                self.assertNotIn("git_commit", flags)
                self.assertNotIn("git-commit", categories)
                self.assertIn("git-other", categories)
                self.assertEqual(classifier.analyze_command(command).uncertainty, [])

    def test_gc1_commit_as_the_subcommand_is_one(self):
        for command in ("git commit -m x", "git -C repo commit -m x", "git -c user.name=x commit -m x",
                        "git --git-dir=.git --no-pager commit -m x", "git --git-dir .git commit -m x",
                        "git --frobnicate x commit -m y", "/usr/bin/git commit -m x", "sudo git -C r commit -m x"):
            with self.subTest(command=command):
                self.assertEqual(classify(command), (["git-commit"], ["git_commit"]))


NV = "nvim --headless"
MT = "--noplugin -u scripts/minimal_init.lua"
PB = "{minimal_init = 'tests/minimal_init.lua'}"

# (case id, command, categories); flags are [] for all
LUA_TABLE = [
    ("L1", "busted", ["test-full"]),
    ("L2", "busted tests/config_test.lua", ["test-narrow"]),
    ("L2", "busted spec/orders_spec.lua", ["test-narrow"]),
    ("L3", "busted --filter export", ["test-narrow"]),
    ("L3", "busted --filter=export", ["test-narrow"]),
    ("L3", "busted -t unit", ["test-narrow"]),
    ("L3", "busted --tags=unit", ["test-narrow"]),
    ("L4", "busted spec/unit", ["test-package"]),
    ("L4", "busted lua/orders/", ["test-package"]),
    ("L5", "busted spec", ["test-full"]),
    ("L6", "./.luarocks/bin/busted --coverage -v tests/a_test.lua", ["test-narrow"]),
    ("L6", ".luarocks/bin/busted", ["test-full"]),
    ("L7", "luarocks test", ["test-full"]),
    ("L8", f'{NV} -u tests/minimal_init.lua -c "PlenaryBustedFile tests/a_spec.lua"', ["test-narrow"]),
    ("L9", f'{NV} -c "PlenaryBustedDirectory tests/ {PB}"', ["test-full"]),
    ("L9", f'{NV} -c "PlenaryBustedDirectory tests"', ["test-full"]),
    ("L10", f'{NV} -c "PlenaryBustedDirectory tests/unit {PB}"', ["test-package"]),
    ("L11", f"""{NV} {MT} -c "lua MiniTest.run_file('tests/test_a.lua')\"""", ["test-narrow"]),
    ("L11", f"""{NV} {MT} -c "lua MiniTest.run_at_location({{file = 'tests/test_a.lua', line = 3}})\"""", ["test-narrow"]),
    ("L12", f'{NV} {MT} -c "lua MiniTest.run()"', ["test-full"]),
    ("L12", f"""{NV} -c "lua require('mini.test').run()\"""", ["test-full"]),
    # audit-shell-lexer S2: the `;` is inside the quoted -c argument, so it is text and no longer splits the command
    # (the old quote-blind split made `vim.cmd('qa!')` a second command, which is where the `other` came from)
    ("L13", f"""{NV} -c "lua MiniTest.run(); vim.cmd('qa!')\"""", ["test-full"]),
    ("L14", f"{NV} -c checkhealth -c qa", ["other"]),
    ("L14", f"{NV} +qa", ["other"]),
    ("L14", "nvim lua/a.lua", ["other"]),
    ("L14", "nvim", ["other"]),
    ("L14", 'nvim -c "PlenaryBustedFile tests/a_spec.lua"', ["other"]),
    ("L14", "/usr/bin/nvim --version", ["other"]),
    ("L15", "mise run test", ["test-full"]),
    ("L15", "mise r test", ["test-full"]),
    ("L15", "mise tasks run test", ["test-full"]),
    ("L15", "mise test", ["test-full"]),
    ("L15", "mise run test:unit", ["test-full"]),
    ("L15", "mise run 'test:*'", ["test-full"]),
    ("L15", "mise run --force test", ["test-full"]),
    ("L15", "mise run -j 4 test", ["test-full"]),
    ("L15", "rtk mise run test", ["test-full"]),
    ("L16", "mise run test tests/a_spec.lua", ["test-narrow"]),
    ("L17", "mise run lint", ["lint"]),
    ("L17", "mise r lint:lua", ["lint"]),
    ("L17", "mise run format", ["lint"]),
    ("L17", "mise run format-check", ["lint"]),
    ("L17", "mise run fmt", ["lint"]),
    ("L18", "mise run all", ["test-full"]),
    ("L18", "mise run check", ["test-full"]),
    ("L18", "mise run ci", ["test-full"]),
    ("L18", "mise check", ["test-full"]),
    ("L19", "mise run setup", ["other"]),
    ("L19", "mise run clean", ["other"]),
    ("L19", "mise install", ["other"]),
    ("L19", "mise ls", ["other"]),
    ("L19", "mise test-tool node", ["other"]),
    # `-c` runs its value through a shell (mise docs), so the value is classified (X1)
    ("L19", "mise exec -c busted", ["other", "test-full"]),
    ("L20", "mise exec -- busted tests/a_spec.lua", ["test-narrow"]),
    ("L20", "mise x -- busted tests/a_spec.lua", ["test-narrow"]),
    ("L20", "mise exec lua@5.4 -- busted tests/a_spec.lua", ["test-narrow"]),
    ("L20", "mise x -C sub -- busted tests/a_spec.lua", ["test-narrow"]),
    ("L21", "mise exec -- busted", ["test-full"]),
    ("L22", "mise x -- luacheck lua/", ["lint"]),
    ("L23", "luacheck lua/ tests/", ["lint"]),
    ("L23", "./.luarocks/bin/luacheck lua/ --no-unused-args", ["lint"]),
    ("L23", "selene lua/", ["lint"]),
    ("L23", "stylua lua/", ["lint"]),
    ("L23", "stylua --check lua/", ["lint"]),
    ("L23", "treefmt", ["lint"]),
    ("L23", "treefmt --ci", ["lint"]),
    ("L24", "mise run format ::: test", ["lint", "test-full"]),
    ("L25", f'timeout 120 {NV} -u tests/minimal_init.lua -c "PlenaryBustedFile tests/a_spec.lua"', ["test-narrow"]),
    ("L25", "timeout --signal=KILL 60 busted tests/a_spec.lua", ["test-narrow"]),
    ("L25", "timeout -k 5 300 mise run test", ["test-full"]),
    ("L25", "timeout 60 pytest", ["test-full"]),
    ("L25", "timeout x busted", ["other", "test-full"]),  # fail closed: `x` may be a duration form we miss
    # LR1: every GNU timeout form, then the fail-closed fallback for shapes not understood
    ("LR1", "timeout --kill-after 5 60 docker compose restart api", ["docker-lifecycle"]),
    ("LR1", "timeout --kill-after=5 60 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout -k5 60 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout -sKILL 5 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout --signal KILL 5 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout --verbose 5 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout -v 5 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout -vk 5 60 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout --foreground --preserve-status 5 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout --kill 5 60 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout -- 5 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout .5 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout 1e3 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout inf docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout 0x10 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout 1.5m docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout 2h docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout --unknown-flag 5 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout -Z -k 5 60 docker restart x", ["docker-lifecycle"]),
    ("LR1", "timeout -Z busted tests/a_spec.lua", ["test-narrow"]),
    ("LR1", "timeout", ["other"]),
    ("LR1", "timeout 5", ["other"]),
    # LR2: mise global flags before exec / x
    ("LR2", "mise -C /tmp exec -- docker restart x", ["docker-lifecycle"]),
    ("LR2", "mise -q x -- docker compose down", ["docker-lifecycle"]),
    ("LR2", "mise --verbose x -- docker restart x", ["docker-lifecycle"]),
    ("LR2", "mise --log-level debug x -- docker restart x", ["docker-lifecycle"]),
    ("LR2", "mise -P dev x -- docker restart x", ["docker-lifecycle"]),
    ("LR2", "mise --profile dev exec -- docker restart x", ["docker-lifecycle"]),
    ("LR2", "mise -vC /tmp x -- docker restart x", ["docker-lifecycle"]),
    ("LR2", "mise -C /tmp x lua@5.4 -- busted tests/a_spec.lua", ["test-narrow"]),
    ("LR2", "mise --log-level debug run test", ["test-full"]),
    ("LR2", "mise -P dev run test tests/a_spec.lua", ["test-narrow"]),
    # LR3: shell escapes of nvim -c / +cmd are classified as their own commands
    ("LR3", f"{NV} -c 'PlenaryBustedFile a_spec.lua' -c '!docker restart x'", ["docker-lifecycle", "test-narrow"]),
    ("LR3", f"{NV} +'!docker restart x'", ["docker-lifecycle", "other"]),
    ("LR3", f"{NV} -c ':!docker compose down'", ["docker-lifecycle", "other"]),
    ("LR3", f"{NV} --cmd '!git push'", ["git-push", "other"]),
    ("LR3", f"{NV} -c 'silent !docker restart x'", ["docker-lifecycle", "other"]),
    ("LR3", f"{NV} -c 'w !docker restart x'", ["docker-lifecycle", "other"]),
    ("LR3", f"{NV} -c '!ls'", ["other"]),
    ("LR3", f"{NV} -c 'qa!'", ["other"]),
    # LR4: any `.lua` file argument makes busted narrow, a `.lua` option value does not
    ("LR4", "busted tests/test_config.lua", ["test-narrow"]),
    ("LR4", "busted spec/config.lua", ["test-narrow"]),
    ("LR4", "busted --helper spec/helper.lua", ["test-package"]),
    ("LR4", "busted --helper=spec/helper.lua", ["test-full"]),
    ("LR4", "busted --helper helper.lua", ["test-full"]),
    ("LR4", "busted -o utfTerminal.lua", ["test-full"]),
    # LR5: luarocks global flags before test
    ("LR5", "luarocks --lua-version 5.1 test", ["test-full"]),
    ("LR5", "luarocks --tree .rocks --local test", ["test-full"]),
    ("LR5", "luarocks --lua-version=5.1 test", ["test-full"]),
    ("LR5", "luarocks install busted", ["other"]),
    # LR6: Neovim runner forms
    ("LR6", f"""{NV} -c "lua require('plenary.test_harness').test_directory('tests/unit', {{}})\"""", ["test-package"]),
    ("LR6", f"""{NV} -c "lua require('plenary.test_harness').test_directory('tests')\"""", ["test-full"]),
    ("LR6", f"""{NV} -c "lua require('plenary.test_harness').test_file('tests/a_spec.lua')\"""", ["test-narrow"]),
    ("LR6", f"""{NV} -c 'lua require"mini.test".run()'""", ["test-full"]),
    ("LR6", f"""{NV} -c "lua require'mini.test'.run()\"""", ["test-full"]),
    ("LR6", f"""{NV} -c 'lua require"mini.test".run_file("tests/test_a.lua")'""", ["test-narrow"]),
    ("LR6", f"{NV} -c 'PlenaryBustedDirectory /home/u/proj/tests {PB}'", ["test-full"]),
    ("LR6", f"{NV} -c 'PlenaryBustedDirectory /home/u/proj/tests/unit {PB}'", ["test-package"]),
]

# (case id, command, categories, flags): the cross-stack effect of stripping `timeout` (spec S6)
TIMEOUT_CROSS_STACK = [
    ("LR7", "timeout 5 git push", ["git-push"], ["git_push"]),
    ("LR7", "timeout 60 docker compose up -d", ["docker-lifecycle"], ["docker_lifecycle"]),
    ("LR7", "timeout --kill-after 5 60 docker compose restart api", ["docker-lifecycle"], ["docker_lifecycle"]),
    ("LR7", "mise -C /tmp x -- docker restart x", ["docker-lifecycle"], ["docker_lifecycle"]),
    ("LR7", f"{NV} -c 'PlenaryBustedFile a_spec.lua' -c '!docker restart x'", ["docker-lifecycle", "test-narrow"],
     ["docker_lifecycle"]),
]


DOCKER_LIFECYCLE = (["docker-lifecycle"], ["docker_lifecycle"])

# (case id, command, categories, flags): review round 2 of lua-agent (task 1)
TIMEOUT_ROUND2 = [
    # leading whitespace in the duration is skipped by strtod
    ("LR8", "timeout ' 5' docker restart x", *DOCKER_LIFECYCLE),
    ("LR8", 'timeout "\t5" git push', ["git-push"], ["git_push"]),
    ("LR8", "timeout -k 1 ' 5s' docker compose down", *DOCKER_LIFECYCLE),
    ("LR8", "timeout -k ' 1' ' 5' docker compose down", *DOCKER_LIFECYCLE),
    # hex floats are durations
    ("LR9", "timeout 0x.8 docker restart x", *DOCKER_LIFECYCLE),
    ("LR9", "timeout +0x.8p1 docker restart x", *DOCKER_LIFECYCLE),
    ("LR9", "timeout 0x1.8p-1s git push", ["git-push"], ["git_push"]),
    # fail closed: a duration form the parser does not know cannot hide the command
    ("LR10", "timeout --bogus 5,5 docker restart x", ["docker-lifecycle", "other"], ["docker_lifecycle"]),
    ("LR10", "timeout 1e3x git push", ["git-push", "other"], ["git_push"]),
    ("LR10", "timeout weird git push", ["git-push", "other"], ["git_push"]),
    # normal commands do not pick up extra categories
    ("LR10", "timeout 5 pytest tests/test_a.py", ["test-narrow"], []),
    ("LR10", "timeout -k 1 5 docker ps", ["docker-read"], []),
    ("LR10", "timeout --signal=KILL 1e3 git status", ["git-other"], []),
]


class LuaCommands(unittest.TestCase):
    """Spec lua-agent, Testing, cases L1-L25: Lua test runners, linters, mise tasks and prefixes."""

    def test_lua_command_classification(self):
        for case, command, categories in LUA_TABLE:
            with self.subTest(case=case, command=command):
                got_categories, got_flags = classify(command)
                self.assertEqual(got_categories, categories)
                if not case.startswith("LR"):  # LR rows include docker/git commands; flags pinned in LR7
                    self.assertEqual(got_flags, [])

    def test_cross_stack_effect_of_timeout_and_shell_escapes(self):
        for case, command, categories, flags in TIMEOUT_CROSS_STACK:
            with self.subTest(case=case, command=command):
                self.assertEqual(classify(command), (categories, flags))

    def test_timeout_review_round_2_forms(self):
        for case, command, categories, flags in TIMEOUT_ROUND2:
            with self.subTest(case=case, command=command):
                self.assertEqual(classify(command), (categories, flags))

    def test_long_digit_token_does_not_backtrack(self):
        """LR11: a long digit duration candidate was quadratic and outlasted the 10 s hook timeout.

        The tokens stay under MAX_COMMAND_LEN, so the cap does not hide a regression in the parser itself."""
        for token in ("1" * 16000, "1" * 16000 + "x", "0x" + "1" * 16000 + "z", "1." + "1" * 16000 + "e"):
            command = f"timeout {token}x; docker restart x"
            with self.subTest(token=token[:12]):
                start = time.monotonic()
                result = classify(command)
                self.assertLess(time.monotonic() - start, 2.0)
                self.assertIn("docker-lifecycle", result[0])
                self.assertIn("docker_lifecycle", result[1])

    def test_nesting_deeper_than_the_cap_fails_closed(self):
        """LR12: shell escapes nested 4 levels deep are no longer dropped silently; since the audit-hook-hardening
        spec they are blocked as unclassified_command, not as a docker lifecycle command."""
        command = "docker ps"
        for _ in range(4):
            command = "nvim -c " + shlex.quote("!" + command)
        categories, flags = classify(command)
        self.assertIn("unclassified_command", flags)
        self.assertIn("unclassified", categories)
        self.assertNotIn("docker_lifecycle", flags)
        self.assertNotIn("docker-lifecycle", categories)
        self.assertEqual(classifier.analyze_command(command).uncertainty, ["nested_shell_depth"])

    def test_nesting_within_the_cap_is_still_classified(self):
        command = "docker restart x"
        for _ in range(3):
            command = "nvim -c " + shlex.quote("!" + command)
        categories, flags = classify(command)
        self.assertEqual(flags, ["docker_lifecycle"])
        self.assertIn("docker-lifecycle", categories)

    def test_long_or_odd_input_stays_bounded(self):
        for command in ("timeout " + "-v " * 5000 + "x", "mise " + "-q " * 5000 + "x", "timeout -k", "mise -C", "luarocks --tree"):
            with self.subTest(command=command[:30]):
                self.assertEqual(classify(command), (["other"], []))


# Third review round: `timeout` value options followed by a word the shell expands (LR13).
TIMEOUT_VALUE_OPTIONS = [
    ("LR13", 'T=5; timeout -s KILL "$T" docker restart x', ["docker-lifecycle", "other"], ["docker_lifecycle"]),
    ("LR13", 'timeout -k 5 "$T" docker restart x', ["docker-lifecycle", "other"], ["docker_lifecycle"]),
    ("LR13", "timeout --signal KILL $T docker compose up -d", ["docker-lifecycle", "other"], ["docker_lifecycle"]),
    ("LR13", "timeout --kill-after 1 $T docker restart x", ["docker-lifecycle", "other"], ["docker_lifecycle"]),
    ("LR13", "timeout --signal=KILL $T docker restart x", ["docker-lifecycle", "other"], ["docker_lifecycle"]),
    ("LR13", 'timeout -s KILL -k 1 "$T" git push', ["git-push", "other"], ["git_push"]),
    ("LR13", 'timeout -k 2 "$T" npm run lint', ["lint", "other"], []),
]


class Round3(unittest.TestCase):
    """Third review-fix round: timeout value options, nvim recursion cost, command length cap (spec lua-agent, task 1)."""

    def test_timeout_value_options_before_an_unknown_duration(self):
        for case, command, categories, flags in TIMEOUT_VALUE_OPTIONS:
            with self.subTest(case=case, command=command):
                self.assertEqual(classify(command), (categories, flags))

    def test_timeout_with_value_options_and_a_real_duration_is_unchanged(self):
        self.assertEqual(classify("timeout -k 5 10 docker restart x"), (["docker-lifecycle"], ["docker_lifecycle"]))
        self.assertEqual(classify("timeout -s KILL 5 npm run lint"), (["lint"], []))

    @staticmethod
    def amplifying_nvim_command(repeats):
        """Every `timeout nvim ...` reading starts with nvim, so each reading re-scanned the raw segment."""
        prefix = "timeout nvim timeout nvim timeout nvim nvim nvim nvim"
        inner = "true"
        for level in range(3):
            if level == 0:
                inner = prefix + " " + " ".join(["-c", "'!" + inner + "'"] * repeats)
            else:
                inner = prefix + " " + (" -c " + shlex.quote("!" + inner)) * repeats
        return inner

    def test_nvim_shell_texts_are_computed_once_per_raw_segment(self):
        """Before the cache, this shape made ~55x more calls (2404 vs 43) and grew with every reading."""
        command = self.amplifying_nvim_command(6)
        self.assertLess(len(command), classifier.MAX_COMMAND_LEN)
        with mock.patch.object(classifier, "nvim_shell_texts", wraps=classifier.nvim_shell_texts) as spy:
            start = time.monotonic()
            result = classify(command)
            elapsed = time.monotonic() - start
        self.assertLess(elapsed, 2.0)
        self.assertLess(spy.call_count, 100)
        self.assertEqual(result, (["other"], []))

    def test_nvim_shell_escape_is_still_found_under_variants(self):
        command = "timeout nvim " + "-c " + shlex.quote("!docker restart x")
        categories, flags = classify(command)
        self.assertIn("docker-lifecycle", categories)
        self.assertEqual(flags, ["docker_lifecycle"])


class CommandLengthCap(unittest.TestCase):
    """Commands over MAX_COMMAND_LEN are never fed to the regex classifier (every time-budget DoS class)."""

    def test_cap_is_16_kib(self):
        self.assertEqual(classifier.MAX_COMMAND_LEN, 16384)

    def test_one_char_over_the_cap_is_flagged(self):
        command = "echo " + "a" * (classifier.MAX_COMMAND_LEN - 4)
        self.assertEqual(len(command), classifier.MAX_COMMAND_LEN + 1)
        self.assertEqual(classify(command), (["other"], ["command_too_long"]))

    def test_exactly_the_cap_is_classified_normally(self):
        command = "pytest -k " + "a" * (classifier.MAX_COMMAND_LEN - len("pytest -k "))
        self.assertEqual(len(command), classifier.MAX_COMMAND_LEN)
        categories, flags = classify(command)
        self.assertEqual(flags, [])
        self.assertIn("test-narrow", categories)

    def test_the_cap_applies_before_heredoc_stripping(self):
        command = "cat <<EOF\n" + "x" * classifier.MAX_COMMAND_LEN + "\nEOF"
        self.assertEqual(classify(command), (["other"], ["command_too_long"]))

    def test_quadratic_shapes_are_denied_fast(self):
        shapes = {
            "spaces": "echo '" + " " * 50000 + "x'",
            "space-token": "docker" + " " * 50000 + "ps",
            "narrow-hint": "pytest " + "a." * 12500,
            "narrow-hint-long": "pytest " + "a" * 25000,
            "nvim-sil": "nvim -c '" + "sil " * 6250 + "x'",
        }
        for name, command in shapes.items():
            with self.subTest(shape=name):
                start = time.monotonic()
                result = classify(command)
                self.assertLess(time.monotonic() - start, 2.0)
                self.assertEqual(result, (["other"], ["command_too_long"]))

    def test_segment_split_is_linear_on_whitespace_under_the_cap(self):
        command = "echo a" + " " * 16000 + "; docker restart x"
        start = time.monotonic()
        result = classify(command)
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertIn("docker-lifecycle", result[0])

    def test_pieces_are_stripped_after_the_split(self):
        self.assertEqual(classify("  pytest tests/test_a.py \t&&\t  docker restart x  \n "),
                         (["docker-lifecycle", "test-narrow"], ["docker_lifecycle"]))
        # audit-shell-lexer S1: `SEGMENT_SPLIT` is gone, so its own assertion (the split of `a  ;  b`) is gone; the
        # parser gives words, never padded pieces, and the assertion above keeps checking the classification


class Round4Timing(unittest.TestCase):
    """Quadratic paths that fit under the length cap (lua-agent review round 4). Each shape is classified in
    well under the 2 s bound asserted here (the hook timeout is 10 s); the deny is asserted so a shortcut that
    skips the analysis cannot pass."""

    LIFECYCLE = "docker re" + "start x"  # assembled so the literal is not one in this file's text

    def assert_fast_lifecycle(self, command):
        self.assertLess(len(command), classifier.MAX_COMMAND_LEN)
        start = time.monotonic()
        categories, flags = classify(command)
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertIn("docker-lifecycle", categories)
        self.assertIn("docker_lifecycle", flags)

    def test_many_heredoc_openers_on_one_command(self):
        self.assert_fast_lifecycle("cat " + "<<a " * 2600 + "; " + self.LIFECYCLE)

    def test_require_followed_by_a_long_whitespace_run(self):
        self.assert_fast_lifecycle("nvim --headless -c 'require" + " " * 8500 + "'; " + self.LIFECYCLE)
        self.assert_fast_lifecycle(
            "timeout nvim timeout nvim timeout nvim nvim nvim --headless -c 'require" + " " * 8500 + "'; " + self.LIFECYCLE)

    def test_nvim_regexes_are_linear_on_whitespace(self):
        for name, text in {
            "mini": "require" + " " * 9000,
            "mini quote": "require(" + " " * 9000 + "x",
            "plenary": "require('plenary.test_harness')" + " " * 9000,
            "directory": "require('plenary.test_harness').test_directory(" + " " * 9000,
            "bare directory": "PlenaryBustedDirectory" + " " * 9000,
        }.items():
            with self.subTest(shape=name):
                start = time.monotonic()
                for rx in (classifier._NVIM_FILE, classifier._NVIM_DIRECTORY, classifier._NVIM_RUN):
                    rx.search(text)
                self.assertLess(time.monotonic() - start, 2.0)

    def test_test_file_hints_in_a_long_token(self):
        self.assert_fast_lifecycle("timeout pytest timeout pytest timeout pytest pytest pytest " + "test_" * 2200
                                   + "; " + self.LIFECYCLE)
        for name, token in {"dots": "a." * 4000, "underscore": "a_" * 4000, "tests": "Tests" * 2000}.items():
            with self.subTest(shape=name):
                self.assert_fast_lifecycle("pytest " + token + "; " + self.LIFECYCLE)

    def test_test_scope_runs_once_per_distinct_reading(self):
        classifier.test_scope.cache_clear()
        classify('timeout -k 2 "$T" pytest tests/test_a.py')
        first = classifier.test_scope.cache_info()
        classify('timeout -k 2 "$T" pytest tests/test_a.py')
        again = classifier.test_scope.cache_info()
        self.assertEqual(again.misses, first.misses)
        self.assertGreater(again.hits, first.hits)

    def test_nvim_category_is_cached_per_segment(self):
        classifier.nvim_category.cache_clear()
        classifier.nvim_category("nvim --headless -c 'PlenaryBustedFile x'")
        classifier.nvim_category("nvim --headless -c 'PlenaryBustedFile x'")
        info = classifier.nvim_category.cache_info()
        self.assertEqual((info.misses, info.hits), (1, 1))


class Round4Equivalence(unittest.TestCase):
    """The rewritten NARROW_HINT and nvim regexes classify like the originals."""

    def test_file_name_hints_are_still_narrow(self):
        for command in (
            "pytest tests/test_a.py", "pytest src/a_test.py", "go test pkg/a_test.go", "vitest src/a.test.ts",
            "jest src/a.spec.mjs", "mvn test FooTest.java", "mvn test FooTests.kt", "rspec spec/a_spec.rb",
            "busted spec/a_spec.lua", "make test x_test.lua", "pytest tests/test_a.py::test_b",
            "pytest -k name", "pytest -t name", "go test -run X", "gradle test --tests X", "mvn test -Dtest=X",
        ):
            with self.subTest(command=command):
                self.assertEqual(classify(command), (["test-narrow"], []))

    def test_non_hints_stay_wide(self):
        for command in ("pytest", "pytest tests/", "pytest test_a.py", "pytest a.test.", "jest .test.js",
                        "pytest a_test.pyc", "pytest test_a.pyc"):
            with self.subTest(command=command):
                self.assertNotIn("test-narrow", classify(command)[0])

    def test_a_token_over_512_chars_is_not_a_file_name(self):
        self.assertEqual(classify("pytest " + "a" * 600 + "_test.py"), (["test-full"], []))
        self.assertEqual(classify("pytest tests/" + "a" * 400 + "_test.py"), (["test-narrow"], []))

    def test_require_forms_still_recognized(self):
        for command, expected in (
            ("nvim --headless -c \"lua require('plenary.test_harness').test_file('a_spec.lua')\"", "test-narrow"),
            ("nvim --headless -c \"lua require ( 'plenary.test_harness' ) .test_directory ( 'tests/x' )\"", "test-package"),
            ("nvim --headless -c \"lua require'mini.test'.run_file('a.lua')\"", "test-narrow"),
            ("nvim --headless -c \"lua require( 'mini.test' ).run()\"", "test-full"),
            ("nvim --headless -c 'PlenaryBustedDirectory tests/x'", "test-package"),
            ("nvim --headless -c 'PlenaryBustedDirectory'", "test-full"),
        ):
            with self.subTest(command=command):
                self.assertEqual(classify(command)[0], [expected])


class AnsiCQuotedWords(unittest.TestCase):
    """Review fix B1: a `$'...'` part with certain text is classified by its decoded text (the words are built from
    pieces; nothing runs)."""

    def test_the_decoded_text_names_the_program_and_the_verb(self):
        for command, categories, flags in (
            ("$'\\x64ocker' re" + "start x", ["docker-lifecycle"], ["docker_lifecycle"]),
            ("git $'\\x70ush'", ["git-push"], ["git_push"]),
            ("git $'\\x63ommit' -m x", ["git-commit"], ["git_commit"]),
            ("docker compose $'\\165p' -d", ["docker-lifecycle"], ["docker_lifecycle"]),
            ("$'g\\u0069t' push", ["git-push"], ["git_push"]),
            ("sudo $'docker' stop x", ["docker-lifecycle"], ["docker_lifecycle"]),
            ("docker $'ps'", ["docker-read"], []),
            ("git $'status'", ["git-other"], []),
        ):
            with self.subTest(command=command):
                result = classifier.analyze_command(command)
                self.assertEqual((result.categories, result.flags, result.uncertainty), (categories, flags, []))

    def test_an_escape_that_cannot_be_decoded_with_certainty_is_not_guessed(self):
        for command in ("$'\\q'ocker x", "git $'pu\\qsh'", "$'\\x'ocker x"):
            with self.subTest(command=command):
                result = classifier.analyze_command(command)
                self.assertIn("unclassified_command", result.flags)
                self.assertIn("dynamic_code", result.uncertainty)


class ParserFormsAtTheHookLevel(unittest.TestCase):
    """Spec audit-shell-lexer, open question 10 (review fix part D2): the forms of the parser fix A5 and A6, asserted
    through the classifier, so a change in the classifier cannot lose one without a test failing. The blocked words
    are built from pieces; nothing runs."""

    LIFECYCLE = "docker re" + "start x"
    PUSH = "git pu" + "sh"

    def result(self, command):
        result = classifier.analyze_command(command)
        return result.categories, result.flags, result.uncertainty

    def assert_lifecycle(self, command):
        categories, flags, uncertainty = self.result(command)
        self.assertIn("docker-lifecycle", categories, command)
        self.assertEqual((flags, uncertainty), (["docker_lifecycle"], []), command)

    def assert_level_b(self, command, reason):
        categories, flags, uncertainty = self.result(command)
        self.assertEqual((flags, uncertainty), (["unclassified_command"], [reason]), command)
        self.assertIn("unclassified", categories)

    def test_decoded_ansi_c_heads_and_verbs(self):
        for command in ("$'\\x64ocker' re" + "start x", "$'\\144ocker' re" + "start x", "docker $'re\\x73tart' x",
                        "$'git' $'\\x70ush'", "sudo $'\\x67it' pu" + "sh", "env A=1 $'docker' re" + "start x"):
            with self.subTest(command=command):
                categories, flags, uncertainty = self.result(command)
                self.assertTrue(set(flags) & {"docker_lifecycle", "git_push"}, (command, flags))
                self.assertEqual(uncertainty, [])
        self.assert_level_b("$'\\q'ocker x", "dynamic_code")
        self.assert_level_b("git $'pu\\qsh'", "dynamic_code")

    def test_a_process_substitution_inside_a_word_or_a_conditional_is_a_nested_script(self):
        for command in ("A=<(true) " + self.LIFECYCLE, "echo a<(" + self.LIFECYCLE + ")b", "cat <(" + self.LIFECYCLE + ")",
                        "[[ -n <(" + self.LIFECYCLE + ") ]]", "[[ -n >(" + self.LIFECYCLE + ") ]]"):
            with self.subTest(command=command):
                self.assert_lifecycle(command)
        self.assertEqual(self.result("[[ -n <(true) ]]"), (["other"], [], []))

    def test_zsh_expansions_at_the_head_are_level_b(self):
        for command in ("$=X restart x", "$~X restart x", "$^X restart x", "${=X} restart x", "$=X"):
            with self.subTest(command=command):
                self.assert_level_b(command, "dynamic_code")
        self.assertEqual(self.result("echo $=X"), (["other"], [], []))  # an argument is data

    def test_repeat_with_a_brace_body_is_rejected_and_the_wrapper_form_is_read(self):
        self.assert_level_b("repeat 2 { " + self.LIFECYCLE + " }", "lex_error")
        self.assert_lifecycle("repeat 2 " + self.LIFECYCLE)
        self.assertEqual(self.result("repeat 2 true"), (["other"], [], []))

    def test_a_pending_heredoc_is_read_at_the_newline_inside_a_conditional_or_an_array(self):
        for quote in ("'EOF'", "EOF"):
            for opener in ("[[ a == b", "x=( a"):
                closer = " ]]" if opener.startswith("[[") else " b )"
                with self.subTest(quote=quote, opener=opener):
                    categories, flags, uncertainty = self.result(
                        f"cat <<{quote} && {opener}\n{self.LIFECYCLE}\nEOF\n{closer}")
                    self.assertEqual((categories, flags), (["other"], []))  # the body is data, not commands
                    self.assertNotIn("lex_error", uncertainty)
        for opener, closer in (("[[ a == b", " ]]"), ("x=( a", " b )")):  # an unquoted body still substitutes
            with self.subTest(opener=opener):
                self.assert_lifecycle(f"cat <<EOF && {opener}\n$({self.LIFECYCLE})\nEOF\n{closer}")
        self.assert_lifecycle("cat <<'EOF' && x=( a\nEOF\n b ); " + self.LIFECYCLE)

    def test_a_heredoc_delimiter_written_with_an_ansi_c_escape_closes_the_body(self):
        self.assertEqual(self.result("cat <<$'E\\x4fF'\n" + self.LIFECYCLE + "\nEOF\n"), (["other"], [], []))

    def test_forms_that_evaluate_text_as_code_are_level_b(self):
        for command in ("echo ${(e)X}", "echo ${X@P}", "echo ${(%)X}", "echo ${(e)${X}}", 'echo "${X@P}"'):
            with self.subTest(command=command):
                self.assert_level_b(command, "dynamic_code")
        for command in ("echo ${(L)X}", "echo ${X@Q}", "echo ${X@U}"):
            with self.subTest(command=command):
                self.assertEqual(self.result(command), (["other"], [], []))


class HeredocOpenerBound(unittest.TestCase):
    """More than MAX_HEREDOC_OPENERS openers: nothing is stripped (fail closed)."""

    def body(self, openers):
        return classify("cat " + "<<a " * openers + "\n" + "docker re" + "start x" + "\na\n")

    def test_up_to_the_bound_the_data_body_is_stripped(self):
        self.assertEqual(classifier.MAX_HEREDOC_OPENERS, 32)
        self.assertEqual(self.body(2), (["other"], []))
        self.assertEqual(self.body(classifier.MAX_HEREDOC_OPENERS), (["other"], []))

    def test_over_the_bound_the_body_is_classified_as_commands(self):
        categories, flags = self.body(classifier.MAX_HEREDOC_OPENERS + 1)
        self.assertIn("docker-lifecycle", categories)
        self.assertEqual(flags, ["docker_lifecycle"])

    def test_the_sink_verdict_is_shared_by_the_openers_of_one_command(self):
        """audit-shell-lexer, tests that change: `strip_heredoc_bodies` and `_is_data_sink` are gone; the spy is on
        `_heredoc_is_data`, reached through `analyze_command`, still one verdict per simple command."""
        with mock.patch.object(classifier, "_heredoc_is_data", wraps=classifier._heredoc_is_data) as sink:
            classifier.analyze_command("cat <<a <<b <<c\nx\na\ny\nb\nz\nc\n")
        self.assertEqual(sink.call_count, 1)
        with mock.patch.object(classifier, "_heredoc_is_data", wraps=classifier._heredoc_is_data) as sink:
            classifier.analyze_command("cat <<a\nx\na\ncat <<b\ny\nb\n")
        self.assertEqual(sink.call_count, 2)


def load_tests(loader, tests, pattern):
    """Independent cases: run them in forked workers (see `ForkedSuite`)."""
    return ForkedSuite(tests)


if __name__ == "__main__":
    unittest.main()
