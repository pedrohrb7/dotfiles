"""Readings by position, uncertainty reasons and `unclassified_command` of agent-audit.py.

Source: docs/features/audit-hook-hardening/spec.md (Testing, `test_uncertainty.py`, cases UN1-UN13; HS8 belongs
to the heredoc task). All commands below are string literals only; nothing is executed.
"""
import contextlib
import shlex
import time
import unittest
from unittest import mock

from ._support import ForkedSuite, TEST_CONFIG, TempRepoCase, audit, call_main, payload
from .test_classify import COMMAND_TABLE, LUA_TABLE, PREFIX_TABLE, TIMEOUT_CROSS_STACK, TIMEOUT_ROUND2, TIMEOUT_VALUE_OPTIONS

analyze = audit.analyze_command
readings = audit.command_readings

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
                    categories, flags = audit.classify_command("timeout a " * k + command)
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
            categories, flags = audit.classify_command("timeout 5 " * 1600 + "docker restart x")
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
        self.assertEqual(audit.classify_command("timeout x busted"), (["other", "test-full"], []))
        self.assertEqual(audit.classify_command('timeout -k 2 "$T" npm run lint'), (["lint", "other"], []))

    def test_un13_a_comma_decimal_duration_is_covered_by_the_union(self):
        self.assertEqual(audit.classify_command("timeout 0,5 docker restart x")[1], ["docker_lifecycle"])


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
        with mock.patch.object(audit, "_classify_segment", side_effect=RecursionError("deep")):
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
        with mock.patch.object(audit, "_classify_segment", side_effect=ValueError("secret text")):
            res = call_main(payload("PostToolUse", "Bash", cwd=self.repo, tool_input={"command": "echo hi"}))
        self.assertEqual(res.records[0]["error"], "ValueError")
        self.assertNotIn("secret", str(res.records[0]))

    def test_an_error_while_evaluating_a_write_is_also_blocked(self):
        with mock.patch.object(audit, "evaluate_write", side_effect=KeyError("x")):
            res = call_main(payload("PreToolUse", "Write", actor="backend-python", cwd=self.repo,
                                    tool_input={"file_path": str(self.repo / "a.py")}))
        self.assertEqual(res.output["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(res.records[0]["error"], "KeyError")


class ShlexFallback(unittest.TestCase):
    """UN8: a piece shlex cannot split is read twice, with and without quote characters."""

    def test_un8_an_unbalanced_quote_cannot_hide_the_command(self):
        result = analyze("\"docker\" restart x '")
        self.assertIn("docker_lifecycle", result.flags)
        self.assertEqual(result.uncertainty, ["shlex_fallback"])

    def test_un8_a_quoted_separator_is_not_a_false_positive(self):
        result = analyze('echo "a; b"')
        self.assertEqual((result.categories, result.flags), (["other"], []))
        self.assertNotIn("shlex_fallback", result.uncertainty)  # both token lists classify the same

    def test_un8_the_reason_needs_two_different_readings(self):
        """The fallback computes both readings always; the reason is kept only when they classify differently."""
        for command in ('grep -E "a|b" f', 'git commit -m "a|b"', 'echo "a; b"', 'echo "a && b" c', 'pytest -k "a or b"'):
            with self.subTest(command=command):
                self.assertNotIn("shlex_fallback", analyze(command).uncertainty)
        self.assertTrue(readings('echo "a').fallback)  # the fallback still ran

    def test_un8_the_reason_is_kept_when_the_readings_differ(self):
        result = analyze('A="x y docker restart api')
        self.assertIn("docker_lifecycle", result.flags)
        self.assertEqual(result.uncertainty, ["shlex_fallback"])  # the loose readings are not `prefix_readings`

    def test_un8_a_differing_unclosed_quote_keeps_the_reason(self):
        result = analyze("\"docker\" restart x '")
        self.assertEqual(result.uncertainty, ["shlex_fallback"])


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
        self.assertTrue(audit._opens_unclosed_quote('A+="x'))
        self.assertFalse(audit._opens_unclosed_quote("A[0]=x"))  # not an assignment name: bash rejects it too

    def test_a_window_that_ends_before_the_command_is_recorded(self):
        """The loose window covers LOOSE_VALUE_TOKENS tokens; a longer value may hide the command. Level A: the
        reason is recorded (a level B denial hit 91 real python heredoc bodies in the replay)."""
        for command in ('A="x y z w v" docker restart api # "', "A='x y z w v' docker restart api # \"",
                        "B=1 A=\"x y z w v\" docker restart api # '"):
            with self.subTest(command=command):
                got = readings(command)
                self.assertTrue(got.fallback)
                self.assertTrue(got.truncated)
                result = analyze(command)
                self.assertIn("loose_assignment_truncated", result.uncertainty)
                self.assertNotIn("unclassified_command", result.flags)

    def test_a_window_that_reaches_the_end_is_not_truncated(self):
        for command in ('A="x y docker restart api', "A='x git push", 'A="x y'):
            with self.subTest(command=command):
                self.assertFalse(readings(command).truncated)
                self.assertNotIn("loose_assignment_truncated", analyze(command).uncertainty)
        self.assertFalse(readings('FOO="a b" echo hi').truncated)

    def test_normal_assignments_are_unchanged(self):
        self.assertEqual(audit.classify_command('FOO="a b" pytest'), (["test-full"], []))
        self.assertEqual(audit.classify_command('FOO="a b" echo hi'), (["other"], []))
        self.assertEqual(readings('FOO="a b" echo hi').texts, ["echo hi"])
        self.assertEqual(analyze('FOO="a b" pytest').uncertainty, [])

    def test_an_unclosed_quote_in_an_assignment_gives_several_readings(self):
        for command, flag in (('A="x y docker restart api', "docker_lifecycle"), ("A='x docker restart api", "docker_lifecycle"),
                              ('A="x git push', "git_push")):
            with self.subTest(command=command):
                got = readings(command)
                self.assertTrue(got.fallback)
                self.assertGreater(len(got.texts), 1)
                self.assertIn(flag, analyze(command).flags)


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
        for command in ("sudo -u x docker restart x", "true & docker restart x", 'bash -c "git push"',
                        "x=$(docker restart x)", "true & git commit -m x"):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual(result.uncertainty, ["deny_token_unmatched"])
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
        self.assertIn("deny_token_unmatched", analyze("true & /usr/bin/docker restart x").uncertainty)

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
                self.assertEqual(audit.classify_command(command), (categories, flags))
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
                    "Run each program as its own short command, without stacked wrappers (timeout, sudo, mise exec) "
                    "or nested shells, and write large content to a file with the Write tool.",
                )
                self.assertEqual(record["decision_category"], "unclassified_command")


def load_tests(loader, tests, pattern):
    """Independent cases: run them in forked workers (see `ForkedSuite`)."""
    return ForkedSuite(tests)


if __name__ == "__main__":
    unittest.main()
