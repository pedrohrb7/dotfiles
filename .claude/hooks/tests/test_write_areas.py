"""Tests of the area flags of agent-audit.py `evaluate_write` and of the declared docs root.

Source: docs/features/audit-hook-test-suite/spec.md, Testing (A1-A9); skills-docs-root spec, Testing
(DR1-DR17: `project_docs_root()` / `normalize_docs_root()` and their effect on writes).
"""
import os
import subprocess
import threading
import unittest
from pathlib import Path

from ._support import TempRepoCase, audit, call_main, config, declare_docs_root, payload

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

    def test_a4_docs_root_paths_are_area_docs_without_md_flag(self):
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


class DocsRootDeclaration(TempRepoCase):
    """Spec skills-docs-root, Testing DR1-DR9 and DR17: `project_docs_root()` and `normalize_docs_root()`."""

    def write_md(self, text, rel="CLAUDE.md"):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
            path.write_text(text, encoding="utf-8")

    def root(self):
        return audit.project_docs_root(self.repo)

    def test_dr1_no_claude_md_defaults(self):
        self.assertEqual(self.root(), "docs/")

    def test_dr2_without_section_or_line_defaults(self):
        for text in ("# p\n\n## Test suites\n\nx\n", "# p\n\n## Workflow\n\n- docs layout: features\n"):
            with self.subTest(text=text):
                self.write_md(text)
                self.assertEqual(self.root(), "docs/")

    def test_dr3_valid_forms_are_normalized(self):
        cases = (
            ("- docs root: .claude/docs/", ".claude/docs/"),
            ("- docs root: .claude/docs", ".claude/docs/"),
            ("- docs root: `kb`", "kb/"),
            ("- docs root:   ./kb/  ", "kb/"),
            ("* Docs Root: kb", "kb/"),
            ("- docs root: a//b/./c", "a/b/c/"),
            ("- docs root: x\\y", "x/y/"),
        )
        for line, expected in cases:
            with self.subTest(line=line):
                self.write_md(f"# p\n\n## Workflow\n\n{line}\n")
                self.assertEqual(self.root(), expected)

    def test_dr4_invalid_values_default(self):
        for value in ("", ".", "..", "a/../b", "/abs", "~/x", "C:/x", "kb\tx"):
            with self.subTest(value=value):
                self.assertIsNone(audit.normalize_docs_root(value))
                self.declare(value)
                self.assertEqual(self.root(), "docs/")

    def test_dr5_line_outside_the_workflow_section_is_ignored(self):
        line = "- docs root: kb/\n"
        cases = {
            "other section": f"# p\n\n## Test suites\n\n{line}",
            "### Workflow only": f"# p\n\n### Workflow\n\n{line}",
            "after a ## that closes it": f"# p\n\n## Workflow\n\n- docs layout: features\n\n## Outra\n\n{line}",
            "level 1 heading": f"# Workflow\n\n{line}",
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                self.write_md(text)
                self.assertEqual(self.root(), "docs/")

    def test_dr6_subheading_and_loose_heading_keep_the_section(self):
        with self.subTest(case="### Sub"):
            self.write_md("# p\n\n## Workflow\n\n### Sub\n\n- docs root: kb/\n")
            self.assertEqual(self.root(), "kb/")
        with self.subTest(case="spaces and case"):
            self.write_md("# p\n\n##   workflow  \n\n- docs root: kb/\n")
            self.assertEqual(self.root(), "kb/")

    def test_dr7_first_docs_root_line_decides(self):
        with self.subTest(case="two valid"):
            self.write_md("# p\n\n## Workflow\n\n- docs root: kb/\n- docs root: other/\n")
            self.assertEqual(self.root(), "kb/")
        with self.subTest(case="first invalid"):
            self.write_md("# p\n\n## Workflow\n\n- docs root: /abs\n- docs root: other/\n")
            self.assertEqual(self.root(), "docs/")

    def test_dr8_unreadable_claude_md_never_raises(self):
        with self.subTest(case="directory"):
            (self.repo / "CLAUDE.md").mkdir()
            self.assertEqual(self.root(), "docs/")
            (self.repo / "CLAUDE.md").rmdir()
        with self.subTest(case="invalid utf-8 before the section"):
            self.write_md(b"\xff\xfe\x00 junk\n## Workflow\n- docs root: kb/\n")
            self.assertEqual(self.root(), "kb/")
        with self.subTest(case="line after 256 KiB"):
            filler = "x" * 99 + "\n"
            self.write_md("## Workflow\n" + filler * 3000 + "- docs root: kb/\n")
            self.assertGreater((self.repo / "CLAUDE.md").stat().st_size, 262144 - 1)
            self.assertEqual(self.root(), "docs/")
        with self.subTest(case="no read permission"):
            if hasattr(os, "geteuid") and os.geteuid() == 0:
                self.skipTest("root reads any file")
            self.write_md("## Workflow\n- docs root: kb/\n")
            (self.repo / "CLAUDE.md").chmod(0)
            self.addCleanup((self.repo / "CLAUDE.md").chmod, 0o600)
            self.assertEqual(self.root(), "docs/")

    def root_within(self, seconds=2.0):
        """Run `project_docs_root` in a daemon thread so a hang fails the test instead of the suite."""
        result = []
        thread = threading.Thread(target=lambda: result.append(self.root()), daemon=True)
        thread.start()
        thread.join(seconds)
        self.assertFalse(thread.is_alive(), "project_docs_root hung")
        return result[0]

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs os.mkfifo")
    def test_dr18_fifo_claude_md_defaults_without_hanging(self):
        os.mkfifo(self.repo / "CLAUDE.md")
        self.assertEqual(self.root_within(), "docs/")

    def test_dr19_symlink_to_char_device_defaults_without_hanging(self):
        if not os.path.exists("/dev/null"):
            self.skipTest("no /dev/null")
        (self.repo / "CLAUDE.md").symlink_to("/dev/null")
        self.assertEqual(self.root_within(), "docs/")

    def test_dr9_only_the_dot_claude_claude_md_declares(self):
        self.write_md("# p\n\n## Workflow\n\n- docs root: kb/\n", rel=".claude/CLAUDE.md")
        self.assertEqual(self.root(), "docs/")

    def test_dr17_non_str_is_invalid(self):
        for value in (None, 3, ["kb"], Path("kb")):
            with self.subTest(value=value):
                self.assertIsNone(audit.normalize_docs_root(value))


class DocsRootEffect(TempRepoCase):
    """Spec skills-docs-root, Testing DR10-DR16: the declared docs root decides the docs area of a write."""

    def ev(self, rel, actor="main", roots=None, cwd=None, target=None):
        path = target or (self.repo / rel)
        return audit.evaluate_write(str(path), str(cwd or self.repo), actor, "Write", None, roots)

    def test_dr10_declared_root_is_the_docs_area(self):
        self.declare("kb/")
        with self.subTest(target="kb/x.md"):
            out = self.ev("kb/x.md")
            self.assertEqual(out["area"], "docs")
            self.assertEqual(out["flags"], [])
        with self.subTest(target="docs/x.md"):
            out = self.ev("docs/x.md")
            self.assertEqual(out["area"], "code")
            self.assertIn("md_outside_docs", out["flags"])

    def test_dr11_backlog_of_the_declared_root(self):
        self.declare("kb/")
        for actor, rel, expected in (
            ("specker", "kb/backlog/bugs/x.md", True),
            ("backlog-keeper", "kb/backlog/bugs/x.md", False),
            ("specker", "docs/backlog/x.md", False),
        ):
            with self.subTest(actor=actor, rel=rel):
                out = self.ev(rel, actor=actor)
                self.assertEqual("backlog_write_by_other" in out["flags"], expected)
                if rel.startswith("docs/"):
                    self.assertIn("md_outside_docs", out["flags"])

    def test_dr12_implementer_write_in_the_declared_root(self):
        self.declare("kb/")
        self.assertIn("docs_write_by_implementer", self.ev("kb/x.md", actor="backend-node")["flags"])

    def test_dr13_undeclared_repo_has_only_docs(self):
        for rel in (".claude/docs/x.md", "services/x/docs/a.md"):
            with self.subTest(rel=rel):
                out = self.ev(rel)
                self.assertEqual(out["area"], "code")
                self.assertIn("md_outside_docs", out["flags"])

    def test_dr14_nested_repo_uses_its_own_declaration(self):
        self.declare("kb/")
        inner = self.repo / "sub"
        inner.mkdir()
        subprocess.run(["git", "init", "-q", str(inner)], check=True)
        declare_docs_root(inner, "notes/")
        out = self.ev(None, target=inner / "notes" / "x.md")
        self.assertEqual(out["rel"], "notes/x.md")
        self.assertEqual(out["area"], "docs")

    def test_dr15_explicit_roots_override_the_declaration(self):
        self.declare("kb/")
        self.assertEqual(self.ev("kb/x.md", roots=["docs/"])["area"], "code")

    def test_dr16_main_reads_the_declaration_and_ignores_the_old_key(self):
        def post_flags(cfg):
            pl = payload("PostToolUse", "Write", cwd=self.repo,
                         tool_input={"file_path": str(self.repo / "kb" / "a.md")})
            result = call_main(pl, cfg)
            self.assertEqual(len(result.records), 1)
            return result.records[0]["flags"]

        def pre_output(actor="specker"):
            pl = payload("PreToolUse", "Write", actor=actor, cwd=self.repo,
                         tool_input={"file_path": str(self.repo / ".claude/docs/features/x/spec.md")})
            return call_main(pl).output

        with self.subTest(case="declared kb/"):
            self.declare("kb/")
            self.assertNotIn("md_outside_docs", post_flags(config()))
        (self.repo / "CLAUDE.md").unlink()
        with self.subTest(case="old docs_roots key ignored"):
            self.assertIn("md_outside_docs", post_flags(config(docs_roots=["kb/"])))
        with self.subTest(case="PreToolUse with .claude/docs/ declared"):
            self.declare(".claude/docs/")
            self.assertIsNone(pre_output())
        with self.subTest(case="PreToolUse without declaration"):
            (self.repo / "CLAUDE.md").unlink()
            out = pre_output()
            assert out is not None
            self.assertIn("md_outside_docs", out["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()


