"""Readings by position, uncertainty reasons and `unclassified_command` of agent-audit.py.

Source: docs/features/audit-hook-hardening/spec.md (Testing, `test_uncertainty.py`, cases UN1-UN13; HS8 belongs
to the heredoc task). All commands below are string literals only; nothing is executed.
"""
import contextlib
import json
import shlex
import time
import unittest
from unittest import mock

from ._support import (HOOKS_DIR, ForkedSuite, HookProcess, TEST_CONFIG, TempRepoCase, audit, call_main, classifier,
                       config, payload)
from .test_classify import COMMAND_TABLE, LUA_TABLE, PREFIX_TABLE, TIMEOUT_CROSS_STACK, TIMEOUT_ROUND2, TIMEOUT_VALUE_OPTIONS

analyze = classifier.analyze_command
readings = classifier.command_readings

DOCKER_UP = "docker compose up -d"


class CommandReadings(unittest.TestCase):
    """UN1: the readings of one piece, deduplicated, the primary first."""

    def test_un1_one_reading_without_a_reason(self):
        for command, texts in (("timeout 5 x", ["x"]), ("rtk proxy sudo x", ["x"])):
            with self.subTest(command=command):
                got = readings(command)
                self.assertEqual(got.texts, texts)
                self.assertEqual(got.reasons, frozenset())
                self.assertTrue(got.complete)

    def test_un1_an_unknown_duration_gives_several_readings(self):
        got = readings('timeout "$T" x')
        self.assertEqual(got.texts, ["$T x", "x"])
        self.assertEqual(got.reasons, frozenset({"prefix_readings"}))
        got = readings('timeout -s KILL "$T" docker restart x')
        self.assertIn("docker restart x", got.texts)
        self.assertEqual(got.reasons, frozenset({"prefix_readings"}))

    def test_a_mise_exec_prefix_is_cut_up_to_the_double_dash(self):
        self.assertEqual(readings("mise -C /tmp x -- docker restart x").texts, ["docker restart x"])
        self.assertEqual(readings("mise x lua").texts, ["mise x lua"])  # no `--`: the command itself

    def test_the_search_is_over_positions_and_ends_on_degenerate_input(self):
        for command in ("timeout", "timeout -s", "sudo", "mise x", "FOO=1", ""):
            with self.subTest(command=command):
                self.assertTrue(readings(command).complete)


class ChainedWrappers(unittest.TestCase):
    """UN2-UN4: no depth cap, a cap on distinct readings only, linear cost."""

    def test_un2_stacked_timeouts_no_longer_hide_the_command(self):
        for k in (4, 5, 7):
            for command, flag in (("docker restart x", "docker_lifecycle"), ("git push", "git_push")):
                with self.subTest(k=k, command=command):
                    categories, flags = classifier.classify_command("timeout a " * k + command)
                    self.assertIn(flag, flags)
                    self.assertIn("other", categories)

    def test_un3_more_readings_than_the_cap_is_unclassified(self):
        for k in (8, 20, 1600):  # 1600 * 10 characters: just under MAX_COMMAND_LEN
            with self.subTest(k=k):
                with self.bounded():
                    result = analyze("timeout a " * k + "docker restart x")
                self.assertEqual((result.categories, result.flags), (["unclassified"], ["unclassified_command"]))
                self.assertEqual(result.uncertainty, ["readings_cap"])

    def test_un3_the_incomplete_piece_is_not_classified_further(self):
        got = readings("timeout a " * 9 + "docker restart x")
        self.assertFalse(got.complete)
        self.assertEqual(got.texts, [])
        self.assertIn("readings_cap", got.reasons)

    def test_un3_other_pieces_of_the_command_are_still_classified(self):
        result = analyze("timeout a " * 9 + "x; docker restart x")
        self.assertIn("docker_lifecycle", result.flags)
        self.assertIn("unclassified_command", result.flags)

    def test_un4_long_chains_stay_linear(self):
        with self.bounded():
            result = analyze("timeout zz " * 1450)
        self.assertEqual(result.uncertainty, ["readings_cap"])
        with self.bounded():
            categories, flags = classifier.classify_command("timeout 5 " * 1600 + "docker restart x")
        self.assertEqual((categories, flags), (["docker-lifecycle"], ["docker_lifecycle"]))
        self.assertEqual(analyze("timeout 5 " * 1600 + "docker restart x").uncertainty, [])

    # The tight bound is CPU time (`process_time`): the property is linear cost, and a loaded machine or the
    # parallel workers of the suite must not turn it into a flaky check. The loose wall-clock bound keeps the
    # wall-time budget of the hook checked too.
    @contextlib.contextmanager
    def bounded(self, cpu=1.0, wall=3.0):
        cpu_start, wall_start = time.process_time(), time.monotonic()
        yield
        self.assertLess(time.process_time() - cpu_start, cpu)
        self.assertLess(time.monotonic() - wall_start, wall)

    def assert_bounded(self, command):
        with self.bounded():
            analyze(command)

    # One test per command (about 0.2 s each of real work): no single test of the suite takes longer than 0.5 s.
    def test_un4_alternating_value_options_stay_bounded_dash_s(self):
        self.assert_bounded("timeout -s " * 1400 + "x")

    def test_un4_alternating_value_options_stay_bounded_dash_k(self):
        self.assert_bounded("timeout -k 1 " * 1200 + "x")

    def test_un4_alternating_value_options_stay_bounded_double_dash(self):
        self.assert_bounded("timeout -- " * 1400 + "x")

    def test_un5_the_primary_reading_owns_other(self):
        self.assertEqual(classifier.classify_command("timeout x busted"), (["other", "test-full"], []))
        self.assertEqual(classifier.classify_command('timeout -k 2 "$T" npm run lint'), (["lint", "other"], []))

    def test_un13_a_comma_decimal_duration_is_covered_by_the_union(self):
        self.assertEqual(classifier.classify_command("timeout 0,5 docker restart x")[1], ["docker_lifecycle"])


