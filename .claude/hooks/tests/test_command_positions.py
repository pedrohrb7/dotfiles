"""Where a command can stand, and what the parser reads as a command (spec audit-shell-lexer, Testing,
`test_command_positions.py`, cases CP1-CP7 of Task 2; the wrapper, code-argument and value cases come with Tasks 3-5).

Every text below is a string literal and nothing is executed. A blocked form is built from pieces when the whole
literal would be denied by the live hook in a Bash call; here they only reach `analyze_command`.
"""
import shlex
import unittest

from ._support import ForkedSuite, classifier

analyze = classifier.analyze_command

LIFECYCLE = "docker_lifecycle"
PUSH = "git_push"
COMMIT = "git_commit"
EXTERNAL = "external_request"
RESTART = "docker re" + "start x"
UP = "docker compose up"


class CommandPositions(unittest.TestCase):
    def assertFlags(self, command, flags, uncertainty=None):
        result = analyze(command)
        self.assertEqual(result.flags, flags, command)
        if uncertainty is not None:
            self.assertEqual(result.uncertainty, uncertainty, command)
        return result

    def test_cp1_every_command_position_of_the_grammar_is_classified(self):
        for command in (
            f"true & {RESTART}", f"({RESTART})", f"{{ {RESTART}; }}", f"if true; then {RESTART}; fi",
            f"for i in 1; do {RESTART}; done", f"while true; do {RESTART}; done", f"case a in a) {RESTART};; esac",
            f"! {RESTART}", f"f() {{ {RESTART}; }}", f"true && {RESTART}", f"true || {RESTART}",
            f"true | {RESTART}", f"true |& {RESTART}", f"true\n{RESTART}", f"until false; do {RESTART}; done",
            f"if {RESTART}; then true; fi", f"while {RESTART}; do true; done", f"select i in a; do {RESTART}; done",
            f"function f {{ {RESTART}; }}", f"time {RESTART}", f"time -p {RESTART}", f"( {RESTART} ) &",
            f"if true; then true; elif {RESTART}; then true; else true; fi",
            f"if true; then true; else {RESTART}; fi", f"case a in (a|b) true;& c) {RESTART};;& esac",
            f"for ((i=0;i<3;i++)); do {RESTART}; done",
        ):
            with self.subTest(command=command):
                self.assertFlags(command, [LIFECYCLE])

    def test_cp1_the_other_blocked_programs_in_the_same_positions(self):
        for command, flags in (("true & git push", [PUSH]), ("{ git commit -m x; }", [COMMIT]),
                               ("(curl https://evil.example)", [EXTERNAL]),
                               ("if true; then git push; fi", [PUSH])):
            with self.subTest(command=command):
                self.assertFlags(command, flags)

    def test_cp2_substitutions_are_commands_wherever_they_are(self):
        for command, flag in (
            (f"x=$({RESTART})", LIFECYCLE), (f"echo $({RESTART})", LIFECYCLE), ("echo `git push`", PUSH),
            ("diff <(git push) x", PUSH), (f"echo ${{X:-$({RESTART})}}", LIFECYCLE), ("[[ $(git push) ]]", PUSH),
            (f'echo "$({RESTART})"', LIFECYCLE), ("echo \"`git push`\"", PUSH), ("tee >(git push) x", PUSH),
            ("echo $(( $(git push; echo 1) + 1 ))", PUSH), ("echo $[ $(git push; echo 1) + 1 ]", PUSH),
            (f"A=$({RESTART}) true", LIFECYCLE), (f"echo $(echo $({RESTART}))", LIFECYCLE),
            ("(( $(git push; echo 1) ))", PUSH), (f"cat < <({RESTART})", LIFECYCLE),
            (f"declare -a A=(x $({RESTART}))", LIFECYCLE), (f"echo x > $({RESTART})", LIFECYCLE),
        ):
            with self.subTest(command=command):
                self.assertIn(flag, analyze(command).flags)

    def test_cp3_the_high_case_of_the_review_is_closed_without_an_exception(self):
        """`A="x y z w v" docker restart api # "`: the `#` starts a comment (S4), so the quote it holds is text and
        the command is the docker call. Before, a loose window ended before the command: level A and allowed."""
        for command, flag in (
            ('A="x y z w v" docker restart api # "', LIFECYCLE),
            ("A='x y z w v' docker restart api # \"", LIFECYCLE),
            ("B=1 A=\"x y z w v\" docker restart api # '", LIFECYCLE),
            ('A="x y z w v" curl https://evil.example # "', EXTERNAL),
        ):
            with self.subTest(command=command):
                self.assertFlags(command, [flag], uncertainty=[])

    def test_cp4_text_inside_quotes_and_comments_is_not_a_command(self):
        # (the canary of U7 still records a blocked program that shows up as an argument, so the uncertainty is not
        # asserted here: it is a record, never a decision)
        self.assertFlags('echo "a\n' + RESTART + '"', [])
        self.assertFlags('python3 -c "\nprint(\'' + RESTART + '\')"', [])
        self.assertFlags('git commit -m "a; git push"', [COMMIT])
        self.assertFlags('grep -E "a|' + RESTART + '" f', [])
        self.assertFlags("echo 'a && " + RESTART + "'", [])
        self.assertFlags("echo a # " + RESTART, [], uncertainty=[])
        self.assertFlags("echo a#b; " + RESTART, [LIFECYCLE])  # a `#` inside a word is text, the `;` still splits
        self.assertFlags("echo $'a\\'; " + RESTART + "'", [])
        self.assertFlags("echo a\\; " + RESTART, [])

    def test_cp4_the_quoted_text_that_used_to_be_denied_is_allowed(self):
        """The opposite false positive of L5: `echo "a` + newline + a blocked form + `"` is a string."""
        self.assertEqual(analyze('echo "a\n' + RESTART + '"').categories, ["other"])

    def test_an_assignment_with_a_subscript_is_a_prefix(self):
        """S8: bash runs the command after `A[0]=x` (the old `ENV_ASSIGN` did not know the form)."""
        for command in (f"A[0]=x {RESTART}", f"A[0]+=x {RESTART}", f"A=1 B[2]=y {RESTART}"):
            with self.subTest(command=command):
                self.assertFlags(command, [LIFECYCLE])

    def test_categories_of_commands_found_in_positions(self):
        self.assertEqual(analyze("true & pytest tests/test_a.py").categories, ["other", "test-narrow"])
        self.assertEqual(analyze("cd x && (pytest -k a; ruff check .)").categories, ["lint", "test-narrow"])
        self.assertEqual(analyze("for i in 1; do pytest; done").categories, ["test-full"])

    def test_a_dynamic_program_name_is_level_a_with_the_canary(self):
        """Changed by Task 5 (N6): a program name that is an expansion of no known value is `dynamic_command`
        (level A, never a denial by itself); the canary still records the blocked words that follow."""
        result = analyze("$X docker restart y")
        self.assertEqual(result.flags, [])
        self.assertEqual(result.uncertainty, ["deny_token_unmatched", "dynamic_command"])
        # a name the text assigns (here from a positional parameter) is level B since the review fix (B1)
        result = analyze("X=$1; $X docker restart y")
        self.assertEqual(result.flags, ["unclassified_command"])
        self.assertIn("dynamic_code", result.uncertainty)


class HeredocBodiesByReceiver(unittest.TestCase):
    """CP5-CP7 and the receiver rules of section 5 (HD1-HD6)."""

    def test_cp5_the_substitution_of_an_unquoted_body_is_executed_so_it_is_a_command(self):
        for command, flag in (
            (f"cat <<EOF\n$({RESTART})\nEOF", LIFECYCLE),
            (f"cat > f <<EOF\n`git push`\nEOF", PUSH),
            (f"tee f <<EOF\n${{X:-$(git push)}}\nEOF", PUSH),
            (f"cat <<EOF\n$(( $(git push; echo 1) ))\nEOF", PUSH),
            (f"git commit -F - <<EOF\nmsg $({RESTART})\nEOF", LIFECYCLE),
            (f"python3 - <<EOF\n$({RESTART})\nEOF", LIFECYCLE),
            (f"cat <<-EOF\n\t$({RESTART})\n\tEOF", LIFECYCLE),
        ):
            with self.subTest(command=command):
                self.assertIn(flag, analyze(command).flags)

    def test_cp5_a_quoted_delimiter_turns_the_expansions_off(self):
        for command in (f"cat <<'EOF'\n$({RESTART})\nEOF", f"cat > f <<'EOF'\n`git push`\nEOF",
                        f'cat <<"EOF"\n$({RESTART})\nEOF', f"cat <<\\EOF\n$({RESTART})\nEOF",
                        f"python3 - <<'EOF'\n$({RESTART})\nEOF"):
            with self.subTest(command=command):
                self.assertEqual(analyze(command).flags, [])
                self.assertEqual(analyze(command).categories, ["other"])

    def test_cp6_a_program_of_another_language_is_not_shell(self):
        for command in (
            f"python3 - <<'EOF'\nimport os\n{UP}\nEOF",
            f"python3 - <<'EOF'\nprint(\"a\n{UP}\nEOF",  # the unbalanced quote that does not close as shell
            f"python3 - <<EOF\nif x:\n    {UP}\nEOF",
            f"node <<EOF\n{UP}\nconsole.log('a\nEOF",
            f"ruby <<'EOF'\n{UP}\nEOF", f"perl <<'EOF'\n{UP}\nEOF", f"lua <<'EOF'\n{UP}\nEOF",
            f"php <<'EOF'\n{UP}\nEOF", f"python3.12 -u - <<'EOF'\n{UP}\nEOF",
        ):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual((result.categories, result.flags, result.uncertainty), (["other"], [], []))

    def test_a_name_that_only_starts_like_an_interpreter_is_not_one(self):
        for receiver in ("pythonic", "python-config", "nodejs", "rubyx", "lua5.4x", "phpx", "perl6"):
            with self.subTest(receiver=receiver):
                self.assertIn(LIFECYCLE, analyze(f"{receiver} <<EOF\n{UP}\nEOF").flags)

    def test_cp6_a_receiver_held_in_a_variable_is_known_by_its_values(self):
        """CP6's last case: `PY=python3` + `$PY - <<EOF`. The values of the variables assigned in the text (V1-V3)
        name the receiver; the other uses of the values (program names, code strings) come with Task 5."""
        for command in (f"PY=python3\n$PY - <<EOF\n{UP}\nEOF", f"PY=.venv/bin/python; $PY - \"$T\" <<'EOF'\n{UP}\nEOF",
                        f"export PY=python3; ${{PY}} - <<EOF\n{UP}\nEOF", f"declare PY=node\n$PY <<EOF\n{UP}\nEOF",
                        f"for p in python3 node; do $p - <<EOF\n{UP}\nEOF\ndone", f"PY=(python3 ruby); $PY - <<EOF\n{UP}\nEOF",
                        f'PY="/usr/bin/python3"; "$PY" - <<EOF\n{UP}\nEOF'):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual((result.flags, result.uncertainty), ([], []))

    def test_cp6_a_receiver_that_may_be_a_shell_is_read_as_one(self):
        """Every way a variable can name something other than a foreign interpreter keeps the body as shell: no
        assignment in the text, a second value, a substitution, `read`, `+=`, a loop over words, `eval`."""
        for command in (
            f"$PY - <<EOF\n{UP}\nEOF", f"PY=python3; PY=bash; $PY - <<EOF\n{UP}\nEOF",
            f"PY=$(which python3); $PY - <<EOF\n{UP}\nEOF", f"PY=python3; read PY; $PY - <<EOF\n{UP}\nEOF",
            f"PY=python3; PY+=x; $PY - <<EOF\n{UP}\nEOF", f"PY=python3; PY[1]=bash; $PY - <<EOF\n{UP}\nEOF",
            f"for p in python3 sh; do $p - <<EOF\n{UP}\nEOF\ndone", f"for p; do $p - <<EOF\n{UP}\nEOF\ndone",
            f"for p in $(ls); do $p - <<EOF\n{UP}\nEOF\ndone", f"PY=python3; eval 'PY=bash'; $PY - <<EOF\n{UP}\nEOF",
            f"PY=; $PY - <<EOF\n{UP}\nEOF", f"PY=python3; declare -n PY=Q; $PY - <<EOF\n{UP}\nEOF",
            f"PY=python3; getopts a PY; $PY - <<EOF\n{UP}\nEOF",
            # more than MAX_VALUE_CANDIDATES (16) values: unknown, even when every one is a foreign interpreter
            f"for p in {' '.join(f'python{i}' for i in range(17))}; do $p - <<EOF\n{UP}\nEOF\ndone",
        ):
            with self.subTest(command=command):
                self.assertIn(LIFECYCLE, analyze(command).flags)

    def test_cp7_a_shell_receiver_is_read_as_a_script(self):
        result = analyze(f"bash <<EOF\nif true; then\n{RESTART}\nfi\nEOF")
        self.assertEqual(result.flags, [LIFECYCLE])
        self.assertEqual(result.uncertainty, [])

    def test_cp7_a_body_that_does_not_close_for_a_shell_receiver_is_level_b(self):
        result = analyze('bash <<EOF\necho "\nEOF')
        self.assertEqual((result.categories, result.flags), (["other", "unclassified"], ["unclassified_command"]))
        self.assertEqual(result.uncertainty, ["lex_error"])

    def test_every_other_receiver_is_a_shell_script(self):
        for receiver in ("ssh host", "sudo bash", "sh -s", "cat | bash", "docker exec -i c sh", "xargs -0 sh -c",
                         "env FOO=1 zsh"):
            with self.subTest(receiver=receiver):
                if "|" in receiver:
                    command = f"cat <<EOF | bash\n{RESTART}\nEOF"
                else:
                    command = f"{receiver} <<EOF\n{RESTART}\nEOF"
                self.assertIn(LIFECYCLE, analyze(command).flags)

    def test_a_heredoc_on_a_compound_is_always_code(self):
        for command in (f"{{ python3 -; }} <<EOF\n{RESTART}\nEOF", f"( cat ) <<EOF\n{RESTART}\nEOF",
                        f"while read l; do :; done <<EOF\n{RESTART}\nEOF", f"f() {{ cat; }} <<EOF\n{RESTART}\nEOF",
                        f"if true; then cat; fi <<EOF\n{RESTART}\nEOF"):
            with self.subTest(command=command):
                self.assertIn(LIFECYCLE, analyze(command).flags)

    def test_data_sinks_are_decided_per_command_and_context(self):
        data = (f"cat > f <<EOF\n{RESTART}\nEOF", f"cd d && cat > f <<EOF\n{RESTART}\nEOF",
                f"tee -a f <<'EOF'\n{RESTART}\nEOF", f"git commit -F - <<EOF\n{RESTART}\nEOF")
        code = (f"x | cat > f <<EOF\n{RESTART}\nEOF", f"{{ cat <<EOF\n{RESTART}\nEOF\n}}",
                f"( cat <<EOF\n{RESTART}\nEOF\n)", f"cat <<EOF | bash\n{RESTART}\nEOF",
                f"cat <<EOF >(bash)\n{RESTART}\nEOF", f"cat <<EOF $(true)\n{RESTART}\nEOF",
                f"cat <<EOF `true`\n{RESTART}\nEOF")
        for command in data:
            with self.subTest(command=command):
                self.assertNotIn(LIFECYCLE, analyze(command).flags)
        for command in code:
            with self.subTest(command=command):
                self.assertIn(LIFECYCLE, analyze(command).flags)

    def test_hd3_cat_with_an_output_redirect_in_a_function_or_group_is_data(self):
        """HD3 as revised by the user (replay E3): a body written to a file by `cat > f` in a function body or a
        `{ }` group that is not in a pipeline is data, even when its text does not parse as shell."""
        broken = 'a "quote that never closes\ndocker compose up'
        for command in (
            f'cd d && mk(){{ cat > "$1/log.md" <<EOF\n{broken}\nEOF\n}}\nmk x',
            f"{{ cat >> f <<EOF\n{broken}\nEOF\n}}", f"{{ tee f > /dev/null <<EOF\n{broken}\nEOF\n}}",
            f"{{ true; {{ cat > f <<'EOF'\n{broken}\nEOF\n}}; }}", f"function mk {{ cat > f <<EOF\n{broken}\nEOF\n}}",
        ):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual((result.flags, result.uncertainty), ([], []))

    def test_hd3_what_stays_code_in_a_group_or_function(self):
        broken = 'a "quote that never closes\ndocker compose up'
        for command in (
            f"HEAD() {{ cat <<EOF\n{broken}\nEOF\n}}",  # no redirect of its own: the function may feed a pipe
            f'{{ HEAD x; cat <<EOF\n{broken}\nEOF\n}} > page.html',  # the redirect is the group's, not cat's
            f"{{ cat > f <<EOF\n{broken}\nEOF\n}} | bash", f"mk() {{ cat > f <<EOF\n{broken}\nEOF\n}} | sh",
            f"( cat > f <<EOF\n{broken}\nEOF\n)", f"if true; then cat > f <<EOF\n{broken}\nEOF\nfi",
            f"{{ cat > f <<EOF | sh\n{broken}\nEOF\n}}", f"x=$(cat > f <<EOF\n{broken}\nEOF\n)",
        ):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertIn("lex_error", result.uncertainty)  # (the canary may add its own record)
                self.assertEqual(result.flags, ["unclassified_command"])
        self.assertIn(LIFECYCLE, analyze(f"{{ cat > f <<EOF | bash\n{RESTART}\nEOF\n}}").flags)

    def test_the_heredoc_of_a_nested_text_is_read_too(self):
        """`nvim -c '!cmd'` text is a script of its own, and its heredocs follow the same rules."""
        def nested(text):
            return "nvim --headless -c " + shlex.quote("!" + text)

        self.assertNotIn(LIFECYCLE, analyze(nested(f"cat > f <<EOF\n{RESTART}\nEOF")).flags)
        self.assertIn(LIFECYCLE, analyze(nested(f"bash <<EOF\n{RESTART}\nEOF")).flags)

    def test_heredoc_bodies_follow_the_code_depth(self):
        """A body is code one level down; four levels are level B (`nested_shell_depth`), as for nvim."""
        body = RESTART
        for _ in range(3):
            body = f"bash <<EOF\n{body}\nEOF"
        self.assertEqual(analyze(body).flags, [LIFECYCLE])
        deeper = f"bash <<EOF\n{body}\nEOF"
        result = analyze(deeper)
        self.assertEqual(result.uncertainty, ["nested_shell_depth"])
        self.assertEqual(result.flags, ["unclassified_command"])


