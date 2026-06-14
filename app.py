"""Main application: wires together editor, highlighter, checker, builder and config."""

import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

import i18n
from i18n import t
from build import Builder
from checker import check_lines
from config import Config
from editor import EditorFrame
from fileio import read_text_file, write_text_file
from ai_client import AIClient
from ai_dialog import AssistantDialog, open_ai_settings
from search_dialog import SearchDialog
from settings_dialog import open_settings
from syntax import SyntaxHighlighter

# Detects line references in messages: 'Line 12', 'Zeile 5', 'LINE 7'
# as well as leading '12:' references at the start of a line (typical for compilers).
LINE_REF = re.compile(
    r"\b(?:LINE|ZEILE|LIGNE|LINEA|LINHA|REGEL|RIGA)\s+(?P<n1>\d+)|^[ \t]*(?P<n2>\d+):",
    re.IGNORECASE | re.MULTILINE,
)


class PLIIDEApp:
    def __init__(self, root):
        self.root = root
        self.root.geometry("850x750")
        self.root.configure(padx=10, pady=10)

        self.current_filepath = None
        self.executable_path = None
        self.file_encoding = "utf-8"  # determined on load (UTF-8 / Latin-1 fallback)
        self.search_dialog = None
        self._link_seq = 0      # running number for clickable links
        self._link_tags = []    # so old link tags can be cleaned up

        self.config = Config()
        # Apply the saved UI language before any widgets are built
        i18n.set_language(self.config.get("language"))

        self.builder = Builder(self.config, self.print_result, self.print_plain)
        self.ai_client = AIClient(self.config)
        self.assistant = None

        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()

        # Ask about unsaved changes when closing via the window's X button
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._update_title()

    # ------------------------------------------------------------------ UI

    def _build_menu(self):
        menu_bar = tk.Menu(self.root)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label=t("menu.file.open"), command=self.select_file)
        file_menu.add_command(label=t("menu.file.save"), command=self.save_file)
        file_menu.add_command(label=t("menu.file.save_as"), command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label=t("menu.file.quit"), command=self.on_close)
        menu_bar.add_cascade(label=t("menu.file"), menu=file_menu)

        settings_menu = tk.Menu(menu_bar, tearoff=0)
        settings_menu.add_command(
            label=t("menu.settings.paths"),
            command=lambda: open_settings(self.root, self.config, on_saved=self._on_settings_saved),
        )
        menu_bar.add_cascade(label=t("menu.settings"), menu=settings_menu)

        # Language menu — one radio entry per JSON file in the lang/ folder
        language_menu = tk.Menu(menu_bar, tearoff=0)
        self._language_var = tk.StringVar(value=i18n.current_language())
        for code, name in i18n.available_languages().items():
            language_menu.add_radiobutton(
                label=name, value=code, variable=self._language_var,
                command=lambda c=code: self._change_language(c),
            )
        menu_bar.add_cascade(label=t("menu.language"), menu=language_menu)

        ai_menu = tk.Menu(menu_bar, tearoff=0)
        ai_menu.add_command(label=t("menu.ai.open"), command=self._open_assistant)
        ai_menu.add_command(label=t("menu.ai.debug"), command=self._ai_debug)
        ai_menu.add_separator()
        ai_menu.add_command(label=t("menu.ai.configure"), command=self._configure_ai)
        menu_bar.add_cascade(label=t("menu.ai"), menu=ai_menu)

        self.root.config(menu=menu_bar)

    def _change_language(self, code):
        """Switch UI language live and rebuild the interface."""
        i18n.set_language(code)
        self.config.set("language", code)
        try:
            self.config.save()
        except Exception:
            pass

        # Preserve editor content and dirty state across the rebuild
        content = self.editor.get_content()
        was_dirty = self.editor.is_dirty()
        cursor = self.editor.text.index("insert")
        output = self.result_text.get("1.0", "end-1c")

        # Close child dialogs (they will be recreated in the new language)
        if self.search_dialog is not None and self.search_dialog.winfo_exists():
            self.search_dialog.close()
            self.search_dialog = None
        if self.assistant is not None and self.assistant.winfo_exists():
            self.assistant.destroy()
            self.assistant = None

        # Rebuild menu and main UI
        for child in self.root.winfo_children():
            child.destroy()
        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()

        # Restore state
        self.editor.set_content(content)
        self.editor.text.mark_set("insert", cursor)
        self.highlighter.highlight()
        if was_dirty:
            self.editor.text.edit_modified(True)
        if self.current_filepath:
            self.file_label.config(text=os.path.basename(self.current_filepath), fg="black")
            self.compile_button.config(state=tk.NORMAL)
            self.save_button.config(state=tk.NORMAL)
            if self.executable_path:
                self.run_button.config(state=tk.NORMAL)
        if output.strip():
            self.result_text.config(state=tk.NORMAL)
            self.result_text.insert("1.0", output + "\n")
            self.result_text.config(state=tk.DISABLED)
        self._update_title()

    def _on_settings_saved(self):
        # Apply a changed tab width immediately (no restart needed)
        self.editor.tab_width = max(1, int(self.config.get("tab_width")))
        self.print_result(t("settings.saved"), is_error=False)

    def _on_terminal_toggle(self):
        self.config.set("run_in_terminal", bool(self.terminal_var.get()))
        try:
            self.config.save()
        except Exception:
            pass  # not critical — the mode still applies for this session

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root)
        header.pack(fill=tk.X, pady=(0, 10))

        tk.Label(header, text=t("header.intro"), font=("Arial", 10)).pack(anchor="w", pady=(0, 10))

        self.select_button = tk.Button(
            header, text=t("header.open"), command=self.select_file,
            font=("Arial", 10, "bold"),
            bg="#4CAF50", fg="white", relief=tk.FLAT, padx=10, pady=5,
        )
        self.select_button.pack(side=tk.LEFT)

        self.save_button = tk.Button(
            header, text=t("header.save"), command=self.save_file,
            font=("Arial", 10, "bold"),
            bg="#9C27B0", fg="white", relief=tk.FLAT, padx=10, pady=5,
            state=tk.DISABLED,
        )
        self.save_button.pack(side=tk.LEFT, padx=(10, 0))

        self.compile_button = tk.Button(
            header, text=t("header.compile"), command=self.start_compilation_thread,
            font=("Arial", 10, "bold"),
            bg="#2196F3", fg="white", relief=tk.FLAT, padx=10, pady=5,
            state=tk.DISABLED,
        )
        self.compile_button.pack(side=tk.LEFT, padx=(10, 0))

        self.run_button = tk.Button(
            header, text=t("header.run"), command=self.start_run_thread,
            font=("Arial", 10, "bold"),
            bg="#FF9800", fg="white", relief=tk.FLAT, padx=10, pady=5,
            state=tk.DISABLED,
        )
        self.run_button.pack(side=tk.LEFT, padx=(10, 0))

        # Toggle: external terminal vs. output in the IDE window
        self.terminal_var = tk.BooleanVar(value=bool(self.config.get("run_in_terminal")))
        tk.Checkbutton(
            header, text=t("header.run_in_terminal"),
            variable=self.terminal_var, command=self._on_terminal_toggle,
        ).pack(side=tk.LEFT, padx=(10, 0))

        self.file_label = tk.Label(header, text=t("header.no_file_selected"), fg="gray")
        self.file_label.pack(side=tk.LEFT, padx=10)

        # PanedWindow: editor on top, output at the bottom
        paned = tk.PanedWindow(self.root, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True)

        self.editor = EditorFrame(
            paned,
            on_changed=self._on_editor_changed,
            on_dirty_changed=lambda dirty: self._update_title(),
            tab_width=self.config.get("tab_width"),
        )
        paned.add(self.editor, minsize=250)

        output_frame = tk.LabelFrame(paned, text=t("output.title"), padx=5, pady=5)
        self.result_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.result_text.pack(fill=tk.BOTH, expand=True)
        self.result_text.config(state=tk.DISABLED)
        paned.add(output_frame, minsize=150)

        # Clickable line references in the output
        self.result_text.tag_config("link", foreground="#1565C0", underline=True)
        self.result_text.tag_bind("link", "<Enter>", lambda e: self.result_text.config(cursor="hand2"))
        self.result_text.tag_bind("link", "<Leave>", lambda e: self.result_text.config(cursor=""))

        self.highlighter = SyntaxHighlighter(self.editor.text)
        # Briefly flash the target line after clicking an error message
        self.editor.text.tag_config("error_line", background="#FFCDD2")

    def _bind_shortcuts(self):
        # Bindings live on the text widget too and return "break". This
        # suppresses tk.Text's built-in <Control-o> (inserts a blank line!)
        # and <Control-h> (backspace), and keeps Ctrl+Shift+S from being
        # swallowed by the Ctrl+S binding.
        for widget in (self.root, self.editor.text):
            widget.bind("<Control-Key-o>", self._on_ctrl_o)
            widget.bind("<Control-Key-O>", self._on_ctrl_o)
            widget.bind("<Control-Key-s>", self._on_ctrl_s)
            widget.bind("<Control-Key-S>", self._on_ctrl_s)
            widget.bind("<Control-Key-f>", self._on_ctrl_f)
            widget.bind("<Control-Key-F>", self._on_ctrl_f)
            widget.bind("<Control-Key-h>", self._on_ctrl_h)
            widget.bind("<Control-Key-H>", self._on_ctrl_h)

        self.root.bind("<F5>", lambda e: self.start_compilation_thread())
        self.root.bind("<F6>", lambda e: self.start_run_thread())
        self.root.bind("<F8>", lambda e: self._open_assistant())

    # ----------------------------------------------------------- shortcuts

    def _on_ctrl_o(self, event=None):
        self.select_file()
        return "break"  # no blank line in the editor

    def _on_ctrl_s(self, event=None):
        # Shift is detected via event.state (bit 0x0001) instead of relying
        # on a competing <Control-Shift-S> binding.
        if event is not None and (event.state & 0x0001):
            self.save_file_as()
        else:
            self.save_file()
        return "break"

    def _on_ctrl_f(self, event=None):
        self._open_search(focus_replace=False)
        return "break"

    def _on_ctrl_h(self, event=None):
        self._open_search(focus_replace=True)
        return "break"

    def _open_search(self, focus_replace=False):
        # Prefill the search term with the current selection
        try:
            prefill = self.editor.text.get("sel.first", "sel.last")
            if "\n" in prefill:
                prefill = None
        except tk.TclError:
            prefill = None

        if self.search_dialog is None or not self.search_dialog.winfo_exists():
            self.search_dialog = SearchDialog(
                self.root, self.editor.text, on_changed=self._on_editor_changed,
            )
        self.search_dialog.focus_search(prefill=prefill, focus_replace=focus_replace)

    # --------------------------------------------------------- AI assistant

    def _open_assistant(self, prefill=None, autosend=False):
        if self.assistant is None or not self.assistant.winfo_exists():
            self.assistant = AssistantDialog(
                self.root,
                self.ai_client,
                get_code=self.editor.get_content,
                get_output=lambda: self.result_text.get("1.0", "end-1c"),
                insert_code=self._insert_ai_code,
                on_configure=self._configure_ai,
            )
        self.assistant.show(prefill=prefill, autosend=autosend)

    def _ai_debug(self):
        """Open the assistant with the debug template and send immediately —
        editor code and the output panel (error messages) go along."""
        self._open_assistant(prefill=t("ai.template_debug"), autosend=True)

    def _insert_ai_code(self, code):
        self.editor.text.insert("insert", code)
        self._on_editor_changed()

    def _configure_ai(self):
        open_ai_settings(self.root, self.config, on_saved=self._on_ai_settings_saved)

    def _on_ai_settings_saved(self):
        self.print_result(t("ai.settings_saved"), is_error=False)
        if self.assistant is not None and self.assistant.winfo_exists():
            self.assistant.refresh_backend_label()

    # ------------------------------------------------------------- editor

    def _on_editor_changed(self):
        self.editor.update_line_numbers()
        self.highlighter.highlight()

    def _update_title(self):
        name = os.path.basename(self.current_filepath) if self.current_filepath else t("app.no_file")
        star = "*" if self.editor.is_dirty() else ""
        self.root.title(t("app.title", star=star, name=name))

    def _confirm_discard(self):
        """Ask about unsaved changes.
        True = it's OK to proceed (possibly after a successful save)."""
        if not self.editor.is_dirty():
            return True
        answer = messagebox.askyesnocancel(t("confirm.unsaved_title"), t("confirm.unsaved"))
        if answer is None:      # Cancel
            return False
        if answer:              # Yes -> save
            return self.save_file()
        return True             # No -> discard changes

    # ----------------------------------------------------- file operations

    def select_file(self, event=None):
        if not self._confirm_discard():
            return "break"
        filepath = filedialog.askopenfilename(
            title=t("dialog.open_title"),
            filetypes=((t("filetype.pli"), "*.pli"), (t("filetype.all"), "*.*")),
        )
        if filepath:
            self._load_file(filepath)
        return "break"

    def _load_file(self, filepath):
        try:
            content, encoding = read_text_file(filepath)
        except Exception as e:
            messagebox.showerror(t("msg.load_error_title"), t("msg.load_error", error=e))
            return

        self.current_filepath = filepath
        self.file_encoding = encoding
        self.editor.set_content(content)
        self.highlighter.highlight()

        self.file_label.config(text=os.path.basename(filepath), fg="black")
        self.compile_button.config(state=tk.NORMAL)
        self.save_button.config(state=tk.NORMAL)
        self.run_button.config(state=tk.DISABLED)
        self.executable_path = None
        self._update_title()

        if encoding != "utf-8":
            self.print_result(t("msg.encoding_hint", encoding=encoding), is_error=False)
        self.run_checks(filepath)

    def save_file(self, event=None):
        """Save the current file. Returns True on success."""
        if not self.current_filepath:
            return self.save_file_as()
        try:
            write_text_file(self.current_filepath, self.editor.get_content(), self.file_encoding)
        except Exception as e:
            messagebox.showerror(t("msg.save_error_title"), t("msg.save_error", error=e))
            return False

        self.editor.mark_saved()
        self._update_title()
        self.print_result(t("msg.saved", name=os.path.basename(self.current_filepath)), is_error=False)
        self.run_checks(self.current_filepath)
        return True

    def save_file_as(self, event=None):
        filepath = filedialog.asksaveasfilename(
            title=t("dialog.save_as_title"),
            defaultextension=".pli",
            filetypes=((t("filetype.pli"), "*.pli"), (t("filetype.all"), "*.*")),
        )
        if not filepath:
            return False

        self.current_filepath = filepath
        self.file_label.config(text=os.path.basename(filepath), fg="black")
        self.compile_button.config(state=tk.NORMAL)
        self.save_button.config(state=tk.NORMAL)
        self.run_button.config(state=tk.DISABLED)
        self.executable_path = None
        return self.save_file()

    # ------------------------------------------------------------ checking

    def run_checks(self, filepath):
        self.clear_results()
        self.print_result(t("check.start", path=filepath), is_error=False)
        self.print_result("-" * 50, is_error=False)

        try:
            content, _ = read_text_file(filepath)
        except Exception as e:
            self.print_result(t("msg.read_error", error=e))
            return

        messages = check_lines(content.splitlines(keepends=True))
        for key, params in messages:
            self.print_result(t(key, **params))

        self.print_result("-" * 50, is_error=False)
        if not messages:
            self.print_result(t("check.none"), is_error=False)
        else:
            self.print_result(t("check.done", count=len(messages)), is_error=True)

    # ------------------------------------------- compiling & running

    def start_compilation_thread(self, event=None):
        if self.compile_button["state"] == tk.DISABLED or not self.current_filepath:
            return

        # Auto-save the editor content before compiling so the current state
        # is compiled, not a stale version on disk.
        if self.editor.is_dirty():
            if not self.save_file():
                return

        self.compile_button.config(state=tk.DISABLED)
        threading.Thread(target=self._compile_worker, daemon=True).start()

    def _compile_worker(self):
        try:
            exe = self.builder.compile(self.current_filepath)
            if exe:
                self.executable_path = exe
                self.root.after(0, lambda: self.run_button.config(state=tk.NORMAL))
        except Exception as e:
            self.print_result(t("compile.error", error=e), is_error=True)
        finally:
            self.root.after(0, lambda: self.compile_button.config(state=tk.NORMAL))

    def start_run_thread(self, event=None):
        if self.run_button["state"] == tk.DISABLED:
            return
        self.run_button.config(state=tk.DISABLED)
        self.compile_button.config(state=tk.DISABLED)
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _run_worker(self):
        try:
            if not self.executable_path or not os.path.exists(self.executable_path):
                self.print_result(t("run.not_found"), is_error=True)
                return
            if self.terminal_var.get():
                self.builder.run_in_terminal(self.executable_path)
            else:
                self.builder.run_captured(self.executable_path)
        except Exception as e:
            self.print_result(t("run.error", error=e), is_error=True)
        finally:
            self._enable_buttons()

    def _enable_buttons(self):
        self.root.after(0, lambda: self.compile_button.config(state=tk.NORMAL))
        if self.executable_path:
            self.root.after(0, lambda: self.run_button.config(state=tk.NORMAL))

    # ------------------------------------------------------------- output

    def print_result(self, message, is_error=True):
        # Thread-safe: always update the UI via the Tk mainloop
        self.root.after(0, self._safe_print_result, message, is_error)

    def print_plain(self, message):
        """Raw program output without a status symbol."""
        self.root.after(0, self._safe_print_plain, message)

    def _safe_print_plain(self, message):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.insert(tk.END, message + "\n")
        self.result_text.config(state=tk.DISABLED)
        self.result_text.see(tk.END)

    def _safe_print_result(self, message, is_error=True):
        self.result_text.config(state=tk.NORMAL)
        prefix = "\u274c " if is_error else "\u2705 "
        self.result_text.insert(tk.END, prefix)
        self._insert_with_links(message + "\n")
        self.result_text.config(state=tk.DISABLED)
        self.result_text.see(tk.END)

    def _insert_with_links(self, body):
        """Insert text and turn line references ('Line 12', 'Zeile 5', '7:')
        into clickable links that jump to the line in the editor."""
        base = self.result_text.index("end-1c")
        self.result_text.insert(tk.END, body)

        for match in LINE_REF.finditer(body):
            lineno = int(match.group("n1") or match.group("n2"))
            matched = match.group(0)
            # do not underline leading whitespace (for '  7:')
            offset = len(matched) - len(matched.lstrip())
            start = f"{base} + {match.start() + offset} chars"
            end = f"{base} + {match.end()} chars"

            self._link_seq += 1
            tag = f"linkref{self._link_seq}"
            self._link_tags.append(tag)
            self.result_text.tag_add("link", start, end)
            self.result_text.tag_add(tag, start, end)
            self.result_text.tag_bind(
                tag, "<Button-1>", lambda e, ln=lineno: self._goto_line(ln)
            )

    def _goto_line(self, lineno):
        """Jump to the line in the editor and flash it briefly."""
        text = self.editor.text
        last_line = int(text.index("end-1c").split(".")[0])
        lineno = max(1, min(lineno, last_line))

        text.mark_set("insert", f"{lineno}.0")
        text.see(f"{lineno}.0")
        text.focus_set()

        text.tag_remove("error_line", "1.0", tk.END)
        text.tag_add("error_line", f"{lineno}.0", f"{lineno}.end")
        self.root.after(1500, lambda: text.tag_remove("error_line", "1.0", tk.END))

    def clear_results(self):
        self.root.after(0, self._safe_clear_results)

    def _safe_clear_results(self):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.config(state=tk.DISABLED)
        # Dispose of old link tags (including their bindings)
        for tag in self._link_tags:
            self.result_text.tag_delete(tag)
        self._link_tags.clear()

    # ------------------------------------------------------------ closing

    def on_close(self):
        """Ask about unsaved changes before closing."""
        if self._confirm_discard():
            self.root.destroy()
