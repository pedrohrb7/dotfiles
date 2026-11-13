"""Tests of the area flags of agent-audit.py `evaluate_write` and of the declared docs root.

Source: docs/features/audit-hook-test-suite/spec.md, Testing (A1-A9); skills-docs-root spec, Testing
(DR1-DR17: `project_docs_root()` / `normalize_docs_root()` and their effect on writes).
"""
import os
import subprocess
import threading
import unittest
from pathlib import Path
from unittest import mock

from ._support import TempRepoCase, audit, call_main, config, declare_docs_root, payload, write_run_state

ROOTS = ["docs/", ".claude/docs/"]


class AreaFlags(TempRepoCase):
    """Spec Testing A1-A9: `md_outside_docs`, `docs_write_by_implementer`, `backlog_write_by_other`,
    `area` and the record fields, in a temp repo without an active run."""

    def ev(self, rel, actor="main", tool="Write", response=None, roots=ROOTS):
        return audit.evaluate_write(str(self.repo / rel), str(self.repo), actor, tool, response, roots)

    def test_a1_main_write_of_md_at_root_has_no_md_flag(self):
        """Spec audit-md-outside-docs, M1: the main session never gets md_outside_docs."""
        out = self.ev("notes.md")
        self.assertNotIn("md_outside_docs", out["flags"])
        self.assertEqual(out["area"], "code")

    def test_a2_edit_of_existing_md_has_no_flag(self):
        """Spec audit-md-outside-docs, M3: an Edit never creates (judged for an actor that gets the flag)."""
        out = self.ev("notes.md", actor="backend-node", tool="Edit")
        self.assertEqual(out["flags"], [])

    def test_a3_exempt_md_names_are_not_md_outside_docs(self):
        """Spec audit-md-outside-docs, M4: known doc names, exact name, any case."""
        rels = ("README.md", "services/api/README.md", "CLAUDE.md", "CHANGELOG.md", "DEPLOY.md",
                "readme.md", "Changelog.MD", "services/api/claude.md")
        for actor in ("test-writer", "docs-writer"):
            for rel in rels:
                with self.subTest(case="A3", actor=actor, rel=rel):
                    self.assertNotIn("md_outside_docs", self.ev(rel, actor=actor)["flags"])

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


MOD = "md_outside_docs"
DWBI = "docs_write_by_implementer"
OOS = "out_of_scope_write"
DSBO = "design_system_write_by_other"
BWBO = "backlog_write_by_other"