class WrappersAndProgramNames(unittest.TestCase):
    """CP8-CP11 (audit-shell-lexer, Task 3): the wrapper table with each flag grammar, and the program name."""

    def assertFlags(self, command, flags, uncertainty=None):
        result = analyze(command)
        self.assertEqual(result.flags, flags, command)
        if uncertainty is not None:
            self.assertEqual(result.uncertainty, uncertainty, command)
        return result

    def test_cp8_a_wrapper_with_its_flags_gives_one_reading(self):
        for command, flag in (
            (f"sudo -u root {RESTART}", LIFECYCLE), (f"sudo -E {RESTART}", LIFECYCLE),
            (f"sudo -- {RESTART}", LIFECYCLE), ("sudo A=1 git push", PUSH), (f"env FOO=1 {RESTART}", LIFECYCLE),
            ("env -i -u X git push", PUSH), ("nice -n 5 git push", PUSH), ("nice -10 git push", PUSH),
            (f"nohup {RESTART}", LIFECYCLE), ("time -p git push", PUSH), ("command time -p git push", PUSH),
            (f"stdbuf -oL {RESTART}", LIFECYCLE), (f"ionice -c 3 {RESTART}", LIFECYCLE),
            ("xargs docker re" + "start", LIFECYCLE), ("xargs -n 1 -P 4 git push", PUSH),
            (f"watch -x {RESTART}", LIFECYCLE), ("command -p git push", PUSH), ("exec git push", PUSH),
            ("noglob git push", PUSH), ("nocorrect git push", PUSH), (f"repeat 2 {RESTART}", LIFECYCLE),
            ("- git push", PUSH), (f"sudo -s {RESTART}", LIFECYCLE), (f"sudo -ni {RESTART}", LIFECYCLE),
            (f"sudo --user=root {RESTART}", LIFECYCLE), (f"sudo --user root {RESTART}", LIFECYCLE),
            (f"env --chdir /tmp {RESTART}", LIFECYCLE), (f"env - {RESTART}", LIFECYCLE),
            ("xargs -I{} git push", PUSH), ("xargs --max-args=1 git push", PUSH), ("xargs -0 -r git push", PUSH),
            ("xargs -i git push", PUSH), ("xargs --replace git push", PUSH), (f"watch -n 5 {RESTART}", LIFECYCLE),
            (f"stdbuf --output=L {RESTART}", LIFECYCLE), (f"sudo -u root nice -n 5 env A=1 {RESTART}", LIFECYCLE),
            ("exec -c git push", PUSH), (f"command time -f %e {RESTART}", LIFECYCLE),
        ):
            with self.subTest(command=command):
                self.assertFlags(command, [flag], [])

    def test_cp9_a_wrapper_that_ends_without_a_command_runs_nothing(self):
        for command in (f"sudo -l {RESTART}", f"sudo -e {RESTART}", f"sudo -v {RESTART}", f"sudo --list {RESTART}",
                        "command -v docker", "command -V git", "ionice -p 12 docker", "ionice -u 1000 docker"):
            with self.subTest(command=command):
                self.assertNotIn(LIFECYCLE, analyze(command).flags)
                self.assertEqual(analyze(command).categories, ["other"])

    def test_cp10_a_program_is_known_by_its_last_path_component(self):
        for command, flags in (
            (f"/usr/bin/{RESTART}", [LIFECYCLE]), (f"./bin/{RESTART}", [LIFECYCLE]),
            (f"~/.local/bin/mise x -- {RESTART}", [LIFECYCLE]), ("/usr/bin/timeout 5 git push", [PUSH]),
            (f"={RESTART}", [LIFECYCLE]), (f"A[0]=x {RESTART}", [LIFECYCLE]), ("/usr/bin/git push", [PUSH]),
            (f"/usr/bin/sudo -u root {RESTART}", [LIFECYCLE]), (f"sudo /usr/bin/{RESTART}", [LIFECYCLE]),
            ("=git push", [PUSH]),
        ):
            with self.subTest(command=command):
                self.assertFlags(command, flags, [])
        self.assertEqual(analyze("./mvnw test -Dtest=X").categories, ["test-narrow"])
        self.assertEqual(analyze("/home/u/.venv/bin/pytest tests/test_a.py").categories, ["test-narrow"])
        for command in ("./mvnw test -Dtest=X", "$S/sync.sh", "./scripts/run.sh a", "/opt/dockerx restart y"):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual(result.flags, [], command)
                self.assertNotIn("dynamic_command", result.uncertainty)

    def test_cp11_an_unknown_flag_is_read_both_ways(self):
        self.assertFlags(f"sudo --frobnicate {RESTART}", [LIFECYCLE], ["prefix_readings"])
        self.assertFlags(f"sudo --frobnicate x {RESTART}", [LIFECYCLE], ["prefix_readings"])
        self.assertFlags(f"nice -Z {RESTART}", [LIFECYCLE], ["prefix_readings"])
        self.assertFlags(f"sudo -h host {RESTART}", [LIFECYCLE], ["prefix_readings"])  # help or host: two readings
        self.assertFlags("xargs -Z git push", [PUSH], ["prefix_readings"])

    def test_the_wrapper_search_stays_linear(self):
        """Each word of the flags is looked at a constant number of times: the number of steps is counted (not the
        time, which depends on the machine) and doubling the words doubles it."""
        from unittest import mock

        def steps(words: int) -> int:
            counter = []
            real = classifier._flag_step

            def counting(*args, **kwargs):
                counter.append(1)
                return real(*args, **kwargs)

            with mock.patch.object(classifier, "_flag_step", counting):
                result = analyze("sudo " + " ".join(["--frobnicate"] * words) + " git push")
            self.assertEqual(result.flags, [PUSH])  # every unknown flag read both ways, and still the push
            self.assertEqual(result.uncertainty, ["prefix_readings"])
            return len(counter)

        small, large = steps(200), steps(400)
        self.assertLessEqual(small, 2 * 200 + 8)
        self.assertLessEqual(large, 2 * small)

    def test_every_wrapper_and_sink_name_is_a_known_head(self):
        for name in ("sudo", "env", "nice", "nohup", "time", "stdbuf", "ionice", "timeout", "xargs", "watch",
                     "command", "exec", "builtin", "noglob", "nocorrect", "repeat", "mise", "docker", "git", "gh",
                     "cat", "tee", "bash", "python3", "node", "busted", "nvim", "pytest", "curl"):
            with self.subTest(name=name):
                self.assertIn(name, classifier.KNOWN_HEADS)
        self.assertNotIn("mvnw", classifier.KNOWN_HEADS)

    def test_the_programs_left_out_of_the_table_are_not_wrappers_but_the_canary_records_them(self):
        """User decision 5: doas, setsid, flock, chrt, taskset, find -exec and parallel are not wrappers here, so
        the command is not classified; spec section 8 relies on the canary to make them visible in the metrics."""
        for command in (f"doas {RESTART}", f"setsid {RESTART}", f"flock /tmp/l {RESTART}",
                        f"find . -exec {RESTART} ;", f"parallel {RESTART}", f"chrt 1 {RESTART}",
                        f"taskset 1 {RESTART}"):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertNotIn(LIFECYCLE, result.flags)
                self.assertIn("deny_token_unmatched", result.uncertainty)


class GitSubcommand(unittest.TestCase):
    """The git subcommand rule (audit-shell-lexer, A2 and question 7): `commit` only counts as the subcommand,
    after git's global options; the heredoc rules of `git` use the same function."""

    def test_the_helper_skips_global_options(self):
        has = classifier._git_has_subcommand
        for args in (["commit", "-m", "x"], ["-C", "repo", "commit"], ["-c", "a=b", "commit"],
                     ["--git-dir=.git", "--no-pager", "commit"], ["--git-dir", ".git", "commit"], ["--", "commit"],
                     ["--frobnicate", "x", "commit"], ["--frobnicate", "commit"], ["-p", "commit"],
                     ["--exec-path", "commit"], ["--exec-path=/x", "commit"]):
            with self.subTest(args=args):
                self.assertTrue(has(args, "commit"))
        for args in (["config", "--get", "commit.gpgsign"], ["log", "--grep", "commit"], ["-C", "repo", "show", "commit"],
                     ["show", "commit"], ["-C", "commit", "status"], ["--git-dir", "commit", "status"], [],
                     ["--git-dir=commit", "status"], ["-c", "commit", "status"]):
            with self.subTest(args=args):
                self.assertFalse(has(args, "commit"))

    def test_the_heredoc_stdin_file_rule_needs_the_subcommand(self):
        """`git ... -F - <<EOF` is data only for `git commit`; `commit` as an argument is no sink."""
        body = f"\n{UP}\nEOF"
        for command in ("git commit -F - <<EOF" + body, "git -C repo commit -F - <<EOF" + body,
                        "git --no-pager commit --file=- <<EOF" + body, "git -c user.name=x commit -F - <<EOF" + body):
            with self.subTest(command=command):
                self.assertNotIn(LIFECYCLE, analyze(command).flags)
        for command in ("git log --grep commit -F - <<EOF" + body, "git config --get commit.x -F - <<EOF" + body,
                        "git show commit -F - <<EOF" + body, "git -C commit status -F - <<EOF" + body):
            with self.subTest(command=command):
                self.assertIn(LIFECYCLE, analyze(command).flags)

    def test_the_message_value_rule_needs_the_subcommand(self):
        """`$(cat <<EOF ...)` as the value of `-m` is data for `git commit` only."""
        body = f"\n{UP}\nEOF\n)\""
        for command in ('git commit -m "$(cat <<EOF' + body, 'git -C repo commit --message="$(cat <<EOF' + body):
            with self.subTest(command=command):
                self.assertNotIn(LIFECYCLE, analyze(command).flags)
        for command in ('git log --grep commit -m "$(cat <<EOF' + body, 'git show commit -m "$(cat <<EOF' + body):
            with self.subTest(command=command):
                self.assertIn(LIFECYCLE, analyze(command).flags)


