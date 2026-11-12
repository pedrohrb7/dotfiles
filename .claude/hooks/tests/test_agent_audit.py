"""Regression tests for agent-audit.py classify_command: heredoc bodies are data, not commands.

Bug: docs/backlog/bugs/2026-11-11-audit-heredoc-docker-lifecycle.md
All docker/git text below is string literals only; nothing is executed.
"""
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from ._loader import load_hook

audit = load_hook("agent-audit.py", "agent_audit")
classify = audit.classify_command

LIFECYCLE = "docker_lifecycle"

# Lines that must never be flagged or categorised when they sit inside a heredoc body.
BODY_LINES = [
    "git push origin main",
    "git commit -m x",
    "curl https://example.com",
    "pytest",
    "docker compose up",
]


class HeredocBodyIsData(unittest.TestCase):
    def assertInert(self, command):
        categories, flags = classify(command)
        self.assertEqual(flags, [], command)
        self.assertEqual(categories, ["other"], command)

    def test_exact_bug_payload_is_not_docker_lifecycle(self):
        cmd = "cat > /tmp/notes.md <<'EOF'\nRestart with:\ndocker compose restart api\nEOF"
        categories, flags = classify(cmd)
        self.assertEqual(categories, ["other"])
        self.assertNotIn(LIFECYCLE, flags)

    def test_body_never_classified_for_each_heredoc_syntax(self):
        syntaxes = {
            "bare": ("<<EOF", "EOF"),
            "dash_tab_terminator": ("<<-EOF", "\tEOF"),
            "space": ("<< EOF", "EOF"),
            "double_quoted": ('<<"EOF"', "EOF"),
            "backslash": ("<<\\EOF", "EOF"),
            "single_quoted": ("<<'EOF'", "EOF"),
        }
        for name, (opener, terminator) in syntaxes.items():
            for line in BODY_LINES:
                with self.subTest(syntax=name, body=line):
                    body = ("\t" + line) if opener == "<<-EOF" else line
                    self.assertInert(f"cat {opener}\n{body}\n{terminator}")

    def test_command_after_terminator_is_still_classified(self):
        for name, opener, terminator in [
            ("bare", "<<EOF", "EOF"),
            ("dash", "<<-EOF", "\tEOF"),
            ("quoted", "<<'EOF'", "EOF"),
        ]:
            with self.subTest(syntax=name):
                cmd = f"cat {opener}\ngit push origin main\n{terminator}\ndocker compose up"
                categories, flags = classify(cmd)
                self.assertEqual(flags, [LIFECYCLE])
                self.assertNotIn("git-push", categories)

    def test_two_heredocs_on_one_line(self):
        cmd = "cat <<A <<B\ndocker compose up\nA\ngit push origin main\nB"
        self.assertInert(cmd)

    def test_two_heredocs_then_command_after_both_terminators(self):
        cmd = "cat <<A <<B\ndocker compose up\nA\ngit push\nB\ndocker compose down"
        categories, flags = classify(cmd)
        self.assertEqual(flags, [LIFECYCLE])
        self.assertNotIn("git-push", categories)

    def test_git_commit_with_heredoc_message_only_flags_commit(self):
        cmd = (
            "git commit -m \"$(cat <<'EOF'\n"
            "Fix the thing\n\ndocker compose up\nEOF\n)\""
        )
        categories, flags = classify(cmd)
        self.assertEqual(flags, ["git_commit"])
        self.assertNotIn("docker-lifecycle", categories)

    def test_unterminated_heredoc_does_not_raise_or_flag_body(self):
        cmd = "cat <<EOF\ndocker compose up\ngit push origin main"
        self.assertInert(cmd)

    def test_terminator_with_trailing_space_does_not_terminate(self):
        cmd = "cat <<EOF\nx\nEOF \ndocker compose up\nEOF"
        self.assertInert(cmd)


class HeredocOpenerStillClassified(unittest.TestCase):
    def test_opener_line_itself(self):
        _, flags = classify("docker compose up <<EOF\nx\nEOF")
        self.assertIn(LIFECYCLE, flags)

    def test_opener_tail_after_operator(self):
        _, flags = classify("cat <<EOF && docker compose restart api\nx\nEOF")
        self.assertIn(LIFECYCLE, flags)


