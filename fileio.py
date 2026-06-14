"""Encoding-tolerant reading and writing of text files.

Older PL/I sources are often not UTF-8 but Latin-1/CP1252. Instead of
failing with a UnicodeDecodeError, UTF-8 is tried first and Latin-1 is used
as a fallback. The encoding used is returned so the file can later be saved
in the same encoding.
"""


def read_text_file(path):
    """Read a text file. Returns (content, encoding)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read(), "utf-8"
    except UnicodeDecodeError:
        # Latin-1 can decode any byte sequence -> never fails.
        with open(path, "r", encoding="latin-1") as f:
            return f.read(), "latin-1"


def write_text_file(path, content, encoding="utf-8"):
    """Write a text file in the given encoding."""
    with open(path, "w", encoding=encoding) as f:
        f.write(content)