class CodeArguments(unittest.TestCase):
    """CP12-CP16 (audit-shell-lexer, Task 4): arguments that run code are analyzed one level down (X1-X6)."""

    NV = "nvim --headless "

    def assertFlags(self, command, flags, uncertainty=None):
        result = analyze(command)
        self.assertEqual(result.flags, flags, command)
        if uncertainty is not None:
            self.assertEqual(result.uncertainty, uncertainty, command)
        return result

    def test_cp12_every_form_that_runs_a_string_is_classified(self):
        for command, flag in (
            (f"bash -c '{RESTART}'", LIFECYCLE), ('sh -lc "git push"', PUSH), ("zsh -c 'true; git commit -m x'", COMMIT),
            ("bash -o pipefail -c 'git push'", PUSH), (f'eval "{RESTART}"', LIFECYCLE), (f"eval {RESTART}", LIFECYCLE),
            ("trap 'git push' EXIT", PUSH), (f"sudo -s {RESTART}", LIFECYCLE), ("su -c 'git push' u", PUSH),
            (f"env -S '{RESTART}'", LIFECYCLE), (f"watch {RESTART}", LIFECYCLE), ("mise exec -c 'git push'", PUSH),
            ("bash <<< 'git push'", PUSH), ("bash -c \"bash -c 'git push'\"", PUSH),
            ("dash -ec 'git push'", PUSH), ("bash -O extglob -c 'git push'", PUSH), ("bash -- -c 'git push'", None),
            ("bash +o history -c 'git push'", PUSH), ("sudo -i git push", PUSH), ("sudo -u root -s 'a; git push'", PUSH),
            ("su --command 'git push' u", PUSH), ("su --command='git push' u", PUSH), ("su u -c 'git push'", PUSH),
            ("env --split-string='git push'", PUSH), ("env -i -S 'git push'", PUSH), ("env -Sgit push", PUSH),
            ("watch -n 2 'x; git push'", PUSH), ("mise x -c 'git push'", PUSH), ("mise exec --command 'git push'", PUSH),
            ("mise exec node@20 -c 'git push' -- true", PUSH), ("trap -- 'git push' EXIT", PUSH),
            ("sudo bash -c 'git push'", PUSH), ("timeout 5 sh -c 'git push'", PUSH),
            ("eval 'a;' git push", PUSH), ("nice env -S 'git push'", PUSH),
        ):
            with self.subTest(command=command):
                self.assertFlags(command, [flag] if flag else [])

    def test_cp12_the_categories_keep_the_other_of_the_outer_command(self):
        self.assertEqual(analyze(f"bash -c '{RESTART}'").categories, ["docker-lifecycle", "other"])
        self.assertEqual(analyze("eval \"git push\"").categories, ["git-push", "other"])

    def test_x1_what_does_not_run_code_is_not_read_as_code(self):
        for command in ("trap -l", "trap -p", "trap - EXIT", "trap -p EXIT", "su - user", "su", "sudo -s", "sudo -i",
                        "bash -c", "eval", "env -S", "watch", "mise exec", "mise exec -- true", "mise run test"):
            with self.subTest(command=command):
                self.assertFlags(command, [], [])

    def test_x1_watch_with_exec_runs_the_words_as_a_command_not_as_a_string(self):
        self.assertFlags("watch -x git push", [PUSH], [])
        self.assertFlags("watch --exec git push", [PUSH], [])
        self.assertFlags("watch -x 'a; git push'", [])  # one program named `a; git push`, not shell text
        self.assertFlags("watch 'a; git push'", [PUSH], [])

    def test_cp13_code_that_is_not_known_is_level_b(self):
        for command, reason in (
            ('bash -c "$X"', "dynamic_code"), ('eval "$cmd"', "dynamic_code"),
            ('bash -c "$(curl -s https://x.example)"', "dynamic_code"), ("bash <(curl -s x)", "dynamic_code"),
            ("source <(x)", "dynamic_code"), (". <(x)", "dynamic_code"), ("echo x | bash", "piped_shell"),
            ("curl x | sh", "piped_shell"), ("xargs -I{} sh -c {}", "dynamic_code"),
            ("xargs -I R bash -c 'echo R'", "dynamic_code"), ("xargs -i sh -c 'echo {}'", "dynamic_code"),
            ("xargs --replace=@ sh -c 'echo @'", "dynamic_code"), ("echo x | source /dev/stdin", "piped_shell"),
            ("echo x | zsh -s", "piped_shell"), ("echo x | sudo bash", "piped_shell"), ('bash -c "$X restart y"', "dynamic_code"),
            ("bash < <(x)", "dynamic_code"), ('trap "$H" EXIT', "dynamic_code"), ('su -c "$C" u', "dynamic_code"),
            ('env -S "$C"', "dynamic_code"), ('watch "$C"', "dynamic_code"), ('mise exec -c "$C"', "dynamic_code"),
            ('sudo -s "$C"', "dynamic_code"), ('bash -c "sudo $X"', "dynamic_code"),
            ('bash -c "$(which docker) ps"', "dynamic_code"),
        ):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertIn("unclassified_command", result.flags, command)
                self.assertIn("unclassified", result.categories, command)
                self.assertIn(reason, result.uncertainty, command)

    def test_cp14_an_expansion_that_is_not_a_command_name_is_accepted(self):
        for command in ('sh -c ": > $F"', 'bash -c "echo > /dev/tcp/$ip/$port"', "bash script.sh", "bash -n x.sh",
                        'bash -c "echo $X"', 'bash -c "$S/sync.sh"', 'bash -c "ls $(date)"', "echo x | bash script.sh",
                        "bash -c 'cd $D && ls'", "bash", "sh -s < file", "printf x | zsh -f -n", "bash -n <(x)", "cat x | sh -c 'ls'", "xargs -I{} echo {}",
                        "xargs -n 1 sh -c 'echo $0'"):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertNotIn("unclassified_command", result.flags, command)
                self.assertEqual(result.uncertainty, [], command)

    def test_cp15_the_nvim_forms_that_run_a_program(self):
        for command, flag in (
            (self.NV + """-c 'exe "!%s"'""" % RESTART, LIFECYCLE),
            (self.NV + """-c 'exe "silent !%s"'""" % RESTART, LIFECYCLE),
            (self.NV + """-c "exe '!%s'" """ % RESTART, LIFECYCLE),
            (self.NV + """-c 'lua vim.fn.system("git push")'""", PUSH),
            (self.NV + """-c "lua vim.fn.system({'git', 'push'})" """, PUSH),
            (self.NV + """-c 'lua os.execute("%s")'""" % RESTART, LIFECYCLE),
            (self.NV + """-c 'lua io.popen("git push")'""", PUSH),
            (self.NV + """-c 'call jobstart("git push")'""", PUSH),
            (self.NV + "-c 'terminal git push'", PUSH),
            (self.NV + "-c 'te! git push'", PUSH),
            (self.NV + """-c 'lua vim.system({"git","push"})'""", PUSH),
            (self.NV + """-c 'lua vim.fn.jobstart({"git", "push"}, {})'""", PUSH),
            (self.NV + """-c 'lua vim.fn.termopen("git push")'""", PUSH),
            (self.NV + """-c 'echo systemlist("git push")'""", PUSH),
            (self.NV + """--cmd 'lua vim.fn.system("git push")'""", PUSH),
            (self.NV + """+'lua vim.fn.system("git push")'""", PUSH),
            (self.NV + """-c 'lua print(vim.fn.system("git rev-parse HEAD"))'""", None),
            (self.NV + """-c 'lua foo.system(x)'""", None),
            (self.NV + """-c 'exe "normal x"'""", None),
        ):
            with self.subTest(command=command):
                self.assertFlags(command, [flag] if flag else [], [])

    def test_cp15_a_call_whose_program_is_not_a_literal_is_level_b(self):
        for argument in ("cmd", "a .. b", '"a" .. b', "[[ls]]", "{cmd}", '{"git", x}', "", '"unclosed'):
            command = self.NV + "-c " + shlex.quote("lua os.execute(" + argument + ")")
            with self.subTest(command=command):
                self.assertFlags(command, ["unclassified_command"], ["nvim_shell_exec"])
        self.assertFlags(self.NV + """-c 'exe "!" . cmd'""", ["unclassified_command"], ["nvim_shell_exec"])

    def test_cp15_an_element_of_a_list_stays_one_word(self):
        """The elements are quoted when joined: a `;` or a quote inside one is no second command (the canary only
        records the text, so only the flags are compared)."""
        for argument in ("{'echo', 'it''s; %s'}" % RESTART, '{"echo", "a; %s"}' % RESTART):
            command = self.NV + "-c " + shlex.quote("lua vim.fn.system(" + argument + ")")
            with self.subTest(command=command):
                self.assertFlags(command, [])

    def test_cp16_code_is_read_three_levels_down_and_not_a_fourth(self):
        three = RESTART
        for _ in range(3):
            three = "bash -c " + shlex.quote(three)
        self.assertFlags(three, [LIFECYCLE], [])
        for wrapper in ("bash -c ", "eval ", "sh -c ", "su -c "):
            text = "docker ps"  # a verb that is no lifecycle one: the canary has nothing to add
            for _ in range(4):
                text = wrapper + shlex.quote(text)
            with self.subTest(wrapper=wrapper):
                self.assertFlags(text, ["unclassified_command"], ["nested_shell_depth"])

    def test_cp16_a_heredoc_body_and_a_code_argument_share_the_depth(self):
        body = f"bash -c {shlex.quote(RESTART)}"
        for _ in range(2):
            body = f"bash <<EOF\n{body}\nEOF"
        self.assertFlags(body, [LIFECYCLE], [])
        deeper = f"bash <<EOF\n{body}\nEOF"
        self.assertIn("nested_shell_depth", analyze(deeper).uncertainty)
        self.assertEqual(analyze(deeper).flags, ["unclassified_command"])

    def test_code_text_that_does_not_close_is_level_b(self):
        self.assertFlags('bash -c "if true; then"', ["unclassified_command"], ["lex_error"])
        self.assertFlags("eval 'echo \"a'", ["unclassified_command"], ["lex_error"])

    def test_the_code_arguments_of_a_command_are_capped(self):
        command = "watch " + " ".join(["watch"] * 40) + " x"
        result = analyze(command)
        self.assertIn("unclassified_command", result.flags)

    def test_a_nested_code_text_with_an_unknown_wrapper_argument_is_not_a_dynamic_name(self):
        result = analyze("bash -c " + shlex.quote('timeout "$T" ' + RESTART))
        self.assertEqual(result.flags, [LIFECYCLE])
        self.assertEqual(result.uncertainty, ["prefix_readings"])


class ValuesAndDynamicNames(unittest.TestCase):
    """CP17-CP20 (V1-V4, N6) of Task 5, with the value rules of the review fix B1: a value is known only when every
    source of the name is seen (an assignment, a loop, a declaration, an array: all of them known); a name with
    another source (a substitution, `read`, `+=`, `${N:=v}`, `eval` / `source` in the text, a positional parameter)
    is unknown, and an unknown name in a program or code-string position is level B (`dynamic_code`). Only a name
    that the text never assigns (it comes from the environment) is level A (`dynamic_command`, N6)."""

    def assertFlags(self, command, flags, uncertainty=None):
        result = analyze(command)
        self.assertEqual(result.flags, flags, command)
        if uncertainty is not None:
            self.assertEqual(result.uncertainty, uncertainty, command)
        return result

    def test_cp17_values_assigned_in_the_text_resolve_names_and_code_strings(self):
        down = "down -" + "v"
        for command, flag in (
            (f'T="docker compose -p d -f x.yml"; zsh -c "$T {down}"', LIFECYCLE),  # the real case (L8)
            (f'T="docker compose"; $T up', LIFECYCLE),
            ("D=docker; $D re" + "start x", LIFECYCLE),
            ("for c in 'git push' 'ls'; do bash -c \"$c\"; done", PUSH),
            ("export G=git; $G push", PUSH),
            ("declare -r G=git; ${G} push", PUSH),
            ('G=git; "$G" push', PUSH),
            ('A=docker; B=re' + 'start; bash -c "$A $B x"', LIFECYCLE),  # two names in one code string
            ("G=(git curl); $G push", PUSH),  # every element is a value
        ):
            with self.subTest(command=command):
                self.assertIn(flag, analyze(command).flags)

    def test_cp17_the_real_loops_are_no_longer_dynamic_code(self):
        result = analyze('for c in "a" "b"; do zsh -c "$c"; done')
        self.assertNotIn("dynamic_code", result.uncertainty)
        self.assertEqual(result.flags, [])
        result = analyze('T="docker compose -p x -f y.yml"; zsh -c "$T down -v"')
        self.assertEqual(result.flags, [LIFECYCLE])
        self.assertNotIn("dynamic_code", result.uncertainty)

    def test_cp17_a_value_goes_down_to_the_nested_text(self):
        self.assertFlags('D=docker; bash -c "bash -c \'$D re' + 'start x\'"', [LIFECYCLE])
        self.assertFlags('D=docker; bash <<EOF\n$D re' + 'start x\nEOF', [LIFECYCLE])
        self.assertFlags("D=docker; bash <<'EOF'\n$D re" + "start x\nEOF", [LIFECYCLE])  # the inner shell has it

    def test_cp17_a_value_with_blanks_or_none_is_split_like_the_shell(self):
        self.assertFlags('E=""; $E docker re' + 'start x', [LIFECYCLE])  # the empty word disappears
        self.assertFlags('T="  sudo   docker "; $T re' + 'start x', [LIFECYCLE])  # a wrapper in the value

    def test_cp17_every_value_of_a_loop_counts_and_the_union_is_flow_insensitive(self):
        self.assertFlags("for c in ls '" + RESTART + "'; do $c; done", [LIFECYCLE])
        self.assertFlags("X=ls; " + "$X; X=git; $X push", [PUSH])

    def test_cp18_more_than_the_cap_or_a_source_the_text_does_not_show_is_dynamic_code(self):
        letters = " ".join("abcdefghijklmnopq")  # 17 values
        for command in (f'for c in {letters}; do bash -c "$c"; done', 'X=$(x); bash -c "$X"', 'read X; bash -c "$X"',
                        'for c in a b; do c=$(x); bash -c "$c"; done', 'X=a; X+=b; bash -c "$X"',
                        'for c in $(ls); do bash -c "$c"; done', 'bash -c "$1"'):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual(result.flags, ["unclassified_command"])
                self.assertIn("dynamic_code", result.uncertainty)

    def test_cp18_sixteen_values_are_still_read(self):
        letters = " ".join("abcdefghijklmnop")
        result = analyze(f'for c in {letters}; do bash -c "$c"; done')
        self.assertEqual(result.flags, [])
        self.assertNotIn("dynamic_code", result.uncertainty)

    def test_cp18_the_product_of_the_values_of_a_string_counts(self):
        four = " ".join("abcd")
        result = analyze(f'for x in {four}; do for y in {four}; do for z in {four}; do bash -c "$x $y $z"; done; done; done')
        self.assertIn("dynamic_code", result.uncertainty)  # 64 combinations

    def test_cp19_a_program_name_that_only_the_environment_gives_is_level_a(self):
        for command in ("$X " + RESTART, "$(which docker) " + RESTART, "dock?r " + RESTART, "$X docker re" + "start y"):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertNotIn("unclassified_command", result.flags)
                self.assertIn("dynamic_command", result.uncertainty)
        self.assertIn("deny_token_unmatched", analyze("$X docker re" + "start y").uncertainty)

    def test_cp19_what_is_not_a_dynamic_name(self):
        for command in ("$S/sync.sh", '"$D"/x a', "[ -f x ]", "echo $X", "timeout \"$T\" ls", "x=1 ls", "[[ -f x ]]",
                        "ls *.md", "$HOME/bin/tool a"):
            with self.subTest(command=command):
                self.assertNotIn("dynamic_command", analyze(command).uncertainty)

    def test_cp19_a_value_that_is_itself_dynamic_stays_dynamic(self):
        """B1: a program name made from a name the text assigns is level B when its value is dynamic (it was
        level A, `dynamic_command`, before the review fix)."""
        result = analyze("X=$1; $X a")
        self.assertEqual(result.flags, ["unclassified_command"])
        self.assertIn("dynamic_code", result.uncertainty)
        self.assertNotIn("dynamic_command", result.uncertainty)
        result = analyze('X=$1; bash -c "$X a"')
        self.assertIn("dynamic_code", result.uncertainty)

    def test_cp20_values_do_not_enter_the_arguments_of_a_wrapper(self):
        """V2: the same as LR13."""
        result = analyze("T=5; timeout -s KILL \"$T\" " + RESTART)
        self.assertEqual((result.categories, result.flags), (["docker-lifecycle", "other"], [LIFECYCLE]))
        self.assertEqual(result.uncertainty, ["prefix_readings"])

    def test_the_known_values_merge_with_the_inherited_ones(self):
        values = classifier._known_values(classifier.shell.parse("A=x; read B", classifier.shell.Budget(1000)))
        self.assertEqual(values, {"A": frozenset({"x"}), "B": None})
        inner = classifier._known_values(classifier.shell.parse("A=y; B=z", classifier.shell.Budget(1000)), values)
        self.assertEqual(inner, {"A": frozenset({"x", "y"}), "B": None})
        self.assertEqual(classifier._known_values(classifier.shell.parse("true", classifier.shell.Budget(100)), values), values)

    def test_code_that_may_assign_anything_knows_nothing(self):
        result = analyze('D=docker; eval "x"; bash -c "$D ' + RESTART.split(" ", 1)[1] + '"')
        self.assertIn("dynamic_code", result.uncertainty)

    def test_the_expansion_of_values_is_bounded_and_ignores_escapes(self):
        env = {"A": frozenset({"x", "y"}), "B": frozenset({"1", "2"}), "U": None}
        self.assertEqual(classifier._expand_values("a $A ${B}z", env), ["a x 1z", "a x 2z", "a y 1z", "a y 2z"])
        self.assertEqual(classifier._expand_values("\\$A $U $1 ${A:-q} $", env), ["\\$A $U $1 ${A:-q} $"])
        self.assertEqual(classifier._expand_values("$A", env), ["x", "y"])
        big = {"A": frozenset(map(str, range(17)))}
        self.assertIsNone(classifier._expand_values("$A", big))

    def test_adversarial_value_forms_stay_cheap(self):
        import time
        many = " ".join(f"v{i}" for i in range(16))
        command = "; ".join(f'for c{i} in {many}; do bash -c "$c{i} $c{i}"; done' for i in range(6))
        began = time.perf_counter()
        analyze(command)
        analyze("; ".join(f"A{i}=$A{i}x" for i in range(300)) + "; bash -c \"$A0\"")
        self.assertLess(time.perf_counter() - began, 2.0)


