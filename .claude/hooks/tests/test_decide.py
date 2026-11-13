"""Tests for decide(), what_to_do(), SEVERITY and WHY of the agent-audit hook.

Source: spec audit-hook-test-suite, section Testing, `test_decide.py` (K1-K12). Only TEST_CONFIG
and config() are used; the live agent-audit.json is never read.
"""
import unittest

from ._support import TEST_CONFIG, audit, config


def cfg(**categories):
    """TEST_CONFIG with the given category actions replacing the whole `categories` map."""
    return config(categories=dict(categories))


def record(*flags, actor="main"):
    return {"actor": actor, "flags": list(flags)}


class Decide(unittest.TestCase):
    """K1-K12: the PreToolUse decision for the strictest flagged category."""

    def test_k1_no_flags_allows_silently_and_leaves_no_decision(self):
        for flags in ([], None):
            with self.subTest(case="K1", flags=flags):
                rec = {"actor": "main", "flags": flags}
                self.assertIsNone(audit.decide(rec, TEST_CONFIG))
                self.assertNotIn("decision", rec)
                self.assertNotIn("decision_category", rec)

    def test_k2_audit_action_allows_silently(self):
        rec = record("docker_build")
        self.assertIsNone(audit.decide(rec, TEST_CONFIG))
        self.assertNotIn("decision", rec)

    def test_k3_flag_missing_from_config_fails_open(self):
        rec = record("not_in_config")
        self.assertIsNone(audit.decide(rec, TEST_CONFIG))
        self.assertNotIn("decision", rec)

    def test_k4_unknown_action_in_config_is_allowed(self):
        rec = record("git_commit")
        self.assertIsNone(audit.decide(rec, cfg(git_commit="bogus")))
        self.assertNotIn("decision", rec)

    def test_k5_block_denies_with_reason_and_what_to_do(self):
        for actor in ("main", "backend-node"):
            with self.subTest(case="K5", actor=actor):
                rec = record("docker_lifecycle", actor=actor)
                out = audit.decide(rec, TEST_CONFIG)
                spec = out["hookSpecificOutput"]
                self.assertEqual(spec["hookEventName"], "PreToolUse")
                self.assertEqual(spec["permissionDecision"], "deny")
                self.assertEqual(
                    spec["permissionDecisionReason"],
                    f"Agent workflow (docker_lifecycle): {audit.WHY['docker_lifecycle']}. "
                    f"{audit.what_to_do(actor, 'docker_lifecycle')}",
                )
                self.assertEqual(rec["decision"], "block")
                self.assertEqual(rec["decision_category"], "docker_lifecycle")
                self.assertNotIn("additionalContext", spec)

    def test_k6_ask_has_reason_without_what_to_do(self):
        rec = record("git_commit")
        spec = audit.decide(rec, TEST_CONFIG)["hookSpecificOutput"]
        self.assertEqual(spec["permissionDecision"], "ask")
        self.assertEqual(
            spec["permissionDecisionReason"],
            f"Agent workflow (git_commit): {audit.WHY['git_commit']}.",
        )
        self.assertNotIn(audit.what_to_do("main", "git_commit"), spec["permissionDecisionReason"])
        self.assertEqual(rec["decision"], "ask")
        self.assertEqual(rec["decision_category"], "git_commit")

    def test_k7_warn_only_adds_context(self):
        rec = record("external_request")
        spec = audit.decide(rec, TEST_CONFIG)["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", spec)
        self.assertNotIn("permissionDecisionReason", spec)
        self.assertIn("Reminder from the agent workflow (external_request)", spec["additionalContext"])
        self.assertEqual(rec["decision"], "warn")
        self.assertEqual(rec["decision_category"], "external_request")

    def test_k8_block_beats_warn_in_any_order(self):
        for flags in (("external_request", "docker_lifecycle"), ("docker_lifecycle", "external_request")):
            with self.subTest(case="K8", flags=flags):
                rec = record(*flags)
                spec = audit.decide(rec, TEST_CONFIG)["hookSpecificOutput"]
                self.assertEqual(spec["permissionDecision"], "deny")
                self.assertEqual(rec["decision_category"], "docker_lifecycle")

    def test_k9_equal_severity_first_in_the_list_wins(self):
        # main() sorts the flags, so the winner there is the alphabetical first (see H5)
        for flags in (("out_of_scope_write", "md_outside_docs"), ("md_outside_docs", "out_of_scope_write")):
            with self.subTest(case="K9", flags=flags):
                rec = record(*flags)
                audit.decide(rec, TEST_CONFIG)
                self.assertEqual(rec["decision"], "warn")
                self.assertEqual(rec["decision_category"], flags[0])

    def test_k10_what_to_do_by_category_and_actor(self):
        for actor in ("main", "backend-node"):
            with self.subTest(case="K10", category="docker_lifecycle", actor=actor):
                self.assertEqual(
                    audit.what_to_do(actor, "docker_lifecycle"),
                    "Put the command in manual_checks for the user instead.",
                )
            with self.subTest(case="K10", category="visual_tool", actor=actor):
                text = audit.what_to_do(actor, "visual_tool")
                self.assertIn("manual_checks", text)
                self.assertIn("ui-verifier", text)
        with self.subTest(case="K10", actor="main"):
            self.assertTrue(audit.what_to_do("main", "git_push").startswith("Explain to the user"))
        with self.subTest(case="K10", actor="subagent"):
            for actor in ("backend-node", "subagent"):
                text = audit.what_to_do(actor, "git_push")
                self.assertTrue(text.startswith("Do not retry"))
                self.assertIn("scope_requests", text)

    def test_k11_config_without_categories_allows(self):
        for cfg_ in ({"mode": "enforce"}, {"mode": "enforce", "categories": None}):
            with self.subTest(case="K11", config=cfg_):
                rec = record("docker_lifecycle")
                self.assertIsNone(audit.decide(rec, cfg_))
                self.assertNotIn("decision", rec)

    def test_k12_every_why_text_reaches_the_reason(self):
        self.assertTrue(audit.WHY)
        for category, why in audit.WHY.items():
            with self.subTest(case="K12", category=category):
                rec = record(category)
                spec = audit.decide(rec, cfg(**{category: "block"}))["hookSpecificOutput"]
                self.assertIn(why, spec["permissionDecisionReason"])
                self.assertIn(f"Agent workflow ({category})", spec["permissionDecisionReason"])

    def test_severity_order(self):
        self.assertLess(audit.SEVERITY["audit"], audit.SEVERITY["warn"])
        self.assertLess(audit.SEVERITY["warn"], audit.SEVERITY["ask"])
        self.assertLess(audit.SEVERITY["ask"], audit.SEVERITY["block"])


if __name__ == "__main__":
    unittest.main()
