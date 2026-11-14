"""Regression tests for agent-audit.py write scope: parallel tasks and writes outside the git root.

Bugs: docs/backlog/bugs/2026-11-11-audit-parallel-task-out-of-scope.md and
docs/backlog/bugs/2026-11-11-audit-path-checks-outside-git-root.md
"""
import io
import json
import os
import shutil
import subprocess
import unittest
import uuid
from pathlib import Path
from unittest import mock

from ._support import ForkedSuite, TempRepoCase, audit, init_repo


class ParallelTasksScope(TempRepoCase):
    """Bug: docs/backlog/bugs/2026-11-11-audit-parallel-task-out-of-scope.md

    With several tasks running at once, a scoped actor is in scope if the path matches the
    allowed_paths or approved_scope of ANY task in `running_tasks`. Without it, the scalar
    current_task is used as before.
    """

    def test_write_of_second_running_task_is_in_scope(self):
        self.write_run(running_tasks=[1, 2])
        out = self.evaluate("services/web/src/App.tsx")
        self.assertTrue(out["in_scope"])
        self.assertNotIn("out_of_scope_write", out["flags"])

    def test_write_of_first_running_task_is_in_scope(self):
        self.write_run(running_tasks=[1, 2])
        out = self.evaluate("services/api/src/main.py", actor="backend-python")
        self.assertTrue(out["in_scope"])
        self.assertNotIn("out_of_scope_write", out["flags"])

    def test_write_outside_every_running_task_is_out_of_scope(self):
        self.write_run(running_tasks=[1, 2])
        out = self.evaluate("services/other/x.py")
        self.assertFalse(out["in_scope"])
        self.assertIn("out_of_scope_write", out["flags"])

    def test_task_not_running_does_not_contribute_scope(self):
        self.write_run(running_tasks=[1])
        out = self.evaluate("services/web/src/App.tsx")
        self.assertIn("out_of_scope_write", out["flags"])

    def test_scalar_current_task_without_running_tasks_is_unchanged(self):
        self.write_run()
        self.assertIn("out_of_scope_write", self.evaluate("services/web/src/App.tsx")["flags"])
        out = self.evaluate("services/api/src/main.py", actor="backend-python")
        self.assertTrue(out["in_scope"])
        self.assertNotIn("out_of_scope_write", out["flags"])

    def test_scoped_support_actors_use_running_tasks_too(self):
        self.write_run(running_tasks=[1, 2])
        for actor in ("quality-fixer", "test-writer"):
            with self.subTest(actor=actor):
                out = self.evaluate("services/web/src/App.test.tsx", actor=actor)
                self.assertNotIn("out_of_scope_write", out["flags"])

    def test_approved_scope_of_running_task_applies(self):
        self.write_run(
            running_tasks=[1, 2],
            approved_scope=[{"task": 2, "target": "services/shared/**", "decision": "approved"}],
        )
        out = self.evaluate("services/shared/util.py", actor="backend-python")
        self.assertTrue(out["in_scope"])
        self.assertNotIn("out_of_scope_write", out["flags"])

    def test_approved_scope_of_task_not_running_does_not_apply(self):
        self.write_run(
            running_tasks=[1],
            approved_scope=[{"task": 2, "target": "services/shared/**", "decision": "approved"}],
        )
        out = self.evaluate("services/shared/util.py", actor="backend-python")
        self.assertIn("out_of_scope_write", out["flags"])

    def test_denied_approved_scope_entry_does_not_apply(self):
        self.write_run(
            running_tasks=[1, 2],
            approved_scope=[{"task": 2, "target": "services/shared/**", "decision": "denied"}],
        )
        out = self.evaluate("services/shared/util.py", actor="backend-python")
        self.assertIn("out_of_scope_write", out["flags"])

    def test_task_reports_all_running_tasks(self):
        self.write_run(running_tasks=[1, 2])
        self.assertEqual(self.evaluate("services/web/src/App.tsx")["task"], "1,2")

    def test_task_reports_single_running_task(self):
        # current_task equals the only running task: reported once, deduplicated
        self.write_run(running_tasks=[2], current_task=2)
        self.assertEqual(self.evaluate("services/web/src/App.tsx")["task"], "2")

    def test_current_task_is_appended_after_running_tasks(self):
        self.write_run(running_tasks=[2], current_task=1)
        self.assertEqual(self.evaluate("services/web/src/App.tsx")["task"], "2,1")

    def test_running_tasks_containing_current_task_are_unchanged(self):
        self.write_run(running_tasks=[1, 2], current_task=1)
        self.assertEqual(self.evaluate("services/web/src/App.tsx")["task"], "1,2")

    def test_stale_running_tasks_never_replace_current_task(self):
        allowed = {"3": ["services/api/**"], "5": ["services/web/**"]}
        self.write_run(running_tasks=[3], current_task=5, allowed_paths=allowed)
        web = self.evaluate("services/web/src/App.tsx")
        self.assertTrue(web["in_scope"])
        self.assertNotIn("out_of_scope_write", web["flags"])
        api = self.evaluate("services/api/src/main.py", actor="backend-python")
        self.assertTrue(api["in_scope"])
        self.assertNotIn("out_of_scope_write", api["flags"])
        other = self.evaluate("services/other/x.py")
        self.assertIn("out_of_scope_write", other["flags"])
        self.assertEqual(web["task"], "3,5")

    def test_malformed_running_tasks_fall_back_to_current_task(self):
        shapes = {"empty_list": [], "string": "2", "dict": {"2": True}, "null_and_empty": [None, ""]}
        for name, value in shapes.items():
            with self.subTest(shape=name):
                self.write_run(running_tasks=value)
                web = self.evaluate("services/web/src/App.tsx")
                self.assertIn("out_of_scope_write", web["flags"])
                api = self.evaluate("services/api/src/main.py", actor="backend-python")
                self.assertNotIn("out_of_scope_write", api["flags"])
                self.assertEqual(api["task"], "1")

    def write_raw_run(self, **state):
        state = {"phase": "implement", "allowed_paths": self.ALLOWED, **state}
        (self.repo / ".claude" / "runs" / "feat-x.json").write_text(json.dumps(state))

    def test_missing_or_null_current_task_is_excluded_from_keys(self):
        for name, extra in {"absent": {}, "null": {"current_task": None}}.items():
            with self.subTest(current_task=name):
                self.write_raw_run(running_tasks=[1, 2], **extra)
                out = self.evaluate("services/web/src/App.tsx")
                self.assertEqual(out["task"], "1,2")
                self.assertNotIn("None", out["task"])
                self.assertNotIn("", out["task"].split(","))
                self.assertNotIn("out_of_scope_write", out["flags"])

    def test_run_without_any_task_has_empty_task_and_does_not_crash(self):
        self.write_raw_run()
        out = self.evaluate("services/web/src/App.tsx")
        self.assertEqual(out["task"], "")
        self.assertIn("out_of_scope_write", out["flags"])

    def test_boolean_current_task_is_ignored(self):
        self.write_raw_run(current_task=True)
        out = self.evaluate("services/api/src/main.py", actor="backend-python")
        self.assertEqual(out["task"], "")
        self.assertIn("out_of_scope_write", out["flags"])

    def test_absent_running_tasks_fall_back_to_current_task(self):
        self.write_run()
        self.assertEqual(self.evaluate("services/api/src/main.py")["task"], "1")

    def test_subagent_start_record_is_tagged_with_running_tasks(self):
        self.write_run(running_tasks=[1, 2])
        metrics = self.repo / "metrics"
        payload = {
            "hook_event_name": "SubagentStart", "session_id": "s1", "agent_type": "frontend-react",
            "agent_id": "a1", "cwd": str(self.repo),
        }
        with mock.patch.object(audit, "METRICS_DIR", metrics), \
                mock.patch.object(audit, "load_config", return_value={"mode": "audit"}), \
                mock.patch("sys.stdin", io.StringIO(json.dumps(payload))):
            audit.main()
        records = [json.loads(line) for line in (metrics / "s1.jsonl").read_text().splitlines()]
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["in_run"])
        self.assertEqual(records[0]["task"], "1,2")

    def test_task_falls_back_to_scalar_current_task(self):
        self.write_run()
        self.assertEqual(self.evaluate("services/api/src/main.py")["task"], "1")

    def test_string_task_ids_in_running_tasks(self):
        self.write_run(running_tasks=["1", "2"])
        out = self.evaluate("services/web/src/App.tsx")
        self.assertNotIn("out_of_scope_write", out["flags"])
        self.assertEqual(out["task"], "1,2")

    def test_mixed_int_and_string_ids_with_approved_scope(self):
        self.write_run(
            running_tasks=[1, "2"],
            approved_scope=[
                {"task": "2", "target": "services/shared/**", "decision": "approved"},
                {"task": 1, "target": "services/lib/**", "decision": "approved"},
            ],
        )
        for rel in ("services/web/a.ts", "services/shared/u.py", "services/lib/l.py"):
            with self.subTest(rel=rel):
                self.assertNotIn("out_of_scope_write", self.evaluate(rel, actor="backend-python")["flags"])


