"""Find & Replace dialog (Ctrl+F / Ctrl+H) for the editor text widget.

Non-modal: the dialog stays open while you work in the editor.
All matches are highlighted yellow, the current match orange.
"""

import tkinter as tk

from i18n import t


class SearchDialog(tk.Toplevel):
    def __init__(self, parent, text_widget, on_changed=None):
        """
        parent:      main window
        text_widget: the editor's tk.Text widget
        on_changed:  callback after replacements (e.g. refresh highlighting)
        """
        super().__init__(parent)
        self.title(t("search.title"))
        self.transient(parent)
        self.resizable(False, False)
        self.configure(padx=10, pady=10)

        self.text = text_widget
        self.on_changed = on_changed

        # Match highlighting in the editor
        self.text.tag_config("search_match", background="#FFF59D")
        self.text.tag_config("search_current", background="#FFB74D")

        self.search_var = tk.StringVar()
        self.replace_var = tk.StringVar()
        self.case_var = tk.BooleanVar(value=False)

        tk.Label(self, text=t("search.find")).grid(row=0, column=0, sticky="w", pady=2)
        self.search_entry = tk.Entry(self, textvariable=self.search_var, width=32)
        self.search_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=2, sticky="we")

        tk.Label(self, text=t("search.replace")).grid(row=1, column=0, sticky="w", pady=2)
        self.replace_entry = tk.Entry(self, textvariable=self.replace_var, width=32)
        self.replace_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=2, sticky="we")

        tk.Checkbutton(
            self, text=t("search.case"), variable=self.case_var,
            command=self._refresh_highlights,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=2)

        btns = tk.Frame(self)
        btns.grid(row=3, column=0, columnspan=3, pady=(8, 2), sticky="we")
        tk.Button(btns, text=t("search.prev"), command=lambda: self.find_next(backwards=True)).pack(side=tk.LEFT)
        tk.Button(btns, text=t("search.next"), command=self.find_next).pack(side=tk.LEFT, padx=5)
        tk.Button(btns, text=t("search.replace_one"), command=self.replace_one).pack(side=tk.LEFT, padx=5)
        tk.Button(btns, text=t("search.replace_all"), command=self.replace_all).pack(side=tk.LEFT, padx=5)

        self.status_label = tk.Label(self, text="", fg="gray", anchor="w")
        self.status_label.grid(row=4, column=0, columnspan=3, sticky="we", pady=(6, 0))

        # Keyboard: Enter = next, Shift+Enter = previous, Escape = close
        self.search_entry.bind("<Return>", lambda e: self.find_next())
        self.search_entry.bind("<Shift-Return>", lambda e: self.find_next(backwards=True))
        self.replace_entry.bind("<Return>", lambda e: self.replace_one())
        self.bind("<Escape>", lambda e: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)

        # Highlight live as the search field changes
        self.search_var.trace_add("write", lambda *_: self._refresh_highlights())

        # Place near the top-right corner of the main window
        self.update_idletasks()
        x = parent.winfo_rootx() + max(0, parent.winfo_width() - self.winfo_width() - 40)
        y = parent.winfo_rooty() + 80
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------- internal

    def _nocase(self):
        return not self.case_var.get()

    def _set_status(self, message, error=False):
        self.status_label.config(text=message, fg="#C62828" if error else "gray")

    def _refresh_highlights(self):
        """Mark all matches yellow. Returns the match count."""
        self.text.tag_remove("search_match", "1.0", tk.END)
        self.text.tag_remove("search_current", "1.0", tk.END)
        pattern = self.search_var.get()
        if not pattern:
            self._set_status("")
            return 0

        count = tk.IntVar()
        idx = "1.0"
        n = 0
        while True:
            idx = self.text.search(pattern, idx, stopindex=tk.END, nocase=self._nocase(), count=count)
            if not idx:
                break
            end = f"{idx} + {count.get()} chars"
            self.text.tag_add("search_match", idx, end)
            idx = end
            n += 1

        self._set_status(t("search.matches", count=n) if n else t("search.no_matches"), error=(n == 0))
        return n

    def _select_match(self, idx, length):
        end = f"{idx} + {length} chars"
        self.text.tag_remove("search_current", "1.0", tk.END)
        self.text.tag_add("search_current", idx, end)
        self.text.tag_remove("sel", "1.0", tk.END)
        self.text.tag_add("sel", idx, end)
        self.text.mark_set("insert", end)
        self.text.see(idx)

    # ------------------------------------------------------------- actions

    def find_next(self, event=None, backwards=False):
        pattern = self.search_var.get()
        if not pattern:
            return "break"
        if self._refresh_highlights() == 0:
            return "break"

        count = tk.IntVar()
        wrapped = False

        if backwards:
            try:
                start = self.text.index("sel.first")
            except tk.TclError:
                start = self.text.index("insert")
            idx = self.text.search(pattern, start, stopindex="1.0",
                                   nocase=self._nocase(), count=count, backwards=True)
            if not idx:
                idx = self.text.search(pattern, tk.END, stopindex="1.0",
                                       nocase=self._nocase(), count=count, backwards=True)
                wrapped = True
        else:
            try:
                start = self.text.index("sel.last")
            except tk.TclError:
                start = self.text.index("insert")
            idx = self.text.search(pattern, start, stopindex=tk.END,
                                   nocase=self._nocase(), count=count)
            if not idx:
                idx = self.text.search(pattern, "1.0", stopindex=tk.END,
                                       nocase=self._nocase(), count=count)
                wrapped = True

        if not idx:
            self._set_status(t("search.no_matches"), error=True)
            return "break"

        self._select_match(idx, count.get())
        if wrapped:
            self._set_status(t("search.wrapped_bottom") if backwards else t("search.wrapped_top"))
        return "break"

    def replace_one(self, event=None):
        pattern = self.search_var.get()
        if not pattern:
            return "break"
        replacement = self.replace_var.get()

        # Is the current selection a match? Then replace it.
        try:
            first = self.text.index("sel.first")
            last = self.text.index("sel.last")
            selected = self.text.get(first, last)
            is_match = (selected.lower() == pattern.lower()) if self._nocase() else (selected == pattern)
        except tk.TclError:
            is_match = False

        if is_match:
            self.text.edit_separator()
            self.text.delete(first, last)
            self.text.insert(first, replacement)
            self.text.mark_set("insert", f"{first} + {len(replacement)} chars")
            if self.on_changed:
                self.on_changed()

        # Jump to the next match (or find the first one)
        self.find_next()
        return "break"

    def replace_all(self):
        pattern = self.search_var.get()
        if not pattern:
            return
        replacement = self.replace_var.get()

        count = tk.IntVar()
        idx = "1.0"
        n = 0
        self.text.edit_separator()  # one undo unit for everything
        while True:
            idx = self.text.search(pattern, idx, stopindex=tk.END,
                                   nocase=self._nocase(), count=count)
            if not idx:
                break
            self.text.delete(idx, f"{idx} + {count.get()} chars")
            self.text.insert(idx, replacement)
            # continue past the replacement — prevents infinite loops when
            # the replacement contains the search term (e.g. 'a' -> 'aa')
            idx = f"{idx} + {len(replacement)} chars"
            n += 1
        self.text.edit_separator()

        if self.on_changed:
            self.on_changed()
        self._refresh_highlights()
        self._set_status(t("search.replaced", count=n), error=(n == 0))

    # ------------------------------------------------------------- window

    def focus_search(self, prefill=None, focus_replace=False):
        """Bring the dialog (back) to front and set focus."""
        if prefill:
            self.search_var.set(prefill)
        self.deiconify()
        self.lift()
        target = self.replace_entry if focus_replace else self.search_entry
        target.focus_set()
        self.search_entry.selection_range(0, tk.END)
        self._refresh_highlights()

    def close(self):
        self.text.tag_remove("search_match", "1.0", tk.END)
        self.text.tag_remove("search_current", "1.0", tk.END)
        self.destroy()