class NotAHeredoc(unittest.TestCase):
    def test_lifecycle_after_non_heredoc_lines_is_flagged(self):
        cases = {
            "here_string": 'cat <<< "x"\ndocker compose up',
            "quoted_shift_text": 'echo "a << b"\ndocker compose up',
            "arithmetic_shift": "echo $((1<<2))\ndocker compose up",
            "comment": "# <<EOF\ndocker compose up",
        }
        for name, cmd in cases.items():
            with self.subTest(case=name):
                _, flags = classify(cmd)
                self.assertIn(LIFECYCLE, flags)


class DataSinkHeredocsAreStripped(unittest.TestCase):
    """Fail-closed allowlist: only provable data sinks have their body stripped."""

    def assertInert(self, command):
        categories, flags = classify(command)
        self.assertEqual(flags, [], command)
        self.assertEqual(categories, ["other"], command)

    def test_cat_and_tee_variants_are_stripped(self):
        cases = {
            "tee_file": "tee /tmp/notes.md <<EOF\ndocker compose up\nEOF",
            "tee_append": "tee -a /tmp/notes.md <<EOF\ndocker compose up\nEOF",
            "sudo_tee": "sudo tee /etc/x <<EOF\ndocker compose up\nEOF",
            "cat_redirect": "cat > /tmp/f <<EOF\ndocker compose up\nEOF",
            "cat_append": "cat >> /tmp/f <<EOF\ndocker compose up\nEOF",
            "env_prefix": "FOO=1 cat <<EOF\ndocker compose up\nEOF",
            "rtk_prefix": "rtk cat <<EOF\ndocker compose up\nEOF",
            "line_continuation_joins_arg": "cat <<EOF\\\nfoo\ndocker compose up\nEOF",
        }
        for name, cmd in cases.items():
            with self.subTest(case=name):
                self.assertInert(cmd)

    def test_git_commit_stdin_message_only_flags_commit(self):
        cases = {
            "short_F": "git commit -F - <<EOF\nmsg\ndocker compose up\nEOF",
            "file_eq": "git commit --file=- <<EOF\nmsg\ndocker compose up\nEOF",
            "file_space": "git commit --file - <<EOF\nmsg\ndocker compose up\nEOF",
        }
        for name, cmd in cases.items():
            with self.subTest(case=name):
                categories, flags = classify(cmd)
                self.assertEqual(flags, ["git_commit"])
                self.assertNotIn("docker-lifecycle", categories)

    def test_gh_body_file_stdin_is_stripped(self):
        cases = {
            "body_file": "gh pr create --body-file - <<EOF\ndocker compose up\nEOF",
            "short_F": "gh pr create -F - <<EOF\ndocker compose up\nEOF",
            "substitution": "gh pr create --body \"$(cat <<'EOF'\ndocker compose up\nEOF\n)\"",
        }
        for name, cmd in cases.items():
            with self.subTest(case=name):
                self.assertInert(cmd)

    def test_cat_substitution_under_git_is_stripped(self):
        cmd = "git commit -m \"$(cat <<'EOF'\nmsg\ngit push origin main\nEOF\n)\""
        categories, flags = classify(cmd)
        self.assertEqual(flags, ["git_commit"])