class OutsideRepoWrites(TempRepoCase):
    """Bug: docs/backlog/bugs/2026-11-11-audit-path-checks-outside-git-root.md

    The governing root is the git root of the session cwd; targets outside it are judged by
    actor-only flags and, for fixed-scope actors in a run, out_of_scope_write.
    """

    SCOPED = ("backend-node", "quality-fixer", "test-writer")

    def setUp(self):
        super().setUp()
        self.write_run()

    def assertOutOfScope(self, out):
        self.assertIn("out_of_scope_write", out.get("flags", []))

    def assertNotOutOfScope(self, out):
        self.assertNotIn("out_of_scope_write", out.get("flags", []))

    def test_scoped_actor_writing_to_dir_without_git_root_is_out_of_scope(self):
        target = self.make_dir() / "x.py"
        out = self.eval_at(target, "backend-node")
        self.assertOutOfScope(out)
        self.assertEqual(out["area"], "outside")
        self.assertEqual(out["rel"], str(target.resolve()))
        self.assertTrue(out["in_run"])

    def test_readonly_agent_writing_outside_is_flagged_and_inside_control(self):
        target = self.make_dir() / "x.md"
        self.assertIn("write_by_readonly_agent", self.eval_at(target, "code-reviewer").get("flags", []))
        inside = self.eval_at(self.repo / "services" / "api" / "x.py", "code-reviewer")
        self.assertIn("write_by_readonly_agent", inside.get("flags", []))

    def test_target_in_another_git_repo_is_out_of_scope(self):
        other = self.make_dir(git=True)
        out = self.eval_at(other / "services" / "api" / "x.py", "backend-node")
        self.assertOutOfScope(out)
        self.assertEqual(out["area"], "outside")

    def test_relative_escape_is_out_of_scope(self):
        escape = Path("..") / (self.make_dir().name) / "x.py"
        out = self.eval_at(escape, "backend-node")
        self.assertOutOfScope(out)
        self.assertEqual(out["area"], "outside")

    def test_symlink_inside_repo_pointing_outside_is_out_of_scope(self):
        outside = self.make_dir()
        link = self.repo / "services" / "api" / "link"
        link.parent.mkdir(parents=True)
        link.symlink_to(outside, target_is_directory=True)
        out = self.eval_at(link / "x.py", "backend-node")
        self.assertOutOfScope(out)
        self.assertEqual(out["area"], "outside")

    def test_every_fixed_scope_actor_is_flagged_but_main_is_not(self):
        target = self.make_dir() / "x.py"
        for actor in self.SCOPED:
            with self.subTest(actor=actor):
                self.assertOutOfScope(self.eval_at(target, actor))
        self.assertNotOutOfScope(self.eval_at(target, "main"))

    def test_approved_absolute_glob_covers_outside_path(self):
        d = self.make_dir()
        self.write_run(approved_scope=[{"task": 1, "target": f"{d}/**", "decision": "approved"}])
        self.assertNotOutOfScope(self.eval_at(d / "sub" / "x.py", "backend-node"))

    def test_repo_relative_glob_does_not_cover_outside_path(self):
        d = self.make_dir()
        self.write_run(approved_scope=[{"task": 1, "target": "**", "decision": "approved"}])
        self.assertOutOfScope(self.eval_at(d / "x.py", "backend-node"))

    def test_always_allowed_patterns_do_not_apply_outside(self):
        d = self.make_dir()
        out = self.eval_at(d / "db" / "migrations" / "001.sql", "backend-node")
        self.assertOutOfScope(out)

    def test_design_director_outside_non_design_system_is_flagged(self):
        out = self.eval_at(self.make_dir() / "x.md", "design-director")
        self.assertIn("design_director_write_outside", out.get("flags", []))

    def test_design_director_may_write_design_system_outside(self):
        out = self.eval_at(self.make_dir() / "DESIGN_SYSTEM.md", "design-director")
        self.assertNotIn("design_director_write_outside", out.get("flags", []))
        self.assertNotIn("design_system_write_by_other", out.get("flags", []))

    def test_design_system_outside_by_other_actor_is_flagged(self):
        out = self.eval_at(self.make_dir() / "DESIGN_SYSTEM.md", "frontend-react")
        self.assertIn("design_system_write_by_other", out.get("flags", []))

    def test_area_flags_do_not_apply_outside(self):
        d = self.make_dir()
        out = self.eval_at(d / "notes.md", "backend-node")
        self.assertNotIn("md_outside_docs", out.get("flags", []))
        out = self.eval_at(d / "docs" / "backlog" / "b.md", "backend-node")
        self.assertNotIn("backlog_write_by_other", out.get("flags", []))
        self.assertNotIn("docs_write_by_implementer", out.get("flags", []))

    def test_cwd_outside_any_repo_judges_target_by_its_repo(self):
        cwd = self.make_dir()
        inside = self.eval_at(self.repo / "services" / "api" / "x.py", "backend-node", cwd=cwd)
        self.assertTrue(inside["in_run"])
        self.assertNotOutOfScope(inside)
        denied = self.eval_at(self.repo / "services" / "web" / "x.py", "backend-node", cwd=cwd)
        self.assertOutOfScope(denied)

    def test_no_run_outside_has_no_scope_flag_but_readonly_still_flagged(self):
        (self.repo / ".claude" / "runs" / "feat-x.json").unlink()
        target = self.make_dir() / "x.py"
        self.assertNotOutOfScope(self.eval_at(target, "backend-node"))
        out = self.eval_at(target, "code-reviewer")
        self.assertIn("write_by_readonly_agent", out.get("flags", []))
        self.assertNotOutOfScope(out)