class NvimDepth(unittest.TestCase):
    """UN6: the depth cap is level B, with its own category."""

    @staticmethod
    def nested(levels, inner="docker restart x"):
        command = inner
        for _ in range(levels):
            command = "nvim -c " + shlex.quote("!" + command)
        return command

    def test_un6_three_levels_are_classified(self):
        result = analyze(self.nested(3))
        self.assertEqual(result.flags, ["docker_lifecycle"])
        self.assertEqual(result.uncertainty, [])

    def test_un6_four_levels_are_unclassified(self):
        result = analyze(self.nested(4))
        self.assertIn("unclassified_command", result.flags)
        self.assertIn("unclassified", result.categories)
        self.assertNotIn("docker_lifecycle", result.flags)
        self.assertEqual(result.uncertainty, ["nested_shell_depth"])

    def test_un6_the_reasons_of_a_nested_text_come_up(self):
        command = "nvim -c " + shlex.quote("!" + 'timeout "$T" docker restart x')
        result = analyze(command)
        self.assertIn("docker_lifecycle", result.flags)
        self.assertEqual(result.uncertainty, ["prefix_readings"])


class ClassifierError(TempRepoCase):
    """UN7: an exception in the classifier is never an allow."""

    def run_broken(self, event, actor):
        with mock.patch.object(classifier, "_classify_segment", side_effect=RecursionError("deep")):
            return call_main(payload(event, "Bash", actor=actor, cwd=self.repo, tool_input={"command": "echo hi"}))

    def test_un7_pre_denies_for_an_agent_and_for_main(self):
        for actor in ("backend-python", "main"):
            with self.subTest(actor=actor):
                res = self.run_broken("PreToolUse", actor)
                spec = res.output["hookSpecificOutput"]
                self.assertEqual(spec["permissionDecision"], "deny")
                self.assertIn("Agent workflow (unclassified_command)", spec["permissionDecisionReason"])
                [record] = res.records
                self.assertEqual(record["uncertainty"], ["classifier_error"])
                self.assertEqual(record["error"], "RecursionError")
                self.assertEqual(record["categories"], ["unclassified"])
                self.assertEqual(record["decision_category"], "unclassified_command")
                self.assertEqual(record["cmd"], "echo hi")

    def test_un7_post_records_without_output(self):
        res = self.run_broken("PostToolUse", "backend-python")
        self.assertIsNone(res.output)
        [record] = res.records
        self.assertEqual(record["uncertainty"], ["classifier_error"])
        self.assertEqual(record["error"], "RecursionError")
        self.assertIn("unclassified_command", record["flags"])

    def test_the_error_name_is_recorded_never_the_message(self):
        with mock.patch.object(classifier, "_classify_segment", side_effect=ValueError("secret text")):
            res = call_main(payload("PostToolUse", "Bash", cwd=self.repo, tool_input={"command": "echo hi"}))
        self.assertEqual(res.records[0]["error"], "ValueError")
        self.assertNotIn("secret", str(res.records[0]))

    def test_an_error_while_evaluating_a_write_is_also_blocked(self):
        with mock.patch.object(audit, "evaluate_write", side_effect=KeyError("x")):
            res = call_main(payload("PreToolUse", "Write", actor="backend-python", cwd=self.repo,
                                    tool_input={"file_path": str(self.repo / "a.py")}))
        self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(res.records[0]["error"], "KeyError")


class TextThatDoesNotClose(unittest.TestCase):
    """UN8, as changed by audit-shell-lexer (S3): a text that does not close is level B (`lex_error`), never read
    twice with a tolerant reading. It is still denied; the reason is the new one."""

    LEVEL_B = (["unclassified"], ["unclassified_command"])

    def test_un8_an_unbalanced_quote_cannot_hide_the_command(self):
        for command in ("\"docker\" restart x '", 'A="x y docker restart api'):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual((result.categories, result.flags), self.LEVEL_B)
                self.assertEqual(result.uncertainty, ["lex_error"])

    def test_un8_a_quoted_separator_is_not_a_false_positive(self):
        result = analyze('echo "a; b"')
        self.assertEqual((result.categories, result.flags), (["other"], []))
        self.assertEqual(result.uncertainty, [])

    def test_un8_the_reason_is_lex_error_and_closed_quotes_have_none(self):
        """The old test needed two different readings; there is one reading now, so a closed quote has no reason
        and the unclosed one has `lex_error` (`Readings.fallback` is gone)."""
        for command in ('grep -E "a|b" f', 'git commit -m "a|b"', 'echo "a; b"', 'echo "a && b" c', 'pytest -k "a or b"'):
            with self.subTest(command=command):
                self.assertEqual(analyze(command).uncertainty, [])
        self.assertEqual(analyze('echo "a').uncertainty, ["lex_error"])
        got = readings('echo "a')
        self.assertEqual((got.texts, got.complete, got.reasons), ([], False, frozenset({"lex_error"})))


