"""Static checks for PL/I source — completely GUI-independent.

Returns error messages as a list of (key, params) tuples so the caller
can translate them via i18n. This keeps the checker free of any language.
"""


def check_lines(lines):
    """Check the lines and return a list of (message_key, params) tuples.

    NOTE: bracket checking is still rudimentary
    (does not yet ignore brackets inside strings/comments).
    """
    messages = []
    brackets = {"(": ")", "{": "}", "[": "]"}
    reverse_brackets = {v: k for k, v in brackets.items()}
    bracket_stack = []

    for line_num, line in enumerate(lines, 1):
        stripped_line = line.rstrip("\n")

        if stripped_line != stripped_line.rstrip():
            messages.append(("check.trailing_whitespace", {"line": line_num}))

        for char_pos, char in enumerate(line, 1):
            if char in brackets:
                bracket_stack.append((char, line_num, char_pos))
            elif char in reverse_brackets:
                if not bracket_stack:
                    messages.append((
                        "check.unexpected_bracket",
                        {"line": line_num, "col": char_pos, "char": char},
                    ))
                else:
                    top_char, _, _ = bracket_stack.pop()
                    if char != brackets[top_char]:
                        messages.append((
                            "check.wrong_bracket",
                            {"line": line_num, "col": char_pos,
                             "char": char, "expected": brackets[top_char]},
                        ))

    for char, line_num, char_pos in bracket_stack:
        messages.append((
            "check.unclosed_bracket",
            {"line": line_num, "col": char_pos, "char": char},
        ))

    return messages