class BodyKeptUnlessDataSink(unittest.TestCase):
    def test_non_sink_heredoc_body_is_classified(self):
        cases = {
            "bash_quoted": "bash <<'EOF'\ndocker compose up\nEOF",
            "sh_dash_s": "sh -s <<EOF\ndocker compose up\nEOF",
            "ssh_host": "ssh host <<EOF\ndocker compose up\nEOF",
            "sudo_bash": "sudo bash <<EOF\ndocker compose up\nEOF",
            "zsh": "zsh <<EOF\ndocker compose up\nEOF",
            "dash": "dash <<EOF\ndocker compose up\nEOF",
            "ksh": "ksh <<EOF\ndocker compose up\nEOF",
            "env_prefix": "FOO=1 bash <<EOF\ndocker compose up\nEOF",
            "python3": "python3 <<EOF\ndocker compose up\nEOF",
            "env_bash": "env bash <<EOF\ndocker compose up\nEOF",
            "timeout_bash": "timeout 5 bash <<EOF\ndocker compose up\nEOF",
            "nohup_bash": "nohup bash <<EOF\ndocker compose up\nEOF",
            "cat_pipe_bash": "cat <<EOF | bash\ndocker compose up\nEOF",
            "cat_trailing_pipe": "cat <<EOF |\ndocker compose up\nEOF\nbash",
            "tee_process_subst": "tee >(bash) <<EOF\ndocker compose up\nEOF",
            "bash_proc_subst": "bash <(cat <<EOF\ndocker compose up\nEOF\n)",
            "eval_substitution": "eval \"$(cat <<EOF\ndocker compose up\nEOF\n)\"",
            "source_stdin": "source /dev/stdin <<EOF\ndocker compose up\nEOF",
            "dot_stdin": ". /dev/stdin <<EOF\ndocker compose up\nEOF",
            "xargs_sh": "xargs -I{} sh -c {} <<EOF\ndocker compose up\nEOF",
            "brace_group": "{ bash; } <<EOF\ndocker compose up\nEOF",
            "while_read": "while read l; do $l; done <<EOF\ndocker compose up\nEOF",
            "kubectl_exec": "kubectl exec -i p -- sh <<EOF\ndocker compose up\nEOF",
            "redirect_before_command": "<<EOF bash\ndocker compose up\nEOF",
            "echo_substitution": "echo \"$(cat <<EOF\ndocker compose up\nEOF\n)\"",
            "cat_substitution_cmd_subst_tail": "cat <<EOF $(bash)\ndocker compose up\nEOF",
        }
        for name, cmd in cases.items():
            with self.subTest(case=name):
                _, flags = classify(cmd)
                self.assertIn(LIFECYCLE, flags)

    def test_git_push_body_kept_for_ssh(self):
        _, flags = classify("ssh host <<EOF\ngit push origin main\nEOF")
        self.assertIn("git_push", flags)


class FailSafeStripsNothing(unittest.TestCase):
    def test_risky_constructs_disable_stripping(self):
        cases = {
            "param_expansion": "echo ${x:-<<EOF}\ndocker compose restart api",
            "ansi_c_quote": "echo $'a\\' <<EOF '\ndocker compose restart api",
            "legacy_arith": "echo $[1<<EOF]\ndocker compose restart api",
            "crlf": "cat <<EOF\r\nhi\r\nEOF\r\ndocker compose up",
            "crlf_body": "cat <<EOF\r\ndocker compose up\r\nEOF\r\n",
            "brace_in_body": "cat <<'EOF'\n${HOME}\ndocker compose up\nEOF",
            "backtick_in_body": "cat <<'EOF'\n`x`\ndocker compose up\nEOF",
        }
        for name, cmd in cases.items():
            with self.subTest(case=name):
                _, flags = classify(cmd)
                self.assertIn(LIFECYCLE, flags)


class TerminatorSemantics(unittest.TestCase):
    def test_backslash_newline_after_delimiter_is_continuation(self):
        cmd = "cat <<EOF\\\n> /tmp/f\nhi\nEOF\ndocker compose up"
        _, flags = classify(cmd)
        self.assertIn(LIFECYCLE, flags)


class ScannerFallback(unittest.TestCase):
    def test_scanner_exception_classifies_original_command(self):
        cmd = "cat <<EOF\ndocker compose up\nEOF"
        with mock.patch.object(audit, "_scan_heredocs", side_effect=RuntimeError("boom")):
            _, flags = classify(cmd)
        self.assertIn(LIFECYCLE, flags)


def _sub(prefix, suffix=""):
    """`prefix` + a quoted $(cat <<'EOF' ...) substitution whose body is a lifecycle line + `suffix`."""
    return prefix + "\"$(cat <<'EOF'\ndocker compose up\nEOF\n)\"" + suffix