class EnvAssignmentPrefix(TempRepoCase):
    """A quoted assignment value may hold spaces; it is a prefix, never the command (review fix, security HIGH)."""

    def test_a_quoted_value_with_spaces_still_reaches_the_command(self):
        for command, flag in (('A="x y" docker restart api', "docker_lifecycle"), ("A='x y' git push", "git_push"),
                              ('A="1" B="2 3" git commit -m x', "git_commit")):
            with self.subTest(command=command):
                self.assertIn(flag, analyze(command).flags)
                res = call_main(payload("PreToolUse", "Bash", actor="backend-python", cwd=self.repo,
                                        tool_input={"command": command}))
                self.assertIn(res.output["hookSpecificOutput"]["permissionDecision"], ("deny", "ask"))

    def test_the_append_form_is_a_prefix_too(self):
        """`NAME+=value` is a prefix assignment in bash: it never hides the command (review fix, security HIGH)."""
        for command, flag in (("A+=x docker restart api", "docker_lifecycle"), ('A+="x y" docker restart api', "docker_lifecycle"),
                              ("A+=x git push", "git_push"), ("A=1 B+='x y' git commit -m x", "git_commit")):
            with self.subTest(command=command):
                self.assertIn(flag, analyze(command).flags)
                res = call_main(payload("PreToolUse", "Bash", actor="backend-python", cwd=self.repo,
                                        tool_input={"command": command}))
                self.assertIn(res.output["hookSpecificOutput"]["permissionDecision"], ("deny", "ask"))
        self.assertEqual(readings("A+=x echo hi").texts, ["echo hi"])
        # audit-shell-lexer S8: `_opens_unclosed_quote` is gone; the assignment rule is `shell.ASSIGNMENT`, and the
        # bash executes the command after `A[0]=x` (`A[0]=x docker restart api` is an assignment prefix)
        self.assertTrue(classifier.shell.ASSIGNMENT.match('A+="x'))
        self.assertTrue(classifier.shell.ASSIGNMENT.match("A[0]=x"))

    def test_a_window_that_ends_before_the_command_is_closed(self):
        """audit-shell-lexer, tests that change (closes the HIGH of eee112a): the `#` is a comment (S4), the
        quotes close, so there is no loose window to end early: the command is `docker_lifecycle`, no uncertainty
        reason, and the hook denies it."""
        for command in ('A="x y z w v" docker restart api # "', "A='x y z w v' docker restart api # \"",
                        "B=1 A=\"x y z w v\" docker restart api # '"):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual(result.flags, ["docker_lifecycle"])
                self.assertEqual(result.uncertainty, [])
                res = call_main(payload("PreToolUse", "Bash", actor="backend-python", cwd=self.repo,
                                        tool_input={"command": command}))
                self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], "deny")
                self.assertEqual(res.records[0]["decision_category"], "docker_lifecycle")

    def test_a_window_that_reaches_the_end_is_level_b(self):
        """audit-shell-lexer S3: a text that does not close is `lex_error`, level B, whatever the assignment."""
        for command in ('A="x y docker restart api', "A='x git push", 'A="x y'):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual((result.categories, result.flags), (["unclassified"], ["unclassified_command"]))
                self.assertEqual(result.uncertainty, ["lex_error"])
        self.assertEqual(readings('FOO="a b" echo hi').texts, ["echo hi"])

    def test_normal_assignments_are_unchanged(self):
        self.assertEqual(classifier.classify_command('FOO="a b" pytest'), (["test-full"], []))
        self.assertEqual(classifier.classify_command('FOO="a b" echo hi'), (["other"], []))
        self.assertEqual(readings('FOO="a b" echo hi').texts, ["echo hi"])
        self.assertEqual(analyze('FOO="a b" pytest').uncertainty, [])

    def test_an_unclosed_quote_in_an_assignment_is_level_b(self):
        for command in ('A="x y docker restart api', "A='x docker restart api", 'A="x git push'):
            with self.subTest(command=command):
                got = readings(command)
                self.assertEqual((got.texts, got.complete, got.reasons), ([], False, frozenset({"lex_error"})))
                result = analyze(command)
                self.assertIn("unclassified_command", result.flags)
                self.assertEqual(result.uncertainty, ["lex_error"])


