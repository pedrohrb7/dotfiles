"""Coherence of the live policy files with the hook code. Read only.

Source: audit-hook-test-suite spec, section Testing, `test_config_contract.py` (F1-F6), rule R16.
This is the only module that reads the live `agent-audit.json` and `settings.json`. It checks
floors (the explicit rules of the global CLAUDE.md), not exact values, so promoting a category from
warn to block does not break the suite. It also reads the root `CLAUDE.md` of the repo (F4a).
"""
import json
import re
import unittest

from ._support import CLAUDE_DIR, HOOKS_DIR, TEST_CONFIG, audit, metrics

HOOK_COMMAND = 'python3 "$HOME/.claude/hooks/agent-audit.py"'
REPO_ROOT = audit.git_root(CLAUDE_DIR)
EVENTS = ("PreToolUse", "PostToolUse", "PostToolUseFailure", "SubagentStart", "SubagentStop")


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ConfigContract(unittest.TestCase):
    """F1-F6: agent-audit.json, WHY, FLAG_LABELS, settings.json and TEST_CONFIG stay coherent."""

    @classmethod
    def setUpClass(cls):
        cls.live = _read_json(HOOKS_DIR / "agent-audit.json")
        cls.settings = _read_json(CLAUDE_DIR / "settings.json")

    def audit_hooks(self, event):
        """(matcher, hook) for every agent-audit hook registered on the event."""
        found = []
        for group in self.settings["hooks"].get(event, []):
            for hook in group.get("hooks", []):
                if "agent-audit.py" in hook.get("command", ""):
                    found.append((group.get("matcher"), hook))
        return found

    def test_f1_config_is_valid(self):
        self.assertIn(self.live["mode"], {"off", "audit", "enforce"})
        for category, action in self.live["categories"].items():
            with self.subTest(category=category):
                self.assertIn(action, audit.SEVERITY)

    def test_f2_floors_of_the_claude_md_rules(self):
        self.assertEqual(self.live["mode"], "enforce")
        categories = self.live["categories"]
        for category in ("docker_lifecycle", "write_by_readonly_agent", "visual_tool", "design_director_write_outside"):
            with self.subTest(category=category):
                self.assertEqual(categories[category], "block")
        for category in ("git_commit", "git_push"):
            with self.subTest(category=category):
                self.assertGreaterEqual(audit.SEVERITY[categories[category]], audit.SEVERITY["ask"])

    def test_f3_categories_why_and_labels_have_the_same_keys(self):
        categories = set(self.live["categories"])
        self.assertEqual(categories, set(audit.WHY), "categories vs WHY")
        self.assertEqual(categories, set(metrics.FLAG_LABELS), "categories vs FLAG_LABELS")

    def test_f4a_repo_declares_its_docs_root_and_the_tree_exists(self):
        """Skills-docs-root spec, F4a (R9): the root CLAUDE.md declares `.claude/docs/` and it exists."""
        self.assertEqual(audit.project_docs_root(REPO_ROOT), ".claude/docs/")
        self.assertTrue((REPO_ROOT / ".claude/docs/features/README.md").is_file())
        self.assertTrue((REPO_ROOT / ".claude/docs/backlog").is_dir())

    def test_f4b_live_config_has_no_docs_roots_key(self):
        """Skills-docs-root spec, F4b (R2): the docs root has a single source, the root CLAUDE.md."""
        self.assertNotIn("docs_roots", self.live)

    def test_f5_settings_register_the_hook(self):
        for event in EVENTS:
            with self.subTest(event=event):
                entries = self.audit_hooks(event)
                self.assertTrue(entries, f"{event} does not call the audit hook")
                for _, hook in entries:
                    self.assertEqual(hook["command"], HOOK_COMMAND)
                    self.assertIn("timeout", hook)
        for _, hook in self.audit_hooks("PreToolUse"):
            self.assertFalse(hook.get("async", False), "PreToolUse must decide before the action")

    def test_f5_pretooluse_matcher_covers_the_audited_tools(self):
        matchers = [m for m, _ in self.audit_hooks("PreToolUse")]
        self.assertTrue(matchers)
        for matcher in matchers:
            for tool in ("Bash", "Write", "Edit", "MultiEdit", "NotebookEdit", "mcp__playwright__browser_take_screenshot"):
                with self.subTest(tool=tool):
                    self.assertIsNotNone(re.fullmatch(matcher, tool))
            with self.subTest(tool="Read"):
                self.assertIsNone(re.fullmatch(matcher, "Read"))

    def test_f6_test_config_has_every_live_category(self):
        live, fixed = set(self.live["categories"]), set(TEST_CONFIG["categories"])
        self.assertEqual(
            live, fixed,
            f"add the new category to TEST_CONFIG in _support.py and cover it (only in live: {sorted(live - fixed)}, "
            f"only in TEST_CONFIG: {sorted(fixed - live)})",
        )


if __name__ == "__main__":
    unittest.main()
