"""Lexer and parser of the shell subset (agent_audit_shell.py).

Source: spec audit-shell-lexer, section Testing, `test_shell_lexer.py` (SL1-SL13), Task 1.
The module is pure, so nothing here starts a process or touches a file. Each table row is `(id, text, expected)`
and runs as a subTest; the expected value is the list of simple commands as `head arg...` (the `.text` of their
words), or the kind of the syntax error.
"""
import unittest

from ._loader import load_hook
from ._support import ForkedSuite

shell = load_hook("agent_audit_shell.py")

BIG = 1 << 20


def parse(text, chars=BIG):
    return shell.parse(text, shell.Budget(chars))


def sites(text):
    return list(shell.iter_sites(parse(text)))


def command_texts(text):
    """The simple commands of the text, in walk order, as `word word ...` of their `.text`."""
    return [" ".join(w.text for w in s.cmd.words) for s in sites(text)]


class Table(unittest.TestCase):
    def check_commands(self, rows):
        for ident, text, expected in rows:
            with self.subTest(ident):
                self.assertEqual(command_texts(text), expected)


class Lists(Table):
    """SL1: lists, pipelines and their separators."""

    def test_separators_give_one_command_each(self):
        self.check_commands([
            ("semicolon", "a; b", ["a", "b"]),
            ("background", "a & b", ["a", "b"]),
            ("and-or", "a && b || c", ["a", "b", "c"]),
            ("newline", "a\nb", ["a", "b"]),
            ("trailing", "a;", ["a"]),
            ("blank lines", "\n\na\n\n\nb\n", ["a", "b"]),
            ("and then newline", "a &&\n  b", ["a", "b"]),
            ("continuation", "a \\\n b", ["a b"]),
            ("empty", "", []),
            ("only a comment", "# nothing\n", []),
        ])

    def test_pipeline_stages(self):
        found = sites("a | b |& c")
        self.assertEqual([(s.stage, s.stages) for s in found], [(0, 3), (1, 3), (2, 3)])
        self.assertTrue(all(s.top_level for s in found))

    def test_a_list_of_pipelines_restarts_the_stage_count(self):
        found = sites("a | b; c && d | e | f")
        self.assertEqual([(s.stage, s.stages) for s in found],
                         [(0, 2), (1, 2), (0, 1), (0, 3), (1, 3), (2, 3)])

    def test_negation_and_time_belong_to_the_pipeline(self):
        pipeline = parse("time -p ! a | b").pipelines[0]
        self.assertTrue(pipeline.timed)
        self.assertTrue(pipeline.negated)
        self.assertEqual(len(pipeline.commands), 2)


class Quoting(Table):
    """SL2: separators, `#` and `$` between quotes are text."""

    def test_quoted_operators_are_not_operators(self):
        self.check_commands([
            ("dq semicolon", 'echo "a; b"', ["echo a; b"]),
            ("sq and", "echo 'a && b'", ["echo a && b"]),
            ("ansi quote", "echo $'a\\'; b'", ["echo a'; b"]),
            ("dq newline", 'echo "a\nb"', ["echo a\nb"]),
            ("escaped semicolon", "echo a\\;b", ["echo a;b"]),
            ("dq pipe", 'grep -E "a|b" f', ["grep -E a|b f"]),
            ("adjacent quotes", "echo a'b'\"c\"d", ["echo abcd"]),
            ("empty quotes", "echo '' \"\"", ["echo  "]),
            ("escaped quote in dq", 'echo "a\\"b"', ['echo a"b']),
            ("escaped dollar in dq", 'echo "\\$(x)"', ["echo $(x)"]),
            ("backslash kept in dq", 'echo "a\\b"', ["echo a\\b"]),
            ("continuation in dq", 'echo "a\\\nb"', ["echo ab"]),
            ("lone dollar", "echo $ a", ["echo $ a"]),
            ("locale string", 'echo $"a b"', ["echo a b"]),
        ])

    def test_a_substitution_in_double_quotes_is_still_code(self):
        self.check_commands([("dq substitution", 'echo "$(x)"', ["echo $(x)", "x"])])
        found = sites('echo "$(x)"')
        self.assertIsNone(found[0].substitution)
        self.assertIs(found[1].substitution, found[0])
        self.assertEqual(found[1].sub_word.text, "$(x)")

    def test_single_quotes_hide_expansions(self):
        self.assertEqual(command_texts("echo '$(x) `y`'"), ["echo $(x) `y`"])

    def test_word_properties(self):
        words = parse("echo a'b' \"c d\" $x \"$y\" *.md '*' a\\*b").pipelines[0].commands[0].words
        self.assertEqual([w.quoted for w in words], [False, True, True, False, True, False, True, True])
        self.assertEqual([w.dynamic for w in words], [False, False, False, True, True, False, False, False])
        self.assertEqual([w.has_glob for w in words], [False, False, False, False, False, True, False, False])

    def test_single_quoted_backslash_is_literal(self):
        self.assertEqual(command_texts("echo 'a\\' b"), ["echo a\\ b"])


class Comments(Table):
    """SL3 (S4): `#` opens a comment at the beginning of a word only."""

    def test_comments(self):
        self.check_commands([
            ("after word", "ls # a; b", ["ls"]),
            ("quote in comment", 'ls #"', ["ls"]),
            ("inside a word", "echo a#b", ["echo a#b"]),
            ("quoted", 'echo "#"', ["echo #"]),
            ("after operator", "ls;#x\necho a", ["ls", "echo a"]),
            ("next line is code", "ls # c\necho a", ["ls", "echo a"]),
            ("escaped", "echo \\#a", ["echo #a"]),
            ("after a quoted part", 'echo "a"#b', ["echo a#b"]),
            ("comment hides a quote", "A='x y' b # '", ["b"]),
        ])


class Compounds(unittest.TestCase):
    """SL4: compound commands; their words (for lists, case patterns) are not commands."""

    CASES = [
        ("subshell", "(a)", ["a"]),
        ("group", "{ a; }", ["a"]),
        ("group no space before brace", "{ a;}", ["a"]),
        ("if", "if a; then b; elif c; then d; else e; fi", ["a", "b", "c", "d", "e"]),
        ("while", "while a; do b; done", ["a", "b"]),
        ("until", "until a; do b; done", ["a", "b"]),
        ("for", "for i in x y; do a; done", ["a"]),
        ("for newline", "for i in x y\ndo\na\ndone", ["a"]),
        ("for no list", "for i; do a; done", ["a"]),
        ("for arith", "for ((i=0;i<3;i++)); do a; done", ["a"]),
        ("select", "select x in a b; do c; done", ["c"]),
        ("case", "case $x in a) b;; (c|d) e;& f) g;;& esac", ["b", "e", "g"]),
        ("case no last separator", "case x in a) b\nesac", ["b"]),
        ("case empty item", "case x in a) ;; b) c;; esac", ["c"]),
        ("function", "f() { a; }", ["a"]),
        ("function keyword", "function f { a; }", ["a"]),
        ("function keyword and parens", "function f() { a; }", ["a"]),
        ("function with subshell body", "f() (a)", ["a"]),
        ("negation", "! a", ["a"]),
        ("time", "time -p a", ["a"]),
        ("coproc", "coproc a", ["a"]),
        ("coproc named", "coproc N { a; }", ["a"]),
        ("nested", "if a; then { b; (c); }; fi", ["a", "b", "c"]),
        ("arith command", "(( x = 1 ))", []),
        ("cond command", "[[ -n x && y == z ]]", []),
        ("reserved word as an argument", "echo then fi done esac", ["echo then fi done esac"]),
        ("quoted reserved word is a command", "'if' a", ["if a"]),
        ("reserved word after assignment", "A=1 if", ["if"]),
        ("compound with redirects", "{ a; } > f 2>&1", ["a"]),
        ("compound in a pipeline", "a | { b; } | c", ["a", "b", "c"]),
        ("brace is a word without a blank", "echo {a,b}", ["echo {a,b}"]),
    ]

    def test_commands_found(self):
        for ident, text, expected in self.CASES:
            with self.subTest(ident):
                self.assertEqual(command_texts(text), expected)

    def test_commands_inside_a_compound_are_marked(self):
        for ident, text, expected in self.CASES:
            if not expected or ident in ("reserved word as an argument", "quoted reserved word is a command",
                                         "reserved word after assignment", "negation", "time",
                                         "compound in a pipeline", "brace is a word without a blank"):
                continue
            with self.subTest(ident):
                self.assertTrue(all(s.in_compound and not s.top_level for s in sites(text)))

    def test_compound_kinds(self):
        kinds = {
            "(a)": "subshell", "{ a; }": "group", "if a; then b; fi": "if", "while a; do b; done": "while",
            "until a; do b; done": "until", "for i in x; do a; done": "for", "select i in x; do a; done": "select",
            "case x in a) b;; esac": "case", "(( 1 ))": "arith", "[[ a ]]": "cond", "f() { a; }": "function",
            "coproc a": "coproc",
        }
        for text, kind in kinds.items():
            with self.subTest(text):
                self.assertEqual(parse(text).pipelines[0].commands[0].kind, kind)

    def test_for_and_case_words_are_kept_as_words(self):
        loop = parse("for i in x $(y) z; do a; done").pipelines[0].commands[0]
        self.assertEqual((loop.name, [w.text for w in loop.words]), ("i", ["x", "$(y)", "z"]))
        case = parse("case $v in a|b) c;; d) e;; esac").pipelines[0].commands[0]
        self.assertEqual([w.text for w in case.words], ["$v", "a", "b", "d"])
        self.assertEqual(len(case.bodies), 2)

    def test_function_name(self):
        self.assertEqual(parse("f() { a; }").pipelines[0].commands[0].name, "f")
        self.assertEqual(parse("function g { a; }").pipelines[0].commands[0].name, "g")

    def test_cond_operands_and_regex(self):
        cond = parse("[[ $x =~ ^(a b)$ && ( y | z ) < w ]]").pipelines[0].commands[0]
        self.assertEqual([w.text for w in cond.words], ["$x", "=~", "^(a b)$", "&&", "(", "y", "|", "z", ")", "<", "w"])
        self.assertEqual(command_texts("[[ a ]] && b"), ["b"])
        self.assertEqual(command_texts("[[ \"]]\" ]] && b"), ["b"])

    def test_arith_command_versus_nested_subshell(self):
        self.assertEqual(command_texts("((a))"), [])
        self.assertEqual(command_texts("((a); b)"), ["a", "b"])
        self.assertEqual(command_texts("( (a) )"), ["a"])
        self.assertEqual(command_texts("(( $(a) + `b` ))"), ["a", "b"])


