"""Lexer and parser of the shell subset the agent-audit hook understands.

Source: spec audit-shell-lexer, sections 2 (grammar) and 3 (this module), Task 1.

Pure on purpose (P2): only `re` from the standard library, no file or process access and no mutable module state.
`parse(text, budget)` reads a command text into a tree (lists, pipelines, compounds, simple commands, words with
their parts, redirections, heredocs); `iter_sites(script)` walks every simple command, nested scripts included. Text
that does not close, or that is outside the subset, is an error (`ShellSyntaxError`), never a guess: the caller
decides what an error means (the hook denies the command, level B).

Load time: the hook runs as a script, so this module is loaded in every call (from bytecode, see the spec, section
7). Its cost is what the module does at import, not its size: the tree nodes are plain `__slots__` classes (a
`typing.NamedTuple` costs about 0.6 ms to create, eight of them 5 ms) and only the regexes of the common paths are
compiled at import; the others are looked up in the `re` cache where they are used.

One pass with a cursor over the text: runs of ordinary characters are consumed by anchored, negated-class regexes
(no backtracking), every nested construct is counted against `MAX_NESTING`, and every text read again (backtick
contents, heredoc bodies) is charged to the `Budget`, so the work is linear in the size of the input.

Positions: `Word.span`, `Simple.span`, `Compound.span` and `Script.span` slice the text given to `parse` (plus
`base`). They are exact except inside a backtick substitution whose content has escapes (`\\\\`, `` \\` ``, `\\$`):
that content is unescaped before it is parsed, so its spans are relative to the unescaped text.
"""
from __future__ import annotations

import re

MAX_NESTING = 32

# ---------------------------------------------------------------------------------------------------------------
# Errors and budget
# ---------------------------------------------------------------------------------------------------------------


class ShellError(Exception):
    """Base class of every error the parser raises on purpose."""


class ShellSyntaxError(ShellError):
    """Text that does not close or is outside the subset.

    `kind`: unterminated_quote | unterminated_substitution | unterminated_expansion | unterminated_compound
            | unexpected_token | bad_heredoc | unsupported. `pos`: index in the text given to `parse` (plus base)."""

    def __init__(self, kind: str, pos: int = 0):
        super().__init__(f"{kind} at {pos}")
        self.kind = kind
        self.pos = pos


class NestingTooDeep(ShellError):
    """More than `MAX_NESTING` nested compounds, groups, substitutions or expansions (S7)."""

    def __init__(self, pos: int = 0):
        super().__init__(f"nesting deeper than {MAX_NESTING} at {pos}")
        self.pos = pos


class BudgetExceeded(ShellError):
    """The characters read by every parse of one analysis passed the budget (S10)."""


class Budget:
    """Characters left for every parse of one analysis (S10)."""

    __slots__ = ("left",)

    def __init__(self, chars: int):
        self.left = chars

    def charge(self, n: int) -> None:
        self.left -= n
        if self.left < 0:
            raise BudgetExceeded(f"budget exceeded by {-self.left} characters")


# ---------------------------------------------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------------------------------------------


class _Node:
    """Base of the tree nodes: plain `__slots__` classes with the field names below, built positionally. Nodes
    compare by identity; they are not meant to be changed after `parse` returns them."""

    __slots__ = ()

    def __repr__(self) -> str:
        return type(self).__name__ + "(" + ", ".join(f"{n}={getattr(self, n)!r}" for n in self.__slots__) + ")"


class Part(_Node):
    """A piece of a word. kind: lit | sq | dq | ansi | param | cmdsub | backtick | arith | procsub_in | procsub_out
    | array. `text` is the source text of the part (quote-removed for lit/sq/dq/ansi); `script` the nested script
    of cmdsub / backtick / procsub; `inner` the parts inside dq, ${...} and arith (their nested expansions);
    `elements` the element words of an array `NAME=(...)`.

    For `ansi`, `text` is the decoded string (what the shell sees); `dyn` is True when some escape cannot be decoded
    with certainty (shells differ, the byte is not text, a NUL), and the part then counts as dynamic. `code` (param
    only): the expansion evaluates its value as code or as a prompt: zsh flags `e` or `%` (`${(e)X}`), bash `@P`."""

    __slots__ = ("kind", "text", "script", "inner", "elements", "dyn", "code")

    def __init__(self, kind, text, script=None, inner=(), elements=(), dyn=False, code=False):
        self.kind = kind
        self.text = text
        self.script = script
        self.inner = inner
        self.elements = elements
        self.dyn = dyn
        self.code = code


# The part kinds that are an expansion (public: the hook's classifier uses the same set).
DYNAMIC_KINDS = frozenset({"param", "cmdsub", "backtick", "arith", "procsub_in", "procsub_out"})


def _part_code(part: Part) -> bool:
    if part.code:
        return True
    for inner in part.inner:
        if _part_code(inner):
            return True
    return False


def _part_dynamic(part: Part) -> bool:
    if part.kind in DYNAMIC_KINDS or part.dyn:
        return True
    if part.kind == "dq":
        return bool(part.inner)
    if part.kind == "array":
        return any(w.dynamic for w in part.elements)
    return False


def part_scripts(part: Part):
    """The nested scripts of a part (substitutions, wherever they sit inside it), outermost first."""
    if part.script is not None:
        yield part.script
    for inner in part.inner:
        yield from part_scripts(inner)
    for word in part.elements:
        yield from word.scripts()


class Word(_Node):
    """parts: tuple of `Part`; span: (start, end) in the source; quoted: some part is quoted ('...', "...", $'...',
    a backslash escape)."""

    __slots__ = ("parts", "span", "quoted")

    def __init__(self, parts, span, quoted):
        self.parts = parts
        self.span = span
        self.quoted = quoted

    @property
    def text(self) -> str:
        """The word without quotes, expansions in their source form (`$T`, `${X:-a}`, `$(cmd)`)."""
        return "".join(p.text for p in self.parts)

    @property
    def dynamic(self) -> bool:
        """An expansion outside single quotes (parameter, substitution, arithmetic)."""
        return any(_part_dynamic(p) for p in self.parts)

    @property
    def has_glob(self) -> bool:
        """An unquoted `*`, `?` or `[`."""
        return any(p.kind == "lit" and ("*" in p.text or "?" in p.text or "[" in p.text) for p in self.parts)

    @property
    def has_brace(self) -> bool:
        """An unquoted brace expansion (`{a,b}`, `{1..3}`, also across quotes: `{a,"b"}`). Quoted and expanded parts
        count as ordinary text; an over-approximation (`{x..y}` is reported although the shell may keep it)."""
        if not any(p.kind == "lit" and "{" in p.text for p in self.parts):
            return False
        flat = "".join(p.text if p.kind == "lit" else "x" for p in self.parts)
        return re.compile(_P_BRACE).search(flat) is not None

    @property
    def evaluates_code(self) -> bool:
        """Some parameter expansion of the word evaluates its value as code (`Part.code`), nested ones included."""
        return any(_part_code(p) for p in self.parts)

    def scripts(self):
        """The nested scripts of this word (substitutions, wherever they sit), outermost first."""
        for part in self.parts:
            yield from part_scripts(part)


