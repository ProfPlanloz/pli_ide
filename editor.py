"""Editor widget: text area with line numbers, coupled scrollbars,
change tracking, auto-indentation and tab behavior.
"""

import re
import tkinter as tk

from i18n import t


class EditorFrame(tk.LabelFrame):
    """Wraps editor + line numbers + scrollbars.

    Callbacks:
      on_changed()            -> after every edit (e.g. for syntax highlighting)
      on_dirty_changed(bool)  -> when the 'unsaved' status changes

    tab_width: number of spaces per tab / indentation level.
    """

    # After these block openers, auto-indent one level deeper
    BLOCK_OPENER = re.compile(
        r"^(\w+\s*:\s*)?(DO|BEGIN|SELECT|PROC|PROCEDURE)\b", re.IGNORECASE
    )

    def __init__(self, master, on_changed=None, on_dirty_changed=None, tab_width=4):
        super().__init__(master, text=t("editor.title"), padx=5, pady=5)
        self.on_changed = on_changed
        self.on_dirty_changed = on_dirty_changed
        self.tab_width = max(1, int(tab_width))
        self._dirty = False

        # Pack the horizontal scrollbar first so it gets the full width
        self.scroll_x = tk.Scrollbar(self, orient=tk.HORIZONTAL)
        self.scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.line_numbers = tk.Text(
            self,
            width=4,
            padx=3,
            takefocus=0,
            border=0,
            background="#f0f0f0",
            state=tk.DISABLED,
            font=("Consolas", 11),
        )
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        self.text = tk.Text(self, wrap=tk.NONE, font=("Consolas", 11), undo=True)
        self.scroll_y = tk.Scrollbar(self, orient=tk.VERTICAL)

        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Couple the scrollbars
        self.text.config(yscrollcommand=self._sync_scroll_y, xscrollcommand=self.scroll_x.set)
        self.scroll_y.config(command=self.text.yview)
        self.scroll_x.config(command=self.text.xview)

        # Events
        self.text.bind("<KeyRelease>", self._on_key_release)
        self.text.bind("<MouseWheel>", lambda e: self._sync_lines_to_text())
        # Linux mouse wheel
        self.text.bind("<Button-4>", lambda e: self._sync_lines_to_text())
        self.text.bind("<Button-5>", lambda e: self._sync_lines_to_text())
        self.text.bind("<Button-1>", lambda e: self._sync_lines_to_text())
        # <<Modified>> is Tk's built-in change tracking
        self.text.bind("<<Modified>>", self._on_modified_event)

        # Auto-indentation & tab behavior
        self.text.bind("<Return>", self._on_return)
        self.text.bind("<Tab>", self._on_tab)
        self.text.bind("<Shift-Tab>", self._on_shift_tab)
        # On Linux/X11 Shift+Tab is called 'ISO_Left_Tab'
        self.text.bind("<ISO_Left_Tab>", self._on_shift_tab)

    # --- Scroll synchronization ---

    def _sync_scroll_y(self, *args):
        """Synchronize the scrollbar with editor and line numbers."""
        self.scroll_y.set(*args)
        self.line_numbers.yview_moveto(args[0])

    def _sync_lines_to_text(self):
        self.line_numbers.yview_moveto(self.text.yview()[0])

    # --- Events ---

    def _on_key_release(self, event=None):
        self.update_line_numbers()
        if self.on_changed:
            self.on_changed()

    def _on_modified_event(self, event=None):
        dirty = self.text.edit_modified()
        if dirty != self._dirty:
            self._dirty = dirty
            if self.on_dirty_changed:
                self.on_dirty_changed(dirty)

    # --- Auto-indentation & tab behavior ---

    def _on_return(self, event=None):
        """Enter: keep the current line's indentation.
        After block openers (DO/BEGIN/SELECT/PROC...) go one level deeper."""
        # Any existing selection is replaced (as usual)
        try:
            self.text.delete("sel.first", "sel.last")
        except tk.TclError:
            pass

        line = self.text.get("insert linestart", "insert lineend")
        indent = line[: len(line) - len(line.lstrip(" \t"))]

        extra = ""
        stripped = line.strip()
        if stripped.endswith(";") and self.BLOCK_OPENER.match(stripped):
            extra = " " * self.tab_width

        self.text.insert("insert", "\n" + indent + extra)
        self.text.see("insert")
        return "break"

    def _on_tab(self, event=None):
        """Tab: insert spaces; with a selection, indent all lines."""
        indent = " " * self.tab_width
        sel = self._selected_lines()
        if sel is None:
            self.text.insert("insert", indent)
        else:
            for ln in range(sel[0], sel[1] + 1):
                self.text.insert(f"{ln}.0", indent)
        return "break"

    def _on_shift_tab(self, event=None):
        """Shift+Tab: dedent the current line or the selected lines."""
        sel = self._selected_lines()
        if sel is None:
            ln = int(self.text.index("insert").split(".")[0])
            self._dedent_line(ln)
        else:
            for ln in range(sel[0], sel[1] + 1):
                self._dedent_line(ln)
        return "break"

    def _selected_lines(self):
        """(first, last) line number of the selection, or None."""
        try:
            first = self.text.index("sel.first")
            last = self.text.index("sel.last")
        except tk.TclError:
            return None
        first_line = int(first.split(".")[0])
        last_line, last_col = (int(x) for x in last.split("."))
        # If the selection ends right at the start of a line, exclude that line
        if last_col == 0 and last_line > first_line:
            last_line -= 1
        return first_line, last_line

    def _dedent_line(self, ln):
        """Remove up to tab_width leading spaces (or one tab)."""
        content = self.text.get(f"{ln}.0", f"{ln}.end")
        removed = 0
        while removed < self.tab_width and removed < len(content) and content[removed] == " ":
            removed += 1
        if removed == 0 and content[:1] == "\t":
            removed = 1
        if removed:
            self.text.delete(f"{ln}.0", f"{ln}.{removed}")

    # --- Public interface ---

    def is_dirty(self):
        """True if there are unsaved changes."""
        return self._dirty

    def mark_saved(self):
        """Call after saving — resets the change status."""
        self.text.edit_modified(False)

    def get_content(self):
        return self.text.get("1.0", "end-1c")

    def set_content(self, content):
        """Load new content; loading itself does not count as a change."""
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", content)
        self.text.edit_reset()          # clear undo history
        self.text.edit_modified(False)  # loading = not 'dirty'
        self.update_line_numbers()

    def update_line_numbers(self):
        """Update the line numbers on the left side."""
        line_count = int(self.text.index("end-1c").split(".")[0])
        numbers = "\n".join(str(i) for i in range(1, line_count + 1))

        self.line_numbers.config(state=tk.NORMAL)
        self.line_numbers.delete("1.0", tk.END)
        self.line_numbers.insert("1.0", numbers)
        self.line_numbers.config(state=tk.DISABLED)

        self._sync_lines_to_text()