class MdOutsideDocs(TempRepoCase):
    """Spec audit-md-outside-docs, Testing MD1-MD15, MD17: `md_outside_docs` is for agents creating a new
    .md outside the docs root (not the main session or docs-writer, not the known doc names, not a markdown
    path in the task's Files), and `docs_write_by_implementer` compares names without case."""

    MD10_ALLOWED = {"1": [".claude/agents/x.md", "services/web/content/*.md", "`kb2/GUIDE.MD`", "services/api/**"]}

    def ev(self, rel, actor="planner", tool="Write", response=None):
        return audit.evaluate_write(str(self.repo / rel), str(self.repo), actor, tool, response, ROOTS)

    def flags(self, rel, **kw):
        return self.ev(rel, **kw)["flags"]

    def test_md1_agents_get_the_flag(self):
        for actor in ("subagent", "backend-node", "planner", "specker", "quality-fixer"):
            for rel in ("notes.md", "PRD.md", "services/api/NOTES.md"):
                with self.subTest(case="MD1", actor=actor, rel=rel):
                    self.assertIn(MOD, self.flags(rel, actor=actor))

    def test_md2_main_session_never_gets_the_flag(self):
        rels = ("PRD.md", "CONSTRAINTS.md", "OPEN_QUESTIONS.md", "DESIGN_SYSTEM.md", "BACKEND.md", "NOTES.md",
                ".claude/agents/x.md", "apps/web/PRD.md")
        for rel in rels:
            with self.subTest(case="MD2", rel=rel):
                self.assertNotIn(MOD, self.flags(rel, actor="main"))
        with self.subTest(case="MD2", rel="docs/backlog/x.md"):
            flags = self.flags("docs/backlog/x.md", actor="main")
            self.assertNotIn(MOD, flags)
            self.assertIn(BWBO, flags)

    def test_md3_names_are_exact(self):
        rels = ("MY_README.md", "NOTCLAUDE.md", "xCHANGELOG.md", "README.md.md", "PREDEPLOY.md",
                "services/api/MY_CLAUDE.md")
        for rel in rels:
            with self.subTest(case="MD3", rel=rel):
                flags = self.flags(rel, actor="backend-node")
                self.assertIn(MOD, flags)
                self.assertNotIn(DWBI, flags)

    def test_md4_extension_is_case_insensitive_and_only_md(self):
        for rel, expected in (("NOTES.MD", True), ("notes.Md", True), ("x.mdx", False), ("x.markdown", False)):
            with self.subTest(case="MD4", rel=rel):
                self.assertEqual(MOD in self.flags(rel, actor="backend-node"), expected)

    def test_md5_tool_response_type_decides(self):
        for response, expected in (({"type": "create"}, True), ({"type": "update"}, False),
                                   ({"filePath": "x"}, True)):
            with self.subTest(case="MD5", response=response):
                self.assertEqual(MOD in self.flags("notes.md", response=response), expected)

    def test_md6_without_response_the_target_existence_decides(self):
        with self.subTest(case="MD6", exists=True):
            (self.repo / "notes.md").write_text("x", encoding="utf-8")
            self.assertNotIn(MOD, self.flags("notes.md"))
        with self.subTest(case="MD6", exists=False):
            self.assertIn(MOD, self.flags("other.md"))

    def test_md7_edit_tools_do_not_create(self):
        cases = (("Edit", None, False), ("Edit", {"type": "create"}, True), ("MultiEdit", None, False))
        for tool, response, expected in cases:
            with self.subTest(case="MD7", tool=tool, response=response):
                self.assertEqual(MOD in self.flags("notes.md", tool=tool, response=response), expected)

    def test_md8_error_checking_existence_counts_as_creation(self):
        real = Path.exists

        def fake(path, *args, **kwargs):
            if path.name == "notes.md":
                raise PermissionError("denied")
            return real(path, *args, **kwargs)

        with mock.patch.object(Path, "exists", fake):
            self.assertIn(MOD, self.flags("notes.md"))

    def test_md9_symlinks_are_judged_by_the_resolved_target(self):
        (self.repo / "real.md").write_text("x", encoding="utf-8")
        try:
            (self.repo / "link.md").symlink_to("real.md")
            (self.repo / "dangling.md").symlink_to("missing.md")
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.subTest(case="MD9", target="link.md"):
            self.assertNotIn(MOD, self.flags("link.md"))
        with self.subTest(case="MD9", target="dangling.md"):
            out = self.ev("dangling.md")
            self.assertIn(MOD, out["flags"])
            self.assertEqual(out["rel"], "missing.md")

    def test_md10_markdown_paths_of_the_task_files_are_exempt(self):
        write_run_state(self.repo, self.MD10_ALLOWED)
        for rel, expected in ((".claude/agents/x.md", False), ("services/web/content/post.md", False),
                              ("kb2/GUIDE.MD", False), ("services/api/NOTES.md", True)):
            with self.subTest(case="MD10", rel=rel):
                flags = self.flags(rel, actor="frontend-react")
                self.assertEqual(MOD in flags, expected)
                self.assertNotIn(OOS, flags)

    def test_md11_approved_scope_exempts_only_approved_markdown_of_running_tasks(self):
        scope = [
            {"task": 1, "target": "services/api/NOTES.md", "decision": "approved"},
            {"task": 1, "target": "services/api/OTHER.md", "decision": "denied"},
            {"task": 2, "target": "services/api/T2.md", "decision": "approved"},
        ]
        write_run_state(self.repo, {"1": ["services/api/**"]}, approved_scope=scope)
        for rel, expected in (("services/api/NOTES.md", False), ("services/api/OTHER.md", True),
                              ("services/api/T2.md", True)):
            with self.subTest(case="MD11", rel=rel):
                self.assertEqual(MOD in self.flags(rel, actor="frontend-react"), expected)

    def test_md12_exemption_is_only_for_fixed_scope_actors_with_a_run(self):
        write_run_state(self.repo, self.MD10_ALLOWED)
        with self.subTest(case="MD12", actor="planner"):
            self.assertIn(MOD, self.flags(".claude/agents/x.md", actor="planner"))
        with self.subTest(case="MD12", actor="frontend-react", run=False):
            self.remove_run()
            self.assertIn(MOD, self.flags(".claude/agents/x.md", actor="frontend-react"))

    def test_md13_design_system_never_enters_the_exemption(self):
        scope = [{"task": 1, "target": "DESIGN_SYSTEM.md", "decision": "approved"}]
        write_run_state(self.repo, {"1": ["services/web/**"]}, approved_scope=scope)
        flags = self.flags("DESIGN_SYSTEM.md", actor="frontend-react", response={"type": "create"})
        self.assertEqual(flags, [DSBO, MOD, OOS])

    def test_md14_doc_file_names_are_compared_without_case(self):
        rels = ("Readme.md", "services/api/readme.md", "changelog.md", "Deploy.md", ".ENV.EXAMPLE")
        for actor, expected in (("backend-node", True), ("docs-writer", False), ("main", False)):
            for rel in rels:
                with self.subTest(case="MD14", actor=actor, rel=rel):
                    self.assertEqual(DWBI in self.flags(rel, actor=actor), expected)

    def test_md15_helpers(self):
        for value, expected in (("a\\B.MD", "b.md"), ("content/*.md", "*.md"), ("", "")):
            with self.subTest(helper="file_name", value=value):
                self.assertEqual(audit.file_name(value), expected)
        cases = (
            ("Write", {"type": "create"}, True), ("Write", {"type": "update"}, False),
            ("Write", {"filePath": "x"}, True), ("Write", None, None),
            ("Edit", None, False), ("Edit", {"type": "create"}, True), ("MultiEdit", None, False),
            ("NotebookEdit", {"type": "update"}, False),
            ("Write", [], True), ("Write", "x", True), ("Write", {"type": 3}, True),
            ("Edit", [], False), ("Edit", "x", False), ("Edit", {"type": 3}, False),
        )
        for tool, response, expected in cases:
            with self.subTest(helper="write_creates", tool=tool, response=response):
                self.assertIs(audit.write_creates(tool, response), expected)

    def test_md17_docs_writer_never_gets_the_flag(self):
        rels = ("NOTES.md", "SUMMARY.MD", "services/api/API.md", "PRD.md")
        for run in (False, True):
            if run:
                write_run_state(self.repo, self.MD10_ALLOWED)
            for rel in rels:
                with self.subTest(case="MD17", rel=rel, run=run):
                    self.assertNotIn(MOD, self.flags(rel, actor="docs-writer"))
        self.remove_run()
        for actor in ("planner", "backend-node"):
            for rel in rels:
                with self.subTest(case="MD17", actor=actor, rel=rel):
                    self.assertIn(MOD, self.flags(rel, actor=actor))
        with self.subTest(case="MD17", rel="DESIGN_SYSTEM.md"):
            self.assertEqual(self.flags("DESIGN_SYSTEM.md", actor="docs-writer", response={"type": "create"}), [DSBO])
        with self.subTest(case="MD17", rel="docs/backlog/x.md"):
            self.assertIn(BWBO, self.flags("docs/backlog/x.md", actor="docs-writer"))


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
    """Spec skills-docs-root, Testing DR10-DR16: the declared docs root decides the docs area of a write.

    The writes that expect `md_outside_docs` use `specker`: the test is about the declared root, and
    the main session never gets that flag (spec audit-md-outside-docs, M1)."""

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
            out = self.ev("docs/x.md", actor="specker")
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
                out = self.ev(rel, actor="specker")
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
            pl = payload("PostToolUse", "Write", actor="specker", cwd=self.repo,
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