class Heredoc(_Node):
    """One heredoc: delimiter, quoted (some quoting in the delimiter: no expansions), strip_tabs (`<<-`), body,
    terminated (the delimiter line was found) and expansions (HD2: the expansion parts of an unquoted body, empty
    when quoted). The body is read at the next newline, after the redirect that opened the heredoc is already in the
    tree, so these are filled in later."""

    __slots__ = ("delimiter", "quoted", "strip_tabs", "body", "terminated", "expansions")

    def __init__(self, delimiter, quoted, strip_tabs):
        self.delimiter = delimiter
        self.quoted = quoted
        self.strip_tabs = strip_tabs
        self.body = ""
        self.terminated = False
        self.expansions = ()


class Redirect(_Node):
    """fd (str or None), op, target (Word or None for a heredoc), heredoc (Heredoc or None)."""

    __slots__ = ("fd", "op", "target", "heredoc")

    def __init__(self, fd, op, target, heredoc):
        self.fd = fd
        self.op = op
        self.target = target
        self.heredoc = heredoc


class Simple(_Node):
    """assignments, words and redirects (tuples) and the span of the command."""

    __slots__ = ("assignments", "words", "redirects", "span")

    def __init__(self, assignments, words, redirects, span):
        self.assignments = assignments
        self.words = words
        self.redirects = redirects
        self.span = span


class Compound(_Node):
    """kind: subshell | group | if | while | until | for | select | case | arith | cond | function | coproc;
    name: the for / select / function / coproc name; words: the for list, the case word and patterns, the arith or
    cond operands; bodies: the nested scripts; redirects; span."""

    __slots__ = ("kind", "name", "words", "bodies", "redirects", "span")

    def __init__(self, kind, name, words, bodies, redirects, span):
        self.kind = kind
        self.name = name
        self.words = words
        self.bodies = bodies
        self.redirects = redirects
        self.span = span


class Pipeline(_Node):
    """commands: tuple of Simple | Compound."""

    __slots__ = ("commands", "negated", "timed")

    def __init__(self, commands, negated, timed):
        self.commands = commands
        self.negated = negated
        self.timed = timed


class Script(_Node):
    """pipelines: in source order (separators do not matter to classification); span."""

    __slots__ = ("pipelines", "span")

    def __init__(self, pipelines, span):
        self.pipelines = pipelines
        self.span = span


class Site(_Node):
    """One simple command and where it sits. cmd: the Simple; top_level: a direct element of the walked script's
    lists (no compound, subshell or substitution); stages / stage: stages of its pipeline and its index (0 =
    first); substitution / sub_word: the command whose word holds the substitution it is in, and that word;
    in_compound."""

    __slots__ = ("cmd", "top_level", "stages", "stage", "substitution", "sub_word", "in_compound")

    def __init__(self, cmd, top_level, stages, stage, substitution, sub_word, in_compound):
        self.cmd = cmd
        self.top_level = top_level
        self.stages = stages
        self.stage = stage
        self.substitution = substitution
        self.sub_word = sub_word
        self.in_compound = in_compound


# ---------------------------------------------------------------------------------------------------------------
# Lexical tables
# ---------------------------------------------------------------------------------------------------------------

# S8: the name, optional subscript and `=` / `+=` at the start of an unquoted literal.
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?\+?=")
# Compiled at import: what almost every command uses. Everything else is a pattern string compiled where it is used
# (`re.compile` finds it in the `re` cache after the first time), so a command that never reaches that code does not
# pay for its compilation at load time (about 0.07 ms each).
_PLAIN = re.compile(r"[^ \t\n;&|<>()'\"\\$`]+")
_DQ_PLAIN = re.compile(r'[^"\\$`]+')
_PARAM = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!\-]")

_P_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_P_SUBSCRIPT_START = r"[A-Za-z_][A-Za-z0-9_]*\["
_P_SUBSCRIPT_END = r"\]\+?="
_P_SUBSCRIPT_OPEN = r"[A-Za-z_][A-Za-z0-9_]*\[[^\]]*"
_P_SUBSCRIPT_CLOSE = r"[^\]\n]*\]\+?="
_P_IONUM_WORD = r"[0-9]+|\{[A-Za-z_][A-Za-z0-9_]*\}"
_P_PLAIN_COND = r"(?:[^ \t\n'\"\\$`<>]|[<>](?!\())+"
_P_BRACE = r"\{[^{}]*(?:,|\.\.)[^{}]*\}"
_P_ZSH_FLAGS = r"\$\{[=~^+#!]*\(([^)]*)\)"
_P_PROMPT_OP = r"\$\{[!#]?[A-Za-z_0-9@*#?$!\-]*(?:\[[^\]]*\])?@P\}"
_P_ZSH_PARAM = r"[=~^]+(?:[A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!\-])"
_P_PLAIN_REGEX = r"[^ \t\n'\"\\$`()]+"
_P_BODY_PLAIN = r"[^\\$`]+"
_P_PARAM_PLAIN = r"[^}$`\\'\"]+"
_P_BACKTICK_PLAIN = r"[^`\\]+"
_P_ANSI_PLAIN = r"[^'\\]+"

_OPS3 = frozenset({";;&", "<<<", "<<-", "&>>"})
_OPS2 = frozenset({"&&", "||", ";;", ";&", "|&", "&>", ">>", "<>", ">|", "<&", ">&", "<<"})
_REDIR_OPS = frozenset({"<", ">", ">>", "<>", ">|", "<&", ">&", "&>", "&>>", "<<", "<<-", "<<<"})
_CASE_ENDS = frozenset({";;", ";&", ";;&"})

_COMPOUND_FIRST = frozenset({"{", "if", "while", "until", "for", "select", "case", "[[", "function", "coproc"})
_COMPOUND_START = frozenset({"{", "if", "while", "until", "for", "select", "case", "[["})
_TERMINATORS = frozenset({"then", "elif", "else", "fi", "do", "done", "esac", "}"})
_RESERVED = (_COMPOUND_FIRST | _TERMINATORS | {"in", "time", "!", "]]"})
_ZSH_ONLY = frozenset({"foreach", "always"})
# The builtins whose arguments are assignments (public: the hook's value tracking uses the same set).
DECLARE_BUILTINS = frozenset({"declare", "typeset", "local", "export", "readonly"})

_EOF, _NL, _OP, _WORD, _IONUM = "eof", "nl", "op", "word", "ionum"
_NO_WORDS: frozenset = frozenset()
_NO_OPS: frozenset = frozenset()
_CLOSE_PAREN = frozenset({")"})