class HeredocUncleanPrefixReason(unittest.TestCase):
    """HS8: a body kept for an unclean prefix with a sink head is recorded (level A); real code heredocs are not."""

    def test_hs8_kept_bodies_carry_the_reason(self):
        for prefix in ("x=$(true) cat <<EOF", 'timeout -s KILL "$T" cat <<EOF', "A=$B cat <<EOF"):
            with self.subTest(prefix=prefix):
                result = analyze(prefix + "\ndocker compose up\nEOF")
                self.assertIn("docker_lifecycle", result.flags)
                self.assertIn("heredoc_unclean_prefix", result.uncertainty)

    def test_hs8_code_heredocs_and_clean_sinks_have_no_reason(self):
        for command in ("python3 - <<EOF\nx\nEOF", "bash <<EOF\nx\nEOF", "cat > $SP/x.sh <<EOF\nx\nEOF",
                        "timeout 5 cat <<EOF\nx\nEOF"):
            with self.subTest(command=command):
                self.assertNotIn("heredoc_unclean_prefix", analyze(command).uncertainty)


class DenyTokenCanary(unittest.TestCase):
    """UN9: a blocked program outside the command head, unmatched, is recorded (never decided)."""

    def test_un9_forms_the_parser_does_not_model_are_recorded(self):
        """audit-shell-lexer, tests that change: `true & docker restart x`, `x=$(docker restart x)` and `true &
        git commit -m x` are modeled now (they are in `test_command_positions.py`); `sudo -u` and `bash -c` are
        modeled by the next tasks. The canary is checked with forms that stay outside the head of a command:
        arguments of other programs, and (Task 5, N6) a program name of no known value, which is also
        `dynamic_command`."""
        for command, reasons in (("ssh h docker restart x", ["deny_token_unmatched"]),
                                 ("echo docker restart x", ["deny_token_unmatched"]),
                                 ("$X docker restart x", ["deny_token_unmatched", "dynamic_command"])):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual(result.uncertainty, reasons)
                self.assertEqual(result.flags, [])

    def test_un9_commands_without_the_pattern_have_no_reason(self):
        for command in ("docker ps", "git log --grep commit", "docker restart x", "git push", "echo hi",
                        "rtk docker compose up -d", "sudo git push", "timeout 5 docker restart x"):
            with self.subTest(command=command):
                self.assertNotIn("deny_token_unmatched", analyze(command).uncertainty)

    def test_the_flag_of_another_piece_counts(self):
        result = analyze("docker restart x; sudo -u x docker restart y")
        self.assertEqual(result.flags, ["docker_lifecycle"])
        self.assertNotIn("deny_token_unmatched", result.uncertainty)

    def test_a_path_prefixed_program_is_recognized(self):
        """Changed by audit-shell-lexer Task 3 (N2): the head `/usr/bin/docker` is the program `docker`, so the
        command is classified by its own rule and the canary has nothing left to report."""
        result = analyze("true & /usr/bin/docker restart x")
        self.assertEqual(result.flags, ["docker_lifecycle"])
        self.assertNotIn("deny_token_unmatched", result.uncertainty)

    def test_the_canary_never_decides(self):
        config = TEST_CONFIG["categories"]
        self.assertEqual(config["parse_uncertain"], "audit")
        record = {"actor": "main", "flags": ["parse_uncertain"]}
        self.assertIsNone(audit.decide(record, TEST_CONFIG))


class WrapperEquivalence(unittest.TestCase):
    """UN10: `classify_command` is `analyze_command` without the uncertainty."""

    def test_un10_every_table_row_matches(self):
        """Both entry points are compared with the expectations of the `test_classify` tables, not with each other."""
        rows = [(command, categories, flags) for table in (COMMAND_TABLE, TIMEOUT_CROSS_STACK, TIMEOUT_ROUND2,
                                                           TIMEOUT_VALUE_OPTIONS)
                for _case, command, categories, flags in table]
        for _case, commands, categories, flags in PREFIX_TABLE:  # PREFIX_TABLE rows hold a list of commands
            rows += [(command, categories, flags) for command in commands]
        self.assertGreater(len(rows) + len(LUA_TABLE), 150)
        for command, categories, flags in rows:
            with self.subTest(command=str(command)[:60]):
                analysis = analyze(command)
                self.assertEqual((analysis.categories, analysis.flags), (categories, flags))
                self.assertEqual(classifier.classify_command(command), (categories, flags))
                self.assertNotIn("parse_uncertain", analysis.flags)
        for _case, command, categories in LUA_TABLE:  # these rows state categories only
            with self.subTest(command=str(command)[:60]):
                self.assertEqual(analyze(command).categories, categories)


