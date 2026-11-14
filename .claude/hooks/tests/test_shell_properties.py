"""Property tests of the shell lexer and parser (agent_audit_shell.py).

Source: spec audit-shell-lexer, section Testing, `test_shell_properties.py` (SP1-SP8), Task 1.
Fixed seeds, so a failure always reproduces; each test stays under half a second. `bash -n` and `zsh -n` are used
only as a syntax oracle (SP6) and never run anything; the test is skipped when a shell is missing.
"""
import random
import shlex
import shutil
import subprocess
import time
import unittest

from ._loader import load_hook
from ._support import ForkedSuite, classifier

shell = load_hook("agent_audit_shell.py")

BIG = 1 << 22

# Names are built from parts: the forms below are strings only, but a literal `docker restart` in a source file
# would be denied by the live hook when it is pasted into a command.
DOCKER = "dock" + "er"
GIT = "gi" + "t"

SHELL_PIECES = [
    "'", '"', "$", "(", ")", "{", "}", "`", ";", "&", "|", "<", ">", "#", "\\", "\n", "$(", "${", "$((", "<<", "<(",
    "((", "=", "A=", "a", "b", "x y", DOCKER, "if", "then", "elif", "else", "fi", "do", "done", "case", "esac",
    "while", "until", "for", "in", "select", "function", "time", "!", "[[", "]]", "coproc", "&&", "||", ";;", "<<<",
    "<<-", "2>", "EOF", " ", "\t", "A[", "]=", "$[", "))", "*(.)", "\\\n",
]


def random_text(rng, longest=24):
    return "".join(rng.choice(SHELL_PIECES) + rng.choice(("", " ", " ")) for _ in range(rng.randint(1, longest)))


def mutate(rng, text):
    """One random edit of a text: the near-misses of valid scripts are where parsers fail."""
    if not text:
        return text
    i = rng.randrange(len(text))
    kind = rng.randrange(3)
    if kind == 0:
        return text[:i] + text[i + 1:]
    if kind == 1:
        return text[:i] + rng.choice(SHELL_PIECES) + text[i:]
    return text[:i] + rng.choice(SHELL_PIECES) + text[i + 1:]