def _plain_text(word: Word) -> str | None:
    """The text of a word made only of literal parts (no expansion), else None."""
    for p in word.parts:
        if p.kind not in ("lit", "sq"):
            return None
    return word.text


def _reserved(word: Word) -> str | None:
    """The reserved word a word spells (unquoted, one literal part), else None."""
    if len(word.parts) == 1 and word.parts[0].kind == "lit":
        text = word.parts[0].text
        if text in _RESERVED:
            return text
    return None


def _is_assignment(word: Word) -> bool:
    """S8: the unquoted literal prefix of the word is `NAME=`, `NAME+=`, `NAME[...]=` or `NAME[...]+=`."""
    first = word.parts[0]
    if first.kind != "lit":
        return False
    if ASSIGNMENT.match(first.text):
        return True
    if "[" in first.text and re.compile(_P_SUBSCRIPT_START).match(first.text):  # A[$(x)]=1: an expansion inside
        end = re.compile(_P_SUBSCRIPT_END)
        return any(p.kind == "lit" and end.search(p.text) for p in word.parts[1:])
    return False


_ANSI_SIMPLE_KEYS = "abeEfnrtv\\'\"?"
_ANSI_SIMPLE_VALUES = "\a\b\x1b\x1b\f\n\r\t\v\\'\"?"
_OCTAL = "01234567"
_HEX = "0123456789abcdefABCDEF"


def _decode_ansi(raw: str) -> tuple[str, bool]:
    """The text of the `$'...'` content `raw` the way bash reads it: `\\a \\b \\e \\E \\f \\n \\r \\t \\v \\\\ \\' \\" \\?`,
    `\\nnn` (octal, up to 3 digits), `\\xHH`, `\\uHHHH`, `\\UHHHHHHHH`, `\\cX`. Returns (text, certain). Not certain
    (the shells differ or the result is not text): an unknown escape (zsh drops the backslash, bash keeps it), `\\x`
    `\\u` `\\U` without digits, a NUL (bash truncates the string), a byte or code point from 0x80 up (locale), a code
    point that is not a character, `\\c` followed by anything but a printable ASCII character. Linear."""
    out: list[str] = []
    certain = True
    i, n = 0, len(raw)
    while i < n:
        j = raw.find("\\", i)
        if j < 0:
            out.append(raw[i:])
            break
        out.append(raw[i:j])
        d = raw[j + 1:j + 2]
        i = j + 2
        if d and d in _ANSI_SIMPLE_KEYS:
            out.append(_ANSI_SIMPLE_VALUES[_ANSI_SIMPLE_KEYS.index(d)])
        elif d and d in _OCTAL:
            k = j + 1
            while k < n and k < j + 4 and raw[k] in _OCTAL:
                k += 1
            v = int(raw[j + 1:k], 8) & 0xFF
            i = k
            if v == 0 or v >= 0x80:
                certain = False
            if v:
                out.append(chr(v))
        elif d and d in "xuU":
            limit = j + 2 + (2 if d == "x" else 4 if d == "u" else 8)
            k = j + 2
            while k < n and k < limit and raw[k] in _HEX:
                k += 1
            if k == j + 2:
                certain = False
                out.append("\\" + d)
                continue
            v = int(raw[j + 2:k], 16)
            i = k
            if v == 0 or v >= 0x80:
                certain = False
            if 0 < v <= 0x10FFFF and not 0xD800 <= v <= 0xDFFF:
                out.append(chr(v))
        elif d == "c":
            x = raw[j + 2:j + 3]
            i = j + 3
            if x and " " <= x <= "~" and x != "\\":
                v = ord(x.upper()) & 0x1F if x != "?" else 0x7F  # bash: `toupper(X) & 0x1f`, and `\c?` is DEL
                if v:
                    out.append(chr(v))
                else:
                    certain = False
            else:
                certain = False
                out.append("\\c" + x)
        else:
            certain = False
            out.append("\\" + d)
    return "".join(out), certain


def _evaluates_code(text: str) -> bool:
    """`text` is a `${...}` expansion that evaluates its value as code or as a prompt: zsh flags with `e` or `%`
    (`${(e)X}`, `${(%)X}`, `${(@e)X}`), bash `${X@P}`."""
    if "@P}" in text and re.compile(_P_PROMPT_OP).fullmatch(text):
        return True
    if text.startswith("${") and "(" in text:
        m = re.compile(_P_ZSH_FLAGS).match(text)
        return m is not None and ("e" in m.group(1) or "%" in m.group(1))
    return False


# ---------------------------------------------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------------------------------------------


