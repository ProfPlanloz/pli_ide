"""Syntax highlighting for PL/I code in a tk.Text widget.

The words live in plain Python lists, so they are easy to extend —
the regex pattern is built from them automatically.
"""

import re
import tkinter as tk

# ---------------------------------------------------------------------------
# Keywords: statements, loop/IO options, attributes, conditions
# ---------------------------------------------------------------------------
PLI_KEYWORDS = [
    # Statements & control flow
    "ALLOCATE", "ALLOC", "BEGIN", "BY", "CALL", "CLOSE", "DECLARE", "DCL",
    "DEFAULT", "DFT", "DELETE", "DISPLAY", "DO", "ELSE", "END", "ENTRY",
    "EXIT", "FETCH", "FORMAT", "FREE", "GET", "GO", "GOTO", "IF", "ITERATE",
    "LEAVE", "LOCATE", "ON", "OPEN", "OTHERWISE", "OTHER", "PROCEDURE",
    "PROC", "PUT", "READ", "RELEASE", "REPEAT", "RETURN", "RETURNS",
    "REVERT", "REWRITE", "SELECT", "SIGNAL", "STOP", "THEN", "TO", "UNTIL",
    "UPTHRU", "DOWNTHRU", "WAIT", "WHEN", "WHILE", "WRITE",
    # Input/output & file options
    "COLUMN", "COL", "COPY", "DATA", "DIRECT", "EDIT", "ENVIRONMENT", "ENV",
    "FILE", "FROM", "INPUT", "INTO", "KEY", "KEYED", "KEYFROM", "KEYTO",
    "LINE", "LINESIZE", "LIST", "OUTPUT", "PAGE", "PAGESIZE", "PRINT",
    "RECORD", "SEQUENTIAL", "SEQL", "SET", "SKIP", "STREAM", "STRING",
    "TITLE", "UPDATE", "BUFFERED", "UNBUFFERED",
    # Attributes & storage classes
    "ALIGNED", "AREA", "AUTOMATIC", "AUTO", "BASED", "BINARY", "BIN", "BIT",
    "BUILTIN", "BYADDR", "BYVALUE", "CHARACTER", "CHAR", "COMPLEX",
    "CONDITION", "COND", "CONNECTED", "CONTROLLED", "CTL", "DECIMAL", "DEC",
    "DEFINED", "DEF", "DIMENSION", "DIM", "EXTERNAL", "EXT", "FIXED",
    "FLOAT", "GENERIC", "INITIAL", "INIT", "INTERNAL", "INT", "LABEL",
    "LIKE", "MAIN", "NONVARYING", "NONVAR", "OFFSET", "OPTIONAL", "OPTIONS",
    "ORDER", "PARAMETER", "PARM", "PICTURE", "PIC", "POINTER", "PTR",
    "POSITION", "POS", "REAL", "RECURSIVE", "REORDER", "SIGNED", "STATIC",
    "UNALIGNED", "UNION", "UNSIGNED", "VARIABLE", "VARYING", "VAR",
    # Conditions (for ON/SIGNAL)
    "ANYCONDITION", "ATTENTION", "CONVERSION", "CONV", "ENDFILE", "ENDPAGE",
    "ERROR", "FINISH", "FIXEDOVERFLOW", "FOFL", "OVERFLOW", "OFL", "SIZE",
    "STORAGE", "STRINGRANGE", "STRG", "STRINGSIZE", "STRZ",
    "SUBSCRIPTRANGE", "SUBRG", "TRANSMIT", "UNDEFINEDFILE", "UNDF",
    "UNDERFLOW", "UFL", "ZERODIVIDE", "ZDIV",
]

# ---------------------------------------------------------------------------
# Builtin functions (own color category)
# ---------------------------------------------------------------------------
PLI_BUILTINS = [
    # Strings
    "SUBSTR", "INDEX", "LENGTH", "VERIFY", "TRANSLATE", "TRIM", "BOOL",
    "UNSPEC", "LOWERCASE", "UPPERCASE", "RANK", "BYTE", "COLLATE", "HIGH",
    "LOW",
    # Math
    "ABS", "CEIL", "FLOOR", "ROUND", "TRUNC", "MOD", "REM", "SIGN", "MAX",
    "MIN", "SQRT", "EXP", "LOG", "LOG2", "LOG10", "ADD", "SUBTRACT",
    "MULTIPLY", "DIVIDE", "RANDOM",
    # Trigonometry
    "SIN", "SIND", "SINH", "COS", "COSD", "COSH", "TAN", "TAND", "TANH",
    "ASIN", "ACOS", "ATAN", "ATAND", "ATANH",
    # Arrays & memory
    "HBOUND", "LBOUND", "ADDR", "NULL", "SYSNULL", "ALLOCATION", "ALLOCN",
    "CURRENTSIZE", "STG", "EMPTY", "POINTERADD", "PTRADD", "POINTERVALUE",
    "PTRVALUE", "OFFSETVALUE",
    # Date/time, conditions & misc
    "DATE", "TIME", "DATETIME", "LINENO", "PAGENO", "COUNT", "SAMEKEY",
    "VALID", "ONCODE", "ONCHAR", "ONSOURCE", "ONFILE", "ONKEY", "ONLOC",
    "PLIRETC", "PLIRETV",
]


def _word_pattern(words):
    """Build a \\b(...)\\b regex pattern from a word list.

    Longer words come first so that e.g. 'PROCEDURE' is not matched
    prematurely as just 'PROC'.
    """
    alternation = "|".join(sorted(set(words), key=len, reverse=True))
    return rf"\b({alternation})\b"


class SyntaxHighlighter:
    """Colors keywords, builtin functions, strings and comments."""

    TAGS = ("keyword", "builtin", "string", "comment")

    def __init__(self, text_widget):
        self.text = text_widget
        self._keyword_pattern = _word_pattern(PLI_KEYWORDS)
        # Words that are already keywords (e.g. COPY, STORAGE, SIZE)
        # stay keywords — otherwise they would get two tags at once.
        builtins_only = set(PLI_BUILTINS) - set(PLI_KEYWORDS)
        self._builtin_pattern = _word_pattern(builtins_only)
        self._setup_tags()

    def _setup_tags(self):
        self.text.tag_config("keyword", foreground="#0000FF", font=("Consolas", 11, "bold"))
        self.text.tag_config("builtin", foreground="#795E26")
        self.text.tag_config("string", foreground="#008000")
        self.text.tag_config("comment", foreground="#808080", font=("Consolas", 11, "italic"))
        # Priority on overlaps: strings/comments win
        self.text.tag_raise("string")
        self.text.tag_raise("comment")

    def highlight(self):
        """Scan the whole code and apply the color tags."""
        content = self.text.get("1.0", tk.END)

        for tag in self.TAGS:
            self.text.tag_remove(tag, "1.0", tk.END)

        self._tag_pattern(content, self._keyword_pattern, "keyword", re.IGNORECASE)
        self._tag_pattern(content, self._builtin_pattern, "builtin", re.IGNORECASE)
        # PL/I uses single quotes for strings
        self._tag_pattern(content, r"'.*?'", "string")
        # Comments /* ... */ — re.DOTALL lets . match newlines too
        self._tag_pattern(content, r"/\*.*?\*/", "comment", re.DOTALL)

    def _tag_pattern(self, content, pattern, tag_name, flags=0):
        for match in re.finditer(pattern, content, flags):
            start_idx = f"1.0 + {match.start()} chars"
            end_idx = f"1.0 + {match.end()} chars"
            self.text.tag_add(tag_name, start_idx, end_idx)