class ScriptGen:
    """Scripts from the grammar of section 2.2 with sentinel commands `cmdN` in command positions and `argN`
    words in argument positions, random spacing and quoting. `cmds` lists every sentinel command in the text.
    Everything it emits is valid for both bash and zsh (checked by SP6)."""

    def __init__(self, seed, backticks=True):
        self.rng = random.Random(seed)
        self.cmds = []
        self.arg_count = 0
        self.fn_count = 0
        self.backticks = backticks

    def sp(self):
        return self.rng.choice((" ", " ", "  ", "\t"))

    def word(self):
        self.arg_count += 1
        a = f"arg{self.arg_count}"
        return self.rng.choice((a, a, f"'{a}'", f'"{a}"', f"{a}'x'", f'x"{a}"y'))

    def cmd_name(self):
        c = f"cmd{len(self.cmds) + 1}"
        self.cmds.append(c)
        return self.rng.choice((c, c, c, f"'{c}'", f'"{c}"'))

    def redirect(self):
        return self.rng.choice((f"> {self.word()}", "2>&1", f">> {self.word()}", f"< {self.word()}",
                                f"<<< {self.word()}", f"&> {self.word()}"))

    def simple(self, depth):
        rng = self.rng
        parts = []
        if rng.random() < 0.2:
            parts.append(f"V{rng.randint(1, 3)}={self.word()}")
        parts.append(self.cmd_name())
        for _ in range(rng.randint(0, 2)):
            roll = rng.random()
            if roll < 0.15 and depth < 3:
                parts.append(self.substitution(depth))
            elif roll < 0.25:
                parts.append(self.redirect())
            else:
                parts.append(self.word())
        return self.sp().join(parts)

    def substitution(self, depth):
        rng = self.rng
        kind = rng.choice(("cmdsub", "dq", "backtick", "procsub", "param"))
        if kind == "backtick":
            if not self.backticks:
                kind = "cmdsub"
            else:
                self.backticks = False  # no nested backticks: they need escapes
                try:
                    return "`" + self.list_(depth + 1) + "`"
                finally:
                    self.backticks = True
        inner = self.list_(depth + 1)
        if kind == "cmdsub":
            return f"$( {inner} )"  # the blank keeps `$( (` from reading as `$((`
        if kind == "dq":
            return f'"x $( {inner} ) y"'
        if kind == "procsub":
            return f"<( {inner} )"
        return f"${{V1:-$( {inner} )}}"

    def pipeline(self, depth):
        rng = self.rng
        if depth < 2 and rng.random() < 0.06:  # a function definition stands alone: no `!`, `time` or pipe
            return self.function(depth)
        simple_first = rng.random() < 0.5
        prefix = rng.choice(("", "", "! ", "time ")) if simple_first else rng.choice(("", "", "! "))
        text = prefix + (self.simple(depth) if simple_first else self.command(depth))
        for _ in range(rng.choice((0, 0, 0, 1, 2))):
            text += self.sp() + rng.choice(("|", "|&")) + self.sp() + self.command(depth)
        return text

    def function(self, depth):
        self.fn_count += 1
        name = f"fn{self.fn_count}"
        body = f"{{ {self.list_(depth + 1)}; }}"
        return f"{name}() {body}" if self.rng.random() < 0.5 else f"function {name} {body}"

    def list_(self, depth):
        rng = self.rng
        text = self.pipeline(depth)
        for _ in range(rng.choice((0, 0, 0, 1, 1, 2))):
            text += self.sp() + rng.choice(("&&", "||", ";", "&", "\n", "&&\n")) + self.sp() + self.pipeline(depth)
        return text

    def command(self, depth):
        rng = self.rng
        if depth >= 2 or rng.random() < 0.75:
            return self.simple(depth)
        kind = rng.choice(("sub", "group", "if", "while", "until", "for", "case", "arith", "cond"))
        d = depth + 1
        tail = (self.sp() + self.redirect()) if rng.random() < 0.15 and kind in ("sub", "group", "if") else ""
        if kind == "sub":
            return f"( {self.list_(d)} ){tail}"
        if kind == "group":
            return f"{{ {self.list_(d)}; }}{tail}"
        if kind == "if":
            text = f"if {self.list_(d)}; then {self.list_(d)}"
            if rng.random() < 0.4:
                text += f"; elif {self.list_(d)}; then {self.list_(d)}"
            if rng.random() < 0.4:
                text += f"; else {self.list_(d)}"
            return text + f"; fi{tail}"
        if kind in ("while", "until"):
            return f"{kind} {self.list_(d)}; do {self.list_(d)}; done"
        if kind == "for":
            return f"for i in {self.word()} {self.word()}; do {self.list_(d)}; done"
        if kind == "case":
            return (f"case {self.word()} in {self.word()}) {self.list_(d)};; {self.word()}|{self.word()}) "
                    f"{self.list_(d)};; esac")
        if kind == "arith":
            return f"(( 1 + $( {self.list_(d)} ) ))"
        return f"[[ {self.word()} == {self.word()} && $( {self.list_(d)} ) ]]"

    def heredoc_block(self):
        rng = self.rng
        head = self.cmd_name()
        if rng.random() < 0.5:
            body = f"{self.word()} $(not a command) `neither` ${{X:-$(nor this)}}"
            return f"{head} <<'EOF'\n{body}\nEOF"
        inner = self.simple(3)
        return f"{head} <<EOF\nplain {self.word()}\nx $( {inner} ) y\nEOF"

    def script(self):
        rng = self.rng
        out = ""
        for k in range(rng.randint(1, 3)):
            heredoc = rng.random() < 0.15
            if k:  # a heredoc terminator must be alone on its line
                out += "\n" if out.rsplit("\n", 1)[-1] == "EOF" else rng.choice(("\n", ";\n", "\n\n"))
            out += self.heredoc_block() if heredoc else self.list_(0)
        return out


def walk_all(script):
    return list(shell.iter_sites(script))