class _Parser:
    """A cursor over one text. `tok` is a one-token lookahead; `pending` the heredocs waiting for the next newline
    of the current substitution level."""

    def __init__(self, text: str, budget: Budget, base: int, depth: int):
        self.s = text
        self.n = len(text)
        self.i = 0
        self.budget = budget
        self.base = base
        self.depth = depth
        self.tok: tuple | None = None
        self.pending: list[Heredoc] = []
        self.array_ok = True
        self.last_end = 0
        self.scan_end = 0

    # -- helpers ---------------------------------------------------------------------------------------------

    def _fail(self, kind: str, pos: int | None = None):
        raise ShellSyntaxError(kind, self.base + (self.i if pos is None else pos))

    def _enter(self, pos: int) -> None:
        self.depth += 1
        if self.depth > MAX_NESTING:
            raise NestingTooDeep(self.base + pos)

    def _leave(self) -> None:
        self.depth -= 1

    def _abs(self, a: int, b: int) -> tuple[int, int]:
        return (self.base + a, self.base + b)

    # -- tokens ----------------------------------------------------------------------------------------------

    def peek(self) -> tuple:
        t = self.tok
        if t is None:
            t = self._lex()
            self.tok = t
        return t

    def take(self) -> tuple:
        t = self.peek()
        self.tok = None
        self.last_end = t[3]
        return t

    def _skip_blanks(self, comments: bool = True) -> int:
        s, n, i = self.s, self.n, self.i
        while i < n:
            c = s[i]
            if c == " " or c == "\t":
                i += 1
            elif c == "\\" and s.startswith("\n", i + 1):
                i += 2
            elif c == "#" and comments:  # S4: a comment starts at the beginning of a word
                j = s.find("\n", i)
                i = n if j < 0 else j
            else:
                break
        self.i = i
        return i

    def _skip_nl(self) -> None:
        while self.peek()[0] == _NL:
            self.take()

    def _lex(self) -> tuple:
        i = self._skip_blanks()
        s, n = self.s, self.n
        if i >= n:
            return (_EOF, None, i, i)
        c = s[i]
        if c == "\n":
            self.i = i + 1
            if self.pending:
                self._read_heredocs()
            return (_NL, None, i, self.i)
        if c in ";&|<>()" and not (c in "<>" and s.startswith("(", i + 1)):
            op = s[i:i + 3]
            if op not in _OPS3:
                op = s[i:i + 2]
                if op not in _OPS2:
                    op = c
            if op == "&" and s[i + 1:i + 2] in ("!", "|"):
                self._fail("unsupported", i)  # S9: the zsh `&!` and `&|`
            self.i = i + len(op)
            return (_OP, op, i, self.i)
        word = self._word(array_ok=self.array_ok)
        if self.i < n and s[self.i] in "<>" and len(word.parts) == 1 and word.parts[0].kind == "lit":
            text = word.parts[0].text
            if re.compile(_P_IONUM_WORD).fullmatch(text):
                return (_IONUM, text, i, self.i)
        return (_WORD, word, i, self.i)

    # -- words -----------------------------------------------------------------------------------------------

    def _word(self, array_ok: bool = False, cond: bool = False, regex: bool = False) -> Word:
        s, n = self.s, self.n
        i = start = self.i
        parts: list[Part] = []
        lit: list[str] = []
        plain = re.compile(_P_PLAIN_REGEX) if regex else (re.compile(_P_PLAIN_COND) if cond else _PLAIN)
        if not regex:  # fast path: the whole word is one run of ordinary characters (most words)
            m = plain.match(s, i)
            if m:
                j = m.end()
                nxt = s[j:j + 1]
                if ((not nxt or nxt in " \t\n;&|<>)") and not (array_ok and nxt in " \t" and "[" in m.group())
                        and not (nxt in "<>" and nxt and s.startswith("(", j + 1))):
                    self.i = j
                    return Word((Part("lit", m.group()),), (self.base + i, self.base + j), False)
        paren = 0

        def flush():
            if lit:
                parts.append(Part("lit", "".join(lit)))
                lit.clear()

        while i < n:
            c = s[i]
            if c in " \t\n":
                if regex and paren > 0:
                    lit.append(c)
                    i += 1
                    continue
                if array_ok and c != "\n" and lit and not parts:
                    # `A[a b]=1 cmd`: a blank inside the subscript of an assignment does not end the word
                    head = "".join(lit)
                    if "[" in head and re.compile(_P_SUBSCRIPT_OPEN).fullmatch(head):
                        m = re.compile(_P_SUBSCRIPT_CLOSE).match(s, i)
                        if m:
                            lit.append(m.group())
                            i = m.end()
                            continue
                break
            if regex and c in "()":
                paren = paren + 1 if c == "(" else max(paren - 1, 0)
                lit.append(c)
                i += 1
                continue
            if c in "<>" and not regex and s.startswith("(", i + 1):
                # `<(` and `>(` are a process substitution anywhere in an unquoted word (`A=<(x)`, `a<(x)`), also
                # in `[[ ]]` operands
                flush()
                kind = "procsub_in" if c == "<" else "procsub_out"
                part, i = self._cmdsub(i, kind, 2)
                parts.append(part)
                continue
            if not cond and c in ";&|<>()":
                if (c == "(" and array_ok and not parts and lit
                        and ASSIGNMENT.fullmatch("".join(lit))):
                    flush()
                    part, i = self._array(i)
                    parts.append(part)
                    continue
                break
            m = plain.match(s, i)
            if m:
                lit.append(m.group())
                i = m.end()
                continue
            if c == "\\":
                if s.startswith("\n", i + 1):
                    i += 2
                elif i + 1 < n:
                    flush()
                    parts.append(Part("sq", s[i + 1]))
                    i += 2
                else:
                    lit.append("\\")
                    i += 1
            elif c == "'":
                j = s.find("'", i + 1)
                if j < 0:
                    self._fail("unterminated_quote", i)
                flush()
                parts.append(Part("sq", s[i + 1:j]))
                i = j + 1
            elif c == '"':
                flush()
                part, i = self._dq(i)
                parts.append(part)
            elif c == "$":
                part, j = self._dollar(i, False)
                if part is None:
                    lit.append("$")
                else:
                    flush()
                    parts.append(part)
                i = j
            elif c == "`":
                flush()
                part, i = self._backtick(i)
                parts.append(part)
            else:  # unreachable: every other character is matched by `plain`
                self._fail("unexpected_token", i)
        flush()
        if i == start:
            self._fail("unexpected_token", i)
        self.i = i
        quoted = any(p.kind in ("sq", "dq", "ansi") for p in parts)
        return Word(tuple(parts), self._abs(start, i), quoted)

    def _dq(self, i: int) -> tuple[Part, int]:
        """`"..."` starting at s[i]. Inside, `\\` escapes `$`, `` ` ``, `"`, `\\` and a newline."""
        s, n = self.s, self.n
        j = i + 1
        text: list[str] = []
        inner: list[Part] = []
        while j < n:
            m = _DQ_PLAIN.match(s, j)
            if m:
                text.append(m.group())
                j = m.end()
                continue
            c = s[j]
            if c == '"':
                return Part("dq", "".join(text), None, tuple(inner)), j + 1
            if c == "\\":
                d = s[j + 1:j + 2]
                if d == "\n":
                    j += 2
                elif d and d in '$`"\\':
                    text.append(d)
                    j += 2
                else:
                    text.append("\\")
                    j += 1
            elif c == "$":
                part, j2 = self._dollar(j, True)
                if part is None:
                    text.append("$")
                else:
                    text.append(part.text)
                    inner.append(part)
                j = j2
            else:  # backtick
                part, j = self._backtick(j)
                text.append(part.text)
                inner.append(part)
        self._fail("unterminated_quote", i)

    def _dollar(self, i: int, in_dq: bool) -> tuple[Part | None, int]:
        """The expansion starting at the `$` in s[i]. (None, i + 1) for a lone `$`, which is literal text."""
        s = self.s
        nxt = s[i + 1:i + 2]
        if nxt == "(":
            if s.startswith("((", i + 1):
                return self._arith(i, i + 3, "))", "$((")
            return self._cmdsub(i, "cmdsub", 2)
        if nxt == "{":
            return self._param_brace(i, in_dq)
        if nxt == "[":
            return self._arith(i, i + 2, "]", "$[")
        m = _PARAM.match(s, i + 1)
        if m:
            return Part("param", s[i:m.end()]), m.end()
        if nxt in ("=", "~", "^"):  # zsh `$=NAME`, `$~NAME`, `$^NAME` (also doubled)
            m = re.compile(_P_ZSH_PARAM).match(s, i + 1)
            if m:
                return Part("param", s[i:m.end()]), m.end()
        if not in_dq and nxt == "'":
            return self._ansi(i)
        if not in_dq and nxt == '"':
            part, j = self._dq(i + 1)
            return part, j
        return None, i + 1

    def _ansi(self, i: int) -> tuple[Part, int]:
        s, n = self.s, self.n
        j = i + 2
        while j < n:
            m = re.compile(_P_ANSI_PLAIN).match(s, j)
            if m:
                j = m.end()
                continue
            if s[j] == "'":
                raw = s[i + 2:j]
                if "\\" not in raw:
                    return Part("ansi", raw), j + 1
                text, certain = _decode_ansi(raw)
                return Part("ansi", text, dyn=not certain), j + 1
            j += 2  # a backslash and the character it escapes
        self._fail("unterminated_quote", i)

    def _param_brace(self, i: int, in_dq: bool) -> tuple[Part, int]:
        """`${...}`: the content is not interpreted, only its quotes and nested expansions are read."""
        s, n = self.s, self.n
        self._enter(i)
        j = i + 2
        inner: list[Part] = []
        while j < n:
            m = re.compile(_P_PARAM_PLAIN).match(s, j)
            if m:
                j = m.end()
                continue
            c = s[j]
            if c == "}":
                self._leave()
                text = s[i:j + 1]
                return Part("param", text, None, tuple(inner), (), False, _evaluates_code(text)), j + 1
            if c == "\\":
                j += 2
            elif c == "$":
                part, j2 = self._dollar(j, in_dq)
                if part is not None:
                    inner.append(part)
                j = j2
            elif c == "'":
                if in_dq:
                    j += 1  # a single quote inside double quotes is literal
                else:
                    k = s.find("'", j + 1)
                    if k < 0:
                        self._fail("unterminated_quote", j)
                    j = k + 1
            elif c == '"':
                part, j = self._dq(j)
                inner.append(part)
            else:  # backtick
                part, j = self._backtick(j)
                inner.append(part)
        self._fail("unterminated_expansion", i)

    def _arith(self, i: int, content: int, closer: str, opener: str) -> tuple[Part, int]:
        """`$((...))` (closer `))`) or `$[...]` (closer `]`) starting at s[i], content at s[content]."""
        self._enter(i)
        inner, end = self._scan_arith(content, closer, i)
        self._leave()
        return Part("arith", self.s[i:end], None, tuple(inner)), end

    def _scan_arith(self, j: int, closer: str, start: int, attempt: bool = False) -> tuple[list[Part], int] | None:
        """Balanced scan up to the closer, reading nested expansions and skipping quotes; nothing else is
        interpreted. Raises `unterminated_expansion` when it does not close (S3: no fallback to a subshell), except
        in `attempt` mode (a command that starts with `((`, which may be nested subshells): None, with the index
        where the scan gave up in `self.scan_end`."""
        s, n = self.s, self.n
        inner: list[Part] = []
        depth = 0
        paren = closer == "))"
        while j < n:
            c = s[j]
            if c == "$":
                part, j2 = self._dollar(j, True)
                if part is not None:
                    inner.append(part)
                j = j2
                continue
            if c == "`":
                part, j = self._backtick(j)
                inner.append(part)
                continue
            if c == "\\":
                j += 2
                continue
            if c == "'":
                k = s.find("'", j + 1)
                if k < 0:
                    if attempt:
                        self.scan_end = n
                        return None
                    self._fail("unterminated_quote", j)
                j = k + 1
                continue
            if c == '"':
                part, j = self._dq(j)
                inner.append(part)
                continue
            if paren:
                if c == "(":
                    depth += 1
                elif c == ")":
                    if depth == 0:
                        if s.startswith("))", j):
                            return inner, j + 2
                        break
                    depth -= 1
            else:
                if c == "[":
                    depth += 1
                elif c == "]":
                    if depth == 0:
                        return inner, j + 1
                    depth -= 1
            j += 1
        if attempt:
            self.scan_end = min(j, n)
            return None
        self._fail("unterminated_expansion", start)

    def _backtick(self, i: int) -> tuple[Part, int]:
        """`` `...` ``: the content, without the escapes `\\\\`, `` \\` `` and `\\$`, is a nested script."""
        s, n = self.s, self.n
        j = i + 1
        chars: list[str] = []
        while True:
            m = re.compile(_P_BACKTICK_PLAIN).match(s, j)
            if m:
                chars.append(m.group())
                j = m.end()
            if j >= n:
                self._fail("unterminated_substitution", i)
            if s[j] == "`":
                break
            d = s[j + 1:j + 2]  # a backslash
            if d and d in "\\`$":
                chars.append(d)
                j += 2
            else:
                chars.append("\\")
                j += 1
        self._enter(i)
        script = _parse_text("".join(chars), self.budget, self.base + i + 1, self.depth)
        self._leave()
        return Part("backtick", s[i:j + 1], script), j + 1

    def _cmdsub(self, i: int, kind: str, open_len: int) -> tuple[Part, int]:
        """`$(...)`, `<(...)`, `>(...)`: a nested script read at the same cursor, up to the `)` that is not its."""
        self._enter(i)
        outer_pending, outer_array, outer_tok = self.pending, self.array_ok, self.tok
        self.pending = []
        self.array_ok = True
        self.tok = None
        self.i = i + open_len
        script = self._script(_NO_WORDS, _CLOSE_PAREN)
        t = self.take()
        if t[0] != _OP:
            self._fail("unterminated_substitution", i)
        if self.pending:
            self._fail("bad_heredoc", i)
        self.pending, self.array_ok, self.tok = outer_pending, outer_array, outer_tok
        self._leave()
        return Part(kind, self.s[i:self.i], script), self.i

    def _array(self, i: int) -> tuple[Part, int]:
        """`NAME=(a b c)`: the words up to the `)`, newlines and comments allowed."""
        s, n = self.s, self.n
        outer_tok = self.tok
        self.tok = None
        self.i = i + 1
        words: list[Word] = []
        while True:
            j = self._skip_blanks()
            while j < n and s[j] == "\n":
                self.i = j + 1
                if self.pending:  # the newline ends the line of a heredoc opened before the array
                    self._read_heredocs()
                j = self._skip_blanks()
            if j >= n:
                self._fail("unterminated_expansion", i)
            if s[j] == ")":
                self.i = j + 1
                break
            if s[j] in ";&|<>(":
                self._fail("unexpected_token", j)
            words.append(self._word())
        self.tok = outer_tok
        return Part("array", s[i:self.i], None, (), tuple(words)), self.i

    # -- heredocs --------------------------------------------------------------------------------------------

    def _read_heredocs(self) -> None:
        """At the newline operator: read the pending bodies in order, line by line, up to the delimiter (HD1)."""
        s, n, i = self.s, self.n, self.i
        pending, self.pending = self.pending, []
        for h in pending:
            body_start = i
            lines: list[str] = []
            terminated = False
            while i < n:
                j = s.find("\n", i)
                if j < 0:
                    line, nxt, eol = s[i:], n, ""
                else:
                    line, nxt, eol = s[i:j], j + 1, "\n"
                if h.strip_tabs:
                    line = line.lstrip("\t")
                if line == h.delimiter:
                    terminated = True
                    i = nxt
                    break
                lines.append(line + eol)
                i = nxt
            h.body = "".join(lines)
            h.terminated = terminated
            if not h.quoted and h.body:  # HD2: the expansions of an unquoted body are scripts
                self.budget.charge(len(h.body))
                sub = _Parser(h.body, self.budget, self.base + body_start, self.depth)
                h.expansions = sub._heredoc_expansions()
        self.i = i

    def _heredoc_expansions(self) -> tuple[Part, ...]:
        """The body read as inside double quotes without a special `"`: `\\` escapes `$`, `` ` ``, `\\` and newline."""
        s, n = self.s, self.n
        parts: list[Part] = []
        i = 0
        while i < n:
            m = re.compile(_P_BODY_PLAIN).match(s, i)
            if m:
                i = m.end()
                continue
            c = s[i]
            if c == "\\":
                i += 2 if s[i + 1:i + 2] in ("$", "`", "\\", "\n") else 1
            elif c == "$":
                part, i = self._dollar(i, True)
                if part is not None:
                    parts.append(part)
            else:
                part, i = self._backtick(i)
                parts.append(part)
        return tuple(parts)

    # -- productions -----------------------------------------------------------------------------------------

    def _script(self, stop_words: frozenset, stop_ops: frozenset) -> Script:
        pipelines: list[Pipeline] = []
        at = self.i
        self._skip_nl()
        while True:
            t = self.peek()
            if self._stops(t, stop_words, stop_ops):
                break
            self._list(pipelines)
            t = self.peek()
            if t[0] == _NL or (t[0] == _OP and t[1] in (";", "&")):
                self.take()
                self._skip_nl()
                continue
            if self._stops(t, stop_words, stop_ops):
                break
            self._fail("unexpected_token", t[2])
        if pipelines:
            span = (pipelines[0].commands[0].span[0], pipelines[-1].commands[-1].span[1])
        else:
            span = self._abs(at, at)
        return Script(tuple(pipelines), span)

    @staticmethod
    def _stops(t: tuple, stop_words: frozenset, stop_ops: frozenset) -> bool:
        if t[0] == _EOF:
            return True
        if t[0] == _OP:
            return t[1] in stop_ops
        return t[0] == _WORD and bool(stop_words) and _reserved(t[1]) in stop_words

    def _list(self, pipelines: list[Pipeline]) -> None:
        pipelines.append(self._pipeline())
        while True:
            t = self.peek()
            if t[0] == _OP and t[1] in ("&&", "||"):
                self.take()
                self._skip_nl()
                pipelines.append(self._pipeline())
            else:
                return

    def _pipeline(self) -> Pipeline:
        timed = negated = False
        t = self.peek()
        if t[0] == _WORD and _reserved(t[1]) == "time":
            self.take()
            timed = True
            t = self.peek()
            if t[0] == _WORD and _plain_text(t[1]) == "-p":
                self.take()
            t = self.peek()
        if t[0] == _WORD and _reserved(t[1]) == "!":
            self.take()
            negated = True
        commands = [self._command()]
        while True:
            t = self.peek()
            if t[0] == _OP and t[1] in ("|", "|&"):
                self.take()
                self._skip_nl()
                commands.append(self._command())
            else:
                return Pipeline(tuple(commands), negated, timed)

    def _command(self) -> "Simple | Compound":
        t = self.peek()
        kind = t[0]
        if kind == _OP and t[1] == "(":
            return self._subshell()
        if kind == _WORD:
            word = t[1]
            r = _reserved(word)
            if r in _COMPOUND_FIRST:
                return self._compound(r)
            if r in _TERMINATORS or r in ("time", "!"):
                self._fail("unexpected_token", t[2])
            if not word.quoted and _plain_text(word) in _ZSH_ONLY:
                self._fail("unsupported", t[2])  # S9: foreach, always
            return self._simple()
        if kind == _IONUM or (kind == _OP and t[1] in _REDIR_OPS):
            return self._simple()
        self._fail("unexpected_token", t[2])

    def _body(self, stop_words: frozenset, stop_ops: frozenset = _NO_OPS) -> Script:
        script = self._script(stop_words, stop_ops)
        if not script.pipelines:
            self._fail("unterminated_compound" if self.peek()[0] == _EOF else "unexpected_token", self.peek()[2])
        return script

    def _expect_word(self, word: str) -> None:
        t = self.peek()
        if t[0] == _WORD and _reserved(t[1]) == word:
            self.take()
        else:
            self._fail("unterminated_compound" if t[0] == _EOF else "unexpected_token", t[2])

    def _expect_op(self, op: str) -> None:
        t = self.peek()
        if t[0] == _OP and t[1] == op:
            self.take()
        else:
            self._fail("unterminated_compound" if t[0] == _EOF else "unexpected_token", t[2])

    def _take_word(self) -> Word:
        t = self.peek()
        if t[0] != _WORD:
            self._fail("unterminated_compound" if t[0] == _EOF else "unexpected_token", t[2])
        self.take()
        return t[1]

    def _redirects(self) -> tuple[Redirect, ...]:
        redirects: list[Redirect] = []
        while True:
            t = self.peek()
            if t[0] == _IONUM or (t[0] == _OP and t[1] in _REDIR_OPS):
                redirects.append(self._redirect())
            else:
                return tuple(redirects)

    def _redirect(self) -> Redirect:
        t = self.peek()
        fd = None
        if t[0] == _IONUM:
            self.take()
            fd = t[1]
            t = self.peek()
        if not (t[0] == _OP and t[1] in _REDIR_OPS):
            self._fail("unexpected_token", t[2])
        self.take()
        op = t[1]
        if op in ("<<", "<<-"):
            self._skip_blanks(comments=False)
            if self.i >= self.n or self.s[self.i] in "\n;&|<>()":
                self._fail("bad_heredoc", self.i)
            word = self._word()
            heredoc = Heredoc(word.text, word.quoted, op == "<<-")
            self.pending.append(heredoc)
            self.last_end = self.i
            return Redirect(fd, op, None, heredoc)
        t = self.peek()
        if t[0] != _WORD:
            self._fail("unexpected_token", t[2])
        self.take()
        return Redirect(fd, op, t[1], None)

    def _simple(self) -> Simple:
        first = self.peek()[2]
        assignments: list[Word] = []
        words: list[Word] = []
        redirects: list[Redirect] = []
        self.array_ok = True
        while True:
            t = self.peek()
            if t[0] == _WORD:
                word = t[1]
                self.take()
                if not words and _is_assignment(word):
                    assignments.append(word)
                    continue
                words.append(word)
                if len(words) == 3 and _reserved(word) == "{" and _plain_text(words[0]) == "repeat" \
                        and not words[0].quoted:
                    self._fail("unsupported", t[2])  # S9: the zsh `repeat N { ... }`
                if len(words) == 1:
                    self.array_ok = _plain_text(word) in DECLARE_BUILTINS
                    if not assignments and not redirects:
                        nt = self.peek()
                        if nt[0] == _OP and nt[1] == "(":
                            self.array_ok = True
                            return self._function(word, first)
            elif t[0] == _IONUM or (t[0] == _OP and t[1] in _REDIR_OPS):
                redirects.append(self._redirect())
            else:
                break
        self.array_ok = True
        if not (assignments or words or redirects):
            self._fail("unexpected_token", t[2])
        return Simple(tuple(assignments), tuple(words), tuple(redirects), self._abs(first, self.last_end))

    def _compound_required(self) -> "Simple | Compound":
        t = self.peek()
        if (t[0] == _OP and t[1] == "(") or (t[0] == _WORD and _reserved(t[1]) in _COMPOUND_START):
            return self._command()
        self._fail("unterminated_compound" if t[0] == _EOF else "unexpected_token", t[2])

    @staticmethod
    def _wrap(command: "Simple | Compound") -> Script:
        return Script((Pipeline((command,), False, False),), command.span)

    def _function(self, name_word: Word, first: int) -> Compound:
        """`NAME ( ) linebreak compound`, with the name already read."""
        name = _plain_text(name_word)
        if name is None:
            self._fail("unexpected_token", first)
        self.take()  # (
        self._expect_op(")")
        self._skip_nl()
        body = self._compound_required()
        return Compound("function", name, (), (self._wrap(body),), (), self._abs(first, self.last_end))

    def _function_keyword(self) -> Compound:
        first = self.take()[2]
        name = _plain_text(self._take_word())
        if name is None:
            self._fail("unexpected_token", first)
        t = self.peek()
        if t[0] == _OP and t[1] == "(":
            self.take()
            self._expect_op(")")
        self._skip_nl()
        body = self._compound_required()
        return Compound("function", name, (), (self._wrap(body),), (), self._abs(first, self.last_end))

    def _subshell(self) -> Compound:
        t = self.peek()
        start = t[2]
        if self.s.startswith("((", start):
            found = self._arith_word(start, attempt=True)
            if found is not None:
                redirects = self._redirects()
                return Compound("arith", None, (found,), (), redirects, self._abs(start, self.last_end))
        self.take()
        self._enter(start)
        body = self._body(_NO_WORDS, _CLOSE_PAREN)
        self._expect_op(")")
        self._leave()
        redirects = self._redirects()
        return Compound("subshell", None, (), (body,), redirects, self._abs(start, self.last_end))

    def _arith_word(self, start: int, attempt: bool = False) -> Word | None:
        """The `((...))` at s[start]: its expansions are read, and the cursor ends after the `))`.

        With `attempt` (a command that may as well be nested subshells), text that is not arithmetic gives None and
        leaves the cursor at `start`; the text scanned is charged to the budget, so that a chain of attempts that
        fail after reading expansions stays inside the global limit (S10) instead of reading everything twice."""
        self.tok = None
        self._enter(start)
        found = self._scan_arith(start + 2, "))", start, attempt)
        self._leave()
        if found is None:
            self.budget.charge(max(self.scan_end - start, 1))
            self.i = start
            return None
        inner, end = found
        part = Part("arith", self.s[start:end], None, tuple(inner))
        self.i = end
        self.last_end = end
        return Word((part,), self._abs(start, end), False)

    def _group(self) -> Compound:
        start = self.take()[2]
        self._enter(start)
        body = self._body(frozenset({"}"}))
        self._expect_word("}")
        self._leave()
        redirects = self._redirects()
        return Compound("group", None, (), (body,), redirects, self._abs(start, self.last_end))

    def _if(self) -> Compound:
        start = self.take()[2]
        self._enter(start)
        bodies = [self._body(frozenset({"then"}))]
        self._expect_word("then")
        bodies.append(self._body(frozenset({"elif", "else", "fi"})))
        while True:
            t = self.peek()
            r = _reserved(t[1]) if t[0] == _WORD else None
            if r == "elif":
                self.take()
                bodies.append(self._body(frozenset({"then"})))
                self._expect_word("then")
                bodies.append(self._body(frozenset({"elif", "else", "fi"})))
            elif r == "else":
                self.take()
                bodies.append(self._body(frozenset({"fi"})))
                self._expect_word("fi")
                break
            elif r == "fi":
                self.take()
                break
            else:
                self._fail("unterminated_compound" if t[0] == _EOF else "unexpected_token", t[2])
        self._leave()
        redirects = self._redirects()
        return Compound("if", None, (), tuple(bodies), redirects, self._abs(start, self.last_end))

    def _while(self) -> Compound:
        t = self.take()
        start, kind = t[2], _reserved(t[1])
        self._enter(start)
        bodies = [self._body(frozenset({"do"}))]
        self._expect_word("do")
        bodies.append(self._body(frozenset({"done"})))
        self._expect_word("done")
        self._leave()
        redirects = self._redirects()
        return Compound(kind, None, (), tuple(bodies), redirects, self._abs(start, self.last_end))

    def _for(self) -> Compound:
        t = self.take()
        start, kind = t[2], _reserved(t[1])
        self._enter(start)
        t = self.peek()
        name = None
        words: list[Word] = []
        if t[0] == _OP and t[1] == "(" and kind == "for" and self.s.startswith("((", t[2]):
            words.append(self._arith_word(t[2]))
            t = self.peek()
            if t[0] == _NL or (t[0] == _OP and t[1] == ";"):
                self.take()
                self._skip_nl()
        else:
            name = _plain_text(self._take_word())
            if name is None or not re.compile(_P_NAME).fullmatch(name):
                self._fail("unexpected_token", t[2])
            t = self.peek()
            if t[0] == _OP and t[1] == "(":
                self._fail("unsupported", t[2])  # S9: for i (1) cmd
            if t[0] == _NL:
                self._skip_nl()
                t = self.peek()
            if t[0] == _WORD and _reserved(t[1]) == "in":
                self.take()
                while self.peek()[0] == _WORD:
                    words.append(self.take()[1])
                t = self.peek()
                if t[0] == _NL or (t[0] == _OP and t[1] == ";"):
                    self.take()
                    self._skip_nl()
                else:
                    self._fail("unterminated_compound" if t[0] == _EOF else "unexpected_token", t[2])
            elif t[0] == _OP and t[1] == ";":
                self.take()
                self._skip_nl()
        self._expect_word("do")
        body = self._body(frozenset({"done"}))
        self._expect_word("done")
        self._leave()
        redirects = self._redirects()
        return Compound(kind, name, tuple(words), (body,), redirects, self._abs(start, self.last_end))

    def _case(self) -> Compound:
        start = self.take()[2]
        self._enter(start)
        words = [self._take_word()]
        self._skip_nl()
        self._expect_word("in")
        self._skip_nl()
        bodies: list[Script] = []
        while True:
            t = self.peek()
            if t[0] == _WORD and _reserved(t[1]) == "esac":
                self.take()
                break
            if t[0] == _EOF:
                self._fail("unterminated_compound", t[2])
            if t[0] == _OP and t[1] == "(":
                self.take()
            while True:
                words.append(self._take_word())
                t = self.peek()
                if t[0] == _OP and t[1] == "|":
                    self.take()
                else:
                    break
            self._expect_op(")")
            bodies.append(self._script(frozenset({"esac"}), _CASE_ENDS))
            t = self.peek()
            if t[0] == _OP and t[1] in _CASE_ENDS:
                self.take()
            self._skip_nl()
        self._leave()
        redirects = self._redirects()
        return Compound("case", None, tuple(words), tuple(bodies), redirects, self._abs(start, self.last_end))

    def _cond(self) -> Compound:
        """`[[ ... ]]`: operands read as words in which `( ) | < > & ;` are text; only substitutions are code."""
        start = self.take()[2]
        s, n = self.s, self.n
        words: list[Word] = []
        prev = None
        while True:
            self.tok = None
            i = self._skip_blanks(comments=False)
            while i < n and s[i] == "\n":
                self.i = i + 1
                if self.pending:  # `cmd <<EOF && [[ x` NL body NL EOF NL `]]`: the body starts after this newline
                    self._read_heredocs()
                i = self._skip_blanks(comments=False)
            if i >= n:
                self._fail("unterminated_compound", start)
            if s.startswith("]]", i) and s[i + 2:i + 3] in ("", " ", "\t", "\n", ";", "&", "|", "<", ">", "(", ")"):
                self.i = i + 2  # the closing `]]` is a word of its own, but an operator may follow it directly
                break
            word = self._word(cond=True, regex=(prev == "=~"))
            text = _plain_text(word)
            if text == "]]" and not word.quoted:
                break
            words.append(word)
            prev = text
        self.last_end = self.i
        redirects = self._redirects()
        return Compound("cond", None, tuple(words), (), redirects, self._abs(start, self.last_end))

    def _coproc(self) -> Compound:
        start = self.take()[2]
        s = self.s
        t = self.peek()
        name = None
        if t[0] == _WORD:
            word = t[1]
            r = _reserved(word)
            text = _plain_text(word)
            if r is None and text is not None and re.compile(_P_NAME).fullmatch(text):
                j = t[3]
                while j < self.n and s[j] in " \t":
                    j += 1
                if s.startswith("(", j) or (s.startswith("{", j) and s[j + 1:j + 2] in ("", " ", "\t", "\n")):
                    self.take()
                    name = text
                    body = self._compound_required()
                else:
                    body = self._simple()
            elif r in _COMPOUND_START:
                body = self._command()
            else:
                body = self._simple()
        elif t[0] == _OP and t[1] == "(":
            body = self._command()
        else:
            body = self._simple()
        return Compound("coproc", name, (), (self._wrap(body),), (), self._abs(start, self.last_end))

    def _compound(self, word: str) -> Compound:
        """The compound command that starts with the reserved word `word` (one of `_COMPOUND_FIRST`)."""
        if word == "{":
            return self._group()
        if word == "if":
            return self._if()
        if word in ("while", "until"):
            return self._while()
        if word in ("for", "select"):
            return self._for()
        if word == "case":
            return self._case()
        if word == "[[":
            return self._cond()
        if word == "function":
            return self._function_keyword()
        return self._coproc()