class OutsideRepoHardening(TempRepoCase):
    """Round 2 of docs/backlog/bugs/2026-11-11-audit-path-checks-outside-git-root.md"""

    def flags(self, target, actor, cwd=None):
        return self.eval_at(target, actor, cwd=cwd).get("flags", [])

    def make_nested_repo(self):
        """self.repo has no run; self.repo/sub is its own repo with a run allowing only a/**."""
        sub = self.repo / "sub"
        sub.mkdir()
        init_repo(sub)
        runs = sub / ".claude" / "runs"
        runs.mkdir(parents=True)
        (runs / "feat-y.json").write_text(json.dumps(
            {"phase": "implement", "current_task": 1, "allowed_paths": {"1": ["a/**"]}}))
        return sub

    def test_nested_repo_target_outside_its_run_scope_is_flagged(self):
        """Pins the behavior accepted today. Refactor: docs/backlog/refactor/2026-11-11-audit-nested-repo-run-lookup.md

        When that entry is resolved, this test changes with it.
        """
        sub = self.make_nested_repo()
        self.assertIn("out_of_scope_write", self.flags(sub / "evil", "backend-node"))

    def test_nested_repo_target_inside_its_run_scope_is_allowed(self):
        """Pins the behavior accepted today. Refactor: docs/backlog/refactor/2026-11-11-audit-nested-repo-run-lookup.md

        When that entry is resolved, this test changes with it.
        """
        sub = self.make_nested_repo()
        self.assertNotIn("out_of_scope_write", self.flags(sub / "a" / "x.py", "backend-node"))

    def test_nested_repo_area_flags_come_from_the_target_root(self):
        """Pins the behavior accepted today. Refactor: docs/backlog/refactor/2026-11-11-audit-nested-repo-run-lookup.md

        When that entry is resolved, this test changes with it.
        """
        sub = self.make_nested_repo()
        self.assertIn("backlog_write_by_other", self.flags(sub / "docs" / "backlog" / "x.md", "backend-node"))

    def test_path_resolution_error_fails_closed_with_actor_flags(self):
        cases = (("code-reviewer", "write_by_readonly_agent"), ("design-director", "design_director_write_outside"))
        for actor, flag in cases:
            with self.subTest(actor=actor, trigger="resolve raises"), \
                    mock.patch.object(Path, "resolve", side_effect=OSError("boom")):
                try:
                    out = self.eval_at(self.repo / "x.md", actor)
                except Exception as exc:
                    self.fail(f"evaluate_write raised {exc!r}")
                self.assertIn(flag, out.get("flags", []))
                self.assertEqual(out.get("area"), "outside")
            with self.subTest(actor=actor, trigger="NUL in path"):
                try:
                    out = audit.evaluate_write(str(self.repo) + "/a\0b.md", str(self.repo), actor, "Write", None)
                except Exception as exc:
                    self.fail(f"evaluate_write raised {exc!r}")
                self.assertIn(flag, out.get("flags", []))
                self.assertEqual(out.get("area"), "outside")

    def test_tilde_path_is_expanded_to_home_and_treated_as_outside(self):
        self.write_run()
        home = self.make_dir()
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            out = audit.evaluate_write("~/x/migrations/evil", str(self.repo), "backend-node", "Write", None)
        self.assertIn("out_of_scope_write", out.get("flags", []))
        self.assertEqual(out.get("area"), "outside")

    def test_dotdot_through_symlink_is_judged_by_lexical_form_too(self):
        self.write_run(allowed_paths={"1": ["src/**"]})
        deep = self.repo / "src" / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (self.repo / "src" / "link").symlink_to(deep, target_is_directory=True)
        target = f"{self.repo}/src/link/../../../evil"
        out = audit.evaluate_write(target, str(self.repo), "backend-node", "Write", None)
        self.assertIn("out_of_scope_write", out.get("flags", []))

    def test_absolute_approved_glob_naming_a_symlink_alias_does_not_cover_the_write(self):
        outside = self.make_dir()
        (outside / "real").mkdir()
        (outside / "alias").symlink_to(outside / "real", target_is_directory=True)
        self.write_run(approved_scope=[{"task": 1, "target": f"{outside}/alias/**", "decision": "approved"}])
        self.assertIn("out_of_scope_write", self.flags(outside / "alias" / "x.py", "backend-node"))

    def test_absolute_approved_glob_naming_the_real_dir_covers_the_write_through_alias(self):
        outside = self.make_dir()
        (outside / "real").mkdir()
        (outside / "alias").symlink_to(outside / "real", target_is_directory=True)
        real = (outside / "real").resolve()
        self.write_run(approved_scope=[{"task": 1, "target": f"{real}/**", "decision": "approved"}])
        self.assertNotIn("out_of_scope_write", self.flags(outside / "alias" / "x.py", "backend-node"))

    def test_symlink_planted_under_approved_prefix_does_not_widen_the_glob(self):
        for name, link_target in (("to_other_tmp", None), ("to_root", Path("/"))):
            with self.subTest(link=name):
                other = self.make_dir()
                approved = self.make_dir()
                (approved / "out").symlink_to(link_target or other, target_is_directory=True)
                self.write_run(approved_scope=[{"task": 1, "target": f"{approved}/out/**", "decision": "approved"}])
                self.assertIn("out_of_scope_write", self.flags(other / "x.py", "backend-node"))

    def test_tilde_approved_glob_is_expanded_literally(self):
        home = self.make_dir()
        self.write_run(approved_scope=[{"task": 1, "target": "~/ext/**", "decision": "approved"}])
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            out = audit.evaluate_write(str(home / "ext" / "a.py"), str(self.repo), "backend-node", "Write", None)
        self.assertNotIn("out_of_scope_write", out.get("flags", []))

    def test_design_system_symlink_to_other_file_is_not_a_design_system_write(self):
        target = self.make_dir() / "x.py"
        target.write_text("")
        (self.repo / "DESIGN_SYSTEM.md").symlink_to(target)
        self.assertIn("design_director_write_outside", self.flags(self.repo / "DESIGN_SYSTEM.md", "design-director"))

    def test_symlink_to_design_system_is_guarded_by_its_resolved_name(self):
        (self.repo / "DESIGN_SYSTEM.md").write_text("")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "alias.md").symlink_to(Path("..") / "DESIGN_SYSTEM.md")
        for actor in ("docs-writer", "planner"):
            with self.subTest(actor=actor):
                self.assertIn("design_system_write_by_other", self.flags(self.repo / "src" / "alias.md", actor))

    def test_design_director_writing_regular_design_system_is_clean(self):
        (self.repo / "DESIGN_SYSTEM.md").write_text("")
        fl = self.flags(self.repo / "DESIGN_SYSTEM.md", "design-director")
        self.assertNotIn("design_director_write_outside", fl)
        self.assertNotIn("design_system_write_by_other", fl)

    def test_resolution_error_with_active_run_flags_scoped_actor_but_not_main(self):
        self.write_run()
        triggers = {
            "resolve raises": lambda: mock.patch.object(Path, "resolve", side_effect=OSError("boom")),
            "NUL in path": None,
        }
        for name, patcher in triggers.items():
            for actor, expected in (("backend-node", True), ("main", False)):
                with self.subTest(trigger=name, actor=actor):
                    path = str(self.repo / "src" / "x.py") if patcher else str(self.repo) + "/a\0b.py"
                    ctx = patcher() if patcher else mock.MagicMock()
                    try:
                        with ctx:
                            out = audit.evaluate_write(path, str(self.repo), actor, "Write", None)
                    except Exception as exc:
                        self.fail(f"evaluate_write raised {exc!r}")
                    self.assertEqual("out_of_scope_write" in out.get("flags", []), expected)

    def test_nested_repo_without_run_is_judged_by_outer_run_and_recorded_with_it(self):
        """Pins the behavior accepted today. Refactor: docs/backlog/refactor/2026-11-11-audit-nested-repo-run-lookup.md

        When that entry is resolved, this test changes with it.
        """
        self.write_run(allowed_paths={"1": ["a/**"]})
        nested = self.repo / "n"
        nested.mkdir()
        init_repo(nested)
        out = self.eval_at(nested / "x.py", "backend-node")
        self.assertIn("out_of_scope_write", out.get("flags", []))
        self.assertTrue(out.get("in_run"))
        self.assertEqual(out.get("run"), "feat-x")
        self.assertEqual(out.get("task"), "1")