class UncertaintyInTheRecord(TempRepoCase):
    """UN11: level A reasons are recorded and flagged, and decide as before."""

    def call(self, event, command, actor="backend-python"):
        return call_main(payload(event, "Bash", actor=actor, cwd=self.repo, tool_input={"command": command}))

    def test_un11_an_ambiguous_prefix_is_flagged_and_recorded(self):
        res = self.call("PostToolUse", 'timeout "$T" pytest tests/a_test.py')
        self.assertIsNone(res.output)
        [record] = res.records
        self.assertIn("parse_uncertain", record["flags"])
        self.assertEqual(record["uncertainty"], ["prefix_readings"])

    def test_un11_a_certain_command_has_no_uncertainty_field(self):
        [record] = self.call("PostToolUse", "pytest").records
        self.assertNotIn("uncertainty", record)
        self.assertNotIn("parse_uncertain", record["flags"])

    def test_un11_the_strictest_reading_decides(self):
        res = self.call("PreToolUse", 'timeout "$T" docker restart x')
        self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], "deny")
        [record] = res.records
        self.assertEqual(record["decision_category"], "docker_lifecycle")
        self.assertIn("parse_uncertain", record["flags"])
        self.assertEqual(record["uncertainty"], ["prefix_readings"])

    def test_the_readings_cap_is_denied_for_every_actor(self):
        for actor in ("backend-python", "main", "subagent"):
            with self.subTest(actor=actor):
                res = self.call("PreToolUse", "timeout a " * 9 + "docker restart x", actor=actor)
                self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], "deny")
                [record] = res.records
                self.assertEqual(record["decision_category"], "unclassified_command")
                self.assertEqual(record["uncertainty"], ["readings_cap"])
                self.assertEqual(sorted(record["flags"]), ["parse_uncertain", "unclassified_command"])


class DecideUnclassified(unittest.TestCase):
    """UN12: the deny text of unclassified_command is the same for every actor."""

    def test_un12_deny_with_why_and_what_to_do(self):
        for actor in ("main", "subagent"):
            with self.subTest(actor=actor):
                record = {"actor": actor, "flags": ["unclassified_command", "parse_uncertain"]}
                spec = audit.decide(record, TEST_CONFIG)["hookSpecificOutput"]
                self.assertEqual(spec["permissionDecision"], "deny")
                self.assertEqual(
                    spec["permissionDecisionReason"],
                    f"Agent workflow (unclassified_command): {audit.WHY['unclassified_command']}. "
                    "Run each program as its own plain command: no stacked wrappers, no shell code built from variables "
                    "or substitutions (bash -c \"$X\", eval), no nested shells, and only common POSIX/bash syntax; "
                    "write scripts and large content to a file with the Write tool and run the file.",
                )
                for word in ("syntax", "run time", "POSIX"):
                    self.assertIn(word, audit.what_to_do(actor, "unclassified_command") + audit.WHY["unclassified_command"])
                self.assertEqual(record["decision_category"], "unclassified_command")


class LevelBByTheParser(TempRepoCase):
    """UN14 (spec audit-shell-lexer, Testing): each level B reason of the parser, through the hook, is a denial
    with the reason in the record, for the main session and for an agent."""

    def deny(self, command, actor, categories=("unclassified",)):
        res = call_main(payload("PreToolUse", "Bash", actor=actor, cwd=self.repo, tool_input={"command": command}))
        self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], "deny")
        [record] = res.records
        self.assertEqual(record["decision_category"], "unclassified_command")
        self.assertEqual(record["categories"], list(categories))
        self.assertEqual(sorted(record["flags"]), ["parse_uncertain", "unclassified_command"])
        return record

    def test_un14_lex_error(self):
        for actor in ("main", "backend-python"):
            with self.subTest(actor=actor):
                for command in ('echo "a', "if true; then docker ps", "(sh -s) cat", "ls *(.)"):
                    self.assertEqual(self.deny(command, actor)["uncertainty"], ["lex_error"])

    def test_un14_nesting_depth(self):
        command = "( " * 33 + "true" + " )" * 33  # spaced: `((` would be read as arithmetic first
        for actor in ("main", "backend-python"):
            with self.subTest(actor=actor):
                self.assertEqual(self.deny(command, actor)["uncertainty"], ["nesting_depth"])
        self.assertEqual(analyze("( " * 32 + "true" + " )" * 32).uncertainty, [])

    def test_un14_analysis_budget(self):
        """The budget of one analysis is MAX_LEX_CHARS characters over every text read; lowered here to reach it
        (a command is at most 16 KiB and the budget 128 KiB, and the recursion reads each part about 4 times)."""
        with mock.patch.object(classifier, "MAX_LEX_CHARS", 20):
            for actor in ("main", "backend-python"):
                with self.subTest(actor=actor):
                    self.assertEqual(self.deny("echo " + "a" * 30, actor)["uncertainty"], ["analysis_budget"])
        self.assertEqual(analyze("echo " + "a" * 30).uncertainty, [])

    def test_un14_the_reasons_of_the_code_arguments(self):
        """Task 4: `dynamic_code` (X3, X5), `piped_shell` (X4) and `nvim_shell_exec` (X6)."""
        for command, reason in (('bash -c "$X"', "dynamic_code"), ("source <(x)", "dynamic_code"),
                                ("echo x | bash", "piped_shell"), ("nvim -c 'lua vim.fn.system(cmd)'", "nvim_shell_exec")):
            for actor in ("main", "backend-python"):
                with self.subTest(command=command, actor=actor):
                    record = self.deny(command, actor, categories=("other", "unclassified"))
                    self.assertEqual(record["uncertainty"], [reason])

    def test_un14_the_code_evaluation_contexts_are_denials_for_every_actor(self):
        """Review fix B1: the contexts where the shell evaluates text as code (`dynamic_code`)."""
        for command in ('echo "${(e)X}"', "PS4='$(date)' bash -x s.sh", "x='a[$(date)]'; (( x ))"):
            for actor in ("main", "backend-python"):
                with self.subTest(command=command, actor=actor):
                    record = self.deny(command, actor, categories=("other", "unclassified") if "(( x ))" not in command
                                       else ("unclassified",))
                    self.assertEqual(record["uncertainty"], ["dynamic_code"])

    def test_un14_the_budget_is_shared_by_the_nested_texts(self):
        """A heredoc body is parsed again as its own script, and that read is charged to the same budget."""
        command = "bash <<EOF\n" + "echo hi\n" * 5 + "EOF"
        with mock.patch.object(classifier, "MAX_LEX_CHARS", len(command) + 10):
            result = analyze(command)
        self.assertEqual(result.uncertainty, ["analysis_budget"])
        self.assertIn("unclassified_command", result.flags)
        self.assertEqual(analyze(command).uncertainty, [])