def _parse_text(text: str, budget: Budget, base: int, depth: int) -> Script:
    budget.charge(len(text))
    nul = text.find("\0")
    if nul >= 0:
        raise ShellSyntaxError("unsupported", base + nul)
    parser = _Parser(text, budget, base, depth)
    script = parser._script(_NO_WORDS, _NO_OPS)
    return script


def parse(text: str, budget: Budget, *, base: int = 0) -> Script:
    """Read `text` as a script of the subset (section 2). Raises `ShellSyntaxError`, `NestingTooDeep` or
    `BudgetExceeded`; never anything else."""
    return _parse_text(text, budget, base, 0)


# ---------------------------------------------------------------------------------------------------------------
# Walking
# ---------------------------------------------------------------------------------------------------------------


def _walk_redirects(redirects, owner: "Site | None", in_compound: bool):
    for r in redirects:
        if r.target is not None:
            for script in r.target.scripts():
                yield from _walk(script, False, in_compound, owner, r.target)
        if r.heredoc is not None:
            for part in r.heredoc.expansions:
                for script in part_scripts(part):
                    yield from _walk(script, False, in_compound, owner, None)


def _walk(script: Script, top: bool, in_compound: bool, parent: "Site | None", sub_word: "Word | None"):
    for pipeline in script.pipelines:
        stages = len(pipeline.commands)
        for index, cmd in enumerate(pipeline.commands):
            if isinstance(cmd, Simple):
                site = Site(cmd, top, stages, index, parent, sub_word, in_compound)
                yield site
                for word in (*cmd.assignments, *cmd.words):
                    for nested in word.scripts():
                        yield from _walk(nested, False, in_compound, site, word)
                yield from _walk_redirects(cmd.redirects, site, in_compound)
            else:
                for word in cmd.words:
                    for nested in word.scripts():
                        yield from _walk(nested, False, True, parent, word)
                for body in cmd.bodies:
                    yield from _walk(body, False, True, parent, sub_word)
                yield from _walk_redirects(cmd.redirects, parent, True)


def iter_compounds(script: Script):
    """Yields every compound command of the script (bodies, substitutions and heredoc expansions included), in no
    particular order."""
    stack = [script]
    while stack:
        current = stack.pop()
        for pipeline in current.pipelines:
            for cmd in pipeline.commands:
                if isinstance(cmd, Compound):
                    yield cmd
                    for word in cmd.words:
                        stack.extend(word.scripts())
                    stack.extend(cmd.bodies)
                else:
                    for word in (*cmd.assignments, *cmd.words):
                        stack.extend(word.scripts())
                for redirect in cmd.redirects:
                    if redirect.target is not None:
                        stack.extend(redirect.target.scripts())
                    if redirect.heredoc is not None:
                        for part in redirect.heredoc.expansions:
                            stack.extend(part_scripts(part))


def iter_sites(script: Script):
    """Yields a `Site` for every simple command of the script, nested scripts included (substitutions, compound
    bodies, heredoc expansions), each with its context. A simple command comes before the commands inside its
    substitutions."""
    return _walk(script, True, False, None, None)