class Substitutions(unittest.TestCase):
    """SL5 (S5): substitutions are scripts, wherever they sit."""

    CASES = [
        ("assignment", "x=$(a)", ["", "a"]),
        ("nested", "echo $(a $(b))", ["echo $(a $(b))", "a $(b)", "b"]),
        ("backtick", "echo `a`", ["echo `a`", "a"]),
        ("backtick in dq", 'echo "`a`"', ["echo `a`", "a"]),
        ("process substitution", "diff <(a) >(b)", ["diff <(a) >(b)", "a", "b"]),
        ("param default", "echo ${X:-$(a)}", ["echo ${X:-$(a)}", "a"]),
        ("arith", "echo $((1 + $(a)))", ["echo $((1 + $(a)))", "a"]),
        ("old arith", "echo $[1+$(a)]", ["echo $[1+$(a)]", "a"]),
        ("cond", "[[ $(a) == x ]]", ["a"]),
        ("arith command", "(( $(a) ))", ["a"]),
        ("case inside", "$(case x in a) b;; esac)", ["$(case x in a) b;; esac)", "b"]),
        ("escaped backtick inside backticks", "echo `a \\`b\\``", ["echo `a \\`b\\``", "a `b`", "b"]),
        ("backtick unescapes dollar", "echo `echo \\$(a)`", ["echo `echo \\$(a)`", "echo $(a)", "a"]),
        ("in redirect target", "a > $(b)", ["a", "b"]),
        ("in a for list", "for i in $(a); do b; done", ["a", "b"]),
        ("in case word", "case $(a) in x) b;; esac", ["a", "b"]),
        ("in an array", "declare -a A=(x $(c))", ["declare -a A=(x $(c))", "c"]),
        ("param with nested quote", 'echo "${X:-"$(a)"}"', ['echo ${X:-"$(a)"}', "a"]),
        ("param with ansi quote", "echo ${X#$'a}'}", ["echo ${X#$'a}'}"]),
        ("subscript with substitution", "A[$(a)]=1 b", ["b", "a"]),
        ("here-string", "a <<< $(b)", ["a", "b"]),
        ("substitution in the middle of a word", "echo x$(a)y", ["echo x$(a)y", "a"]),
    ]

    def test_commands_found(self):
        for ident, text, expected in self.CASES:
            with self.subTest(ident):
                self.assertEqual(command_texts(text), expected)

    def test_nested_commands_know_the_command_that_holds_them(self):
        found = sites("echo $(a $(b))")
        self.assertEqual([s.substitution is not None for s in found], [False, True, True])
        self.assertIs(found[1].substitution, found[0])
        self.assertIs(found[2].substitution, found[1])
        self.assertFalse(any(s.top_level for s in found[1:]))

    def test_literal_dollar_text_is_not_code(self):
        self.assertEqual(command_texts("echo $ $$ $1 $@ ${x} $(( 1 ))"), ["echo $ $$ $1 $@ ${x} $(( 1 ))"])


class Assignments(unittest.TestCase):
    """SL6 (S8)."""

    CASES = [
        ("plain", "A=1 b", ["b"], 1),
        ("append", "A+=1 b", ["b"], 1),
        ("subscript", "A[0]=1 b", ["b"], 1),
        ("subscript append", "A[0]+=1 b", ["b"], 1),
        ("quoted value", 'A="x y" b', ["b"], 1),
        ("substitution value", "A=$(c) b", ["b", "c"], 1),
        ("array", "A=(x y) b", ["b"], 1),
        ("two", "A=1 B=2 c", ["c"], 2),
        ("declare array", "declare -a A=(x $(c))", ["declare -a A=(x $(c))", "c"], 0),
        ("quoted name is the command", '"A=1" b', ["A=1 b"], 0),
        ("only an assignment", "A=1", [""], 1),
        ("after the command word", "b A=1", ["b A=1"], 0),
        ("escaped name", "\\A=1 b", ["A=1 b"], 0),
        ("not a name", "1A=1 b", ["1A=1 b"], 0),
        ("subscript with a blank", "A[a b]=1 c", ["c"], 1),
        ("subscript with a blank, appended", "A[a  b]+=1 c", ["c"], 1),
        ("subscript that never closes", "A[a b c", ["A[a b c"], 0),
        ("subscript with a blank and no equals", "A[a b] c", ["A[a b] c"], 0),
        ("equals only", "=b c", ["=b c"], 0),
    ]

    def test_assignments(self):
        for ident, text, expected, count in self.CASES:
            with self.subTest(ident):
                self.assertEqual(command_texts(text), expected)
                self.assertEqual(len(parse(text).pipelines[0].commands[0].assignments), count)

    def test_array_elements_are_kept(self):
        word = parse("A=(x $(c) 'y z')").pipelines[0].commands[0].assignments[0]
        array = word.parts[-1]
        self.assertEqual(array.kind, "array")
        self.assertEqual([w.text for w in array.elements], ["x", "$(c)", "y z"])
        self.assertEqual(word.text, "A=(x $(c) y z)".replace("(x $(c) y z)", array.text))

    def test_array_with_newlines_and_comments(self):
        self.assertEqual(command_texts("A=(x # one\n  y\n) b"), ["b"])

    def test_an_array_value_is_not_read_in_argument_position(self):
        with self.assertRaises(shell.ShellSyntaxError):
            parse("echo A=(x y)")

    def test_the_assignment_pattern(self):
        for text in ("A=1", "A+=x", "A[0]=x", "a_b9+=", "A[x y]=1"):
            with self.subTest(text):
                self.assertTrue(shell.ASSIGNMENT.match(text))
        for text in ("1A=1", "A", "=x", "A[0", "A[0]x", "-A=1"):
            with self.subTest(text):
                self.assertIsNone(shell.ASSIGNMENT.match(text))
        self.assertTrue(shell.ASSIGNMENT.match('A+="x'))


class Redirections(unittest.TestCase):
    """SL7."""

    CASES = [
        ("out", "a > f", [(None, ">", "f")]),
        ("fd dup", "a 2>&1", [("2", ">&", "1")]),
        ("both", "a &> f", [(None, "&>", "f")]),
        ("both append", "a &>> f", [(None, "&>>", "f")]),
        ("named fd", "a {fd}> f", [("{fd}", ">", "f")]),
        ("here-string", 'a <<< "s"', [(None, "<<<", "s")]),
        ("leading", "> f a", [(None, ">", "f")]),
        ("clobber", "a >| f", [(None, ">|", "f")]),
        ("read write", "a <> f", [(None, "<>", "f")]),
        ("append", "a >> f", [(None, ">>", "f")]),
        ("input fd", "a 3< f", [("3", "<", "f")]),
        ("input dup", "a <&3", [(None, "<&", "3")]),
        ("close", "a >&-", [(None, ">&", "-")]),
        ("two", "a < in > out 2> err", [(None, "<", "in"), (None, ">", "out"), ("2", ">", "err")]),
        ("no space", "a>f", [(None, ">", "f")]),
        ("digit argument is not an fd", "a 2 > f", [(None, ">", "f")]),
        ("word ending in a digit", "a b2>f", [(None, ">", "f")]),
    ]

    def test_redirections(self):
        for ident, text, expected in self.CASES:
            with self.subTest(ident):
                found = sites(text)
                self.assertEqual(len(found), 1)
                self.assertEqual([(r.fd, r.op, r.target.text) for r in found[0].cmd.redirects], expected)

    def test_redirection_words_are_not_arguments(self):
        self.assertEqual(command_texts("a b > f c"), ["a b c"])
        self.assertEqual(command_texts("a 2 > f"), ["a 2"])
        self.assertEqual(command_texts("a b2>f"), ["a b2"])


