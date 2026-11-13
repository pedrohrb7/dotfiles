"""Tests of the area flags of agent-audit.py `evaluate_write` and of `docs_roots()`.

Source: docs/features/audit-hook-test-suite/spec.md, Testing (A1-A9, D1-D11).
"""
from ._support import TempRepoCase, audit, call_main, config, payload

ROOTS = ["docs/", ".claude/docs/"]


class AreaFlags(TempRepoCase):
    """Spec Testing A1-A9: `md_outside_docs`, `docs_write_by_implementer`, `backlog_write_by_other`,
    `area` and the record fields, in a temp repo without an active run."""

    def ev(self, rel, actor="main", tool="Write", response=None, roots=ROOTS):
        return audit.evaluate_write(str(self.repo / rel), str(self.repo), actor, tool, response, roots)

    def test_a1_main_write_of_md_at_root_is_md_outside_docs(self):
        """Refactor: docs/backlog/refactor/2026-11-11-audit-md-outside-docs-false-positive.md

        Pins the behavior accepted today: any new .md outside the docs roots is flagged, even a
        legitimate one. When that entry is resolved, this test changes with it.
        """
        out = self.ev("notes.md")
        self.assertIn("md_outside_docs", out["flags"])
        self.assertEqual(out["area"], "code")

    def test_a2_edit_of_existing_md_has_no_flag(self):
        out = self.ev("notes.md", tool="Edit")
        self.assertEqual(out["flags"], [])

    def test_a3_exempt_md_names_are_not_md_outside_docs(self):
        for rel in ("README.md", "services/api/README.md", "CLAUDE.md", "CHANGELOG.md"):
            with self.subTest(case="A3", rel=rel):
                self.assertNotIn("md_outside_docs", self.ev(rel)["flags"])

    def test_a4_docs_roots_are_area_docs_without_md_flag(self):
        for rel in ("docs/x.md", ".claude/docs/x.md"):
            with self.subTest(case="A4", rel=rel):
                out = self.ev(rel)
                self.assertEqual(out["area"], "docs")
                self.assertNotIn("md_outside_docs", out["flags"])

    def test_a5_code_file_has_no_md_flag(self):
        out = self.ev("services/api/x.py")
        self.assertNotIn("md_outside_docs", out["flags"])
        self.assertEqual(out["area"], "code")

    def test_a6_docs_write_by_implementer_only_for_implementers(self):
        rels = ("docs/x.md", "services/api/README.md", ".env.example", "DEPLOY.md", "CHANGELOG.md")
        for actor, expected in (("backend-node", True), ("docs-writer", False), ("main", False)):
            for rel in rels:
                with self.subTest(case="A6", actor=actor, rel=rel):
                    flags = self.ev(rel, actor=actor)["flags"]
                    self.assertEqual("docs_write_by_implementer" in flags, expected)

    def test_a7_backlog_write_by_other_except_keeper_and_unknown(self):
        for actor, expected in (
            ("backend-node", True), ("docs-writer", True), ("main", True),
            ("backlog-keeper", False), ("unknown", False),
        ):
            with self.subTest(case="A7", actor=actor):
                flags = self.ev("docs/backlog/bugs/x.md", actor=actor)["flags"]
                self.assertEqual("backlog_write_by_other" in flags, expected)

    def test_a8_run_state_area(self):
        out = self.ev(".claude/runs/x.json")
        self.assertEqual(out["area"], "run-state")

    def test_a9_record_without_run(self):
        out = self.ev("services/api/x.py")
        self.assertEqual(out["rel"], "services/api/x.py")
        self.assertIs(out["in_run"], False)
        self.assertNotIn("run", out)
        self.assertNotIn("task", out)


class DocsRoots(TempRepoCase):
    """Spec Testing D1-D11: `docs_roots()` normalization (D1-D7) and its effect on writes (D8-D11).
    Source of the rules: log of the design-director feature, "Added scope r3"."""

    def ev(self, rel, actor="main", roots=ROOTS):
        return audit.evaluate_write(str(self.repo / rel), str(self.repo), actor, "Write", None, roots)

    def test_d1_missing_key_defaults(self):
        self.assertEqual(audit.docs_roots({}), ["docs/"])

    def test_d2_non_list_defaults(self):
        self.assertEqual(audit.docs_roots({"docs_roots": "docs"}), ["docs/"])

    def test_d3_empty_list_defaults(self):
        self.assertEqual(audit.docs_roots({"docs_roots": []}), ["docs/"])

    def test_d4_only_invalid_entries_default(self):
        self.assertEqual(audit.docs_roots({"docs_roots": [3, "", ".", "..", "a/../b", None]}), ["docs/"])

    def test_d5_entries_are_normalized(self):
        self.assertEqual(
            audit.docs_roots({"docs_roots": [" ./x\\y/ ", "/z", "kb"]}), ["x/y/", "z/", "kb/"])

    def test_d6_duplicates_are_dropped(self):
        self.assertEqual(audit.docs_roots({"docs_roots": ["docs", "docs/", "./docs/"]}), ["docs/"])

    def test_d7_order_is_preserved(self):
        self.assertEqual(audit.docs_roots({"docs_roots": ["b/", "a/"]}), ["b/", "a/"])

    def test_d8_second_root_is_docs_area(self):
        out = self.ev(".claude/docs/features/x.md")
        self.assertEqual(out["area"], "docs")
        self.assertNotIn("md_outside_docs", out["flags"])

    def test_d9_backlog_under_second_root(self):
        for actor, expected in (("specker", True), ("backlog-keeper", False)):
            with self.subTest(case="D9", actor=actor):
                flags = self.ev(".claude/docs/backlog/refactor/x.md", actor=actor)["flags"]
                self.assertEqual("backlog_write_by_other" in flags, expected)

    def test_d10_nested_docs_and_default_roots_are_code(self):
        cases = (("services/x/docs/a.md", ROOTS), (".claude/docs/a.md", None))
        for rel, roots in cases:
            with self.subTest(case="D10", rel=rel):
                out = self.ev(rel, roots=roots)
                self.assertEqual(out["area"], "code")
                self.assertIn("md_outside_docs", out["flags"])

    def test_d11_main_uses_configured_docs_roots(self):
        def flags_for(cfg):
            pl = payload(
                "PostToolUse", "Write", cwd=self.repo,
                tool_input={"file_path": str(self.repo / "kb" / "a.md")},
            )
            result = call_main(pl, cfg)
            self.assertEqual(len(result.records), 1)
            return result.records[0]["flags"]

        with self.subTest(case="D11", docs_roots=["kb/"]):
            self.assertNotIn("md_outside_docs", flags_for(config(docs_roots=["kb/"])))
        with self.subTest(case="D11", docs_roots=7):
            self.assertIn("md_outside_docs", flags_for(config(docs_roots=7)))