class ReviewFixB1(unittest.TestCase):
    """Review-fix round, part B1 (audit-shell-lexer): the parser API of part A wired in, expansions in the verbs of
    git and docker, value propagation that fails closed, code-evaluation contexts, shell operands and the budget.
    Whatever can be resolved with certainty is resolved; what cannot is level B; a deny never becomes a level A
    allow. Blocked words are built from pieces; nothing runs."""

    RESTART = "re" + "start"

    def assertBlocked(self, command, reason="dynamic_code"):
        result = analyze(command)
        self.assertIn("unclassified_command", result.flags, command)
        self.assertIn("unclassified", result.categories, command)
        self.assertIn(reason, result.uncertainty, command)
        return result

    def assertNotBlocked(self, command):
        result = analyze(command)
        self.assertNotIn("unclassified_command", result.flags, command)
        return result

    # -- 1. the part A API -------------------------------------------------------------------------------------

    def test_a_ansi_c_part_with_certain_text_is_classified_by_its_decoded_text(self):
        for command, flag in (
            ("$'\\x64ocker' " + self.RESTART + " x", LIFECYCLE), ("$'\\144ocker' " + self.RESTART + " x", LIFECYCLE),
            ("$'\\u0064ocker' " + self.RESTART + " x", LIFECYCLE), ("git $'\\x70ush'", PUSH),
            ("git $'pu\\x73h' origin", PUSH), ("docker $'\\x72estart' x", LIFECYCLE),
            ("bash -c $'git \\x70ush'", PUSH), ("git $'\\x63ommit' -m x", COMMIT),
        ):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual(result.flags, [flag], command)
                self.assertNotIn("dynamic_command", result.uncertainty)

    def test_a_ansi_c_part_that_cannot_be_decoded_is_a_dynamic_head_at_level_b(self):
        """`$'\\q'` is `\\q` in bash and `q` in zsh: the program name is not known. A command name in this state
        is not a level A name of the environment: the shells disagree, so it cannot be resolved."""
        for command in ("$'\\q'ocker " + self.RESTART + " x", "$'\\x'ocker x", "$'\\u'ocker x", "$'a\\0b' x"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        self.assertBlocked("git $'pu\\q'sh")  # in the verb position too

    def test_a_brace_expansion_at_the_head_is_resolved_when_it_can_be(self):
        for command, flag in (("{docker," + self.RESTART + ",x}", LIFECYCLE), ("{git,push}", PUSH),
                              ("{docker,compose,up}", LIFECYCLE), ("sudo {git,push}", PUSH),
                              ("{{git,}push,x}", None)):
            with self.subTest(command=command):
                result = analyze(command)
                if flag:
                    self.assertEqual(result.flags, [flag], command)

    def test_a_brace_expansion_at_the_head_that_cannot_be_resolved_is_level_b(self):
        """A range (D1, M2, revised: it was level A outside a code string): level B anywhere. A quoted part is
        text now, so `{git,"push"} y` is resolved (see `ReviewFixD1`)."""
        for command in ("{1..3} x", "x{a..c}"):
            with self.subTest(command=command):
                self.assertBlocked(command)
            with self.subTest(command=command, inside="a code string"):
                self.assertBlocked("bash -c " + shlex.quote(command))
        self.assertIn(PUSH, analyze('{git,"push"} y').flags)

    def test_a_brace_expansion_that_is_not_one_is_not_dynamic(self):
        for command in ("echo {a,b}", "find . -exec {} \\;", "git log {}", "ls ${HOME}/{a,b}"):
            with self.subTest(command=command):
                self.assertNotIn("dynamic_command", analyze(command).uncertainty)

    def test_a_word_that_evaluates_code_is_dynamic_code(self):
        for command in ('echo "${(e)X}"', "echo ${(e)X}", 'echo "${X@P}"', 'A="${(%)X}" true', "echo ${(%):-%n}",
                        "f > ${(e)X}", "for i in ${(e)X}; do :; done", 'x=(${(e)Y} b)', 'echo "${X@P} $(date)"',
                        "case ${(e)X} in a) :;; esac", "echo $(echo ${(e)X})"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        for command in ('echo "${X}"', "echo ${X#a}", "echo ${(L)X}", 'echo "${X@Q}"', "echo ${X@U}"):
            with self.subTest(command=command, ok=True):
                self.assertNotBlocked(command)

    # -- 2. expansions in the verb positions ----------------------------------------------------------------------

    def test_known_values_in_the_verb_of_git_and_docker_are_substituted(self):
        for command, flag in (
            ("c=push; git $c", PUSH), ("c=pu; git ${c}sh", PUSH), ('c=push; git "$c" origin', PUSH),
            ("for a in stop start; do docker compose $a api; done", LIFECYCLE),
            ("for a in ps logs; do docker compose $a api; done", None),
            ("v=" + self.RESTART + "; docker $v x", LIFECYCLE), ("c=commit; git $c -m x", COMMIT),
            ("c=push; sudo git $c", PUSH), ("c=push; timeout 5 git -C d $c", PUSH),
            ("c=push; git -c a=b $c", PUSH), ("p=compose; docker $p up", LIFECYCLE),
            ("f='-f x.yml'; docker compose $f up", LIFECYCLE), ("c='push origin'; git $c", PUSH),
            ("g=git; c=push; $g $c", PUSH), ("c=push; bash -c 'git $c'", PUSH),
        ):
            with self.subTest(command=command):
                result = analyze(command)
                if flag:
                    self.assertIn(flag, result.flags, command)
                    self.assertNotIn("unclassified_command", result.flags, command)
                else:
                    self.assertNotIn("unclassified_command", result.flags, command)
                    self.assertEqual(result.flags, [], command)

    def test_a_dynamic_word_left_where_the_verb_could_be_is_level_b(self):
        for command in ("git $X", "git $X origin", 'git "$@"', "docker $X x", "docker $(cmd) x", "git `cmd` x",
                        "git {a..c} y", "git pu*", "git -C d $X", "docker compose $X up",
                        'docker compose -p x "$@"', "git {a,$X}", "docker --context c $X x",
                        "c=push; git $d", "git ${X:-push}", "git ${X}sh"):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_a_name_with_values_and_an_unknown_part_keeps_the_deny_and_is_level_b(self):
        result = self.assertBlocked("if x; then c=push; fi; git $c")
        self.assertIn(PUSH, result.flags)

    def test_a_dynamic_word_that_is_not_the_verb_is_not_level_b(self):
        for command in ("git -C $d status", 'git commit -m "$m"', "docker compose -f $F ps", "docker exec $c ls",
                        'git log --grep "$p"', 'docker run --name "$n" x', "git --git-dir=$d log",
                        "docker compose --project-name $n ps", "git add $files", "docker rm $(docker ps -aq)",
                        "docker logs $c", "gh pr create --title $t", "gh $g create"):
            with self.subTest(command=command):
                self.assertNotBlocked(command)

    def test_the_cap_and_the_splitting_of_the_verb_substitution_fail_closed(self):
        names = " ".join(f"a{i}" for i in range(17))
        self.assertBlocked(f"for c in {names}; do git $c; done")
        self.assertBlocked("IFS=:; c=push; git $c")
        self.assertBlocked("setopt shwordsplit; c=push; git $c")
        two = " ".join(f"b{i}" for i in range(5))
        self.assertBlocked(f"for c in {two}; do for d in {two}; do git $c $d; done; done")  # 25 combinations

    # -- 3. value propagation that fails closed ------------------------------------------------------------------

    def test_a_head_over_the_cap_is_level_b(self):
        names = " ".join(f"a{i}" for i in range(17))
        self.assertBlocked(f"for c in {names}; do $c x; done")
        sixteen = " ".join(f"a{i}" for i in range(16))
        result = analyze(f"for c in {sixteen}; do $c x; done")
        self.assertNotIn("unclassified_command", result.flags)
        self.assertNotIn("dynamic_code", result.uncertainty)

    def test_a_dynamic_head_of_a_name_the_text_assigns_is_level_b_and_the_environment_alone_is_level_a(self):
        for command in ("X=$1; $X a", "X=a$(cmd); $X a", "X=a; X+=b; $X a", "read X; $X a", "for x in $(ls); do $x a; done",
                        "$X a; X=ls", "$1 a", "$@ a", "$* a", "${a[@]} a", "${a[0]} a", "${!n} a", "${X:-ls} a; X=1",
                        "${1} a", "$# a"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        for command in ("$X a", "${X:-ls} a", '"$X" a', "$HOME_BIN a", "$(which x) a", "x* a", "$X/b a"):
            with self.subTest(command=command, level="a"):
                result = analyze(command)
                self.assertNotIn("unclassified_command", result.flags)

    def test_eval_source_and_dot_make_every_assigned_name_level_b(self):
        for loader in ("eval 'x=1'", "source ./f", ". ./f", "builtin eval x", "command eval x", "command source f",
                       "sudo eval x"):
            command = f"D=docker; {loader}; $D {self.RESTART} x"
            with self.subTest(command=command):
                self.assertBlocked(command)
            command = f"{loader}; D=docker; $D x"
            with self.subTest(command=command):
                self.assertBlocked(command)
        self.assertBlocked("source ./f; $D x")  # any name: the file may have set it
        self.assertBlocked("R=read; $R D <<< docker; D=docker; $D x")  # a head that may be a builtin

    def test_the_forms_that_assign_make_the_name_unknown(self):
        for assign in (
            "D+=x", "read D", "read -r D", "mapfile D", "mapfile -t D", "readarray D", "printf -v D %s x",
            "print -v D x", "vared D", "declare D=$1", "declare -n D=Q", "typeset -n D=Q", "export -n D=Q",
            "local -n D=Q", "builtin export D=$1", "command export D=$1", "command read D", "builtin read D",
            ": ${D:=x}", ": ${D=x}", ": ${D::=x}", ": ${(L)D:=x}", "D[1]=x", "unset D", "getopts a D",
            "read 'D?prompt'", "set -A D x y", "declare -n Q=D", "export -n Q=D", "let D=1",
        ):
            command = f"D=docker; {assign}; $D {self.RESTART} x"
            with self.subTest(assign=assign):
                self.assertBlocked(command)

    def test_the_builtins_behind_a_wrapper_are_matched_by_their_normalized_head(self):
        for command in ("D=docker; command read D; $D x", "D=docker; builtin read D; $D x",
                        "D=docker; command export -n D=Q; $D x", "D=docker; sudo read D; $D x"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        result = analyze("command export D=docker; $D " + self.RESTART + " x")
        self.assertEqual(result.flags, [LIFECYCLE])

    def test_a_use_before_the_first_unconditional_assignment_keeps_the_environment_as_a_value(self):
        for command in ("$D x; D=docker", "if true; then D=docker; fi; $D x", "true && D=docker; $D x",
                        "false || D=docker; $D x", "false || D=docker && $D x", "true && D=docker || $D x",
                        "true && D=docker | cat && $D x", "D=docker & $D x", "D=docker | cat; $D x", "( D=docker ); $D x",
                        "{ D=docker; }; $D x", "f() { D=docker; }; $D x", "while x; do $D y; D=docker; done",
                        "echo $(D=docker) ; $D x"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        for command in ("D=docker; $D x", "D=docker\n$D x", "true; D=docker; $D x", "true & D=docker; $D x",
                        "true && D=docker && $D x", "S=x && D=docker && echo hi && $D x", "a || b && D=docker && $D x",
                        "for D in docker; do $D x; done", "D=docker; f() { $D x; }", "D=docker; if x; then $D y; fi",
                        "X=1 D=docker; $D x"):
            with self.subTest(command=command, ok=True):
                result = analyze(command)
                self.assertNotIn("dynamic_code", result.uncertainty, command)

    def test_the_known_values_of_a_late_use_are_still_read(self):
        result = self.assertBlocked("if x; then D=docker; fi; $D " + self.RESTART + " x")
        self.assertIn(LIFECYCLE, result.flags)

    def test_a_zsh_array_in_the_program_position_joins_its_elements(self):
        result = analyze("D=(docker " + self.RESTART + " x); $D")
        self.assertIn(LIFECYCLE, result.flags)
        self.assertNotIn("unclassified_command", result.flags)
        self.assertIn(LIFECYCLE, analyze("D=(docker compose up); $D a").flags)
        self.assertIn(PUSH, analyze('D=(git push); "${D[@]}"').flags + analyze("D=(git push); ${D[*]}").flags
                      + analyze("D=(git push); ${D}").flags)
        self.assertBlocked("D=(docker $(x)); $D y")
        self.assertBlocked("D=(docker x); D[1]=y; $D")
        self.assertBlocked("D=(a b); ${D[@]}")

    def test_a_change_of_the_word_splitting_makes_split_values_unknown(self):
        value = "docker " + self.RESTART + " x"
        for setup in ("IFS=:", "IFS=", "export IFS=:", "declare IFS=,", "local IFS=x", "read IFS", "unset IFS",
                      "setopt shwordsplit", "setopt sh_word_split", "setopt SH_WORD_SPLIT", "set -o shwordsplit",
                      "emulate sh", "emulate -L ksh", "emulate bash", ": ${IFS:=x}", "typeset IFS=y"):
            command = f"{setup}; D='{value}'; $D"
            with self.subTest(setup=setup):
                result = self.assertBlocked(command)
        for command in ("while IFS= read -r l; do :; done; D=ls; $D x", "IFS=: read a b; D=ls; $D x",
                        "emulate zsh; D=ls; $D x", "setopt extendedglob; D=ls; $D x"):
            with self.subTest(command=command, ok=True):
                self.assertNotBlocked(command)

    def test_b1b_a_head_whose_only_unknown_value_is_a_command_substitution_is_level_a(self):
        for command in ("R=$(which ruff); $R check", "BIN=$(ls -t target | head -1); $BIN runner::", 'R="$(which x)"; "$R" a',
                        "R=`which x`; $R a", "R=ls; R=$(which x); $R a", "R=$(x) ; ${R} a", "R=$(x); sudo $R a",
                        "true && R=$(x) && $R a", "R=$(x)\n$R a"):
            with self.subTest(command=command):
                result = self.assertNotBlocked(command)
                self.assertIn("dynamic_command", result.uncertainty)
                self.assertNotIn("dynamic_code", result.uncertainty)
        result = analyze("R=docker; R=$(x); $R " + self.RESTART + " x")  # the known value still counts
        self.assertEqual(result.flags, [LIFECYCLE])
        self.assertIn("dynamic_command", result.uncertainty)
        values = classifier._known_values(classifier.shell.parse("A=x; B=$(y); C=a$(y)", classifier.shell.Budget(1000)))
        self.assertEqual(values["B"], frozenset({None}))
        self.assertEqual(values["C"], None)
        self.assertEqual(values.soft, frozenset({"B"}))

    def test_b1b_what_stays_level_b_for_a_name_a_substitution_gives(self):
        for command in (
            'R=$(x); bash -c "$R a"', 'R=$(x); eval "$R a"', "R=$(x); git $R", "R=$(x); docker $R x",
            "R=$(x); docker compose $R up", "if x; then R=$(y); fi; $R a", "$R a; R=$(y)", "R=$(x); R+=a; $R a",
            "R=$(x); read R; $R a", "R=$(x); printf -v R %s a; $R a", "R=$(x); declare -n R=Q; $R a",
            "eval x; R=$(y); $R a", "source f; R=$(y); $R a", "R=a$(x); $R a", "R=$(x)b; $R a", "for r in $(ls); do $r a; done",
            "R=$(x); : ${R:=a}; $R a", "R=$(x); IFS=:; $R a", "R=$(x); setopt shwordsplit; $R a", "R=$(x) true; $R a",
            "R=$(x) | cat; $R a", "R=$(x) & $R a", "false || R=$(x); $R a", "R=$(x); bash -c 'echo'; $@",
            "R=$(x); bash -c 'a=1; $R a'", "x=$(y); ./prog <<< \"$x\"",
        ):
            with self.subTest(command=command):
                self.assertBlocked(command)
        self.assertBlocked("for c in a b; do c=$(x); bash -c \"$c\"; done")
        self.assertBlocked("R=$(x); bash -c 'R=$(y); $R a'")  # a head in a code argument is always B

    def test_a_value_with_a_dynamic_directory_names_the_program_by_its_last_component(self):
        for command in ("S=/tmp; X=$S/x.sh; $X a", 'S=/tmp; X="python3 $S/t.py"; $X a', "S=/tmp && X=$S/x.sh && $X a"):
            with self.subTest(command=command):
                self.assertNotBlocked(command)
        self.assertBlocked("S=/tmp; X=$S; $X a")
        self.assertIn(LIFECYCLE, analyze("S=/tmp; X=$S/docker; $X " + self.RESTART + " x").flags)

    def test_a_wrapper_argument_that_is_a_variable_is_the_ambiguity_of_the_readings_not_a_dynamic_name(self):
        for command in ('eval "timeout $a true"', "eval x; timeout $a true", 'bash -c "timeout $a true"',
                        "a=5; eval 'x'; timeout $a true"):
            with self.subTest(command=command):
                result = self.assertNotBlocked(command)
                self.assertEqual(result.uncertainty, ["prefix_readings"])

    def test_a_heredoc_receiver_set_after_its_use_is_not_known(self):
        up = "docker compose up"
        self.assertIn(LIFECYCLE, analyze(f"$PY - <<EOF\n{up}\nEOF\nPY=python3").flags)
        self.assertNotIn(LIFECYCLE, analyze(f"PY=python3; $PY - <<EOF\n{up}\nEOF").flags)
        self.assertIn(LIFECYCLE, analyze(f"if x; then PY=python3; fi; $PY - <<EOF\n{up}\nEOF").flags)

    def test_the_values_of_a_text_reach_a_code_string_in_the_same_state(self):
        """The unknown possibility of a late name goes down with it: the inner text finds its own head dynamic."""
        self.assertBlocked("if x; then D=docker; fi; bash -c \"$D " + self.RESTART + " x\"")
        result = analyze("D=docker; bash -c \"$D " + self.RESTART + " x\"")
        self.assertEqual(result.flags, [LIFECYCLE])
        result = analyze("D=docker bash -c '$D " + self.RESTART + " x'")  # the prefix reaches the shell it starts
        self.assertEqual(result.flags, [LIFECYCLE])

    # -- 5. shell operands -------------------------------------------------------------------------------------

    def test_a_lone_dash_is_the_end_of_the_options_and_the_shell_reads_stdin(self):
        for command in ("echo x | sh -", "echo x | sudo -E bash -", "curl x | bash -", "cat f | zsh -s -", "echo | sh -x -",
                        "printf x | sudo -u root dash -"):
            with self.subTest(command=command):
                self.assertBlocked(command, "piped_shell")
        self.assertEqual(analyze("bash - <<< 'git push'").flags, [PUSH])
        self.assertEqual(analyze("sh - <<< ''").flags, [])
        self.assertEqual(analyze("bash - script.sh").flags, [])
        self.assertNotBlocked("echo x | sh - script.sh")

    def test_c_with_no_operand_under_a_feeder_is_dynamic_code(self):
        for command in ("echo x | xargs sh -c", "xargs bash -c", "xargs -n1 zsh -c", "xargs sudo sh -c",
                        "xargs -I{} sh -c", "xargs -0 -P4 -- dash -c", "ls | xargs env bash -c"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        for command in ("sh -c", "bash -c", "sudo sh -c", "echo x | xargs sh -c 'echo $0'"):
            with self.subTest(command=command, ok=True):
                self.assertNotBlocked(command)

    def test_the_code_argument_table_has_emulate_and_mapfile(self):
        for command in ("emulate zsh -c 'git push'", "emulate -L sh -c 'git push'", "emulate -c 'git push'",
                        "emulate -LRc 'git push'", "mapfile -C 'git push' -c 1 a < f", "readarray -C'git push' a",
                        "mapfile -tC 'git push' a", "sudo emulate sh -c 'git push'", "mapfile -O 1 -C 'git push' a"):
            with self.subTest(command=command):
                self.assertEqual(analyze(command).flags, [PUSH], command)
        for command in ("emulate sh", "emulate -L zsh", "mapfile a", "mapfile -t a", "readarray -c 5 a", "emulate -c"):
            with self.subTest(command=command, ok=True):
                self.assertEqual(analyze(command).flags, [], command)
        self.assertBlocked('emulate sh -c "$X"')
        self.assertBlocked('mapfile -C "$X" a')

    # -- 6. the budget ---------------------------------------------------------------------------------------------

    def test_the_fan_out_of_values_and_code_texts_fails_closed_inside_the_cpu_budget(self):
        import time
        values = " ".join(f"v{j}" for j in range(16))
        command = "; ".join(f'for c{i} in {values}; do bash -c "$c{i} $c{i}"; done' for i in range(120))[:16000]
        began = time.process_time()
        result = analyze(command)
        self.assertLess(time.process_time() - began, 1.0)
        self.assertIn("analysis_budget", result.uncertainty)
        self.assertIn("unclassified_command", result.flags)
        another = "; ".join(f'for a{i} in {values}; do for b{i} in {values}; do git $a{i} $b{i} x; done; done'
                            for i in range(20))[:16000]
        began = time.process_time()
        analyze(another)
        self.assertLess(time.process_time() - began, 1.0)
        began = time.process_time()
        analyze("; ".join(f"x{i}=$x{i}; bash -c '$x{i}'" for i in range(500))[:16000])
        analyze("bash -c 'bash -c \"bash -c x\"';" * 400)
        self.assertLess(time.process_time() - began, 1.0)

    def test_every_text_and_every_value_combination_is_charged(self):
        budget = classifier.shell.Budget(10 ** 6)
        classifier.analyze_command('for c in a b c; do bash -c "$c x"; done', _budget=budget)
        used = 10 ** 6 - budget.left
        self.assertGreaterEqual(used, classifier.TEXT_COST * 4 + classifier.VARIANT_COST * 3)  # the text and its three code texts
        tight = classifier.shell.Budget(classifier.TEXT_COST * 3)
        result = classifier.analyze_command("bash -c 'bash -c \"bash -c x\"'", _budget=tight)
        self.assertEqual(result.uncertainty, ["analysis_budget"])
        self.assertEqual(result.flags, ["unclassified_command"])


class ReviewFixB2(unittest.TestCase):
    """Review-fix round, part B2 (audit-shell-lexer): here-strings on compounds and inner readers, functions that
    forward their arguments, interpreter launchers and SQL / DSL clients as receivers, `NAME=$(cat <<'EOF')`,
    every reading of a receiver, git aliases given on the command line, docker global options and management
    commands, and the xargs canary. Blocked words are built from pieces; nothing runs."""

    RESTART = "re" + "start"
    DOWN = "docker restart x".replace("restart", "re" + "start")

    def assertBlocked(self, command, reason="dynamic_code"):
        result = analyze(command)
        self.assertIn("unclassified_command", result.flags, command)
        self.assertIn(reason, result.uncertainty, command)
        return result

    def assertNotBlocked(self, command):
        result = analyze(command)
        self.assertNotIn("unclassified_command", result.flags, command)
        return result

    # -- 1. here-strings ---------------------------------------------------------------------------------------

    def test_a_here_string_on_a_compound_or_an_inner_reader_is_code(self):
        for command in (
            "{ bash; } <<< 'git push'", "( sh ) <<< 'git push'", "bash -c bash <<< 'git push'",
            "sh -c '. /dev/stdin' <<< 'git push'", "bash /dev/fd/3 3<<<'git push'", "exec 0<<<'git push'; bash",
            "f() { bash; }; f <<< 'git push'", "{ cat; bash; } <<< 'git push'", "{ bash; } <<< 'g'\"it push\"",
            "if true; then bash; fi <<< 'git push'", "while read x; do bash; done <<< 'git push'",
            "{ { bash; }; } <<< 'git push'", "for i in 1; do sh; done <<< 'git push'",
            "bash - <<< 'git push'", "sudo bash <<< 'git push'",
        ):
            with self.subTest(command=command):
                self.assertIn(PUSH, analyze(command).flags)
        self.assertIn(LIFECYCLE, analyze("{ bash; } <<< '" + self.DOWN + "'").flags)

    def test_a_here_string_handed_to_data_is_not_read_as_code(self):
        for command in ("cat <<< 'git push'", "python3 - <<< 'print(1)'", "jq . <<< '{\"a\": 1}'",
                        "read -r a b <<< 'git push'", "grep push <<< 'git push'",
                        "x=$(foo); jq -c .Env <<<\"$x\"", "x=$(foo); grep a <<< \"$x\"",
                        "x=$(foo); while read l; do echo \"$l\"; done <<< \"$x\"", "x=$(foo); { cat; } <<< \"$x\""):
            with self.subTest(command=command):
                result = self.assertNotBlocked(command)
                self.assertNotIn(PUSH, result.flags)

    def test_a_here_string_that_a_filter_may_run_as_its_program_is_code(self):
        """`sed -f -` and `awk -f /dev/stdin` read their program from the here-string (and `dc` is not a filter)."""
        for command in ("awk -f - <<< 'git push'", "sed -f /dev/stdin x <<< 'git push'", "gawk --file=- <<< 'git push'",
                        "dc <<< 'git push'"):
            with self.subTest(command=command):
                self.assertIn(PUSH, analyze(command).flags)
        self.assertBlocked("awk -f - <<< 'BEGIN{system(\"x\")}'", "lex_error")  # not shell: level B, never a pass
        for command in ("awk '{print $1}' <<< 'git push'", "sed -E 's/a/b/' <<< 'git push'"):
            with self.subTest(command=command):
                self.assertNotIn(PUSH, analyze(command).flags)

    def test_a_here_string_that_cannot_be_known_goes_to_a_reader_at_level_b(self):
        for command in ("x=$(foo); { bash; } <<< \"$x\"", "bash <<< \"$X\"", "x=$(foo); ./prog <<< \"$x\"",
                        "x=$(foo); f() { sh; }; f <<< \"$x\""):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_a_body_that_a_reader_runs_and_an_expansion_makes_is_level_b(self):
        """`bash <<EOF` / `{ bash; } <<< "$(cmd)"`: the output of the substitution is the program the shell runs."""
        make = "$(echo 'g''it push')"
        for command in (f"{{ bash; }} <<< \"{make}\"", f"bash <<EOF\n{make}\nEOF", f"{{ bash; }} <<EOF\n{make}\nEOF",
                        f"at now <<< \"{make}\"", f"f() {{ sh; }}; f <<< \"{make}\"", f"bash <<< \"{make}\"",
                        f"x=$(foo); { '{' } sh; {'}'} <<< \"$x\"", f"sudo bash <<< \"{make}\""):
            with self.subTest(command=command):
                self.assertBlocked(command)
        for command in (f"cat <<EOF\n{make}\nEOF", f"cat <<< \"{make}\"", f"grep a <<< \"{make}\"",
                        f"psql <<EOF\nselect 1;\nEOF"):
            with self.subTest(command=command):
                self.assertNotBlocked(command)

    def test_a_heredoc_on_a_function_call_or_compound_keeps_the_receiver_rule(self):
        self.assertIn(PUSH, analyze("f() { bash; }; f <<EOF\ngit push\nEOF").flags)
        self.assertIn(PUSH, analyze("{ bash; } <<EOF\ngit push\nEOF").flags)
        self.assertEqual(analyze("cat <<EOF\ngit push\nEOF").flags, [])

    # -- 2. functions that forward their arguments -----------------------------------------------------------

    def test_a_function_that_forwards_its_arguments_is_classified_with_the_call_arguments(self):
        for command, flag in (
            (f"f() {{ \"$@\"; }}; f docker {self.RESTART} x", LIFECYCLE),
            (f"f() {{ \"$@\"; }}\nf docker {self.RESTART} x", LIFECYCLE),
            ("function f { \"$@\"; }; f git push", PUSH),
            ("g() { git -C repo \"$@\"; }; g commit -m x", COMMIT),
            (f"d() {{ docker \"$@\"; }}\nd {self.RESTART} x", LIFECYCLE),
            ("d() { docker compose \"$1\" api; }; d stop", LIFECYCLE),
            ("f() { sudo \"$@\"; }; f docker rm x", LIFECYCLE),
            ("f() { \"$1\" restart \"$2\"; }; f docker x", LIFECYCLE),
            (f"f() {{ \"$@\"; }}; f \"docker {self.RESTART}\" x", LIFECYCLE),
            ("P() { docker exec pihole \"$@\"; }; P pihole-FTL --config x", LIFECYCLE),
            ("m() { curl -s \"https://repo.example/$1/x\"; }; m a/b", EXTERNAL),
        ):
            with self.subTest(command=command):
                self.assertIn(flag, analyze(command).flags)

    def test_a_function_that_forwards_is_level_b_only_when_a_call_cannot_be_resolved(self):
        """Revised by the user (round D1): the definition alone is not level B and each call is classified with its
        arguments; a call whose arguments are not known is (the cases that pass are in `ReviewFixD1`)."""
        for command in ("run() { echo \"+ $*\"; \"$@\"; }; run \"$cmd\" a", "f() { \"$@\"; }; f $X"):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_a_function_that_only_uses_its_arguments_as_data_is_not_a_finding(self):
        for command in ("log() { echo \"$1\"; }; log 'git push done'", "n() { wc -l \"$1\"; }; n a.txt"):
            with self.subTest(command=command):
                self.assertNotBlocked(command)
                self.assertEqual(analyze(command).flags, [])

    def test_the_positional_parameters_are_replaced_by_the_arguments(self):
        text = classifier._positional_text
        self.assertEqual(text('{ "$@"; }', ["docker", "ps", "-a"]), "{ docker ps -a; }")
        self.assertEqual(text('{ git -C r "$1" "${2}"; }', ["log", "-n1"]), "{ git -C r log -n1; }")
        self.assertEqual(text("{ echo '$1' $1 \"x$1\"; }", ["a"]), "{ echo '$1' a \"xa\"; }")
        self.assertEqual(text("{ x $3; }", ["a"]), "{ x ; }")
        self.assertEqual(text("{ x ${@} $*; }", ["a", "b"]), "{ x a b a b; }")
        self.assertEqual(text("{ x \\$1; }", ["a"]), "{ x \\$1; }")
        # unquoted: the shell splits the argument into words, so the quotes of the call do not keep it whole
        self.assertEqual(text("{ $1 $@; }", ["'docker restart'", "x"], ["docker restart", "x"]),
                         "{ docker restart docker restart x; }")
        self.assertEqual(text('{ "$1"; }', ["'docker restart'"], ["docker restart"]), "{ 'docker restart'; }")
        self.assertIn(LIFECYCLE, analyze(f"f() {{ $@; }}; f '{self.DOWN}'").flags)
        self.assertIn(LIFECYCLE, analyze(f"f() {{ $1 x; }}; f 'docker {self.RESTART}'").flags)
    def test_the_calls_of_forwarding_functions_are_bounded(self):
        command = "f() { \"$@\"; }; " + "; ".join(f"f echo {i}" for i in range(40))
        result = self.assertBlocked(command, "analysis_budget")
        self.assertLess(len(result.uncertainty), 8)

    # -- 3. launchers and query clients as receivers ----------------------------------------------------------

    def test_an_interpreter_behind_a_launcher_is_a_foreign_receiver(self):
        for launcher in ("uv run", "uv run --with x", "uv run --python 3.12 --no-sync", "poetry run", "pdm run",
                         "hatch run", "pipenv run", "rye run", "conda run -n env", "conda run --no-capture-output -n e",
                         "uv --quiet run", "poetry run --"):
            command = launcher + " python - <<'EOF'\nprint(\"it's\")\nEOF"
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual(result.flags, [], command)
                self.assertNotIn("lex_error", result.uncertainty)

    def test_a_shell_or_a_program_behind_a_launcher_still_classifies(self):
        for command, flag in (
            ("uv run bash -c 'git push'", PUSH), (f"uv run docker {self.RESTART} x", LIFECYCLE),
            (f"poetry run docker {self.RESTART} x", LIFECYCLE), (f"conda run -n env docker {self.RESTART} x", LIFECYCLE),
            ("pipenv run git push", PUSH), ("rye run git push", PUSH), ("pdm run sh -c 'git push'", PUSH),
            (f"uv --quiet run --no-sync docker {self.RESTART} x", LIFECYCLE),
            (f"conda run -n env bash <<'EOF'\n{self.DOWN}\nEOF", LIFECYCLE),
            (f"uv run bash <<'EOF'\n{self.DOWN}\nEOF", LIFECYCLE),
        ):
            with self.subTest(command=command):
                self.assertIn(flag, analyze(command).flags)

    def test_a_launcher_without_run_is_the_command(self):
        for command in ("uv sync", "uv", "uv pip install x", "poetry install", "conda install x", "hatch build"):
            with self.subTest(command=command):
                self.assertEqual(analyze(command).uncertainty, [])
                self.assertEqual(classifier._prefix_steps(command.split(), 0), [])

    def test_the_flags_of_the_launchers_are_read_with_their_grammar(self):
        steps = classifier._prefix_steps
        self.assertEqual(steps("uv run --with x python -".split(), 0), [4])
        self.assertEqual(steps("uv --quiet run --no-sync python".split(), 0), [4])
        self.assertEqual(steps("conda run -n env python".split(), 0), [4])
        self.assertEqual(steps("poetry run -- python".split(), 0), [3])
        self.assertEqual(steps("uv run".split(), 0), [2])
        self.assertEqual(len(steps("uv run --frobnicate python".split(), 0)), 2)  # an unknown flag: both ways
        for name in ("uv", "poetry", "pdm", "hatch", "pipenv", "rye", "conda"):
            self.assertIn(name, classifier.KNOWN_HEADS)
        self.assertEqual(analyze("/usr/bin/uv run pytest tests/test_a.py").categories, ["test-narrow"])

    def test_a_launcher_with_an_unknown_flag_reads_the_body_as_shell(self):
        result = analyze("uv run --frobnicate python - <<'EOF'\nprint(\"it's\")\nEOF")
        self.assertIn("prefix_readings", result.uncertainty)  # the strictest reading wins: not every one is Python

    def test_a_launched_python_test_run_is_a_test_run(self):
        self.assertEqual(analyze("uv run python -m pytest").categories, ["test-full"])
        self.assertEqual(analyze("uv run pytest tests/test_a.py").categories, ["test-narrow"])

    def test_a_query_client_reads_its_body_as_a_query(self):
        for command in ("sqlite3 db <<'EOF'\nselect it's;\nEOF", "psql <<'EOF'\nselect 'x';\nEOF",
                        "mysql -u root <<'EOF'\nselect 1;\nEOF", "mariadb <<'EOF'\nselect 1;\nEOF",
                        "cypher-shell -u n <<'EOF'\nMATCH (n) RETURN n;\nEOF", "sqlite3 db <<< \"select 'it''s'\"",
                        "uv run sqlite3 db <<'EOF'\nselect 1;\nEOF", "/usr/bin/psql <<'EOF'\nselect \"it's\n;\nEOF"):
            with self.subTest(command=command):
                self.assertEqual(analyze(command).flags, [], command)

    def test_a_query_that_asks_the_client_to_run_a_command_is_level_b(self):
        for command in ("sqlite3 db <<'EOF'\nselect 1;\n.shell " + self.DOWN + "\nEOF",
                        "sqlite3 db <<'EOF'\n.system ls\nEOF", "sqlite3 db <<'EOF'\n.once |cat\nEOF",
                        "psql <<'EOF'\n\\! " + self.DOWN + "\nEOF", "psql <<'EOF'\nselect 1 \\g |cat\nEOF",
                        "psql <<'EOF'\n\\o |cat\nEOF", "mysql <<'EOF'\nsystem ls\nEOF", "mysql <<'EOF'\n\\! ls\nEOF",
                        "psql -c '\\! " + self.DOWN + "'", "sqlite3 db '.shell ls'", "mysql -e 'system ls'",
                        "sqlite3 db <<< '.shell ls'", "uv run psql <<'EOF'\n\\! ls\nEOF"):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_a_plain_query_argument_is_not_an_escape(self):
        for command in ("psql -c 'select 1 || 2'", "sqlite3 db 'select 1;'", "mysql -e 'show tables'",
                        "psql <<'EOF'\nselect 'a\\nb' || x from t;\nEOF"):
            with self.subTest(command=command):
                self.assertNotBlocked(command)

    def test_the_receiver_is_foreign_only_when_every_reading_is(self):
        """`sudo -x python3 bash <<EOF`: the unknown flag may take `python3` as its value, then `bash` is the
        program and the body is its script. The strictest reading wins."""
        command = f"sudo -x python3 bash <<EOF\n{self.DOWN}\nEOF"
        self.assertIn(LIFECYCLE, analyze(command).flags)
        self.assertEqual(analyze("sudo python3 - <<'EOF'\nprint(\"it's\")\nEOF").flags, [])
        readings = classifier.command_readings("sudo -x python3 bash")
        self.assertIsNone(classifier._foreign_receiver(readings, lambda: {}))
        self.assertEqual(classifier._foreign_receiver(classifier.command_readings("python3 -"), lambda: {}), "interpreter")
        self.assertEqual(classifier._foreign_receiver(classifier.command_readings("psql -d x"), lambda: {}), "query")
        self.assertEqual(classifier._foreign_receiver(classifier.command_readings("uv run python3 -"), lambda: {}), "interpreter")
        values = {"P": frozenset({"python3", "psql"}), "Q": frozenset({"python3", None}), "R": frozenset({"bash"})}
        self.assertEqual(classifier._foreign_receiver(classifier.command_readings("$P -"), lambda: values), "query")
        self.assertIsNone(classifier._foreign_receiver(classifier.command_readings("$Q -"), lambda: values))
        self.assertIsNone(classifier._foreign_receiver(classifier.command_readings("$R -"), lambda: values))

    # -- 4. NAME=$(cat <<'EOF' ... EOF) -----------------------------------------------------------------------

    def test_a_lone_cat_heredoc_that_is_a_whole_assignment_value_is_data(self):
        for command in ("BODY=$(cat <<'EOF'\nit's a `doc` $(x\nEOF\n); gh pr create --body \"$BODY\"",
                        "BODY=\"$(cat <<'EOF'\nit's a `doc`\nEOF\n)\"; echo \"$BODY\"",
                        "local BODY=$(cat <<'EOF'\nit's\nEOF\n)", "export B=$(cat <<'EOF'\nit's\nEOF\n)",
                        "BODY=$(cat <<-'EOF'\n\tit's\n\tEOF\n)", "BODY=$(cat <<'EOF'\nit's\nEOF\n) env"):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertNotIn("lex_error", result.uncertainty, command)
                self.assertEqual(result.flags, [], command)

    def test_a_cat_heredoc_that_is_not_a_whole_assignment_value_stays_code(self):
        for command in ("BODY=$(cat > f <<'EOF'\nit's\nEOF\n)", "echo $(cat <<'EOF'\nit's\nEOF\n)",
                        "BODY=x$(cat <<'EOF'\nit's\nEOF\n)", "BODY=$(cat -n <<'EOF'\nit's\nEOF\n)",
                        "BODY=$(cat <<'EOF' | tr a b\nit's\nEOF\n)", "A=$(cat <<'EOF'\nit's\nEOF\n; x)"):
            with self.subTest(command=command):
                self.assertIn("lex_error", analyze(command).uncertainty, command)

    def test_a_cat_value_that_reaches_a_head_or_a_code_string_is_classified(self):
        body = "git push"
        for command, flag in ((f"BODY=$(cat <<'EOF'\n{self.DOWN}\nEOF\n); $BODY", LIFECYCLE),
                              (f"BODY=$(cat <<'EOF'\n{body}\nEOF\n); bash -c \"$BODY\"", PUSH),
                              (f"BODY=$(cat <<'EOF'\n{body}\nEOF\n); zsh -c \"$BODY\"", PUSH)):
            with self.subTest(command=command):
                self.assertIn(flag, analyze(command).flags)
        self.assertBlocked(f"BODY=$(cat <<'EOF'\n{body}\nEOF\n); eval \"$BODY\"")
        self.assertEqual(analyze(f"BODY=$(cat <<'EOF'\n{body}\nEOF\n); echo \"$BODY\"").flags, [])
        # an unquoted delimiter: the body has expansions, so the value is not known (the substitutions are commands)
        self.assertIn(LIFECYCLE, analyze(f"BODY=$(cat <<EOF\n$({self.DOWN})\nEOF\n)").flags)

    # -- 6. git aliases ----------------------------------------------------------------------------------------

    def test_a_git_alias_given_on_the_command_line_is_the_command_it_expands_to(self):
        for command, flag in (
            ("git -c alias.p=push p", PUSH), ("git -c alias.c=commit c -m x", COMMIT),
            ("git -c alias.a=b -c alias.b=push a", PUSH), ("git -c alias.P=push p", PUSH),
            ("git -c alias.p='push --force' p", PUSH), ("sudo git -c alias.p=push p", PUSH),
            ("PV=push git --config-env=alias.p=PV p", PUSH), ("git --config-env alias.p=PV p", None),
            ("GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.p GIT_CONFIG_VALUE_0=push git p", PUSH),
            ("GIT_CONFIG_PARAMETERS=\"'alias.p=push'\" git p", PUSH),
            ("export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.p GIT_CONFIG_VALUE_0=commit; git p", COMMIT),
            ("git -c alias.p='!" + self.DOWN + "' p", LIFECYCLE),
            ("git -c alias.p='!docker " + self.RESTART + "' p x", LIFECYCLE),
            ("git -c alias.p='!git push' p", PUSH),
            ("git -c alias.p=push -C d p", PUSH),
        ):
            with self.subTest(command=command):
                result = analyze(command)
                if flag is None:  # the variable's value is not known: level B
                    self.assertBlocked(command)
                else:
                    self.assertIn(flag, result.flags)

    def test_a_git_alias_that_cannot_be_known_is_level_b(self):
        for command in ("git -c \"$K=push\" p", "git -c alias.p=$V p", "export GIT_CONFIG_COUNT=$N; git p",
                        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.p git p"):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_git_configuration_that_is_not_an_alias_is_not_a_finding(self):
        for command in ("git -c user.name=x status", "git -c alias.s=status s", "git -c core.pager=cat log",
                        "git -c color.ui=always diff", "git -c alias.l='log --oneline' l",
                        "git -c alias.a=a a"):  # (an alias loop is an error of git, not a command)
            with self.subTest(command=command):
                result = self.assertNotBlocked(command)
                self.assertEqual(result.flags, [], command)

    def test_the_git_walk_finds_the_subcommand_and_the_configuration(self):
        verbs, configs = classifier._git_walk(["-c", "alias.p=push", "--config-env=alias.q=V", "-C", "d", "p"])
        self.assertEqual(verbs, [5])
        self.assertEqual(sorted(configs), [(0 + 1, False, False), (2, True, True)])
        self.assertTrue(classifier._git_has_subcommand(["-c", "x=commit", "commit"], "commit"))
        self.assertFalse(classifier._git_has_subcommand(["log", "--grep", "commit"], "commit"))

    # -- 7. docker global options and management commands -----------------------------------------------------

    def test_docker_global_options_and_management_commands_classify_like_the_short_forms(self):
        for command in (
            "docker --context x restart y", "docker -H tcp://h:2375 restart y", "docker -H h restart y",
            "docker -Hh restart y", "docker --host=h restart y", "docker container restart y",
            "docker container rm y", "docker container stop a b", "docker container kill a", "docker container start a",
            "docker container create i", "docker container run i", "docker container exec c sh",
            "docker --context x container restart y", "docker -D --tls restart y", "docker --config d --log-level debug stop y",
            "docker compose --project-name p -f f restart", "docker compose -p p down",
            "docker compose --project-directory d down", "docker compose --ansi never down",
            "docker --context c compose -f f.yml up -d", "docker-compose -p p down", "docker-compose --ansi never restart",
            "docker-compose --project-directory d -f f up", "docker compose --profile a --env-file e kill",
            "docker compose --parallel 2 --progress plain pull", "docker compose --dry-run rm", "sudo docker --context x rm y",
            "docker compose -H h run svc", "docker --context x compose exec svc sh", "docker-compose -f a -f b create",
        ):
            with self.subTest(command=command):
                self.assertEqual(analyze(command).flags, [LIFECYCLE], command)

    def test_docker_reads_and_builds_through_the_same_options(self):
        self.assertEqual(analyze("docker --context x ps").categories, ["docker-read"])
        self.assertEqual(analyze("docker container ls").categories, ["docker-read"])
        self.assertEqual(analyze("docker container logs c").categories, ["docker-read"])
        self.assertEqual(analyze("docker --tls compose -f a.yml logs web").categories, ["docker-read"])
        self.assertEqual(analyze("docker-compose -p p ps").categories, ["docker-read"])
        self.assertEqual(analyze("docker image build .").flags, ["docker_build"])
        self.assertEqual(analyze("docker --context x build .").flags, ["docker_build"])

    def test_a_docker_option_that_is_not_known_is_read_both_ways(self):
        result = analyze("docker --frobnicate restart x")
        self.assertEqual(result.flags, [LIFECYCLE])
        self.assertIn("prefix_readings", result.uncertainty)
        self.assertEqual(analyze("docker --frobnicate=1 restart x").flags, [LIFECYCLE])

    def test_a_dynamic_verb_after_a_management_word_is_level_b(self):
        for command in ("docker container $v y", "docker --context x $v y", "docker compose -p p $v"):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_the_docker_forms_are_bounded(self):
        command = "docker " + " ".join(f"--unknown{i}" for i in range(200)) + " " + self.RESTART
        result = analyze(command)
        self.assertLessEqual(len(classifier._docker_forms(["docker"] + ["--u"] * 200 + [self.RESTART])), classifier.MAX_DOCKER_FORMS)
        self.assertIn(LIFECYCLE, result.flags)

    # -- 8. the xargs canary ------------------------------------------------------------------------------------

    def test_the_canary_sees_a_program_reached_through_xargs_without_a_literal_verb(self):
        for command in (f"echo {self.RESTART} x | xargs docker", "echo push | xargs git", "echo x | xargs -n1 docker",
                        "find . -exec git status \\;", "parallel docker ::: x", "echo x | sudo xargs git",
                        "echo x | xargs docker compose"):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertIn("deny_token_unmatched", result.uncertainty, command)
                self.assertNotIn("unclassified_command", result.flags)  # a record, never a decision (user decision)

    def test_the_canary_is_quiet_when_nothing_is_fed(self):
        for command in ("docker ps", "git status", "echo docker | cat", "xargs echo", "find . -name x"):
            with self.subTest(command=command):
                self.assertNotIn("deny_token_unmatched", analyze(command).uncertainty)

    # -- 9. standards: the module's own names ------------------------------------------------------------------

    def test_the_hook_uses_the_names_of_the_parser_module(self):
        self.assertIs(classifier._DYNAMIC_PART_KINDS, classifier.shell.DYNAMIC_KINDS)
        self.assertEqual(classifier._DECLARE_BUILTINS, classifier.shell.DECLARE_BUILTINS)
        for name in ("_part_scripts", "_compounds"):
            self.assertFalse(hasattr(classifier, name), name)
        script = classifier.shell.parse("f() { (x); }; for i in 1; do { y; }; done", classifier.shell.Budget(10 ** 5))
        self.assertEqual(sorted(c.kind for c in classifier.shell.iter_compounds(script)),
                         ["for", "function", "group", "group", "subshell"])
        part = classifier.shell.parse("echo $(a $(b))", classifier.shell.Budget(10 ** 5)).pipelines[0].commands[0].words[1].parts[0]
        self.assertEqual(len(list(classifier.shell.part_scripts(part))), 1)


class ReviewFixD1(unittest.TestCase):
    """Final review-fix round, part D1 (audit-shell-lexer): the findings of the second review (security H1-H4, M1-M4,
    L1, L2; code majors 1-3 and minors), the PS4 false positive and the forwarding functions decided by the user.
    Blocked words are built from pieces; every text is only analyzed, nothing runs."""

    RESTART = "re" + "start"
    DOWN = "dow" + "n"

    def assertBlocked(self, command, reason="dynamic_code"):
        result = analyze(command)
        self.assertIn("unclassified_command", result.flags, command)
        self.assertIn(reason, result.uncertainty, command)
        return result

    def assertNotBlocked(self, command):
        result = analyze(command)
        self.assertNotIn("unclassified_command", result.flags, command)
        return result

    # -- H1: docker forms ---------------------------------------------------------------------------------------

    def test_h1_docker_short_option_clusters_are_read_like_pflag_reads_them(self):
        for options in ("-Dl info", "-Dl=info", "-lcrit", "-Dlcrit", "-D", "-Dc ctx", "-H h -Dl info", "-vD"):
            command = f"docker {options} {self.RESTART} x"
            with self.subTest(command=command):
                self.assertEqual(analyze(command).flags, [LIFECYCLE], command)
        texts = classifier.command_readings(f"docker -Dl info -Dl info {self.RESTART} x").texts
        self.assertEqual(texts, [f"docker {self.RESTART} x"])  # one reading: no ambiguity left

    def test_h1_docker_forms_over_the_cap_are_level_b_not_truncated(self):
        command = "docker " + " ".join(f"-x a{i}" for i in range(10)) + f" $'\\x72estart' x"
        self.assertBlocked(command, "readings_cap")
        self.assertBlocked("docker " + " ".join(f"-Dx a{i}" for i in range(12)) + f" {self.RESTART} x", "readings_cap")
        with self.assertRaises(classifier._FormsCap):
            classifier._docker_forms(["docker"] + ["--u"] * 40 + ["-x", "a"] * 12 + [self.RESTART])
        self.assertEqual(classifier.command_readings(command).reasons, frozenset({"readings_cap"}))

    # -- H2, H3: names the data rules trust ---------------------------------------------------------------------

    def test_h2_a_function_named_like_a_reader_or_a_sink_loses_the_data_exemption(self):
        for command in ("jq() { bash; }; jq <<< 'g''it push'", "function sed { sh; }; sed <<< 'g''it push'",
                        "read() { sh; }; read <<< 'g''it push'", "grep() { bash; }; grep x <<< 'git push'",
                        "python3() { bash; }; python3 <<'EOF'\ngit push\nEOF", "psql() { sh; }; psql <<< 'git push'",
                        "cat() { bash; }; cat <<'EOF'\ngit push\nEOF", "node() { sh; }; node - <<< 'git push'"):
            with self.subTest(command=command):
                self.assertIn(PUSH, analyze(command).flags)
        self.assertNotIn(PUSH, analyze("jq . <<< 'git push'").flags)  # the program itself stays data

    def test_h3_hash_enable_and_path_disqualify_the_data_exemptions(self):
        body = "\ncat <<'EOF'\ng''it push\nEOF"
        for prefix in ("hash -p /bin/bash cat;", "hash cat=/bin/bash;", "hash -p /bin/sh cat; true;",
                       "enable -f /tmp/x.so cat;", "PATH=/tmp/x:$PATH;", "export PATH=/tmp/x:$PATH;",
                       "PATH=/tmp/x cat <<'EOF'\ng''it push\nEOF\n:;"):
            command = prefix + body if "cat <<" not in prefix else prefix
            with self.subTest(command=command):
                self.assertIn(PUSH, analyze(command).flags)
        for command in ("hash -p /bin/bash jq; jq . <<< 'g''it push'", "hash jq=/bin/bash; jq . <<< 'git push'",
                        "path=(/tmp/x $path); jq . <<< 'git push'"):
            with self.subTest(command=command):
                self.assertIn(PUSH, analyze(command).flags)
        self.assertEqual(analyze("hash -r; cat > f <<'EOF'\ngit push\nEOF").flags, [])  # a plain `hash` rebinds nothing

    def test_h3_a_rebinding_covers_only_the_commands_it_reaches(self):
        """The commands before the rebinding, a subshell or a command of its own keep their names, so a `PATH` set for
        `mvnw` or a rebinding after the body does not turn a Python heredoc into shell."""
        body = "python3 - <<'EOF'\nimport sys\np = sys.argv[1]\nEOF\n"
        for command in (body + "export PATH=/x:$PATH\n", "PATH=/x ./mvnw verify\n" + body, "(PATH=/x; true)\n" + body,
                        "x=$(PATH=/y true)\n" + body, "true | PATH=/x true\n" + body, "hash -r\n" + body):
            with self.subTest(command=command):
                self.assertNotBlocked(command)
        for command in ("export PATH=/x:$PATH\ncat <<'EOF'\ngit push\nEOF", "PATH=/x cat <<'EOF'\ngit push\nEOF",
                        "for i in 1 2; do cat <<'EOF'\ngit push\nEOF\nPATH=/x; done",
                        "hash -p /bin/bash cat\ncat <<'EOF'\ngit push\nEOF", "cat() { bash; }\ncat <<'EOF'\ngit push\nEOF"):
            with self.subTest(command=command):
                self.assertIn(PUSH, analyze(command).flags, command)
        self.assertNotIn(PUSH, analyze("cat <<'EOF'\ngit push\nEOF\nexport PATH=/x:$PATH").flags)
        self.assertNotIn(PUSH, analyze("(PATH=/x; true)\ncat <<'EOF'\ngit push\nEOF").flags)

    # -- H4, code major 1: parameter operators in the head -------------------------------------------------------

    def test_h4_the_operator_word_of_a_head_expansion_is_classified(self):
        for command, flag in (
            (f"${{PWD:+docker}} {self.RESTART} x", LIFECYCLE), (f"${{R:-docker}} {self.RESTART} x", LIFECYCLE),
            (f"R=$(true); ${{R:-docker}} {self.RESTART} x", LIFECYCLE), ("${HOME:+git} $'\\x70ush'", PUSH),
            (f"${{PWD/*/docker}} {self.RESTART} x", LIFECYCLE), (f"\"${{NOPE:-docker}}\" {self.RESTART} x", LIFECYCLE),
            (f"${{NOPE:+}} docker {self.RESTART} y", LIFECYCLE), (f"${{X:=docker}} {self.RESTART} x", LIFECYCLE),
            (f"${{1:-docker}} {self.RESTART} y", LIFECYCLE), ("${A:-git} push", PUSH), ("/usr/bin/${A:-git} push", PUSH),
            ("${A-git} push", PUSH), ("${A//x/git} push", PUSH),
        ):
            with self.subTest(command=command):
                self.assertIn(flag, analyze(command).flags)

    def test_h4_a_head_operator_that_cannot_be_known_is_level_b(self):
        for command in ("${X%.sh} y", "${X^^} y", "${X:1:3} y", "${X:-$Y} y", "${X:-$(cmd)} y", "${X@Q} y", "${!X} y",
                        "${A:-x}${B%y} z", "${X/a/$Y} z"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        for command in ("${HOME}/bin/tool x", "${X:-/usr/bin}/ls -la", "echo ${X:-a}", "${#X}"):
            with self.subTest(command=command):
                self.assertNotBlocked(command)

    def test_major1_a_slash_inside_an_expansion_is_not_a_path_separator(self):
        for command in (f"X=lsocker; \"${{X/ls/d}}\" {self.RESTART} y", f"X=lsocker; Y=${{X/ls/d}}; $Y {self.RESTART} y",
                        "X=lsocker; ${X/ls/d} y", "\"${X%/*}\" y", "\"${A//\\//-}\" y"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        self.assertEqual(classifier._path_tail("${X/a/b}"), "${X/a/b}")
        self.assertEqual(classifier._path_tail("a/${X/a/b}/c"), "c")
        self.assertEqual(classifier._path_tail("$(x/y)/z"), "z")
        self.assertEqual(classifier._path_tail("${X%/*}"), "${X%/*}")

    # -- M1, code major 3: git aliases and GIT_CONFIG_PARAMETERS ---------------------------------------------------

    def test_m1_alias_values_are_split_and_dequoted_like_git_does(self):
        for command in ("git -c \"alias.p='push'\" p", "git -c \"alias.p=pu''sh\" p", "git -c alias.p=pu\\\\sh p",
                        "git -c 'alias.p=\"push\" --force' p", "git -c alias.p=\"p\"ush p", "git -c 'alias.p=!git push' p"):
            with self.subTest(command=command):
                self.assertIn(PUSH, analyze(command).flags)
        self.assertEqual(classifier._split_cmdline("'a b' \"c d\" e\\ f g''h"), ["a b", "c d", "e f", "gh"])
        self.assertEqual(classifier._split_cmdline(""), [])
        for bad in ("'open", "\"open", "x\\", "'a\\b'"):
            self.assertIsNone(classifier._split_cmdline(bad), bad)
        self.assertBlocked("git -c \"alias.p='push\" p")  # a quote that does not close: git refuses it or reads it its way

    def test_m1_both_forms_of_git_config_parameters_are_read(self):
        for value in ("'alias.p=push'", "'alias.p'='push'", "'core.x=1' 'alias.p'='push'", "'alias.p'='pu'\\''sh'"):
            command = f"GIT_CONFIG_PARAMETERS=\"{value}\" git p"
            if value.endswith("\\''sh'"):
                continue  # (the escaped quote form is covered by `_config_parameters` below)
            with self.subTest(command=command):
                self.assertIn(PUSH, analyze(command).flags)
        self.assertEqual(classifier._config_parameters("'a.b=c' 'd'='e f' 'g'"), ([("a.b", "c"), ("d", "e f"), ("g", "")], False))
        self.assertEqual(classifier._config_parameters("'k'='it'\\''s'"), ([("k", "it's")], False))
        for bad in ("x", "'a'=b", "'a' x", "'open"):
            self.assertTrue(classifier._config_parameters(bad)[1], bad)
        self.assertBlocked("GIT_CONFIG_PARAMETERS=\"'alias.p'=x\" git p")

    # -- M2: brace heads --------------------------------------------------------------------------------------

    def test_m2_quoted_and_decoded_elements_of_a_brace_head_are_resolved(self):
        for command, flag in (("{'git',push}", PUSH), ('""{git,push}', PUSH), ("{git,$'\\x70ush'}", PUSH),
                              ('{g""it,push}', PUSH), ('{"git",push}', PUSH), ("sudo {'git',push}", PUSH),
                              (f"{{docker,{self.RESTART}}} x", LIFECYCLE), (f"{{'docker',\"{self.RESTART}\"}} x", LIFECYCLE)):
            with self.subTest(command=command):
                self.assertEqual(analyze(command).flags, [flag], command)
        def word(text):
            return classifier.shell.parse(text, classifier.shell.Budget(10 ** 5)).pipelines[0].commands[0].words[0]
        self.assertEqual(classifier._brace_words(word("{'a,b',c}")), ["a,b", "c"])
        self.assertEqual(classifier._brace_words(word("{'{a}',b}")), ["{a}", "b"])
        self.assertIsNone(classifier._brace_words(word("{$X,b}")))

    def test_m2_a_brace_head_that_cannot_be_resolved_is_level_b(self):
        for command in ("{1..3} x", "x{a..c}", "{$X,y} z", "{a,$(c)} z", "{a,b}$X z", "{git,push}{1..2}", "${X}{a,b}"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        for command in ("echo {a,b}", "ls {a,\"b\"}", "echo '{a,b}'", "'{git,push}'"):
            with self.subTest(command=command):
                self.assertNotBlocked(command)

    # -- M3, L2: subscript contexts and taint ------------------------------------------------------------------

    def test_m3_indirection_and_v_test_are_subscript_contexts(self):
        for command in ("x='a[$(g''it push)]'; echo ${!x}", "x='a[$(c)]'; echo \"${!x:-d}\"", "x='a[$(c)]'; [[ -v $x ]]",
                        "x='a[$(c)]'; [ -v \"$x\" ]", "x='a[$(c)]'; test -v $x", "x='a[$(c)]'; echo ${(P)x}",
                        "x='a[$(c)]'; echo ${(PU)x}", "[[ -v 'a[$(c)]' ]]", "y='$(c)'; x=$y; echo ${!x}"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        for command in ("x=a; echo ${!x}", "echo ${!x}", "x=y; [[ -v $x ]]", "[[ -v HOME ]]", "x='a[$(c)]'; echo $x"):
            with self.subTest(command=command):
                self.assertNotBlocked(command)

    def test_m3_taint_comes_from_known_values_and_from_read_with_a_substitution_in_its_input(self):
        for command in ("d=$; x=\"a[${d}(g''it push)]\"; (( x ))", "p='$('; x=\"a[${p}c)]\"; echo $((x))",
                        "read -r x <<< 'a[$(c)]'; (( x ))", "read -r x <<'EOF'\na[$(c)]\nEOF\n(( x ))",
                        "mapfile -t a <<< 'a[`c`]'; (( a ))", "read x <<< 'a[$(c)]'; y=$x; [[ $y -eq 1 ]]",
                        "read x <<< 'a[$(c)]'; echo ${!x}"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        for command in ("d=x; x=\"a[${d}(c)]\"; (( x ))", "read -r x <<< 'a[1]'; (( x ))", "read -r x <<< 'a[$(c)]'; echo $x",
                        "n=0; while [ $n -lt 3 ]; do n=$((n+1)); done; echo $((n*2))", "fails=0; fails=$((fails+1)); (( fails ))"):
            with self.subTest(command=command):
                self.assertNotBlocked(command)

    def test_l2_a_long_chain_of_names_is_linear(self):
        n = 1200
        command = "; ".join(["a0='$(x)'"] + [f"a{i}=$a{i - 1}" for i in range(1, n)] + [f"(( a{n - 1} ))"])
        self.assertLess(len(command), classifier.MAX_COMMAND_LEN)
        import time
        start = time.process_time()
        result = analyze(command)
        self.assertLess(time.process_time() - start, 1.0)
        self.assertIn("unclassified_command", result.flags)
        quiet = "; ".join(["a0=x"] + [f"a{i}=$a{i - 1}" for i in range(1, n)] + [f"echo $a{n - 1}"])
        start = time.process_time()
        self.assertEqual(analyze(quiet).flags, [])
        self.assertLess(time.process_time() - start, 1.0)
        # the worklist reaches every name once, however the assignments are ordered
        scrambled = "; ".join(reversed([f"a{i}=$a{i - 1}" for i in range(1, 300)])) + "; a0='$(x)'; (( a299 ))"
        self.assertBlocked(scrambled)

    # -- M4: SQL / DSL client escapes ---------------------------------------------------------------------------

    def test_m4_the_escapes_of_the_sql_clients_are_level_b_in_bodies_and_arguments(self):
        bodies = (
            "select edit('', 'gi'||'t push;');", "select EDIT ( 'x' , 'y' );", "\\setenv PSQL_EDITOR 'git push #'\n\\e",
            "\\ef f", "\\ev v", "\\e", "COPY t TO PROGRAM 'git push';", "copy t from\nprogram 'x';", "\\set x `docker x`",
            "\\echo `id`", "select 1 \\g (format=csv) |cmd", "select 1 \\g |cmd", "select 1\n\\o '|cmd'", "\\w |cmd",
            "\\gx |cmd", ".syste cmd", ".sys cmd", ".she cmd", ".shell cmd", ".system cmd", ".once |cmd", "edit", "system ls",
            "\\! ls", "pager less", "\\| cmd", ".read |cmd",
        )
        for client in ("sqlite3 db", "psql", "mysql", "mariadb", "cypher-shell"):
            for body in bodies:
                command = f"{client} <<'EOF'\n{body}\nEOF"
                with self.subTest(command=command):
                    self.assertBlocked(command)
        for body in ("select 1;", "select credit(1);", "select 'a'||'b' \\g", "\\echo hi", "\\d t", ".tables", ".mode csv",
                     ".s", ".sh", "select `a` from t\\G", "\\gexec", "\\o out.txt", "\\g out.txt"):
            command = f"psql <<'EOF'\n{body}\nEOF"
            with self.subTest(command=command):
                self.assertNotBlocked(command)
        self.assertBlocked("psql -c '\\set x `cmd`'")
        self.assertBlocked("sqlite3 db \"select edit('a', 'b')\"")
        self.assertBlocked("sqlite3 db '.syste cmd'")
        self.assertBlocked("psql -c 'select 1 \\g (format=csv) |cmd'")
        self.assertNotBlocked("sqlite3 db 'select 1'")

    # -- L1, minors ---------------------------------------------------------------------------------------------

    def test_l1_the_canary_also_reads_the_decoded_words(self):
        for command in ("strace -f git $'\\x70ush'", "unshare git pu''sh", "bundle exec git $'\\x70ush'",
                        "direnv exec . git $'\\x70ush'", "npx -c 'g''it push'", "watch -n1 git pu''sh"):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertTrue(PUSH in result.flags or "deny_token_unmatched" in result.uncertainty, command)

    def test_l1_hatch_env_run_is_a_launcher(self):
        for command in ("hatch env run -- git push", "hatch env run -e test -- git push", "hatch -v env run git push",
                        "hatch env run --env x -- bash -c 'git push'"):
            with self.subTest(command=command):
                self.assertEqual(analyze(command).flags, [PUSH], command)
        self.assertEqual(analyze("hatch env show").flags, [])
        self.assertEqual(classifier.command_readings("hatch env run -- pytest x").texts, ["pytest x"])

    def test_minor_uv_run_dash_p_and_the_conda_family_and_pixi(self):
        for command in ("uv run -p 3.12 sh -c 'git push'", "uv run --python 3.12 sh -c 'git push'",
                        "uv run -p3.12 git push", "mamba run -n e git push", "micromamba run -n e git push",
                        "micromamba run --name e git push", "pixi run git push", "pixi run -e dev git push",
                        "pixi --quiet run git push"):
            with self.subTest(command=command):
                self.assertEqual(analyze(command).flags, [PUSH], command)
        self.assertEqual(classifier.command_readings("uv run -p 3.12 pytest x").texts, ["pytest x"])
        self.assertEqual(analyze("mamba install x").flags, [])

    def test_minor_ansi_c_control_characters_follow_bash(self):
        shell = classifier.shell
        for raw, text, certain in (("\\cA", "\x01", True), ("\\ca", "\x01", True), ("\\c$", "\x04", True),
                                   ("\\c[", "\x1b", True), ("\\c?", "\x7f", True), ("\\c@", "", False),
                                   ("\\c ", "", False)):
            with self.subTest(raw=raw):
                self.assertEqual(shell._decode_ansi(raw), (text, certain))
        self.assertEqual(analyze("$'\\c$ocker' " + self.RESTART + " x").flags, [])  # not `docker`: another program name

    # -- the PS4 false positive ---------------------------------------------------------------------------------

    def test_ps4_is_read_in_shell_words_only(self):
        for command in ("python3 -c 'PS4=x; print(\"-xc\")'", "python3 -c 'x = \"PS4= -xc\"'", "uv run python -c 'PS4=1 -x'",
                        "node -e 'PS4=1; -xc'", "cat > f.sh <<'EOF'\nPS4='$(x)'\nset -x\nEOF",
                        "python3 - <<'EOF'\nPS4='$(x)'; run('bash -xc')\nEOF"):
            with self.subTest(command=command):
                self.assertNotBlocked(command)
        for command in ("PS4='$(x)' bash -xc :", "PS4='$(x)'; set -x", "PS4='$(x)' sh -c 'set -x; ls'",
                        "PS4='$(x)'; python3 -c 'x' ; set -o xtrace", "env PS4='$(x)' bash -x s"):
            with self.subTest(command=command):
                self.assertBlocked(command)

    # -- forwarding functions (user decision) ------------------------------------------------------------------------

    def test_a_forwarding_function_that_is_only_defined_passes(self):
        for command in ("f() { \"$@\"; }", "function f { \"$@\"; }", "f() { git \"$@\"; }", "retry() { for i in 1 2 3; do \"$@\" && return; done; }",
                        "run() { echo \"+ $*\"; \"$@\"; }"):
            with self.subTest(command=command):
                self.assertEqual(analyze(command).flags, [], command)
                self.assertNotBlocked(command)

    def test_a_forwarding_function_call_is_classified_with_its_arguments(self):
        for command, categories in (
            ("f() { \"$@\"; }; f pytest tests/test_a.py", ["other", "test-narrow"]),
            ("retry() { for i in 1 2 3; do \"$@\" && return; done; }; retry curl -s http://localhost:8000",
             ["other", "request-local"]),
            ("f() { \"$@\"; }; f ls -la", ["other"]), ("f() { \"$@\"; }; f echo hi; f echo there", ["other"]),
            # an argument that is an expansion is fine where it is only the argument of the program the call names
            ("f() { \"$@\"; }; f ls \"$HOME\"", ["other"]), ("f() { \"$@\"; }; f ls $(date)", ["other"]),
            ("c() { curl -sS -m 10 \"$@\"; }; D=/tmp/x; c http://localhost:9/a -o $D/f", ["other", "request-local"]),
            ("f() { \"$@\"; }; timeout 5 f ls", ["other"]), ("f() { git -C r \"$1\"; }; f status", ["git-other", "other"]),
        ):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertEqual(result.categories, categories, command)
                self.assertNotIn("unclassified_command", result.flags, command)
        for command, flag in (("f() { git \"$@\"; }; f push", PUSH), ("f() { \"$@\"; }; f git push", PUSH),
                              (f"f() {{ \"$@\"; }}; f docker {self.RESTART} x", LIFECYCLE),
                              (f"f() {{ \"$@\"; }}; X=f; $X docker {self.RESTART} x", LIFECYCLE),
                              ("f() { \"$@\"; }; f bash -c 'git push'", PUSH), ("f() { git \"$@\"; }; f -C r push", PUSH)):
            with self.subTest(command=command):
                self.assertIn(flag, analyze(command).flags, command)

    def test_a_forwarding_function_call_that_cannot_be_resolved_is_level_b(self):
        for command in ("f() { \"$@\"; }; f $X", "f() { \"$@\"; }; f $(cmd)", "f() { git \"$@\"; }; f $X",
                        "f() { \"$@\"; }; f \"$X\" a", "f() { sudo \"$@\"; }; f $X restart y",
                        "f() { \"$@\"; }; echo x | xargs f", "f() { \"$@\"; }; eval f ls", "f() { \"$@\"; }; watch f ls",
                        "f() { \"$@\"; }; find . -exec f {} \\;", "f() { \"$@\"; }; g() { f \"$@\"; }; g ls",
                        "f() { f \"$@\"; }; f ls", "f() { \"$@\"; }; bash -c 'f ls'", "f() { \"$@\"; }; export -f f; bash -c 'f ls'",
                        "f() { \"$@\"; }; " + "; ".join(f"f echo {i}" for i in range(20))):
            with self.subTest(command=command):
                self.assertIn("unclassified_command", analyze(command).flags, command)
        self.assertNotBlocked("run() { \"$@\"; }; docker run x")  # the verb of docker is not a call
        # the parameter in a word with other text: the text stays (the URL is external, the function name in a quote is no call)
        self.assertIn(EXTERNAL, analyze("m() { curl -s \"https://repo.example/$1/x\"; }; m a/b").flags)
        self.assertNotBlocked("logout() { docker exec \"$1\" curl -s -w 'logout %{http_code}' x; }; logout c")
        self.assertNotBlocked("f() { \"$@\"; }; echo f; type f")

    def test_a_forwarding_function_body_still_classifies_what_is_literal_in_it(self):
        for command in ("f() { git push \"$@\"; }", "f() { \"$@\"; git commit -m x; }"):
            with self.subTest(command=command):
                self.assertTrue({PUSH, COMMIT} & set(analyze(command).flags), command)
        self.assertBlocked("f() { \"$@\"; $1$X; }")  # a name that is not only a parameter is still level B
        self.assertBlocked("f() { \"$1$X\"; }")

    def test_the_code_evaluation_docstring_describes_the_reach_rule(self):
        doc = classifier._code_evaluation.__doc__
        self.assertIn("reaches", doc)
        self.assertNotIn("in a text that also evaluates arithmetic", doc)


class ReviewFixE(unittest.TestCase):
    """Part E (audit-shell-lexer), the five findings V1-V5 of the narrow security verification. Blocked words are
    built from pieces; every text is only analyzed, nothing runs."""

    RESTART = "re" + "start"

    def assertBlocked(self, command):
        result = analyze(command)
        self.assertIn("unclassified_command", result.flags, command)
        self.assertIn("dynamic_code", result.uncertainty, command)

    def test_v1_slices_shift_and_argv_are_substituted_with_their_real_meaning(self):
        r = self.RESTART
        for command in (
            f"f() {{ \"$1\" \"${{@:2}}\"; }}; f docker {r} x", f"f() {{ $1 \"${{@:2}}\"; }}; f docker {r} x",
            f"f() {{ docker \"${{@:2}}\"; }}; f a {r} x", f"f() {{ \"${{@:2}}\"; }}; f a docker {r} x",
            f"f() {{ shift; \"$@\"; }}; f a docker {r} x", f"f() {{ $argv; }}; f docker {r} x",
            f"f() {{ \"${{argv[@]}}\"; }}; f docker {r} x", f"f() {{ \"$argv[1]\" \"$argv[2]\" x; }}; f docker {r}",
            f"f() {{ \"${{*:2:2}}\"; }}; f a docker {r} x", f"f() {{ shift 2; \"$@\"; }}; f a b docker {r} x",
            f"f() {{ shift; shift; \"${{@:1}}\"; }}; f a b docker {r} x",
        ):
            with self.subTest(command=command):
                self.assertIn(LIFECYCLE, analyze(command).flags, command)
        # the first argument alone is not the program: `${@:2}` really drops it
        self.assertNotIn(LIFECYCLE, analyze(f"f() {{ \"${{@:2:1}}\" x; }}; f a docker {r}").flags)
        self.assertEqual(analyze("f() { echo \"${@:2}\"; }; f a b c").flags, [])
        # a parameter before the `shift` is the first argument, after it the second (the usual `run()` helper)
        helper = "run() { echo \"### $1\"; shift; \"$@\"; echo \"[exit=$?]\"; }; "
        self.assertEqual(analyze(helper + "run V4a ls -la").flags, [])
        self.assertIn(LIFECYCLE, analyze(helper + f"run V4a docker {r} x").flags)
        self.assertIn(LIFECYCLE, analyze(f"run() {{ \"$@\"; shift; \"$1\" {r} x; }}; run ls docker").flags)

    def test_v1_a_body_that_uses_the_parameters_in_a_way_that_is_not_modeled_is_level_b(self):
        for command in ("f() { if x; then shift; fi; \"$@\"; }; f a ls", "f() { true && shift; \"$@\"; }; f a ls",
                        "f() { set -- a b; \"$@\"; }; f ls", "f() { \"${@:$n}\"; }; f ls",
                        "f() { \"${1:-ls}\"; }; f ls", "f() { \"$@[2]\"; }; f a ls", "f() { \"${!1}\"; }; f ls",
                        "f() { while x; do shift; done; \"$@\"; }; f a ls", "f() { shift $n; \"$@\"; }; f a ls",
                        "f() { shift | \"$@\"; }; f a ls", "f() { \"${@[2]}\"; }; f a ls", "f() { \"${@:1:$m}\"; }; f ls"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        for command in ("f() { shift; \"$@\"; }", "f() { \"${@:2}\"; }", "f() { if x; then shift; fi; \"$@\"; }"):
            with self.subTest(command=command):  # a definition that is never called passes
                self.assertEqual(analyze(command).flags, [], command)

    def test_v1_the_positional_forms_and_the_model(self):
        p = classifier._positional
        self.assertEqual(p("${@:2}"), ("${@:2}", ("slice", 2, None)))
        self.assertEqual(p("${*:2:3}"), ("${*:2:3}", ("slice", 2, 3)))
        self.assertEqual(p("$argv"), ("$argv", "all"))
        self.assertEqual(p("${argv[@]}"), ("${argv[@]}", "all"))
        self.assertEqual(p("$argv[2]"), ("$argv[2]", 2))
        self.assertEqual(p("${argv[2]}"), ("${argv[2]}", 2))
        self.assertEqual(p("$argvx"), None)
        self.assertEqual(p("${#1}"), None)
        for text in ("${@:$n}", "${1:-x}", "$@[1]", "${!1}", "${@/a/b}", "${@:0}x"):
            self.assertEqual(p(text)[1] if p(text) else None, classifier._BAD, text)
        model = classifier._positional_model
        self.assertEqual(model('{ shift; "$@"; }'), [(7, 1)])
        self.assertEqual([total for _, total in model('{ shift 2; shift; "$@"; }')], [2, 3])
        self.assertEqual(model('{ "$@"; }'), [])
        self.assertEqual([total for _, total in model('{ "$@"; shift; }')], [1])  # a parameter before it is unchanged
        self.assertIsNone(model('{ x && shift; "$@"; }'))
        self.assertIsNone(model('{ set -- 1; "$@"; }'))
        self.assertEqual(model('{ set -e; "$@"; }'), [])

    def test_v2_a_nameref_to_a_tainted_name_is_tainted(self):
        for command in ("x='a[$(c)]'; declare -n r=x; (( r ))", "x='a[$(c)]'; typeset -n r=x; echo $(( r + 1 ))",
                        "x='a[$(c)]'; local -n r=x; let r", "x='a[$(c)]'; declare -n r=x; declare -n s=r; (( s ))",
                        "x='a[$(c)]'; declare -n r=x; [[ $r -eq 1 ]]", "x='a[$(c)]'; declare -n r=x; echo ${!r}"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        for command in ("x=1; declare -n r=x; (( r ))", "x='a[$(c)]'; declare -n r=y; (( r ))",
                        "x='a[$(c)]'; declare -n r=x; echo $r"):
            with self.subTest(command=command):
                self.assertNotIn("unclassified_command", analyze(command).flags, command)

    def test_v3_edit_is_found_whatever_the_sql_spelling(self):
        for call in ("\"edit\"('', 'x')", "[edit]('', 'x')", "`edit`('', 'x')", "edit/**/('', 'x')", "EDIT ('', 'x')",
                     "edit -- c\n('', 'x')", "main.\"edit\"('x')"):
            with self.subTest(call=call):
                self.assertBlocked(f"sqlite3 :memory: <<'EOF'\nselect {call};\nEOF")
        for command in ("sqlite3 x 'select edit(1)'", "sqlite3 x 'select [edit](1)'", "sqlite3 x 'select edit/**/(1)'",
                        "sqlite3 x \"select `edit`(1)\"", "sqlite3 x <<< 'select \"edit\"(1)'"):
            with self.subTest(command=command):
                self.assertBlocked(command)
        for text in ("select credit(1), reedit(2), editor, edits from t;", "select 1 -- no", ".tables"):
            with self.subTest(text=text):
                self.assertNotIn("unclassified_command", analyze(f"sqlite3 :memory: <<'EOF'\n{text}\nEOF").flags, text)

    def test_v4_env_and_sudo_operands_feed_the_git_configuration(self):
        for command in (
            "env GIT_CONFIG_PARAMETERS=\"'alias.p'='push'\" git p", "env GIT_CONFIG_PARAMETERS=\"'alias.p=push'\" git p",
            "env GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.p GIT_CONFIG_VALUE_0=push git p",
            "env -u X GIT_CONFIG_PARAMETERS=\"'alias.p'='push'\" git p", "env -i GIT_CONFIG_PARAMETERS=\"'alias.p'='push'\" git p",
            "sudo GIT_CONFIG_PARAMETERS=\"'alias.p'='push'\" git p", "sudo -u root env GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.p "
            "GIT_CONFIG_VALUE_0=push git p", "A=1 env GIT_CONFIG_PARAMETERS=\"'alias.p=push'\" git p",
        ):
            with self.subTest(command=command):
                self.assertIn(PUSH, analyze(command).flags, command)
        self.assertBlocked("env GIT_CONFIG_PARAMETERS=\"$X\" git p")
        self.assertBlocked("env GIT_CONFIG_PARAMETERS=\"'alias.p'=\" git p".replace("=\" git", "=x\" git"))
        for command in ("env FOO=1 git status", "sudo -u root git status", "env -i git log", "env GIT_CONFIG_COUNT=0 git log"):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertNotIn("unclassified_command", result.flags, command)
                self.assertEqual(result.flags, [], command)

    def test_v5_sqlite_dot_command_prefixes(self):
        for dot in (".sy", ".sys", ".syst", ".system", ".she", ".shel", ".shell", ".SY"):
            with self.subTest(dot=dot):
                self.assertBlocked(f"sqlite3 :memory: <<'EOF'\n{dot} cmd\nEOF")
                self.assertBlocked(f"sqlite3 :memory: '{dot} cmd'")
        for dot in (".s", ".sh", ".st", ".schema", ".tables", ".mode csv", ".sha3sum", ".stats on"):
            with self.subTest(dot=dot):
                self.assertNotIn("unclassified_command", analyze(f"sqlite3 :memory: <<'EOF'\n{dot}\nEOF").flags, dot)


def load_tests(loader, tests, pattern):
    """Independent cases: run them in forked workers (see `ForkedSuite`)."""
    return ForkedSuite(tests)


if __name__ == "__main__":
    unittest.main()