class Heredocs(unittest.TestCase):
    """SL8 (HD1, section 2.3)."""

    def heredocs(self, text):
        out = []
        for s in sites(text):
            out.extend(r.heredoc for r in s.cmd.redirects if r.heredoc is not None)
        return out

    def test_forms(self):
        rows = [
            ("plain", "cat <<EOF\nb\nEOF\nx", "EOF", False, False, "b\n", True, ["cat", "x"]),
            ("dash strips tabs", "cat <<-EOF\n\tb\n\t\tEOF\nx", "EOF", False, True, "b\n", True, ["cat", "x"]),
            ("space before delimiter", "cat << EOF\nb\nEOF\nx", "EOF", False, False, "b\n", True, ["cat", "x"]),
            ("double quoted", 'cat <<"EOF"\nb\nEOF\nx', "EOF", True, False, "b\n", True, ["cat", "x"]),
            ("backslash", "cat <<\\EOF\nb\nEOF\nx", "EOF", True, False, "b\n", True, ["cat", "x"]),
            ("single quoted", "cat <<'EOF'\nb\nEOF\nx", "EOF", True, False, "b\n", True, ["cat", "x"]),
            ("partly quoted", "cat <<E'O'F\nb\nEOF\nx", "EOF", True, False, "b\n", True, ["cat", "x"]),
            ("without terminator", "cat <<EOF\nabc\ndef\n", "EOF", False, False, "abc\ndef\n", False, ["cat"]),
            ("nothing after the opener", "cat <<EOF", "EOF", False, False, "", False, ["cat"]),
            ("terminator at the end of the text", "cat <<EOF\nb\nEOF", "EOF", False, False, "b\n", True, ["cat"]),
            ("terminator with a trailing blank is body", "cat <<EOF\nb\nEOF \nx", "EOF", False, False,
             "b\nEOF \nx", False, ["cat"]),
            ("indented terminator is body without a dash", "cat <<EOF\n\tEOF\nEOF\nx", "EOF", False, False,
             "\tEOF\n", True, ["cat", "x"]),
            ("carriage return is a character", "cat <<EOF\nx\nEOF\r\nEOF\nz", "EOF", False, False,
             "x\nEOF\r\n", True, ["cat", "z"]),
            ("continuation in the delimiter", "cat <<E\\\nOF\nx\nEOF\nz", "EOF", False, False, "x\n", True,
             ["cat", "z"]),
            ("newline in quotes on the opener line", 'cat <<EOF "a\nb"\nbody\nEOF\nz', "EOF", False, False,
             "body\n", True, ["cat a\nb", "z"]),
            ("empty body", "cat <<EOF\nEOF\nz", "EOF", False, False, "", True, ["cat", "z"]),
            ("body that looks like code", "cat <<'EOF'\n$(a); b | c\nEOF\nz", "EOF", True, False,
             "$(a); b | c\n", True, ["cat", "z"]),
            ("stage of a pipeline", "cat <<EOF | b\nx\nEOF\nz", "EOF", False, False, "x\n", True,
             ["cat", "b", "z"]),
            ("opener then list", "cat <<EOF; b\nx\nEOF\nz", "EOF", False, False, "x\n", True, ["cat", "b", "z"]),
        ]
        for ident, text, delimiter, quoted, strip, body, terminated, commands in rows:
            with self.subTest(ident):
                found = self.heredocs(text)
                self.assertEqual(len(found), 1)
                h = found[0]
                self.assertEqual((h.delimiter, h.quoted, h.strip_tabs, h.body, h.terminated),
                                 (delimiter, quoted, strip, body, terminated))
                self.assertEqual(command_texts(text), commands)

    def test_two_on_one_line_are_read_in_order(self):
        found = self.heredocs("cat <<A <<B\n1\nA\n2\nB\nz")
        self.assertEqual([(h.delimiter, h.body) for h in found], [("A", "1\n"), ("B", "2\n")])
        self.assertEqual(command_texts("cat <<A <<B\n1\nA\n2\nB\nz"), ["cat", "z"])

    def test_two_commands_on_one_line_read_their_bodies_at_the_same_newline(self):
        text = "a <<A; b <<B\n1\nA\n2\nB\nz"
        self.assertEqual([(h.delimiter, h.body) for h in self.heredocs(text)], [("A", "1\n"), ("B", "2\n")])
        self.assertEqual(command_texts(text), ["a", "b", "z"])

    def test_heredoc_inside_a_substitution_reads_its_body_at_the_inner_newline(self):
        text = "echo $(cat <<EOF\nbody\nEOF\n) after"
        self.assertEqual(command_texts(text), ["echo $(cat <<EOF\nbody\nEOF\n) after", "cat"])
        outer, inner = sites(text)
        self.assertEqual(inner.cmd.redirects[0].heredoc.body, "body\n")
        self.assertIs(inner.substitution, outer)

    def test_heredoc_in_a_group_keeps_its_body_for_the_next_newline(self):
        text = "{ cat <<EOF; } | x\nb\nEOF\nz"
        self.assertEqual(command_texts(text), ["cat", "x", "z"])
        self.assertEqual(self.heredocs(text)[0].body, "b\n")

    def test_heredoc_on_a_compound(self):
        text = "{ b; } <<EOF\nx\nEOF\nz"
        compound = parse(text).pipelines[0].commands[0]
        self.assertEqual(compound.redirects[0].heredoc.body, "x\n")
        self.assertEqual(command_texts(text), ["b", "z"])

    def test_a_substitution_that_closes_before_its_body_is_an_error(self):
        text = "echo $(cat <<EOF) \nx\nEOF\n"
        with self.assertRaises(shell.ShellSyntaxError) as caught:
            parse(text)
        self.assertEqual(caught.exception.kind, "bad_heredoc")

    def test_backticks_that_close_before_the_body_leave_the_body_to_the_outer_text(self):
        # Not an error (section 2.3, point 3: pending openers at the end of a text have empty bodies); the lines
        # that follow are then read as commands, which is the more restrictive reading.
        self.assertEqual(command_texts("echo `cat <<EOF`\nx\nEOF\n"), ["echo `cat <<EOF`", "cat", "x", "EOF"])

    def test_a_heredoc_inside_backticks_ends_with_the_backtick_text(self):
        text = "echo `cat <<EOF\nx\nEOF\n`"
        self.assertEqual(command_texts(text), ["echo `cat <<EOF\nx\nEOF\n`", "cat"])

    def test_the_opener_in_a_comment_or_quote_is_not_a_heredoc(self):
        self.assertEqual(self.heredocs("a # <<EOF\nb\nEOF"), [])
        self.assertEqual(command_texts("a # <<EOF\nb"), ["a", "b"])
        self.assertEqual(command_texts("echo '<<EOF'\nb"), ["echo <<EOF", "b"])

    def test_the_delimiter_is_literal(self):
        self.assertEqual(self.heredocs("cat <<$X\nb\n$X\n")[0].delimiter, "$X")

    def test_a_delimiter_is_required(self):
        for text in ("cat <<", "cat <<\n", "cat << ;", "cat <<-"):
            with self.subTest(text):
                with self.assertRaises(shell.ShellSyntaxError) as caught:
                    parse(text)
                self.assertEqual(caught.exception.kind, "bad_heredoc")


