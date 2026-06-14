"""AI assistant (window) and AI settings dialog.

The assistant can send along the current editor content and the last output
(error messages) — for debugging help and code generation.
"""

import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from ai_client import AIError, PROVIDER_DEFAULTS, extract_code_blocks
from i18n import t

MAX_CODE_CHARS = 15000   # cap on the code sent along
MAX_OUTPUT_CHARS = 4000  # cap on the output sent along


class AssistantDialog(tk.Toplevel):
    def __init__(self, parent, client, get_code, get_output, insert_code, on_configure):
        """
        client:       AIClient
        get_code:     Callable() -> current editor content
        get_output:   Callable() -> content of the output panel
        insert_code:  Callable(code) -> inserts code into the editor
        on_configure: Callable() -> opens the AI settings dialog
        """
        super().__init__(parent)
        self.title(t("ai.assistant_title"))
        self.geometry("720x640")
        self.client = client
        self.get_code = get_code
        self.get_output = get_output
        self.insert_code = insert_code
        self.on_configure = on_configure
        self.configure(padx=10, pady=10)

        # Header: current backend + configure
        head = tk.Frame(self)
        head.pack(fill=tk.X)
        self.backend_label = tk.Label(head, text="", fg="gray")
        self.backend_label.pack(side=tk.LEFT)
        tk.Button(head, text=t("ai.configure"), command=self.on_configure).pack(side=tk.RIGHT)

        # Request
        prompt_frame = tk.LabelFrame(self, text=t("ai.request"), padx=5, pady=5)
        prompt_frame.pack(fill=tk.X, pady=(8, 4))
        self.prompt_text = scrolledtext.ScrolledText(prompt_frame, height=6, wrap=tk.WORD,
                                                     font=("Consolas", 10))
        self.prompt_text.pack(fill=tk.X)

        options = tk.Frame(prompt_frame)
        options.pack(fill=tk.X, pady=(5, 0))
        self.include_code_var = tk.BooleanVar(value=True)
        self.include_output_var = tk.BooleanVar(value=True)
        tk.Checkbutton(options, text=t("ai.include_code"),
                       variable=self.include_code_var).pack(side=tk.LEFT)
        tk.Checkbutton(options, text=t("ai.include_output"),
                       variable=self.include_output_var).pack(side=tk.LEFT, padx=10)
        tk.Button(options, text=t("ai.template_debug_btn"),
                  command=lambda: self._set_prompt(t("ai.template_debug"))).pack(side=tk.RIGHT)
        tk.Button(options, text=t("ai.template_generate_btn"),
                  command=lambda: self._set_prompt(t("ai.template_generate"))).pack(side=tk.RIGHT, padx=5)

        actions = tk.Frame(self)
        actions.pack(fill=tk.X, pady=4)
        self.send_button = tk.Button(actions, text=t("ai.send"), command=self.send,
                                     bg="#2196F3", fg="white", font=("Arial", 10, "bold"),
                                     relief=tk.FLAT, padx=12, pady=4)
        self.send_button.pack(side=tk.LEFT)
        self.status_label = tk.Label(actions, text="", fg="gray")
        self.status_label.pack(side=tk.LEFT, padx=10)

        # Answer
        answer_frame = tk.LabelFrame(self, text=t("ai.answer"), padx=5, pady=5)
        answer_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 4))
        self.answer_text = scrolledtext.ScrolledText(answer_frame, wrap=tk.WORD,
                                                     font=("Consolas", 10))
        self.answer_text.pack(fill=tk.BOTH, expand=True)
        self.answer_text.config(state=tk.DISABLED)

        tk.Button(self, text=t("ai.insert_code"),
                  command=self._insert_answer_code).pack(anchor="e")

        self.refresh_backend_label()

    # --------------------------------------------------------------- UI

    def refresh_backend_label(self):
        self.backend_label.config(text=t("ai.backend", backend=self.client.describe_backend()))

    def _set_prompt(self, text):
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", text)
        self.prompt_text.focus_set()

    def _set_status(self, message, error=False):
        self.status_label.config(text=message, fg="#C62828" if error else "gray")

    def show(self, prefill=None, autosend=False):
        self.deiconify()
        self.lift()
        self.refresh_backend_label()
        if prefill:
            self._set_prompt(prefill)
        if autosend:
            self.send()
        else:
            self.prompt_text.focus_set()

    # ------------------------------------------------------------ sending

    def _build_user_message(self):
        prompt = self.prompt_text.get("1.0", "end-1c").strip()
        if not prompt:
            return None
        parts = [prompt]

        if self.include_code_var.get():
            code = self.get_code()
            if code.strip():
                if len(code) > MAX_CODE_CHARS:
                    code = code[:MAX_CODE_CHARS] + "\n" + t("ai.truncated")
                parts.append(t("ai.code_header") + "\n" + code)

        if self.include_output_var.get():
            output = self.get_output()
            if output.strip():
                if len(output) > MAX_OUTPUT_CHARS:
                    output = t("ai.truncated") + "\n" + output[-MAX_OUTPUT_CHARS:]
                parts.append(t("ai.output_header") + "\n" + output)

        return "\n\n".join(parts)

    def send(self):
        user_message = self._build_user_message()
        if not user_message:
            self._set_status(t("ai.enter_request"), error=True)
            return
        self.send_button.config(state=tk.DISABLED)
        self._set_status(t("ai.running"))
        threading.Thread(target=self._worker, args=(user_message,), daemon=True).start()

    def _worker(self, user_message):
        try:
            answer = self.client.chat(t("ai.system_prompt"), user_message)
        except AIError as e:
            self.after(0, self._show_error, str(e))
            return
        except Exception as e:  # safety net
            self.after(0, self._show_error, t("ai.unexpected", error=e))
            return
        self.after(0, self._show_answer, answer)

    def _show_answer(self, answer):
        self.answer_text.config(state=tk.NORMAL)
        self.answer_text.delete("1.0", tk.END)
        self.answer_text.insert("1.0", answer)
        self.answer_text.config(state=tk.DISABLED)
        self.send_button.config(state=tk.NORMAL)
        self._set_status(t("ai.done"))

    def _show_error(self, message):
        self.answer_text.config(state=tk.NORMAL)
        self.answer_text.delete("1.0", tk.END)
        self.answer_text.insert("1.0", t("ai.error_prefix", message=message))
        self.answer_text.config(state=tk.DISABLED)
        self.send_button.config(state=tk.NORMAL)
        self._set_status(t("ai.request_error"), error=True)

    # ----------------------------------------------------- insert code

    def _insert_answer_code(self):
        answer = self.answer_text.get("1.0", "end-1c")
        if not answer.strip():
            self._set_status(t("ai.no_answer"), error=True)
            return
        blocks = extract_code_blocks(answer)
        code = "\n\n".join(blocks) if blocks else answer
        self.insert_code(code)
        self._set_status(t("ai.inserted", count=len(blocks) or 1))