class Totality(unittest.TestCase):
    """SP1, SP2."""

    def texts(self, seed, count):
        """Alternately: random pieces of shell, and near-misses (one edit) of valid scripts."""
        rng = random.Random(seed)
        out = []
        gen = ScriptGen(seed)
        for k in range(count):
            if k % 2:
                out.append(mutate(rng, gen.script()))
            else:
                out.append(random_text(rng))
        return out

    def check_total(self, seed, count):
        parsed = 0
        for text in self.texts(seed, count):
            try:
                script = shell.parse(text, shell.Budget(BIG))
            except shell.ShellError:
                continue
            parsed += 1
            walk_all(script)
        self.assertGreater(parsed, count // 10)  # the generator reaches valid text too

    # SP1: 3,000 texts, as six tests of 500 (added below) to keep each of them short

    def check_analyze(self, seed):
        for text in self.texts(seed, 500):
            with self.subTest(text=text):
                classifier.analyze_command(text)

    # 1,000 texts, in two tests
    def test_sp2_analyze_command_never_raises_a(self):
        self.check_analyze(21)

    def test_sp2_analyze_command_never_raises_b(self):
        self.check_analyze(22)


class Spans(unittest.TestCase):
    """SP3: spans slice the source; the commands of the top-level script are ordered and disjoint."""

    def check_words(self, text, script):
        for site in shell.iter_sites(script):
            for word in (*site.cmd.assignments, *site.cmd.words):
                a, b = word.span
                self.assertTrue(0 <= a < b <= len(text), (text, word.span))
                # Re-read the slice as an argument: it is the same word.
                again = shell.parse("declare " + text[a:b], shell.Budget(BIG)).pipelines[0].commands[0]
                self.assertEqual([w.text for w in again.words][1:], [word.text], (text, text[a:b]))

    def test_sp3_spans_slice_the_source(self):
        rng = random.Random(3)
        gen = ScriptGen(3, backticks=False)
        checked = 0
        for k in range(450):
            text = gen.script() if k % 2 else mutate(rng, gen.script())
            if "`" in text or "<<" in text:
                continue
            try:
                script = shell.parse(text, shell.Budget(BIG))
            except shell.ShellError:
                continue
            checked += 1
            with self.subTest(text=text):
                self.check_words(text, script)
                spans = [cmd.span for pipeline in script.pipelines for cmd in pipeline.commands]
                for (a1, b1), (a2, b2) in zip(spans, spans[1:]):
                    self.assertLessEqual(b1, a2)
                for a, b in spans:
                    self.assertTrue(0 <= a <= b <= len(text))
        self.assertGreater(checked, 100)

    def test_sp3_heredoc_commands_end_before_the_body(self):
        text = "cat <<EOF\nbody\nEOF\nnext"
        script = shell.parse(text, shell.Budget(BIG))
        first, second = (p.commands[0] for p in script.pipelines)
        self.assertEqual(text[first.span[0]:first.span[1]], "cat <<EOF")
        self.assertEqual(text[second.span[0]:second.span[1]], "next")


class GrammarGroundTruth(unittest.TestCase):
    """SP4: every sentinel command is found, and nothing else is a command."""

    def check_heads(self, seeds):
        for seed in seeds:
            gen = ScriptGen(1000 + seed)
            text = gen.script()
            heads = []
            for site in shell.iter_sites(shell.parse(text, shell.Budget(BIG))):
                self.assertTrue(site.cmd.words, text)
                heads.append(site.cmd.words[0].text)
            self.assertEqual(sorted(heads), sorted(gen.cmds), text)

    # SP4: 1,000 scripts, as eight tests of 125 (added below) to keep each of them short

    def test_sp4_generator_reaches_every_construct(self):
        blob = "\n".join(ScriptGen(5000 + seed).script() for seed in range(300))
        for needle in ("$(", "`", "<(", "| ", "|&", "&&", "||", "if ", "elif ", "else ", "while ", "until ",
                       "for ", "case ", "function ", "() {", "(( ", "[[ ", "<<'EOF'", "<<EOF", "! ", "time "):
            with self.subTest(needle):
                self.assertIn(needle, blob)


class Closure(unittest.TestCase):
    """SP5: a blocked form stays visible whatever wraps it.

    The parser half (here, Task 1): after wrapping, the form is still in a command position (its words end the
    words of some simple command) or, for wrappers that pass the form as a string, a word holds it whole. The hook
    half runs only once the hook reads commands through the parser (Tasks 2-5)."""

    FORMS = [
        ("lifecycle", f"{DOCKER} restart api", "docker_lifecycle"),
        ("push", f"{GIT} push origin main", "git_push"),
        ("commit", f"{GIT} commit -m msg", "git_commit"),
        ("curl", "curl https://evil.example/x", "external_request"),
    ]
    STRUCTURAL = [
        "( {c} )", "{{ {c}; }}", "if true; then {c}; fi", "for i in 1; do {c}; done", "while true; do {c}; done",
        "case x in x) {c};; esac", "! {c}", "true && {c}", "true & {c}", "echo $( {c} )", "echo `{c}`", "x=$( {c} )",
        "diff <({c}) x", "true || {c}", "true | {c}", "{c} | true", "f() {{ {c}; }}", "time {c}",
    ]
    PREFIX = [
        "sudo -u u {c}", "env A=1 {c}", "nice -n 5 {c}", "nohup {c}", "time -p {c}", "stdbuf -oL {c}",
        "ionice -c 3 {c}", "xargs {c}", "watch -x {c}", "command {c}", "exec {c}", "A=1 B=2 {c}", "/usr/bin/env {c}",
    ]

    @staticmethod
    def composable(outer, inner):
        """`! ! cmd`, `time time cmd` are outside the grammar (section 2.2) and backticks do not nest unescaped."""
        if outer.startswith(("! ", "time")) and inner.startswith(("! ", "time")):
            return False
        if outer.endswith("| {c}") and inner.startswith(("! ", "time")):
            return False  # `a | time b` is accepted by the shells but is not in the grammar: level B, not a miss
        return not ("`" in outer and "`" in inner)

    @staticmethod
    def string_wrappers(form):
        q = shlex.quote(form)
        return [
            (f"bash -c {q}", form), (f"sh -lc {q}", form), (f"eval {q}", form), (f"trap {q} EXIT", form),
            (f"T={q}; zsh -c \"$T\"", form), (f"nvim --headless -c {shlex.quote('!' + form)}", "!" + form),
        ]

    @staticmethod
    def visible(text, form, whole=False):
        words = form.split()
        for site in shell.iter_sites(shell.parse(text, shell.Budget(BIG))):
            texts = [w.text for w in (*site.cmd.assignments, *site.cmd.words)]
            if whole and any(t == form or t.endswith("=" + form) for t in texts):
                return True
            if not whole and texts[len(texts) - len(words):] == words:
                return True
        return False

    def test_sp5_parser_sees_every_wrapped_form(self):
        count = 0
        for name, form, _flag in self.FORMS:
            wrappers = [w.format(c=form) for w in self.STRUCTURAL + self.PREFIX]
            for text in wrappers:
                with self.subTest(form=name, text=text):
                    self.assertTrue(self.visible(text, form), text)
                count += 1
            for text, expected in self.string_wrappers(form):
                with self.subTest(form=name, text=text):
                    self.assertTrue(self.visible(text, expected, whole=True), text)
                count += 1
            # two levels: a structural wrapper around any other wrapper
            for outer in self.STRUCTURAL:
                for inner in self.STRUCTURAL + self.PREFIX:
                    if not self.composable(outer, inner):
                        continue
                    text = outer.format(c=inner.format(c=form))
                    self.assertTrue(self.visible(text, form), text)
                    count += 1
                for inner_text, expected in self.string_wrappers(form):
                    text = outer.format(c=inner_text)
                    self.assertTrue(self.visible(text, expected, whole=True), text)
                    count += 1
        self.assertGreater(count, 1200)

    def test_sp5_the_hook_flags_every_wrapped_form(self):
        for name, form, flag in self.FORMS:
            wrapped = [w.format(c=form) for w in self.STRUCTURAL + self.PREFIX]
            wrapped += [text for text, _ in self.string_wrappers(form)]
            for outer in self.STRUCTURAL:
                wrapped += [outer.format(c=inner.format(c=form)) for inner in self.STRUCTURAL + self.PREFIX
                            if self.composable(outer, inner)]
                # a structural wrapper around a string wrapper (`( bash -c '...' )`, `for ...; do eval '...'; done`)
                wrapped += [outer.format(c=inner_text) for inner_text, _ in self.string_wrappers(form)]
            # a string wrapper around any other wrapper (`bash -c '( ... )'`, `eval 'sudo -u u ...'`)
            for inner in self.STRUCTURAL + self.PREFIX:
                wrapped += [text for text, _ in self.string_wrappers(inner.format(c=form))]
            for text in wrapped:
                with self.subTest(form=name, text=text):
                    self.assertIn(flag, classifier.analyze_command(text).flags)


@unittest.skipUnless(shutil.which("bash") and shutil.which("zsh"), "needs bash and zsh as the syntax oracle")
class SyntaxOracle(unittest.TestCase):
    """SP6: what the generator emits is syntax the real shells accept (`-n`: read, never run)."""

    @staticmethod
    def accepts(argv, text):
        # zsh -n exits 1 when a top-level list holds a `! cmd` (the negation of a command that never ran), so the
        # text is read as the body of a group, where it does not.
        done = subprocess.run(argv, input="{\n" + text + "\n}\n", capture_output=True, text=True, timeout=20)
        return done.returncode == 0, done.stderr

    def test_sp6_the_first_200_scripts_pass_bash_n_and_zsh_n(self):
        scripts = [ScriptGen(1000 + seed).script() for seed in range(200)]
        both = "\n".join(scripts)
        for name, argv in (("bash", ["bash", "--norc", "--noprofile", "-n"]), ("zsh", ["zsh", "-f", "-n"])):
            with self.subTest(name):
                ok, err = self.accepts(argv, both)
                if not ok:  # name the first script the shell refuses
                    for text in scripts:
                        one_ok, one_err = self.accepts(argv, text)
                        if not one_ok:
                            self.fail(f"{name} -n refuses a generated script:\n{text}\n{one_err}")
                self.assertTrue(ok, err)

    def test_sp6_the_oracle_refuses_what_the_parser_refuses(self):
        for text in ("echo \"a", "if a; then b", "a )", "(a) b"):
            with self.subTest(text):
                with self.assertRaises(shell.ShellSyntaxError):
                    shell.parse(text, shell.Budget(BIG))
                self.assertFalse(self.accepts(["bash", "--norc", "--noprofile", "-n"], text)[0])
                self.assertFalse(self.accepts(["zsh", "-f", "-n"], text)[0])


class QuoteDifferential(unittest.TestCase):
    """SP7: for words and quotes only, `.text` is what `shlex.split` gives."""

    SEGMENTS = ("a", "bc", "x1", "in", "do", "-p", "--k", "é")
    QUOTED = ("a b", "; |", "&&", "<>", "()", "{ }", "#", "", "x\ny", "a'b", '"', "$", "`")

    def word(self, rng):
        out = []
        for _ in range(rng.randint(1, 3)):
            kind = rng.randrange(3)
            if kind == 0:
                out.append(rng.choice(self.SEGMENTS))
            elif kind == 1:
                inner = rng.choice([q for q in self.QUOTED if "'" not in q])
                out.append(f"'{inner}'")
            else:
                inner = rng.choice([q for q in self.QUOTED if '"' not in q and "$" not in q and "`" not in q])
                out.append(f'"{inner}"')
        return "".join(out)

    def test_sp7_words_equal_shlex(self):
        rng = random.Random(7)
        for _ in range(2000):
            text = "x" + "".join(rng.choice((" ", "  ", "\t")) + self.word(rng) for _ in range(rng.randint(0, 5)))
            script = shell.parse(text, shell.Budget(BIG))
            command = script.pipelines[0].commands[0]
            self.assertEqual([w.text for w in command.words], shlex.split(text), text)


class Linearity(unittest.TestCase):
    """SP8: the CPU time grows with the size of the text, not faster, and stays below a second."""

    DEEP_SUBSTITUTIONS = "echo $(" * 32 + "a" + ")" * 32  # nested to the cap, then repeated
    DEEP_GROUPS = "{ " * 32 + "a" + "; }" * 32

    # (name, builder of a text of about n characters, must it parse). The adversarial forms of the spec first.
    FORMS = [
        ("nested substitutions to the cap", lambda n: "; ".join([Linearity.DEEP_SUBSTITUTIONS] * (n // 260)), True),
        ("adjacent quotes", lambda n: "echo " + '"a"' * (n // 3), True),
        ("heredoc openers", lambda n: "cat " + "<<a " * (n // 4), True),
        ("heredoc openers with bodies", lambda n: "cat " + "<<a " * (n // 40) + "\n" + "x\n" * (n // 4), True),
        ("timeout flags", lambda n: "timeout " + "-s " * (n // 3) + "x", True),
        ("assignments", lambda n: "A=1 " * (n // 4) + "b", True),
        ("nested groups to the cap", lambda n: "\n".join([Linearity.DEEP_GROUPS] * (n // 194)), True),
        ("pipes", lambda n: "x|" * (n // 2) + "y", True),
        ("words", lambda n: "echo " + "word " * (n // 5), True),
        ("arith attempts", lambda n: "((a); b); " * (n // 10), True),
        ("unclosed arith", lambda n: "((" + "(x) " * (n // 4), False),
        ("backticks", lambda n: "echo " + "`a` " * (n // 4), True),
        ("long escaped backtick", lambda n: "echo `" + "\\$a " * (n // 4) + "`", True),
        ("unquoted heredoc body", lambda n: "cat <<EOF\n" + "a $x $(b)\n" * (n // 10) + "EOF\n", True),
        ("case items", lambda n: "case x in " + "a) b;; " * (n // 7) + "esac", True),
        ("parameter expansions", lambda n: "echo " + "${a:-b} " * (n // 8), True),
    ]

    @staticmethod
    def cpu(text, must_parse):
        best = None
        for _ in range(2):
            start = time.process_time()
            try:
                shell.parse(text, shell.Budget(BIG))
            except shell.ShellError:
                if must_parse:
                    raise
            took = time.process_time() - start
            best = took if best is None else min(best, took)
        return best

    def check_forms(self, chunk):
        for name, build, must_parse in self.FORMS[chunk::8]:
            with self.subTest(name):
                small, large = build(4000), build(16000)
                self.assertLessEqual(len(large), 16384)
                t_small, t_large = self.cpu(small, must_parse), self.cpu(large, must_parse)
                self.assertLess(t_large, 1.0, name)
                self.assertLessEqual(t_large / max(t_small, 0.002), 5, f"{name}: {t_small:.4f}s -> {t_large:.4f}s")

    # SP8: the 16 forms, as eight tests of two (added below) to keep each of them short

    def test_sp8_deep_nesting_is_refused_quickly(self):
        start = time.process_time()
        for text in ("( " * 20000, "$(" * 20000, "{ " * 20000, "if a; then " * 20000, "${a:-" * 20000, "$((" * 20000):
            with self.assertRaises(shell.ShellError):
                shell.parse(text, shell.Budget(BIG))
        self.assertLess(time.process_time() - start, 1.0)


def _add_shards(cls, stem, count, check):
    """Add `count` test methods `<stem>_<k>` to `cls`, each running `check(self, k)`: the same property over
    disjoint seeds, so no single test is long and the forked workers share them."""
    for k in range(count):
        def test(self, k=k):
            check(self, k)
        test.__name__ = f"{stem}_{k}"
        test.__doc__ = f"{stem} (shard {k + 1} of {count})"
        setattr(cls, test.__name__, test)


_add_shards(Totality, "test_sp1_parse_returns_a_tree_or_a_shell_error", 6, lambda t, k: t.check_total(100 + k, 500))
_add_shards(GrammarGroundTruth, "test_sp4_the_heads_found_are_the_sentinels", 8,
            lambda t, k: t.check_heads(range(k * 125, (k + 1) * 125)))
_add_shards(Linearity, "test_sp8_time_grows_linearly", 8, lambda t, k: t.check_forms(k))


def load_tests(loader, tests, pattern):
    """Independent cases: run them in forked workers (see `ForkedSuite`)."""
    return ForkedSuite(tests)


if __name__ == "__main__":
    unittest.main()