class HeredocExpansions(unittest.TestCase):
    """SL9 (HD2): an unquoted body is read like double quotes, a quoted one is data."""

    def check(self, body, expected, quoted=False):
        delimiter = "'EOF'" if quoted else "EOF"
        text = f"cat <<{delimiter}\n{body}\nEOF\n"
        with self.subTest(text):
            self.assertEqual(command_texts(text), ["cat"] + expected)

    def test_unquoted_body_expansions_are_commands(self):
        self.check("$(a)", ["a"])
        self.check("x `a` y", ["a"])
        self.check("${X:-$(a)}", ["a"])
        self.check("$((1 + $(a)))", ["a"])
        self.check("one\n$(a)\ntwo $(b c)", ["a", "b c"])
        self.check("a $(case x in a) b;; esac)", ["b"])

    def test_quoted_body_is_data(self):
        self.check("$(a)", [], quoted=True)
        self.check("`a` ${X:-$(a)}", [], quoted=True)

    def test_escaped_expansions_are_text(self):
        self.check("\\$(a) \\`b\\` \\\\$(c)", ["c"])

    def test_lone_dollars_and_quotes_in_the_body_are_text(self):
        self.check("a \" ' $ $1 $@ end", [])

    def test_the_expansions_are_in_the_tree(self):
        h = parse("cat <<EOF\n$(a) `b`\nEOF\n").pipelines[0].commands[0].redirects[0].heredoc
        self.assertEqual([p.kind for p in h.expansions], ["cmdsub", "backtick"])
        quoted = parse("cat <<'EOF'\n$(a)\nEOF\n").pipelines[0].commands[0].redirects[0].heredoc
        self.assertEqual(quoted.expansions, ())

    def test_expansion_sites_know_their_command(self):
        found = sites("cat <<EOF\n$(a)\nEOF\n")
        self.assertEqual([s.cmd.words[0].text for s in found], ["cat", "a"])
        self.assertIs(found[1].substitution, found[0])
        self.assertFalse(found[1].top_level)

    def test_an_unclosed_expansion_in_an_unquoted_body_is_an_error(self):
        for body in ("$(a", "${a", "`a"):
            with self.subTest(body):
                with self.assertRaises(shell.ShellSyntaxError):
                    parse(f"cat <<EOF\n{body}\nEOF\n")
        self.assertEqual(command_texts("cat <<'EOF'\n$(a\nEOF\n"), ["cat"])


class Errors(unittest.TestCase):
    """SL10 (S3, S9): text that does not close or is outside the subset is an error with a kind and a position."""

    CASES = [
        ("dq", 'echo "a', "unterminated_quote", 5),
        ("sq", "echo 'a", "unterminated_quote", 5),
        ("ansi", "echo $'a", "unterminated_quote", 5),
        ("backtick", "echo `a", "unterminated_substitution", 5),
        ("cmdsub", "echo $(a", "unterminated_substitution", 5),
        ("procsub", "echo <(a", "unterminated_substitution", 5),
        ("param", "echo ${a", "unterminated_expansion", 5),
        ("arith", "echo $((1", "unterminated_expansion", 5),
        ("old arith", "echo $[1", "unterminated_expansion", 5),
        ("arith that is a subshell", "echo $((a); b)", "unterminated_expansion", 5),
        ("if", "if a; then b", "unterminated_compound", None),
        ("while", "while a; do b", "unterminated_compound", None),
        ("case", "case x in a) b;;", "unterminated_compound", None),
        ("group", "{ a;", "unterminated_compound", None),
        ("subshell", "(a", "unterminated_compound", None),
        ("cond", "[[ a", "unterminated_compound", None),
        ("for", "for i in a", "unterminated_compound", None),
        ("stray fi", "fi", "unexpected_token", 0),
        ("stray then", "a; then b", "unexpected_token", 3),
        ("stray brace", "a; }", "unexpected_token", 3),
        ("stray close paren", "a )", "unexpected_token", 2),
        ("word after a subshell", "(a) b", "unexpected_token", 4),
        ("word after a group", "{ a; } b", "unexpected_token", 7),
        ("lone separator", ";", "unexpected_token", 0),
        ("double separator", "a ;; b", "unexpected_token", 2),
        ("and-or without right side", "a &&", "unexpected_token", 4),
        ("pipe without right side", "a |", "unexpected_token", 3),
        ("redirect without target", "a >", "unexpected_token", 3),
        ("empty subshell", "()", "unexpected_token", 1),
        ("empty group", "{ ; }", "unexpected_token", 2),
        ("empty if body", "if a; then fi", "unexpected_token", 11),
        ("heredoc without delimiter", "cat <<", "bad_heredoc", 6),
        ("zsh for", "for i (1) a", "unsupported", 6),
        ("zsh foreach", "foreach i (1) a end", "unsupported", 0),
        ("zsh always", "always { b; }", "unsupported", 0),
        ("zsh always after a group", "{ a; } always { b; }", "unexpected_token", 7),
        ("brace without semicolon", "{ a }", "unterminated_compound", None),
        ("zsh glob qualifier", "ls *(.)", "unexpected_token", 4),
        ("zsh equals substitution", "echo =(a)", "unexpected_token", 6),
        ("zsh disown", "a &| b", "unsupported", 2),
        ("zsh disown bang", "a &! b", "unsupported", 2),
        ("anonymous function", "() { a }", "unexpected_token", 1),
        ("extglob", "echo @(a|b)", "unexpected_token", 6),
        ("nul", "a\0b", "unsupported", 1),
        ("function body is not compound", "f() a", "unexpected_token", 4),
        ("two time", "time time a", "unexpected_token", 5),
        ("name and paren", "a (b)", "unexpected_token", 3),
        ("for without do", "for i in a; b; done", "unexpected_token", None),
        ("subshell as arith that does not close", "((a;", "unterminated_compound", None),
    ]

    def test_errors(self):
        for ident, text, kind, pos in self.CASES:
            with self.subTest(ident):
                with self.assertRaises(shell.ShellSyntaxError) as caught:
                    parse(text)
                self.assertEqual(caught.exception.kind, kind)
                if pos is not None:
                    self.assertEqual(caught.exception.pos, pos)
                self.assertIsInstance(caught.exception.pos, int)

    def test_the_errors_are_shell_errors(self):
        self.assertTrue(issubclass(shell.ShellSyntaxError, shell.ShellError))
        self.assertTrue(issubclass(shell.NestingTooDeep, shell.ShellError))
        self.assertTrue(issubclass(shell.BudgetExceeded, shell.ShellError))

    def test_valid_neighbours_of_the_errors_parse(self):
        for text in ("echo \"a\"", "echo $(a)", "echo ${a}", "echo $((1))", "if a; then b; fi", "{ a; }", "(a)",
                     "a &", "a & b", "cat <<EOF", "echo ';' \"(\" '`'", "echo a\\", "echo a #\\", "a ; b ;"):
            with self.subTest(text):
                parse(text)

    def test_the_position_is_shifted_by_base(self):
        with self.assertRaises(shell.ShellSyntaxError) as caught:
            shell.parse("echo 'a", shell.Budget(100), base=10)
        self.assertEqual(caught.exception.pos, 15)