class SessionScratchpad(TempRepoCase):
    """Spec audit-scratch-exemption, Testing SC1-SC17 (refactor docs/backlog/refactor/2026-11-11-audit-scratch-exemption-too-broad.md).

    Outside the repo, a fixed-scope actor with an active run is in scope only inside the session scratchpad
    (`scratchpad_dir` of the payload) or an approved absolute glob. Actor `backend-node`, run ALLOWED, unless stated.
    """

    def setUp(self):
        super().setUp()
        self.write_run()
        self.sp = self.make_scratchpad()
        self.base = self.sp.parents[3]  # the temp dir holding claude-<uid>/

    def at(self, target, actor="backend-node", scratchpad="sp"):
        return self.eval_at(target, actor, scratchpad=str(self.sp) if scratchpad == "sp" else scratchpad)

    def assertFlagged(self, out, scratch="no-match"):
        self.assertIn("out_of_scope_write", out["flags"])
        self.assertEqual(out.get("scratch"), scratch)

    def test_sc1_inside_the_session_scratchpad_is_in_scope(self):
        for rel in ("n.txt", "a/b/c.py"):  # intermediate directories do not exist
            with self.subTest(rel=rel):
                out = self.at(self.sp / rel)
                self.assertNotIn("out_of_scope_write", out["flags"])
                self.assertEqual(out["area"], "outside")
                self.assertIs(out["in_scope"], True)
                self.assertEqual(out["scratch"], "match")

    def test_sc2_string_prefix_siblings_and_the_scratchpad_itself_are_flagged(self):
        for target in (Path(f"{self.sp}x") / "n.txt", Path(f"{self.sp}-other") / "n.txt", self.sp):
            with self.subTest(target=str(target)):
                self.assertFlagged(self.at(target))

    def test_sc3_scratchpad_of_another_session_is_flagged(self):
        other = self.make_scratchpad(session="s2")
        self.assertFlagged(self.at(other / "n.txt"))

    def test_sc4_other_claude_directories_are_flagged(self):
        uid = self.sp.parents[2].name
        targets = {
            "bash-edit-diff": self.base / uid / "bash-edit-diff" / "x",
            "claude-xyz": self.base / "claude-xyz" / "x",
        }
        for name, target in targets.items():
            with self.subTest(case=name):
                self.assertFlagged(self.at(target))
        with self.subTest(case="literal /tmp/claude-*"):
            if not (Path("/tmp").is_dir() and os.access("/tmp", os.W_OK)):
                self.skipTest("/tmp is not writable")
            literal = Path("/tmp") / f"claude-audit-test-{uuid.uuid4().hex}"
            literal.mkdir()
            self.addCleanup(shutil.rmtree, literal, ignore_errors=True)
            self.assertFlagged(self.at(literal / "n.txt"))

    def test_sc5_same_session_id_on_a_wrong_path_is_flagged(self):
        uid = self.sp.parents[2].name
        for rel in (f"{uid}/-wrong/s1/scratchpad/x", f"{uid}/s1/scratchpad/x"):
            with self.subTest(rel=rel):
                self.assertFlagged(self.at(self.base / rel))

    def test_sc6_without_scratchpad_there_is_no_exemption(self):
        self.assertFlagged(self.at(self.sp / "n.txt", scratchpad=None), scratch="unavailable")

    def test_sc7_invalid_scratchpad_counts_as_absent(self):
        for value in ("", "rel/scratchpad", "/", 42, ["/x"], {"a": 1}, str(self.sp) + "\0"):
            with self.subTest(value=value):
                self.assertFlagged(self.at(self.sp / "n.txt", scratchpad=value), scratch="unavailable")

    def test_sc8_symlink_inside_the_scratchpad_to_the_outside_is_flagged(self):
        (self.sp / "link").symlink_to(self.make_dir())
        self.assertFlagged(self.at(self.sp / "link" / "x.py"))

    def test_sc9_scratchpad_replaced_by_a_symlink_does_not_widen_the_exemption(self):
        d = self.make_dir()
        self.sp.rmdir()
        self.sp.symlink_to(d)
        for target in (d / "x", self.sp / "x"):
            with self.subTest(target=str(target)):
                self.assertIn("out_of_scope_write", self.at(target)["flags"])

    def test_sc10_dotdot_is_judged_resolved_and_lexical(self):
        self.assertIn("out_of_scope_write", self.at(self.sp / ".." / "fora" / "x")["flags"])
        self.assertNotIn("out_of_scope_write", self.at(self.sp / "a" / ".." / "b.txt")["flags"])

    def test_sc11_not_normalized_scratchpad_values_are_accepted(self):
        values = (str(self.sp) + "/", str(self.sp) + "/./", f"{self.sp.parent}/x/../scratchpad")
        for value in values:
            with self.subTest(value=value):
                out = self.at(self.sp / "n.txt", scratchpad=value)
                self.assertNotIn("out_of_scope_write", out["flags"])
                self.assertEqual(out["scratch"], "match")

    def test_sc12_actors_without_fixed_scope_are_not_judged(self):
        for actor in ("main", "docs-writer", "planner"):
            for scratchpad in ("sp", None):
                with self.subTest(actor=actor, scratchpad=scratchpad):
                    out = self.at(self.base / "claude-xyz" / "x", actor=actor, scratchpad=scratchpad)
                    self.assertNotIn("out_of_scope_write", out["flags"])
                    self.assertNotIn("scratch", out)

    def test_sc13_actor_flags_do_not_change_in_the_scratchpad(self):
        self.assertIn("write_by_readonly_agent", self.at(self.sp / "n.txt", actor="code-reviewer")["flags"])
        self.assertIn("design_director_write_outside", self.at(self.sp / "x.md", actor="design-director")["flags"])

    def test_sc14_without_an_active_run_there_is_no_scope_flag_or_scratch(self):
        self.remove_run()
        out = self.at(self.base / "claude-xyz" / "x")
        self.assertNotIn("out_of_scope_write", out["flags"])
        self.assertNotIn("scratch", out)
        self.assertIs(out["in_run"], False)

    def test_sc15_scratchpad_inside_the_repo_exempts_nothing(self):
        inner = self.repo / "tmp" / "claude-1" / "p" / "s1" / "scratchpad"
        inner.mkdir(parents=True)
        out = self.at(inner / "n.txt", scratchpad=str(inner))
        self.assertIn("out_of_scope_write", out["flags"])
        self.assertEqual(out["area"], "code")
        self.assertNotIn("scratch", out)

    def test_sc16_approved_absolute_glob_still_applies_with_a_scratchpad(self):
        d = self.make_dir()
        self.write_run(approved_scope=[{"task": 1, "target": f"{d}/**", "decision": "approved"}])
        for target, scratch in ((d / "sub" / "x.py", "no-match"), (self.sp / "n.txt", "match")):
            with self.subTest(target=str(target)):
                out = self.at(target)
                self.assertNotIn("out_of_scope_write", out["flags"])
                self.assertEqual(out["scratch"], scratch)

    def test_sc17_session_scratchpad_validation(self):
        sp = str(self.sp)
        cases = [
            (None, None), (Path(sp), None), ("", None), ("rel/x", None), ("/", None), ("//", None),
            ("/a/..", None), (42, None), (["/x"], None), (sp + "\0", None),
            (sp, Path(sp)), (sp + "/", Path(sp)), (sp + "/./", Path(sp)),
            (f"{self.sp.parent}/x/../scratchpad", Path(sp)),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(audit.session_scratchpad(raw), expected)


class InRepoScope(TempRepoCase):
    """Spec audit-hook-test-suite, Testing S1-S11: scope of a write inside the git root.

    Active run with allowed_paths {"1": ["services/api/**"]}, actor backend-node unless stated.
    """

    ALLOWED = {"1": ["services/api/**"]}

    def setUp(self):
        super().setUp()
        self.write_run()

    def flags(self, rel, actor="backend-node"):
        return self.evaluate(rel, actor=actor)["flags"]

    def test_s1_write_inside_allowed_paths(self):
        out = self.evaluate("services/api/x.py", actor="backend-node")
        self.assertIs(out["in_scope"], True)
        self.assertNotIn("out_of_scope_write", out["flags"])
        self.assertEqual(out["area"], "code")
        self.assertEqual(out["run"], "feat-x")
        self.assertEqual(out["task"], "1")

    def test_s2_write_outside_allowed_paths(self):
        out = self.evaluate("services/web/x.ts", actor="backend-node")
        self.assertIn("out_of_scope_write", out["flags"])
        self.assertIs(out["in_scope"], False)

    def test_s3_always_allowed_paths_are_in_scope(self):
        for rel in (
            "services/web/package-lock.json", "go.sum", "services/x/migrations/001.sql",
            "db/migrate/1.rb", "alembic/versions/a.py", "src/__snapshots__/a.snap", "a.snap",
        ):
            with self.subTest(case="S3", rel=rel):
                self.assertNotIn("out_of_scope_write", self.flags(rel))

    def test_s4_support_actors_are_scoped(self):
        for actor in ("quality-fixer", "test-writer"):
            with self.subTest(case="S4", actor=actor):
                self.assertIn("out_of_scope_write", self.flags("services/web/x.ts", actor))

    def test_s5_unscoped_actors_have_no_scope_verdict(self):
        for actor in ("main", "docs-writer", "planner"):
            with self.subTest(case="S5", actor=actor):
                out = self.evaluate("services/web/x.ts", actor=actor)
                self.assertNotIn("out_of_scope_write", out["flags"])
                self.assertNotIn("in_scope", out)

    def test_s6_no_active_run_means_no_scope_flag(self):
        with self.subTest(case="S6", runs_dir="missing"):
            shutil.rmtree(self.repo / ".claude" / "runs")
            out = self.evaluate("services/web/x.ts", actor="backend-node")
            self.assertIs(out["in_run"], False)
            self.assertNotIn("out_of_scope_write", out["flags"])
        with self.subTest(case="S6", runs_dir="only done"):
            (self.repo / ".claude" / "runs").mkdir()
            self.write_run(phase="done")
            out = self.evaluate("services/web/x.ts", actor="backend-node")
            self.assertIs(out["in_run"], False)
            self.assertNotIn("out_of_scope_write", out["flags"])

    def test_s7_most_recent_run_wins(self):
        runs = self.repo / ".claude" / "runs"
        old, new = runs / "feat-old.json", runs / "feat-new.json"
        old.write_text(json.dumps({"phase": "implement", "current_task": 1, "allowed_paths": {"1": ["old/**"]}}))
        new.write_text(json.dumps({"phase": "implement", "current_task": 1, "allowed_paths": {"1": ["new/**"]}}))
        (runs / "feat-x.json").unlink()
        os.utime(old, (1_000_000, 1_000_000))
        os.utime(new, (2_000_000, 2_000_000))
        out = self.evaluate("new/a.py", actor="backend-node")
        self.assertEqual(out["run"], "feat-new")
        self.assertIs(out["in_scope"], True)
        self.assertIn("out_of_scope_write", self.flags("old/a.py"))

    def test_s8_invalid_run_json_is_ignored(self):
        bad = self.repo / ".claude" / "runs" / "broken.json"
        bad.write_text("{not json")
        os.utime(bad, (4_000_000_000, 4_000_000_000))  # newer than the valid run
        out = self.evaluate("services/api/x.py", actor="backend-node")
        self.assertEqual(out["run"], "feat-x")
        self.assertIs(out["in_scope"], True)

    def test_s9_approved_scope_without_decision_counts_as_approved(self):
        self.write_run(approved_scope=[{"task": 1, "target": "services/shared/**"}])
        self.assertNotIn("out_of_scope_write", self.flags("services/shared/u.py"))

    def test_s10_matches(self):
        m = audit.matches
        with self.subTest(case="S10", what="pattern without glob"):
            self.assertTrue(m("services/api/x.py", ["services/api"]))
        with self.subTest(case="S10", what="backticks"):
            self.assertTrue(m("services/api/x.py", ["`services/api/**`"]))
        with self.subTest(case="S10", what="empty patterns"):
            self.assertFalse(m("services/api/x.py", ["", "  ", "``"]))
        with self.subTest(case="S10", what="sibling prefix"):
            self.assertFalse(m("services/apix/a", ["services/api/**"]))

    def test_s11_matches_falls_back_to_prefix_when_full_match_raises(self):
        with mock.patch.object(audit.PurePosixPath, "full_match", side_effect=ValueError("boom")):
            self.assertTrue(audit.matches("services/api/x.py", ["services/api/**"]))
            self.assertFalse(audit.matches("services/apix/a", ["services/api/**"]))


class GitRootUnknownCase(TempRepoCase):
    """Review fix (security low): a git timeout or failure is not "not a repository"; it is uncertainty."""

    def unknown(self, why="TimeoutExpired"):
        return mock.patch.object(audit, "git_toplevel", side_effect=audit.GitRootUnknown(why))

    def test_not_a_repository_is_none_not_unknown(self):
        outside = self.make_dir()
        self.assertIsNone(audit.git_toplevel(outside))
        self.assertIsNone(audit.git_root(outside))
        self.assertEqual(audit.git_toplevel(self.repo), self.repo.resolve())

    def test_a_timeout_or_failure_is_unknown(self):
        for effect in (subprocess.TimeoutExpired("git", 2), OSError("no git"), PermissionError("x")):
            with self.subTest(effect=type(effect).__name__):
                with mock.patch.object(audit.subprocess, "run", side_effect=effect):
                    with self.assertRaises(audit.GitRootUnknown):
                        audit.git_toplevel(self.repo)
                    self.assertIsNone(audit.git_root(self.repo))  # the tagging reading stays "no run"
        for rc, err in ((128, "fatal: unable to read config file"), (1, ""), (0, "")):
            with self.subTest(rc=rc):
                done = subprocess.CompletedProcess(["git"], rc, stdout="", stderr=err)
                with mock.patch.object(audit.subprocess, "run", return_value=done):
                    with self.assertRaises(audit.GitRootUnknown):
                        audit.git_toplevel(self.repo)

    def test_the_not_a_repository_condition_is_recognized_by_its_text(self):
        done = subprocess.CompletedProcess(["git"], 128, stdout="", stderr="fatal: not a git repository (or any parent)")
        with mock.patch.object(audit.subprocess, "run", return_value=done):
            self.assertIsNone(audit.git_toplevel(self.repo))

    def test_a_scoped_actor_in_a_run_fails_closed(self):
        self.write_run()
        for actor in ("backend-python", "quality-fixer", "test-writer"):
            with self.subTest(actor=actor):
                with self.unknown():
                    out = self.evaluate("services/api/src/main.py", actor=actor)
                self.assertIn("out_of_scope_write", out["flags"])
                self.assertIs(out["in_run"], True)
                self.assertEqual(out["uncertainty"], ["git_root_unknown"])

    def test_an_unscoped_actor_is_not_blocked_but_the_uncertainty_is_recorded(self):
        for actor in ("main", "code-reviewer"):
            with self.subTest(actor=actor):
                with self.unknown():
                    out = self.evaluate("services/api/src/main.py", actor=actor)
                self.assertNotIn("out_of_scope_write", out["flags"])
                self.assertEqual(out["uncertainty"], ["git_root_unknown"])

    def test_a_known_root_has_no_uncertainty(self):
        self.write_run()
        self.assertNotIn("uncertainty", self.evaluate("services/api/src/main.py", actor="backend-python"))
        outside = self.make_dir()
        out = audit.evaluate_write(str(outside / "x.py"), str(outside), "backend-python", "Write", None)
        self.assertNotIn("uncertainty", out)

    def test_the_hook_records_the_reason_and_blocks_the_scoped_write(self):
        from ._support import call_main, payload
        self.write_run()
        target = str(self.repo / "services" / "web" / "x.py")
        with self.unknown():
            res = call_main(payload("PostToolUse", "Write", actor="backend-python", cwd=self.repo,
                                    tool_input={"file_path": target}))
        [record] = res.records
        self.assertEqual(record["uncertainty"], ["git_root_unknown"])
        self.assertIn("parse_uncertain", record["flags"])
        self.assertIn("out_of_scope_write", record["flags"])  # the same flag, and so the same decision, as a known root
        self.assertIs(record["in_run"], True)


class RunEntryCap(TempRepoCase):
    """Review fix: every directory entry counts against MAX_RUN_ENTRIES, not only the `*.json` files."""

    def test_many_stray_files_stop_the_listing(self):
        runs = self.repo / ".claude" / "runs"
        for n in range(audit.MAX_RUN_ENTRIES + 20):
            (runs / f"stray-{n:04d}.txt").write_text("x")
        self.write_run()  # created after the strays: scandir order is arbitrary, the cap bounds the work
        seen = []
        real = audit.os.scandir

        def counting(path):
            it = real(path)

            class Spy:
                def __enter__(self_inner):
                    self_inner.it = it.__enter__()
                    return self_inner

                def __exit__(self_inner, *exc):
                    return it.__exit__(*exc)

                def __iter__(self_inner):
                    for entry in self_inner.it:
                        seen.append(entry.name)
                        yield entry
            return Spy()
        with mock.patch.object(audit.os, "scandir", counting):
            audit.active_run(self.repo)
        self.assertLessEqual(len(seen), audit.MAX_RUN_ENTRIES + 1)

    def test_a_run_among_few_stray_entries_is_still_found(self):
        runs = self.repo / ".claude" / "runs"
        (runs / "sub").mkdir()
        (runs / "notes.txt").write_text("x")
        self.write_run()
        self.assertEqual(audit.active_run(self.repo)["_slug"], "feat-x")


def load_tests(loader, tests, pattern):
    """Independent cases: run them in forked workers (see `ForkedSuite`)."""
    return ForkedSuite(tests)


if __name__ == "__main__":
    unittest.main()