class SubstitutionOnlyDataAsMessageValue(unittest.TestCase):
    def test_substitution_elsewhere_under_git_or_gh_keeps_body(self):
        cases = {
            "rebase_x": _sub("git rebase -x ", " HEAD~1"),
            "submodule_foreach": _sub("git submodule foreach "),
            "bisect_run": _sub("git bisect run sh -c "),
            "alias_config": "git -c alias.x=\"!$(cat <<'EOF'\ndocker compose up\nEOF\n)\" x",
            "alias_arg": _sub("git -c 'alias.x=!sh -c \"$1\"' x "),
            "gh_alias_shell": _sub("gh alias set --shell x "),
        }
        for name, cmd in cases.items():
            with self.subTest(case=name):
                _, flags = classify(cmd)
                self.assertIn(LIFECYCLE, flags)

    def test_message_and_body_values_are_stripped(self):
        git_cases = {
            "commit_m": _sub("git commit -m "),
            "commit_message_eq": "git commit --message=\"$(cat <<'EOF'\ndocker compose up\nEOF\n)\"",
        }
        for name, cmd in git_cases.items():
            with self.subTest(case=name):
                categories, flags = classify(cmd)
                self.assertEqual(flags, ["git_commit"])
        gh_cases = {
            "pr_create_title_body": _sub("gh pr create --title t --body "),
            "issue_comment_b": _sub("gh issue comment 1 -b "),
        }
        for name, cmd in gh_cases.items():
            with self.subTest(case=name):
                self.assertEqual(classify(cmd), (["other"], []))


class StdinFileSinkLimits(unittest.TestCase):
    def test_git_commit_stdin_with_alias_or_core_option_keeps_body(self):
        cases = {
            "alias": "git -c alias.x='!sh' commit -F - <<EOF\ndocker compose up\nEOF",
            "core": "git -c core.pager=sh commit -F - <<EOF\ndocker compose up\nEOF",
        }
        for name, cmd in cases.items():
            with self.subTest(case=name):
                _, flags = classify(cmd)
                self.assertIn(LIFECYCLE, flags)

    def test_gh_stdin_sink_only_for_message_subcommands(self):
        kept = {
            "api": "gh api repos/x -F - <<EOF\ndocker compose up\nEOF",
            "extension": "gh someext -F - <<EOF\ndocker compose up\nEOF",
            "api_body_file": "gh api repos/x --body-file - <<EOF\ndocker compose up\nEOF",
        }
        for name, cmd in kept.items():
            with self.subTest(case=name):
                _, flags = classify(cmd)
                self.assertIn(LIFECYCLE, flags)
        stripped = {
            "pr_create": "gh pr create --body-file - <<EOF\ndocker compose up\nEOF",
            "pr_edit": "gh pr edit 1 -F - <<EOF\ndocker compose up\nEOF",
            "issue_create": "gh issue create -F - <<EOF\ndocker compose up\nEOF",
            "issue_comment": "gh issue comment 1 --body-file - <<EOF\ndocker compose up\nEOF",
            "release_create": "gh release create v1 -F - <<EOF\ndocker compose up\nEOF",
            "pr_review": "gh pr review 1 --body-file - <<EOF\ndocker compose up\nEOF",
        }
        for name, cmd in stripped.items():
            with self.subTest(case=name):
                self.assertEqual(classify(cmd), (["other"], []))


class QuotesAndTopLevel(unittest.TestCase):
    def test_newline_inside_quotes_on_opener_line_fails_closed(self):
        cmd = "cat <<EOF \"\n\"; docker compose up\nEOF\n"
        _, flags = classify(cmd)
        self.assertIn(LIFECYCLE, flags)

    def test_cat_in_group_piped_to_shell_keeps_body(self):
        cases = {
            "subshell": "(cat <<EOF\ngit push origin main\nEOF\n) | sh",
            "brace_group": "{ cat <<EOF\ngit push origin main\nEOF\n} | bash",
        }
        for name, cmd in cases.items():
            with self.subTest(case=name):
                _, flags = classify(cmd)
                self.assertIn("git_push", flags)