class Nesting(unittest.TestCase):
    """SL11 (S7): `MAX_NESTING` is 32."""

    @staticmethod
    def subshells(n):
        return "( " * n + "a" + " )" * n

    @staticmethod
    def substitutions(n):
        return "echo $(" * n + "a" + ")" * n

    @staticmethod
    def ifs(n):
        return "if a; then " * n + "b" + "; fi" * n

    def test_the_limit_is_32(self):
        self.assertEqual(shell.MAX_NESTING, 32)

    def test_32_levels_read_and_33_do_not(self):
        for name, build in (("subshell", self.subshells), ("substitution", self.substitutions), ("if", self.ifs)):
            with self.subTest(name):
                tree = parse(build(32))
                self.assertGreaterEqual(len(list(shell.iter_sites(tree))), 1)
                with self.assertRaises(shell.NestingTooDeep):
                    parse(build(33))

    def test_other_nesting_forms_are_counted(self):
        forms = {
            "group": ("{ " * 33 + "a" + "; }" * 33),
            "param": "echo " + "${a:-" * 33 + "x" + "}" * 33,
            "arith": "echo " + "$((" * 33 + "1" + "))" * 33,
            "case": "case a in a) " * 33 + "b" + ";; esac" * 33,
            "while": "while a; do " * 33 + "b" + "; done" * 33,
            "for": "for i in a; do " * 33 + "b" + "; done" * 33,
        }
        for name, text in forms.items():
            with self.subTest(name):
                with self.assertRaises(shell.NestingTooDeep):
                    parse(text)

    def test_nesting_through_backticks_is_counted(self):
        parse(self.alternating(32))
        with self.assertRaises(shell.NestingTooDeep):
            parse(self.alternating(33))

    @staticmethod
    def alternating(n):
        """n nested command substitutions, alternating `$(` and (escaped) backticks."""
        text = "a"
        for level in range(n):
            if level % 2:
                text = "echo `" + text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$") + "`"
            else:
                text = "echo $(" + text + ")"
        return text

    def test_a_sequence_is_not_nesting(self):
        parse("; ".join(["( a )"] * 500))
        parse("echo " + " ".join(["$(a)"] * 500))


class Budgets(unittest.TestCase):
    """SL12 (S10)."""

    def test_the_text_is_charged(self):
        with self.assertRaises(shell.BudgetExceeded):
            parse("echo hello!", 10)
        parse("echo hello", 10)

    def test_the_budget_is_shared_by_every_parse(self):
        budget = shell.Budget(20)
        shell.parse("echo 12345", budget)
        shell.parse("echo 12345", budget)
        with self.assertRaises(shell.BudgetExceeded):
            shell.parse("a", budget)

    def test_backtick_contents_are_charged_again(self):
        text = "echo `echo x`"
        parse(text, len(text) + len("echo x"))
        with self.assertRaises(shell.BudgetExceeded):
            parse(text, len(text) + len("echo x") - 1)

    def test_nested_backticks_are_charged_at_every_level(self):
        text = "echo `echo \\`echo x\\``"
        with self.assertRaises(shell.BudgetExceeded):
            parse(text, len(text) + 10)

    def test_unquoted_heredoc_bodies_are_charged_again(self):
        text = "cat <<EOF\n" + "x" * 50 + "\nEOF\n"
        parse(text, len(text) + 51)
        with self.assertRaises(shell.BudgetExceeded):
            parse(text, len(text) + 49)
        quoted = text.replace("<<EOF", "<<'EOF'")
        parse(quoted, len(quoted))

    def test_substitutions_in_the_same_text_are_not_charged_again(self):
        text = "echo $(a $(b))"
        parse(text, len(text))

    def test_the_budget_is_a_plain_counter(self):
        budget = shell.Budget(5)
        budget.charge(5)
        with self.assertRaises(shell.BudgetExceeded):
            budget.charge(1)


class Walk(unittest.TestCase):
    """SL13: `iter_sites` gives each simple command its context."""

    def test_command_after_a_list_is_top_level(self):
        found = sites("cd x && cat > f <<EOF\nb\nEOF\n")
        self.assertEqual([(s.cmd.words[0].text, s.top_level, s.stages, s.stage) for s in found],
                         [("cd", True, 1, 0), ("cat", True, 1, 0)])
        self.assertTrue(all(s.substitution is None and not s.in_compound for s in found))

    def test_a_group_in_a_pipeline_is_not_top_level(self):
        found = sites("{ cat <<EOF; } | x\nb\nEOF\n")
        by_head = {s.cmd.words[0].text: s for s in found}
        self.assertFalse(by_head["cat"].top_level)
        self.assertTrue(by_head["cat"].in_compound)
        self.assertEqual((by_head["cat"].stages, by_head["cat"].stage), (1, 0))
        self.assertEqual((by_head["x"].top_level, by_head["x"].stages, by_head["x"].stage), (True, 2, 1))

    def test_stage_of_a_command_with_a_heredoc(self):
        found = sites("x | cat > f <<EOF\nb\nEOF\n")
        self.assertEqual([(s.cmd.words[0].text, s.stages, s.stage, s.top_level) for s in found],
                         [("x", 2, 0, True), ("cat", 2, 1, True)])

    def test_a_message_substitution_knows_its_word(self):
        text = "gi" "t commit -m \"$(cat <<'EOF'\nmsg\nEOF\n)\""
        found = sites(text)
        self.assertEqual([s.cmd.words[0].text for s in found], ["git", "cat"])
        outer, inner = found
        self.assertTrue(outer.top_level and outer.substitution is None)
        self.assertFalse(inner.top_level)
        self.assertIs(inner.substitution, outer)
        self.assertEqual(inner.sub_word.text, "$(cat <<'EOF'\nmsg\nEOF\n)")
        self.assertIs(inner.sub_word, outer.cmd.words[3])
        self.assertEqual(inner.cmd.redirects[0].heredoc.body, "msg\n")
        self.assertTrue(inner.cmd.redirects[0].heredoc.quoted)

    def test_a_simple_command_comes_before_the_ones_in_its_words(self):
        self.assertEqual(command_texts("a $(b) $(c $(d)) e"), ["a $(b) $(c $(d)) e", "b", "c $(d)", "d"])

    def test_substitutions_in_assignments_and_redirects_are_walked(self):
        found = sites("A=$(a) b > $(c)")
        self.assertEqual([s.cmd.words[0].text if s.cmd.words else "" for s in found], ["b", "a", "c"])
        self.assertIs(found[1].substitution, found[0])
        self.assertIs(found[2].substitution, found[0])
        self.assertEqual(found[1].sub_word.text, "A=$(a)")  # the assignment word holds it

    def test_compound_words_hold_substitutions_without_a_command(self):
        found = sites("for i in $(a); do b; done")
        self.assertEqual([(s.cmd.words[0].text, s.substitution, s.in_compound) for s in found],
                         [("a", None, True), ("b", None, True)])
        self.assertEqual(found[0].sub_word.text, "$(a)")

    def test_a_compound_inside_a_substitution_keeps_the_command(self):
        found = sites("echo $( (a) )")
        self.assertIs(found[1].substitution, found[0])
        self.assertTrue(found[1].in_compound)

    def test_spans_slice_the_source(self):
        text = "a  b ${X:-1}  >f; (c d) | e\nf g"
        script = parse(text)
        spans = [cmd.span for pipeline in script.pipelines for cmd in pipeline.commands]
        self.assertEqual([text[a:b] for a, b in spans], ["a  b ${X:-1}  >f", "(c d)", "e", "f g"])
        self.assertEqual(script.span, (0, len(text)))
        word = script.pipelines[0].commands[0].words[1]
        self.assertEqual(text[word.span[0]:word.span[1]], "b")

    def test_spans_follow_base(self):
        script = shell.parse("a b", shell.Budget(10), base=100)
        self.assertEqual(script.pipelines[0].commands[0].span, (100, 103))

    def test_the_empty_script(self):
        script = parse("")
        self.assertEqual((script.pipelines, script.span), ((), (0, 0)))
        self.assertEqual(list(shell.iter_sites(script)), [])


class PipedStdin(unittest.TestCase):
    """`Site.piped`: a command in a compound body fed by a pipe stage reads that pipe on stdin."""

    def piped_of(self, text, head="bash"):
        found = [s for s in sites(text) if s.cmd.words and s.cmd.words[0].text == head]
        self.assertEqual(len(found), 1, text)
        return getattr(found[0], "piped", None)

    def test_a_command_in_a_group_after_a_pipe_is_piped(self):
        for text in ("echo x | { bash; }", "echo x | ( bash )", "echo x | { bash; } < f"):
            with self.subTest(text=text):
                self.assertIs(self.piped_of(text), True)

    def test_a_command_without_inherited_stdin_is_not_piped(self):
        for text in ("f() { bash; }", "{ bash; }"):
            with self.subTest(text=text):
                self.assertIs(self.piped_of(text), False)

    def test_a_process_substitution_writer_script_is_piped(self):
        """The stdin of a `>(...)` script is always the pipe the writer fills, whatever encloses it."""
        for text in (
            "echo x > >(bash)", "echo x >> >(bash)", "echo x &> >(bash)", "echo x 2> >(bash)",
            "echo x 2>&1 > >(bash)", "tee >(bash) <<< x", "echo x > >( { bash; } )", "echo x > >( ( bash ) )",
            "echo x > >(while read l; do bash; done)",
        ):
            with self.subTest(text=text):
                self.assertIs(self.piped_of(text), True)

    def test_a_process_substitution_reader_script_is_not_piped(self):
        self.assertIs(self.piped_of("bash <(echo x)", head="echo"), False)

    def test_a_coproc_body_is_always_piped(self):
        """User decision 2026-11-18: a coproc body is piped whether or not the writer is visible."""
        for text in ("coproc { bash; }", "coproc NAME { bash; }", "coproc bash", "coproc NAME ( bash )"):
            with self.subTest(text=text):
                self.assertIs(self.piped_of(text), True)

    def test_a_function_body_is_not_piped_at_its_definition(self):
        for text in ("f() { bash; }", "function f { bash; }", "f() ( bash )"):
            with self.subTest(text=text):
                self.assertIs(self.piped_of(text), False)


def first_words(text):
    return parse(text).pipelines[0].commands[0].words


class AnsiQuoting(unittest.TestCase):
    """SL14: `$'...'` is decoded the way bash reads it; what cannot be decoded for certain is dynamic."""

    def test_escapes_decode_to_what_the_shell_sees(self):
        rows = [
            ("hex", "$'\\x64ocker'", "docker"),
            ("hex one digit", "$'\\x6z'", "\x06z"),
            ("octal", "$'\\144ocker'", "docker"),
            ("octal two digits", "$'\\65'", "5"),
            ("unicode", "$'\\u0064ocker'", "docker"),
            ("long unicode", "$'\\U00000064ocker'", "docker"),
            ("control", "$'\\cA'", "\x01"),
            ("escape e", "$'\\e[0m'", "\x1b[0m"),
            ("escape E", "$'\\E'", "\x1b"),
            ("simple", "$'\\a\\b\\f\\n\\r\\t\\v\\\\\\'\\\"'", "\a\b\f\n\r\t\v\\'\""),
            ("plain", "$'docker'", "docker"),
            ("mixed with a literal", "do$'\\x63'ker", "docker"),
        ]
        for ident, text, expected in rows:
            with self.subTest(ident):
                (word,) = first_words(text)
                self.assertEqual(word.text, expected)
                self.assertFalse(word.dynamic)
                self.assertTrue(word.quoted)

    def test_program_name_and_argument_are_the_decoded_text(self):
        self.assertEqual(command_texts("$'\\x64ocker' restart $'\\141pi'"), ["docker restart api"])

    def test_heredoc_delimiter_is_the_decoded_text(self):
        h = parse("cat <<$'E\\x4fF'\nbody\nEOF\n").pipelines[0].commands[0].redirects[0].heredoc
        self.assertEqual((h.delimiter, h.quoted, h.body, h.terminated), ("EOF", True, "body\n", True))

    def test_assignment_value_is_the_decoded_text(self):
        (assignment,) = parse("A=$'\\x64ocker' b").pipelines[0].commands[0].assignments
        self.assertEqual(assignment.text, "A=docker")

    def test_what_cannot_be_decoded_for_certain_is_dynamic(self):
        rows = [
            ("unknown escape", "$'\\q'"),
            ("zsh meta", "$'\\C-a'"),
            ("nul octal", "$'a\\0b'"),
            ("nul hex", "$'a\\x00b'"),
            ("nul unicode", "$'a\\u0000b'"),
            ("high byte", "$'\\xff'"),
            ("high octal", "$'\\377'"),
            ("non ascii code point", "$'\\u00e9'"),
            ("not a character", "$'\\UFFFFFFFF'"),
            ("surrogate", "$'\\ud800'"),
            ("hex without digits", "$'\\xg'"),
            ("unicode without digits", "$'\\u'"),
            ("control without a character", "$'\\c'"),
            ("control of a backslash", "$'\\c\\\\'"),
            ("control that is nul", "$'\\c@'"),
            ("line continuation", "$'a\\\nb'"),
        ]
        for ident, text in rows:
            with self.subTest(ident):
                (word,) = first_words(text)
                self.assertTrue(word.dynamic)
                self.assertTrue(word.parts[0].dyn)

    def test_a_dynamic_part_leaves_the_other_words_alone(self):
        a, b = first_words("$'\\q' $'\\x41'")
        self.assertTrue(a.dynamic)
        self.assertFalse(b.dynamic)


class HeredocBodiesInsideCompoundWords(unittest.TestCase):
    """SL15: a newline consumed inside `[[ ]]` or an array starts the pending heredoc bodies."""

    def test_a_cond_after_a_heredoc_opener_reads_the_body_first(self):
        text = "bash <<EOF && [[ -n x\ndocker restart a\nEOF\n]]"
        script = parse(text)
        first = script.pipelines[0].commands[0]
        self.assertEqual((first.redirects[0].heredoc.body, first.redirects[0].heredoc.terminated),
                         ("docker restart a\n", True))
        self.assertEqual(command_texts(text), ["bash"])
        self.assertEqual(script.pipelines[1].commands[0].kind, "cond")

    def test_a_declare_array_after_a_heredoc_opener_reads_the_body_first(self):
        text = "cat <<EOF; declare -a B=(a\ndocker restart a\nEOF\nb)"
        script = parse(text)
        h = script.pipelines[0].commands[0].redirects[0].heredoc
        self.assertEqual((h.body, h.terminated), ("docker restart a\n", True))
        declare = script.pipelines[1].commands[0]
        (array,) = declare.words[2].parts[-1:]
        self.assertEqual([w.text for w in array.elements], ["a", "b"])

    def test_an_assignment_array_after_a_heredoc_opener_reads_the_body_first(self):
        text = "<<EOF A=(a\ndocker restart a\nEOF\nb) cmd"
        script = parse(text)
        h = script.pipelines[0].commands[0].redirects[0].heredoc
        self.assertEqual((h.body, h.terminated), ("docker restart a\n", True))
        self.assertEqual(command_texts(text), ["cmd"])

    def test_an_unterminated_body_inside_the_cond_is_empty(self):
        with self.assertRaises(shell.ShellSyntaxError):
            parse("bash <<EOF && [[ -n x\ndocker restart a\n")


class ProcessSubstitutionPlaces(unittest.TestCase):
    """SL16: `<(` and `>(` are a process substitution anywhere in an unquoted word, `[[ ]]` operands included."""

    def test_in_an_assignment_value(self):
        for text in ("A=<(true) cmd", "A=x<(true) cmd", "A=>(true) cmd", "A=x>(true) cmd"):
            with self.subTest(text):
                self.assertEqual(command_texts(text), ["cmd", "true"])
                (assignment,) = sites(text)[0].cmd.assignments
                self.assertIn(assignment.parts[-1].kind, ("procsub_in", "procsub_out"))

    def test_in_the_middle_of_a_word(self):
        found = sites("echo a<(true)b")
        self.assertEqual([" ".join(w.text for w in s.cmd.words) for s in found], ["echo a<(true)b", "true"])
        self.assertIs(found[1].substitution, found[0])

    def test_in_a_cond_operand(self):
        for text in ("[[ -n <(true) ]]", "[[ x == y<(true) ]]", "[[ >(true) ]]"):
            with self.subTest(text):
                self.assertEqual(command_texts(text), ["true"])

    def test_at_the_start_of_a_word_as_before(self):
        self.assertEqual(command_texts("cat <(a) >(b)"), ["cat <(a) >(b)", "a", "b"])

    def test_quoted_and_regex_text_is_not_a_substitution(self):
        self.assertEqual(command_texts("echo 'a<(b)' \"c>(d)\""), ["echo a<(b) c>(d)"])
        self.assertEqual(command_texts("[[ x =~ a<(b) ]]"), [])

    def test_a_redirect_is_still_a_redirect(self):
        cmd = sites("echo a >out 2>&1 <in")[0].cmd
        self.assertEqual([r.op for r in cmd.redirects], [">", ">&", "<"])


class ZshParameterForms(unittest.TestCase):
    """SL17: `$=NAME`, `$~NAME`, `$^NAME` and the brace forms are parameter expansions."""

    def test_the_forms_are_param_parts(self):
        for text in ("$=NAME", "$~NAME", "$^NAME", "$==NAME", "$~~NAME", "$=1", "$=@", "${=NAME}", "${~NAME}",
                     "${^NAME}", "${==NAME}"):
            with self.subTest(text):
                (word,) = first_words(text)
                self.assertEqual([p.kind for p in word.parts], ["param"])
                self.assertEqual(word.text, text)
                self.assertTrue(word.dynamic)

    def test_the_form_in_double_quotes_and_in_the_head(self):
        (word,) = first_words('"$=NAME"')
        self.assertTrue(word.dynamic)
        self.assertEqual(first_words("$=CMD restart")[0].parts[0].kind, "param")

    def test_a_lone_marker_is_text(self):
        for text in ("a-b", "$=", "$~", "$^", "$= x", "~/bin"):
            with self.subTest(text):
                self.assertFalse(first_words(text)[0].dynamic)

    def test_the_text_after_the_name_stays_literal(self):
        (word,) = first_words("$=NAME-x")
        self.assertEqual([(p.kind, p.text) for p in word.parts], [("param", "$=NAME"), ("lit", "-x")])


class ZshRepeat(unittest.TestCase):
    """SL18: the zsh `repeat N { ... }` is outside the grammar."""

    def test_a_brace_after_repeat_and_count_is_unsupported(self):
        for text in ("repeat 3 { echo a; }", "repeat $N { echo a; }", "repeat 3 {\n echo a\n}", "A=1 repeat 3 { x; }"):
            with self.subTest(text):
                with self.assertRaises(shell.ShellSyntaxError) as raised:
                    parse(text)
                self.assertEqual(raised.exception.kind, "unsupported")

    def test_other_repeat_forms_and_braces_read_as_before(self):
        self.assertEqual(command_texts("repeat 3 echo a"), ["repeat 3 echo a"])
        self.assertEqual(command_texts("echo repeat 3 '{'"), ["echo repeat 3 {"])
        self.assertEqual(command_texts("echo repeat 3 x {a,b}"), ["echo repeat 3 x {a,b}"])
        self.assertEqual(command_texts("repeat; { echo a; }"), ["repeat", "echo a"])


class BraceExpansion(unittest.TestCase):
    """SL19: `Word.has_brace` reports an unquoted brace expansion."""

    def test_brace_expansions(self):
        for text in ("{a,b}", "{1..3}", "x{a,b}y", "{a,{b,c}}", "{,}", "{a..z}", "{a,\"b\"}", "{a,$X}", "{$X,b}",
                     "a{1..3}b{x,y}"):
            with self.subTest(text):
                self.assertTrue(first_words(text)[0].has_brace)

    def test_not_brace_expansions(self):
        for text in ("{a}", "{}", "'{a,b}'", '"{a,b}"', "\\{a,b}", "{a\\,b}", "${X}", "${X:-a,b}", "$'{a,b}'",
                     "a,b", "{a", "a}", "{\"a,b\"}", "$((1,2))"):
            with self.subTest(text):
                self.assertFalse(first_words(text)[0].has_brace)

    def test_a_quoted_comma_is_not_a_separator_but_a_second_one_is(self):
        self.assertFalse(first_words("{a\",\"b}")[0].has_brace)
        self.assertTrue(first_words("{a\",\",b}")[0].has_brace)

    def test_has_glob_is_independent(self):
        word = first_words("{a,b}*")[0]
        self.assertTrue(word.has_brace and word.has_glob)


class CodeEvaluatingExpansions(unittest.TestCase):
    """SL20: `Word.evaluates_code` and `Part.code` report `${(e)X}`, `${(%)X}` and `${X@P}`."""

    def test_the_evaluating_forms(self):
        for text in ("${(e)X}", "${(%)X}", "${(%%)X}", "${(@e)X}", "${(e%)X}", "${(ej:,:)X}", "${=(e)X}", "${X@P}",
                     "${X[@]@P}", "${!X@P}", "${(e)X[1]}", "${(e)${Y}}", "${Z:-${(e)X}}", '"${(e)X}"', '"${X@P}"',
                     "pre${(e)X}post"):
            with self.subTest(text):
                (word,) = first_words(text)
                self.assertTrue(word.evaluates_code)

    def test_the_part_carries_the_flag(self):
        (word,) = first_words("${(e)X}")
        self.assertTrue(word.parts[0].code)
        (word,) = first_words('"a${X@P}"')
        self.assertTrue(word.parts[0].inner[0].code)

    def test_forms_that_do_not_evaluate(self):
        for text in ("${X}", "${(j:,:)X}", "${(@)X}", "${(P)X}", "${(L)X}", "${X:-(e)}", "${X@Q}", "${X@E}",
                     "${#X}", "$X", "$(echo)", "'${(e)X}'", "${X:-@P}", "$'${(e)X}'"):
            with self.subTest(text):
                (word,) = first_words(text)
                self.assertFalse(word.evaluates_code)

    def test_the_expansion_is_still_dynamic(self):
        self.assertTrue(first_words("${(e)X}")[0].dynamic)


class FactsValue(unittest.TestCase):
    """`Facts`, `NO_FACTS`, `UNKNOWN_FACTS` and the contexts built from and read back into facts."""

    def test_join_is_the_union_with_or_on_the_flags(self):
        a = shell.Facts(frozenset({"p"}), False, True)
        b = shell.Facts(frozenset({"q"}), True, False)
        self.assertEqual(a.join(b), shell.Facts(frozenset({"p", "q"}), True, True))
        self.assertEqual(a.join(shell.NO_FACTS), a)

    def test_for_parent_child_clears_moved_only(self):
        facts = shell.Facts(frozenset({"p"}), True, True)
        self.assertEqual(facts.for_parent("child"), shell.Facts(frozenset({"p"}), True, False))
        self.assertEqual(facts.for_parent("same"), facts)
        self.assertEqual(facts.for_parent("body"), facts)

    def test_a_link_goes_up_from_a_child_with_the_directory_change_it_implies(self):
        linked = shell.Facts(frozenset({"p"}), False, True, True)
        self.assertEqual(linked.for_parent("child"), linked)
        self.assertEqual(linked.for_parent("same"), linked)
        self.assertEqual(linked.for_parent("body"), linked)
        self.assertTrue(shell.Facts(linked=True).moved)  # (a link is a change of what a relative path names)
        self.assertEqual(shell.Facts(frozenset({"p"}), True, True, False).for_parent("child"),
                         shell.Facts(frozenset({"p"}), True, False, False))

    def test_join_keeps_a_link_and_equality_tells_it_apart(self):
        a = shell.Facts(frozenset(), False, True, True)
        b = shell.Facts(frozenset({"q"}), False, True, False)
        self.assertEqual(a.join(b), shell.Facts(frozenset({"q"}), False, True, True))
        self.assertNotEqual(a, b)
        self.assertNotEqual(shell.Facts(moved=True), shell.Facts(linked=True))
        self.assertEqual(hash(a), hash(shell.Facts(frozenset(), False, False, True)))
        self.assertTrue(shell.Facts(linked=True))

    def test_equality_and_hash_are_by_fields(self):
        a = shell.Facts(frozenset({"p"}), False, False)
        b = shell.Facts(["p"])
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))
        self.assertNotEqual(a, shell.Facts(frozenset({"q"})))
        self.assertNotEqual(a, shell.Facts(frozenset({"p"}), True))
        self.assertNotEqual(a, shell.Facts(frozenset({"p"}), False, True))

    def test_truthiness_and_constants(self):
        self.assertFalse(shell.NO_FACTS)
        self.assertTrue(shell.UNKNOWN_FACTS)
        self.assertEqual(shell.UNKNOWN_FACTS, shell.Facts(frozenset(), True, True))
        self.assertTrue(shell.Facts(frozenset({"p"})))
        self.assertTrue(shell.Facts(moved=True))

    def test_facts_are_immutable(self):
        with self.assertRaises(AttributeError):
            shell.NO_FACTS.moved = True
        with self.assertRaises(AttributeError):
            del shell.NO_FACTS.fifos

    def test_of_builds_the_fifos_and_moved(self):
        ctx = shell.StdinContext.of({3: shell.DYNAMIC}, shell.Facts(frozenset({"a/p"}), False, True))
        self.assertTrue(ctx.fifos.match_text("./a/p"))
        self.assertFalse(ctx.fifos.match_text("other"))
        self.assertTrue(ctx.moved)
        self.assertEqual(ctx.fds, {3: shell.DYNAMIC})
        self.assertIs(ctx.end, ctx.fds)
        unknown = shell.StdinContext.of(None, shell.UNKNOWN_FACTS, {})
        self.assertTrue(unknown.fifos.match_text("anything"))
        self.assertEqual(unknown.end, {})

    def test_facts_round_trip_through_a_context(self):
        for facts in (shell.NO_FACTS, shell.UNKNOWN_FACTS, shell.Facts(frozenset({"p", "q"}), False, True),
                      shell.Facts(frozenset({"p"}), True, False)):
            with self.subTest(facts=facts):
                self.assertEqual(shell.StdinContext.of({}, facts).facts(), facts)
        self.assertEqual(shell.StdinContext().facts(), shell.NO_FACTS)
        self.assertEqual(shell.StdinContext({}, None, True).facts(), shell.Facts(moved=True))


class StdinNames(unittest.TestCase):
    """The pure helpers of the stdin state (`stdin_alias`, `normalize_name`, `normalize_path`, `Fifos`, `fd_states`,
    `stdin_state`, `exec_fds`). Texts are only parsed."""

    def redirects(self, text):
        return sites(text)[0].cmd.redirects

    def fifos(self, *names, unknown=False):
        fifos = shell.Fifos()
        fifos.names.update(names)
        fifos.unknown = unknown
        return fifos

    def first_word(self, text, index=1):
        return sites(text)[0].cmd.words[index]

    # -- normalize_name / normalize_path -------------------------------------------------------------------------

    def test_normalize_name_applies_dots_and_empty_components(self):
        for text, expected in (
            ("./a//b/../c", "a/c"), ("..", ".."), ("../..", "../.."), ("a/..", "."), ("/", "/"), ("//a/./b", "/a/b"),
            ("/..", "/"), ("", "."), ("/a/../../b", "/b"), ("../a/..", ".."),
        ):
            with self.subTest(text=text):
                self.assertEqual(shell.normalize_name(text), expected)

    def test_normalize_path_is_none_for_a_relative_path(self):
        self.assertIsNone(shell.normalize_path("dev/stdin"))
        self.assertIsNone(shell.normalize_path("../dev/stdin"))
        self.assertEqual(shell.normalize_path("/dev/./fd//3"), "/dev/fd/3")

    # -- stdin_alias ---------------------------------------------------------------------------------------------

    def test_stdin_alias_names_the_descriptor_of_a_stdin_path(self):
        for text, expected in (
            ("/dev/stdin", 0), ("/dev/./stdin", 0), ("/dev//stdin", 0), ("/dev/fd/3", 3), ("/dev//fd/3", 3),
            ("/proc/self/fd/0", 0), ("/proc/123/fd/5", 5), ("/proc/self/task/7/fd/2", 2), ("/proc/$$/fd/0", 0),
            ("/a/../../dev/stdin", 0),
        ):
            with self.subTest(text=text):
                self.assertEqual(shell.stdin_alias(text), expected)

    def test_stdin_alias_is_none_for_any_other_path(self):
        for text in ("/dev/null", "/dev/stdout", "/dev/fd/x", "stdin", "dev/stdin", "/tmp/stdin", "/dev/fd/"):
            with self.subTest(text=text):
                self.assertIsNone(shell.stdin_alias(text))

    def test_stdin_alias_sees_through_the_root_link_of_proc(self):
        """User decision 2026-11-18: `/proc/<pid>/root` and `/proc/<pid>/cwd` prefixes are stripped."""
        for text, expected in (
            ("/proc/self/root/dev/stdin", 0), ("/proc/self/root/proc/self/fd/0", 0),
            ("/proc/self/root/dev/fd/3", 3),
        ):
            with self.subTest(text=text):
                self.assertEqual(shell.stdin_alias(text), expected)

    # -- Fifos ---------------------------------------------------------------------------------------------------

    def test_an_empty_fifo_set_matches_nothing(self):
        fifos = shell.Fifos()
        self.assertFalse(fifos)
        self.assertFalse(fifos.match(self.first_word("bash p")))

    def test_a_fifo_set_matches_the_normalized_names_it_holds(self):
        fifos = self.fifos("p", "/tmp/q")
        self.assertTrue(fifos)
        for text, expected in (("bash p", True), ("bash ./p", True), ("bash /tmp/./q", True), ("bash other", False)):
            with self.subTest(text=text):
                self.assertEqual(fifos.match(self.first_word(text)), expected)
        self.assertFalse(fifos.match(None))

    def test_a_fifo_set_with_an_unreadable_name_matches_any_word(self):
        fifos = self.fifos(unknown=True)
        self.assertTrue(fifos)
        for text in ("bash other", "bash $f", "bash *.sh"):
            with self.subTest(text=text):
                self.assertTrue(fifos.match(self.first_word(text)))

    def test_a_dynamic_or_glob_word_may_name_a_known_fifo(self):
        fifos = self.fifos("p")
        for text in ("bash $f", "bash ?", "bash [p]"):
            with self.subTest(text=text):
                self.assertTrue(fifos.match(self.first_word(text)))

    # -- fd_states / stdin_state ---------------------------------------------------------------------------------

    def test_a_here_string_and_a_heredoc_replace_the_incoming_state(self):
        self.assertIsNone(shell.stdin_state(self.redirects("bash <<< x"), shell.PIPED))
        self.assertIsNone(shell.stdin_state(self.redirects("bash <<E\nx\nE"), shell.PIPED))

    def test_a_file_never_replaces_a_pipe_but_a_process_substitution_replaces_none(self):
        self.assertEqual(shell.stdin_state(self.redirects("bash < f"), shell.PIPED), shell.PIPED)
        self.assertIsNone(shell.stdin_state(self.redirects("bash < f"), None))
        self.assertEqual(shell.stdin_state(self.redirects("bash < <(x)"), None), shell.DYNAMIC)

    def test_a_descriptor_copy_takes_the_state_of_the_source(self):
        states = shell.fd_states(self.redirects("bash 3<&0"), shell.PIPED)
        self.assertEqual(states, {0: shell.PIPED, 3: shell.PIPED})
        ctx = shell.StdinContext({3: shell.DYNAMIC})
        self.assertEqual(shell.fd_states(self.redirects("bash <&3"), None, ctx)[0], shell.DYNAMIC)

    def test_the_last_redirection_of_descriptor_zero_wins(self):
        ctx = shell.StdinContext({3: shell.DYNAMIC})
        self.assertIsNone(shell.stdin_state(self.redirects("bash <&3 <<< x"), None, ctx))
        self.assertEqual(shell.stdin_state(self.redirects("bash <<< x <&3"), None, ctx), shell.DYNAMIC)

    def test_a_fifo_file_makes_the_descriptor_piped(self):
        ctx = shell.StdinContext({}, self.fifos("p"))
        self.assertEqual(shell.stdin_state(self.redirects("bash < p"), None, ctx), shell.PIPED)
        self.assertIsNone(shell.stdin_state(self.redirects("bash < other"), None, ctx))

    def test_a_stdin_alias_file_after_a_copy_keeps_the_copied_state(self):
        ctx = shell.StdinContext({3: shell.DYNAMIC})
        self.assertEqual(shell.stdin_state(self.redirects("bash 0<&3 < /dev/stdin"), None, ctx), shell.DYNAMIC)

    def test_a_descriptor_move_takes_the_state_of_the_source(self):
        ctx = shell.StdinContext({3: shell.DYNAMIC})
        self.assertEqual(shell.stdin_state(self.redirects("bash <&3-"), None, ctx), shell.DYNAMIC)

    def test_fd_state_is_the_first_active_descriptor_with_zero_first(self):
        redirects = self.redirects("bash 3< <(x)")
        self.assertEqual(shell.fd_state(redirects, None), shell.DYNAMIC)
        self.assertIsNone(shell.fd_state(self.redirects("bash < f"), None))
        self.assertEqual(shell.fd_state(self.redirects("bash 3< <(x)"), shell.PIPED), shell.PIPED)

    # -- exec_fds ------------------------------------------------------------------------------------------------

    def test_exec_fds_sets_the_descriptors_the_redirections_name(self):
        self.assertEqual(shell.exec_fds(self.redirects("exec 3< <(x)"), shell.NO_CONTEXT), {3: shell.DYNAMIC})
        self.assertEqual(shell.exec_fds(self.redirects("exec < <(x)"), shell.NO_CONTEXT), {0: shell.DYNAMIC})

    def test_exec_fds_keeps_the_descriptors_it_does_not_name_and_drops_the_cleared_ones(self):
        ctx = shell.StdinContext({3: shell.DYNAMIC})
        self.assertEqual(shell.exec_fds(self.redirects("exec 4< <(x)"), ctx), {3: shell.DYNAMIC, 4: shell.DYNAMIC})
        self.assertEqual(shell.exec_fds(self.redirects("exec 3<<< x"), ctx), {})

    def test_exec_fds_of_a_fifo_redirect_is_piped(self):
        ctx = shell.StdinContext({}, self.fifos("p"))
        self.assertEqual(shell.exec_fds(self.redirects("exec 3< p"), ctx), {3: shell.PIPED})

    def test_exec_fds_copies_the_state_of_descriptor_zero_from_the_context(self):
        """Decision G: a copy of stdin (`exec 3<&0`) keeps the state of the descriptor it copies."""
        ctx = shell.StdinContext({0: shell.PIPED})
        self.assertEqual(shell.exec_fds(self.redirects("exec 3<&0"), ctx), {0: shell.PIPED, 3: shell.PIPED})


class SiteGiven(unittest.TestCase):
    """`Site.given` (spec audit-stdin-facts, Design 8): `dynamic_code` for what runs in the body of a compound whose own
    redirections give some descriptor a process substitution, whatever the command's own redirections."""

    def given(self, text, fds=None):
        """`head -> given` of the simple commands of the text (`resolve` gives every offset the descriptors `fds`)."""
        ctx = shell.StdinContext(dict(fds or {}))
        found = {}
        for site in shell.iter_sites(parse(text), None, lambda offset: ctx):
            found[site.cmd.words[0].text] = site.given
        return found

    def test_the_body_of_each_kind_of_compound_is_given(self):
        for text in ("{ inner; } < <(x)", "( inner ) < <(x)", "while true; do inner; done < <(x)",
                     "for i in 1; do inner; done < <(x)", "if true; then inner; fi < <(x)",
                     "case x in x) inner;; esac < <(x)", "f() { inner; } < <(x)", "{ { inner; }; } < <(x)",
                     "{ echo $(inner); } < <(x)", "{ inner; } 3< <(x)", "{ inner; } <> <(x)"):
            with self.subTest(text=text):
                self.assertEqual(self.given(text)["inner"], shell.DYNAMIC)

    def test_what_is_not_inside_such_a_body_is_not_given(self):
        found = self.given("before; { inner; } < <(x); after")
        self.assertEqual((found["before"], found["after"]), (None, None))
        self.assertIsNone(self.given("{ inner; } < <(x)")["x"])  # (the procsub itself)

    def test_a_pipe_a_fifo_and_a_body_with_no_redirection_give_nothing(self):
        for text in ("{ inner; } | cat", "cat | { inner; }", "{ inner; } < file", "{ inner; }", "{ inner; } > out",
                     "{ inner; } <<< x", "{ inner; } > >(w)"):
            with self.subTest(text=text):
                self.assertIsNone(self.given(text)["inner"])

    def test_a_descriptor_that_an_exec_gave_a_process_substitution_is_given(self):
        fds = {3: shell.DYNAMIC}
        for text in ("{ inner; } <&3", "{ inner; } < /dev/fd/3", "{ inner; } 0<&3"):
            with self.subTest(text=text):
                self.assertEqual(self.given(text, fds)["inner"], shell.DYNAMIC)
        self.assertIsNone(self.given("{ inner; } <&4", fds)["inner"])
        self.assertIsNone(self.given("{ inner; } <&3", {3: shell.PIPED})["inner"])

    def test_an_inner_compound_inherits_what_the_outer_one_gave(self):
        found = self.given("{ ( inner ) < file; } < <(x)")
        self.assertEqual(found["inner"], shell.DYNAMIC)


def load_tests(loader, tests, pattern):
    """Independent cases: run them in forked workers (see `ForkedSuite`)."""
    return ForkedSuite(tests)


if __name__ == "__main__":
    unittest.main()
