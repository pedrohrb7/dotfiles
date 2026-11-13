"""DESIGN_SYSTEM.md rules of agent-audit.py (cases H1-H28).

Source: spec of the design-director feature (Testing, cases H), as reconstructed in
docs/features/audit-hook-test-suite/spec.md. Each case sends a PreToolUse and a PostToolUse with the
same payload through `main()` in process, with TEST_CONFIG (enforce) unless the case says otherwise.
"""
from ._support import TempRepoCase, assert_no_git_root, call_main, config, payload

DS = "DESIGN_SYSTEM.md"
DSBO = "design_system_write_by_other"
DDWO = "design_director_write_outside"
MOD = "md_outside_docs"
OOS = "out_of_scope_write"

SILENT = ("silent", None)
CREATE = {"type": "create"}


def deny(cat):
    return ("deny", cat)


def warn(cat):
    return ("warn", cat)


# id, actor, tool, path, create, run, pre, flags, extras
# run: None (no run), "run" (allowed_paths services/web/src/**) or "scope" (run + approved_scope)
# pre / flags None: not asserted for that case (the spec table has "-")
CASES = [
    ("H1", "design-director", "Write", DS, False, None, SILENT, []),
    ("H2", "design-director", "Write", "services/web/DESIGN_SYSTEM.md", False, None, SILENT, []),
    ("H3", "design-director", "Write", "NOTES.md", False, None, deny(DDWO), [DDWO, MOD]),
    ("H4", "frontend-react", "Edit", DS, False, None, warn(DSBO), [DSBO]),
    ("H5", "frontend-react", "Edit", DS, False, "run", warn(DSBO), [DSBO, OOS]),
    ("H6", "docs-writer", "Edit", DS, False, None, warn(DSBO), [DSBO]),
    ("H7", "main", "Edit", DS, False, None, SILENT, []),
    ("H9", "subagent", "Edit", DS, False, None, warn(DSBO), [DSBO]),
    ("H10", "frontend-react", "Edit", ".claude/templates/project-root/DESIGN_SYSTEM.md", False, None, warn(DSBO), [DSBO]),
    ("H11", "design-director", "Edit", DS, False, None, SILENT, []),
    ("H12", "design-director", "Write", DS, True, None, None, []),
    ("H13", "backend-node", "Write", DS, True, None, warn(DSBO), [DSBO, MOD]),
    ("H15", "design-director", "Edit", "src/a.ts", False, None, deny(DDWO), [DDWO]),
    ("H16", "design-director", "Write", "src/a.ts", True, None, deny(DDWO), [DDWO]),
    ("H17", "design-director", "Edit", "apps/web/DESIGN_SYSTEM.md", False, None, SILENT, []),
    ("H18", "design-director", "Write", "apps/web/DESIGN_SYSTEM.md", True, None, None, []),
    ("H19", "frontend-react", "Edit", "design_system.md", False, None, warn(DSBO), [DSBO]),
    ("H20", "design-director", "Write", "design_system.md", True, None, None, []),
    ("H21", "frontend-react", "Edit", "apps/web/DESIGN_SYSTEM.md", False, None, warn(DSBO), [DSBO]),
    ("H22", "main", "Edit", "apps/web/Design_System.md", False, None, SILENT, []),
    ("H26", "frontend-react", "Edit", DS, False, "scope", None, [DSBO, OOS]),
    ("H27", "frontend-react", "Edit", "apps/web/design_system.md", False, "scope", None, [DSBO, OOS]),
    ("H28", "frontend-react", "Edit", "services/api/x.ts", False, "scope", None, []),
]


class DesignSystemRules(TempRepoCase):
    """Cases H1-H28 of the design-director spec (Testing, cases H), run through `main()`.

    H14 (`test_h14_main_creates_design_system_md`): the main session is free of md_outside_docs.
    """

    def _run_state(self, kind):
        self.remove_run()  # cases share one repo: start every case without a run
        if kind is None:
            return
        extra: dict = {"allowed_paths": {"1": ["services/web/src/**"]}}
        if kind == "scope":
            extra["approved_scope"] = [
                {"task": 1, "target": DS, "decision": "approved"},
                {"task": 1, "target": "services/api/**", "decision": "approved"},
            ]
        self.write_run(**extra)

    def _payloads(self, actor, tool, path, create, cwd, target_root):
        tool_input = {"file_path": str(target_root / path)}
        response = CREATE if create else None
        return (
            payload("PreToolUse", tool, actor=actor, cwd=cwd, tool_input=tool_input, tool_response=response),
            payload("PostToolUse", tool, actor=actor, cwd=cwd, tool_input=tool_input, tool_response=response),
        )

    def _assert_pre(self, out, expected, case):
        kind, cat = expected
        if kind == "silent":
            self.assertIsNone(out, f"{case}: expected silence, got {out}")
            return
        self.assertIsNotNone(out, f"{case}: expected {kind} {cat}, got no output")
        hso = out["hookSpecificOutput"]
        if kind == "deny":
            self.assertEqual(hso.get("permissionDecision"), "deny", case)
            self.assertIn(f"Agent workflow ({cat})", hso["permissionDecisionReason"], case)
        else:
            self.assertNotIn("permissionDecision", hso, case)
            self.assertIn(f"Reminder from the agent workflow ({cat})", hso["additionalContext"], case)

    def _check(self, case, actor, tool, path, create, run, pre, flags, cfg=None):
        self._run_state(run)
        pre_payload, post_payload = self._payloads(actor, tool, path, create, self.repo, self.repo)
        if pre is not None:
            self._assert_pre(call_main(pre_payload, cfg).output, pre, case)
        if flags is not None:
            result = call_main(post_payload, cfg)
            self.assertEqual(len(result.records), 1, case)
            self.assertEqual(result.records[0]["flags"], flags, case)

    def test_table(self):
        for case, actor, tool, path, create, run, pre, flags in CASES:
            with self.subTest(case=case):
                self._check(case, actor, tool, path, create, run, pre, flags)

    def test_h8_audit_mode_is_silent_but_flags(self):
        """H8: frontend-react Edit on DESIGN_SYSTEM.md in `mode: audit` -> silent pre, flag recorded."""
        with self.subTest(case="H8"):
            self._check("H8", "frontend-react", "Edit", DS, False, None, SILENT, [DSBO], cfg=config(mode="audit"))

    def test_h14_main_creates_design_system_md(self):
        """H14: main Write-creating DESIGN_SYSTEM.md at the root -> silent, no flags.

        The root DESIGN_SYSTEM.md is a legitimate file of the main session, which never gets
        md_outside_docs (spec audit-md-outside-docs, M1).
        """
        with self.subTest(case="H14"):
            self._check("H14", "main", "Write", DS, True, None, SILENT, [])

    def test_no_git_root_cases(self):
        """H23-H25: target and cwd in a directory without a git root (premise asserted)."""
        cases = [
            ("H23", "Edit", "x.ts", deny(DDWO)),
            ("H24", "Edit", DS, SILENT),
            ("H25", "Edit", "app/design_system.MD", SILENT),
        ]
        for case, tool, path, pre in cases:
            with self.subTest(case=case):
                outside = self.make_dir()
                assert_no_git_root(outside)
                pre_payload, _ = self._payloads("design-director", tool, path, False, outside, outside)
                self._assert_pre(call_main(pre_payload).output, pre, case)