class CodeEvaluationContexts(unittest.TestCase):
    """Review fix B1, item 4: a `PS4` that tracing expands, and a single-quoted `$(` or backquote in a text that also
    evaluates arithmetic (bash evaluates the subscript of `a[$(cmd)]` and runs the command)."""

    def blocked(self, command):
        result = analyze(command)
        self.assertIn("unclassified_command", result.flags, command)
        self.assertIn("dynamic_code", result.uncertainty, command)

    def allowed(self, command):
        result = analyze(command)
        self.assertNotIn("unclassified_command", result.flags, command)
        self.assertNotIn("dynamic_code", result.uncertainty, command)

    def test_ps4_in_a_text_that_turns_tracing_on_is_dynamic_code(self):
        for command in ("PS4='$(date)' bash -x s.sh", "PS4='$(x)'; set -x; ls", "export PS4='+ $(id) '; bash -ex s.sh",
                        "PS4='$(x)' sh -c 'set -x; ls'", "PS4='$(x)'; set -o xtrace; ls", "PS4='$(x)'; setopt xtrace",
                        "declare -x PS4='$(x)'; zsh -x s.sh", "PS4=$'$(x)' bash -xe s", "PS4='`x`'; sh -ux s",
                        "bash -c \"PS4='\\$(x)'; set -x; ls\""):
            with self.subTest(command=command):
                self.blocked(command)

    def test_ps4_without_tracing_and_tracing_without_ps4_are_not(self):
        for command in ("PS4=x; ls", "bash -x s.sh", "set -x; ls", "echo PS4", "PS4='$(x)'; ls", "tar -xzf a.tgz"):
            with self.subTest(command=command):
                self.allowed(command)
        # an over-approximation, on purpose: any short option cluster with `x` counts as tracing
        self.blocked("PS4='$(x)' tar -xzf a.tgz")

    def test_a_single_quoted_substitution_with_arithmetic_is_dynamic_code(self):
        """B1b: only when the quoted text reaches arithmetic: a subscript, `(( ))`, `$(( ))`, `let`, `declare -i` or a
        numeric test whose operand is the quoted text or a variable that holds it."""
        for command in ("x='a[$(date)]'; (( x ))", "x='a[$(date)]'; echo $((x+1))", "x='$(date)'; [[ $x -eq 1 ]]",
                        "x='$(date)'; [[ x -gt 1 ]]", "x='$(date)'; let y=x", "let 'a[$(date)]'",
                        "x='`date`'; declare -i n=$x", "declare -i n='$(x)'", "typeset -i n='$(x)'",
                        "x='$(d)'; y=$x; (( y ))", "x='$(d)'; echo ${a[$x]}", "x='$(d)'; A[$x]=1", "unset 'a[$(x)]'",
                        "x='$(d)'; [ \"$x\" -eq 1 ]", "x='$(d)'; echo ${s:$x}", "A['$(x)']=1", "x=\\$\\(date\\); (( x ))",
                        "x=\"\\$(date)\"; (( x ))", "x='a[$(d)]' bash -c '(( x ))'", "x='$(d)'; bash -c 'echo $((x))'",
                        "x='$(d)'; $[x+1]", "x='$(d)'; for ((i=x;i<3;i++)); do :; done", "read 'a[$(x)]'",
                        "printf -v 'a[$(x)]' %s 1", "[[ 'a[$(x)]' -eq 1 ]]"):
            with self.subTest(command=command):
                self.blocked(command)

    def test_a_substitution_that_does_not_reach_arithmetic_is_not_denied(self):
        """Arithmetic somewhere else in the same text no longer counts (B1b); sed, awk and grep patterns, `adb
        shell '...'` and `sh -c 'echo $(date)'` arguments are not denied by this rule."""
        for command in ("echo '$(date)' ls", "echo $((1+1))", "awk '{print $(NF)}' f", 'echo "$(date)" $((1))',
                        "echo $(date) $((1))", "echo '`x`'; ls ${a:-b}", "echo '$(x)' ${a:-1} ${b:=2}", "echo '$x' $((1))",
                        "echo '$(date)' $((1+1))", "echo '`date`' $((1+1))", "[[ 1 -eq 1 ]]; echo '$(x)'",
                        "echo '$(x)' ${a[1]}", "echo '$(x)' ${s:1}", "for ((i=0;i<3;i++)); do echo '$(x)'; done",
                        "let x=1; echo '$(x)'", "echo \\$\\(x\\) $((1))", "echo \"\\$(x)\" $((1))",
                        "bash -c 'echo $((1))'; echo '$(x)'", "echo $'$(x)' $[1+1]", "[ 1 -eq 1 ]; echo '$(x)'",
                        "declare -i n; echo '$(x)'", "echo '$(x)' ${a[@]:1:2}", "if [[ $a -lt 3 ]]; then echo '$(x)'; fi",
                        "echo '$(x)'; ((i++))", "x='$(d)'; echo $x; (( i ))", "x='$(d)'; (( i )); echo $x",
                        "adb shell 'for p in $(pm list); do [ \"$d\" -gt 0 ]; done'",
                        "docker run x sh -c 'echo $(date)'; echo $((1))", "grep '^```sql' f; sed -n \"$((s+1)),$((e-1))p\" f",
                        "sed -n 's/`a`/b/p' f; echo $((s+1))", "awk '{a[$(NF)]}' f; echo $((n+1))",
                        "x='$(d)'; y=1; [ \"$y\" -eq 1 ]", "x='$(d)'; echo ${a[$y]}", "x='$(d)'; A[$y]=1",
                        "unset a; read b", "x='$(d)'; (( y )); [[ $x == a ]]"):
            with self.subTest(command=command):
                if "docker run" in command:
                    self.assertNotIn("dynamic_code", analyze(command).uncertainty)
                else:
                    self.allowed(command)


