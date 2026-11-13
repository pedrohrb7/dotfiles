"""Regression tests for agent-audit.py classify_command: heredoc bodies are data, not commands.

Bug: docs/backlog/bugs/2026-11-11-audit-heredoc-docker-lifecycle.md
All docker/git text below is string literals only; nothing is executed.
"""
import unittest
from unittest import mock

from ._support import audit

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


if __name__ == "__main__":
    unittest.main()