# ---------------------------------------------------------------------------
# AI settings
# ---------------------------------------------------------------------------

def open_ai_settings(parent, config, on_saved=None):
    """Dialog for provider, model, API key and base URL."""
    win = tk.Toplevel(parent)
    win.title(t("ai.settings_title"))
    win.geometry("620x300")
    win.grab_set()
    win.configure(padx=20, pady=20)

    provider_var = tk.StringVar(value=config.get("ai_provider") or "ollama")
    model_var = tk.StringVar(value=config.get("ai_model") or "")
    key_var = tk.StringVar(value=config.get("ai_api_key") or "")
    url_var = tk.StringVar(value=config.get("ai_base_url") or "")

    tk.Label(win, text=t("ai.provider")).grid(row=0, column=0, sticky="w", pady=5)
    provider_box = ttk.Combobox(win, textvariable=provider_var, state="readonly",
                                values=list(PROVIDER_DEFAULTS.keys()), width=20)
    provider_box.grid(row=0, column=1, sticky="w", padx=5)

    tk.Label(win, text=t("ai.model")).grid(row=1, column=0, sticky="w", pady=5)
    tk.Entry(win, textvariable=model_var, width=42).grid(row=1, column=1, columnspan=2, padx=5, sticky="we")

    tk.Label(win, text=t("ai.api_key")).grid(row=2, column=0, sticky="w", pady=5)
    tk.Entry(win, textvariable=key_var, width=42, show="*").grid(row=2, column=1, columnspan=2, padx=5, sticky="we")

    tk.Label(win, text=t("ai.base_url")).grid(row=3, column=0, sticky="w", pady=5)
    tk.Entry(win, textvariable=url_var, width=42).grid(row=3, column=1, columnspan=2, padx=5, sticky="we")

    tk.Label(
        win, justify="left", fg="gray", wraplength=560, anchor="w",
        text=t("ai.settings_info"),
    ).grid(row=4, column=0, columnspan=3, sticky="we", pady=(10, 0))

    def on_provider_changed(event=None):
        defaults = PROVIDER_DEFAULTS[provider_var.get()]
        model_var.set(defaults["model"])
        url_var.set(defaults["base_url"])

    provider_box.bind("<<ComboboxSelected>>", on_provider_changed)

    def save_and_close():
        config.set("ai_provider", provider_var.get())
        config.set("ai_model", model_var.get().strip())
        config.set("ai_api_key", key_var.get().strip())
        config.set("ai_base_url", url_var.get().strip())
        try:
            config.save()
        except Exception as e:
            messagebox.showerror(t("paths.save_error_title"), t("paths.save_error", error=e), parent=win)
            return
        win.destroy()
        if on_saved:
            on_saved()

    tk.Button(
        win, text=t("ai.save"), command=save_and_close,
        bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
    ).grid(row=5, column=0, columnspan=3, pady=18)