class LevelBReasonsD1(unittest.TestCase):
    """Review fix D1: the forms that became level B (`unclassified_command`) and the reason each one records."""

    CASES = (
        ("docker " + " ".join(f"-x a{i}" for i in range(10)) + " re" + "start x", "readings_cap"),
        ("${X%.sh} y", "dynamic_code"), ("${X:-$Y} y", "dynamic_code"), ("{1..3} x", "dynamic_code"),
        ("x{a..c} y", "dynamic_code"), ("git -c \"alias.p='push\" p", "dynamic_code"),
        ("GIT_CONFIG_PARAMETERS=\"'alias.p'=x\" git p", "dynamic_code"),
        ("x='a[$(c)]'; echo ${!x}", "dynamic_code"), ("read x <<< 'a[$(c)]'; (( x ))", "dynamic_code"),
        ("sqlite3 db <<'EOF'\nselect edit('a', 'b');\nEOF", "dynamic_code"),
        ("psql <<'EOF'\n\\e\nEOF", "dynamic_code"), ("psql <<'EOF'\n\\set x `c`\nEOF", "dynamic_code"),
        ("psql <<'EOF'\nselect 1 \\g (format=csv) |c\nEOF", "dynamic_code"),
        ("sqlite3 db <<'EOF'\n.syste c\nEOF", "dynamic_code"), ("psql <<'EOF'\nCOPY t TO PROGRAM 'c';\nEOF", "dynamic_code"),
        ("f() { \"$@\"; }; f $X", "dynamic_code"), ("f() { \"$@\"; }; echo x | xargs f", None),
        ("f() { \"$@\"; }; g() { f \"$@\"; }; g ls", "dynamic_code"),
        ("PS4='$(x)' bash -xc :", "dynamic_code"),
    )

    def test_each_form_is_level_b_with_its_reason(self):
        for command, reason in self.CASES:
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual(result.categories.count("unclassified"), 1, command)
                self.assertIn("unclassified_command", result.flags, command)
                if reason:
                    self.assertIn(reason, result.uncertainty, command)

    def test_the_forms_that_stay_below_level_b(self):
        for command in ("f() { \"$@\"; }", "f() { \"$@\"; }; f ls -la", "${X:-/usr/bin}/ls -la", "{'git',x} y",
                        "python3 -c 'PS4=1; -xc'", "psql <<'EOF'\nselect 1;\nEOF", "docker -Dl info ps",
                        "x=$(foo); read y <<< \"$x\"; echo $y"):
            with self.subTest(command=command):
                self.assertNotIn("unclassified_command", analyze(command).flags, command)


class OldReadersAreGone(unittest.TestCase):
    """UN15: the hook has one reader of command text, the parser (S1)."""

    def test_un15_the_old_readers_and_reasons_do_not_appear_in_the_source(self):
        source = "".join((HOOKS_DIR / name).read_text(encoding="utf-8")
                          for name in ("agent-audit.py", "agent_audit_classify.py"))
        for name in ("shlex", "SEGMENT_SPLIT", "LOOSE_VALUE_TOKENS", "shlex_fallback", "loose_assignment_truncated",
                     "_scan_heredocs", "NVIM_MAX_DEPTH"):
            with self.subTest(name=name):
                self.assertNotIn(name, source)