class FailSafeMarkersAnywhere(unittest.TestCase):
    def test_markers_disable_stripping(self):
        cases = {
            "exec_fd_process_subst": "exec 3> >(bash)\ncat <<EOF >&3\ndocker compose up\nEOF",
            "exec_stdout_process_subst": "exec > >(sh)\ncat <<EOF\ndocker compose up\nEOF",
            "mkfifo": "mkfifo p; bash < p & cat <<EOF > p\ndocker compose up\nEOF",
            "coproc": "coproc bash\ncat <<EOF\ndocker compose up\nEOF",
            "cat_function": "cat() { bash; }; cat <<EOF\ndocker compose up\nEOF",
            "tee_function_keyword": "function tee { sh; }; tee <<EOF\ndocker compose up\nEOF",
            "fd_redirect_on_opener": "cat <<EOF >&3\ndocker compose up\nEOF",
        }
        for name, cmd in cases.items():
            with self.subTest(case=name):
                _, flags = classify(cmd)
                self.assertIn(LIFECYCLE, flags)


class TempRepoCase(unittest.TestCase):
    """Temp git repo with an active /implement run state, and evaluate_write helpers."""

    ALLOWED = {"1": ["services/api/**"], "2": ["services/web/**"]}

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / ".claude" / "runs").mkdir(parents=True)

    def write_run(self, **extra):
        state = {"phase": "implement", "current_task": 1, "allowed_paths": self.ALLOWED}
        state.update(extra)
        (self.repo / ".claude" / "runs" / "feat-x.json").write_text(json.dumps(state))

    def make_dir(self, prefix="audit-", git=False):
        d = Path(tempfile.mkdtemp(prefix=prefix))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        if git:
            subprocess.run(["git", "init", "-q", str(d)], check=True)
        return d

    def eval_at(self, target, actor, cwd=None):
        return audit.evaluate_write(str(target), str(cwd or self.repo), actor, "Write", None)

    def evaluate(self, rel, actor="frontend-react"):
        return audit.evaluate_write(str(self.repo / rel), str(self.repo), actor, "Write", None)


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

    def test_scratchpad_under_tmp_claude_dir_is_allowed(self):
        d = Path(tempfile.mkdtemp(prefix="claude-", dir=tempfile.gettempdir()))
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        self.assertNotOutOfScope(self.eval_at(d / "scratch" / "n.txt", "backend-node"))

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
        subprocess.run(["git", "init", "-q", str(sub)], check=True)
        runs = sub / ".claude" / "runs"
        runs.mkdir(parents=True)
        (runs / "feat-y.json").write_text(json.dumps(
            {"phase": "implement", "current_task": 1, "allowed_paths": {"1": ["a/**"]}}))
        return sub

    def test_nested_repo_target_outside_its_run_scope_is_flagged(self):
        sub = self.make_nested_repo()
        self.assertIn("out_of_scope_write", self.flags(sub / "evil", "backend-node"))

    def test_nested_repo_target_inside_its_run_scope_is_allowed(self):
        sub = self.make_nested_repo()
        self.assertNotIn("out_of_scope_write", self.flags(sub / "a" / "x.py", "backend-node"))

    def test_nested_repo_area_flags_come_from_the_target_root(self):
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
        self.write_run(allowed_paths={"1": ["a/**"]})
        nested = self.repo / "n"
        nested.mkdir()
        subprocess.run(["git", "init", "-q", str(nested)], check=True)
        out = self.eval_at(nested / "x.py", "backend-node")
        self.assertIn("out_of_scope_write", out.get("flags", []))
        self.assertTrue(out.get("in_run"))
        self.assertEqual(out.get("run"), "feat-x")
        self.assertEqual(out.get("task"), "1")

    def test_literal_tmp_claude_dir_is_scratch_even_if_tempdir_differs(self):
        if not Path("/tmp").is_dir():
            self.skipTest("no /tmp")
        self.write_run()
        scratch = Path("/tmp") / f"claude-audit-test-{uuid.uuid4().hex}"
        scratch.mkdir()
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        other = self.make_dir()
        with mock.patch.object(tempfile, "tempdir", str(other)):
            self.assertNotIn("out_of_scope_write", self.flags(scratch / "n.txt", "backend-node"))


if __name__ == "__main__":
    unittest.main()