class ShellModuleLoad(TempRepoCase):
    """UN16 (and P-SL4 in test_hook_process): the parser and the classifier are parts of the hook, loaded by path. A
    module that is missing or does not load never lets a Bash command through; the rest of the hook does not depend
    on them (a file write is still judged by its own rules)."""

    def hook(self):
        return HookProcess(self.make_dir(prefix="agent-audit-tests-shell-"), config())

    def bash(self, hp, command="echo hi"):
        proc = hp.run(payload("PreToolUse", "Bash", actor="backend-python", cwd=self.repo,
                              tool_input={"command": command}), self.repo)
        self.assertEqual((proc.returncode, proc.stderr), (0, ""))
        return json.loads(proc.stdout)["hookSpecificOutput"]

    def assert_denied_as_unclassified(self, hp):
        for command in ("echo hi", "pytest tests/test_a.py", "docker ps"):
            with self.subTest(command=command):
                spec = self.bash(hp, command)
                self.assertEqual(spec["permissionDecision"], "deny")
                self.assertIn("Agent workflow (unclassified_command)", spec["permissionDecisionReason"])
        [first, *_] = hp.records()
        self.assertEqual(first["uncertainty"], ["classifier_error"])
        self.assertEqual(first["error"], "RuntimeError")  # the name only, never the message
        # a file write does not use the parser: the normal rules apply
        write = payload("PreToolUse", "Write", actor="main", cwd=self.repo,
                        tool_input={"file_path": str(self.repo / "a.txt")})
        proc = hp.run(write, self.repo)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))

    def test_un16_a_missing_module_denies_bash(self):
        hp = self.hook()
        (hp.dir / "agent_audit_shell.py").unlink()
        self.assert_denied_as_unclassified(hp)

    def test_un16_a_module_with_a_syntax_error_denies_bash(self):
        hp = self.hook()
        (hp.dir / "agent_audit_shell.py").write_text("def broken(:\n", encoding="utf-8")
        self.assert_denied_as_unclassified(hp)

    def test_un16_a_module_that_fails_while_loading_denies_bash(self):
        hp = self.hook()
        hp.patch_source("MAX_NESTING = 32\n", "MAX_NESTING = 32\nraise ImportError('probe')\n", file="agent_audit_shell.py")
        self.assert_denied_as_unclassified(hp)

    def test_un16_a_missing_classifier_denies_bash(self):
        hp = self.hook()
        (hp.dir / "agent_audit_classify.py").unlink()
        self.assert_denied_as_unclassified(hp)

    def test_un16_a_classifier_with_a_syntax_error_denies_bash(self):
        hp = self.hook()
        (hp.dir / "agent_audit_classify.py").write_text("def broken(:\n", encoding="utf-8")
        self.assert_denied_as_unclassified(hp)

    def test_un16_a_classifier_that_fails_while_loading_denies_bash(self):
        hp = self.hook()
        hp.patch_source("MAX_CODE_DEPTH = 3\n", "MAX_CODE_DEPTH = 3\nraise ImportError('probe')\n",
                        file="agent_audit_classify.py")
        self.assert_denied_as_unclassified(hp)

    def test_un16_a_classifier_that_raises_when_called_denies_bash(self):
        hp = self.hook()
        hp.patch_source('    command = command or ""\n', '    raise ValueError("probe")\n    command = command or ""\n',
                        file="agent_audit_classify.py")
        for command in ("echo hi", "docker ps"):
            with self.subTest(command=command):
                spec = self.bash(hp, command)
                self.assertEqual(spec["permissionDecision"], "deny")
                self.assertIn("Agent workflow (unclassified_command)", spec["permissionDecisionReason"])
        [first, *_] = hp.records()
        self.assertEqual((first["uncertainty"], first["error"]), (["classifier_error"], "ValueError"))

    def test_un16_a_classifier_without_its_parser_does_not_load(self):
        """The classifier imports the parser by name: with the parser gone the classifier is gone too."""
        hp = self.hook()
        (hp.dir / "agent_audit_shell.py").unlink()
        self.assertEqual(hp.run(payload("PreToolUse", "Bash", actor="main", cwd=self.repo,
                                        tool_input={"command": "echo hi"}), self.repo).returncode, 0)
        [first, *_] = hp.records()
        self.assertEqual((first["uncertainty"], first["error"]), (["classifier_error"], "RuntimeError"))

    def test_un16_the_intact_copy_works(self):
        spec = self.bash(self.hook(), "docker restart x")
        self.assertEqual(spec["permissionDecision"], "deny")
        self.assertIn("Agent workflow (docker_lifecycle)", spec["permissionDecisionReason"])


def load_tests(loader, tests, pattern):
    """Independent cases: run them in forked workers (see `ForkedSuite`)."""
    return ForkedSuite(tests)


if __name__ == "__main__":
    unittest.main()
