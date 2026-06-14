"""Settings dialog: configure paths to plic, the lib folder and gcc,
plus the tab width."""

import tkinter as tk
from tkinter import filedialog, messagebox

from i18n import t


def open_settings(parent, config, on_saved=None):
    """Open the modal settings dialog.

    parent:   main window
    config:   Config object (updated and saved on 'Save')
    on_saved: optional callback after a successful save
    """
    win = tk.Toplevel(parent)
    win.title(t("paths.title"))
    win.geometry("600x290")
    win.grab_set()  # block the main window until the dialog is closed
    win.configure(padx=20, pady=20)

    def browse_file(var):
        path = filedialog.askopenfilename(parent=win)
        if path:
            var.set(path)

    def browse_dir(var):
        path = filedialog.askdirectory(parent=win)
        if path:
            var.set(path)

    plic_var = tk.StringVar(value=config.get("plic_path"))
    lib_var = tk.StringVar(value=config.get("lib_path"))
    gcc_var = tk.StringVar(value=config.get("gcc_path"))

    tk.Label(win, text=t("paths.plic")).grid(row=0, column=0, sticky="w", pady=5)
    tk.Entry(win, textvariable=plic_var, width=40).grid(row=0, column=1, padx=5)
    tk.Button(win, text=t("paths.browse"), command=lambda: browse_file(plic_var)).grid(row=0, column=2)

    tk.Label(win, text=t("paths.lib")).grid(row=1, column=0, sticky="w", pady=5)
    tk.Entry(win, textvariable=lib_var, width=40).grid(row=1, column=1, padx=5)
    tk.Button(win, text=t("paths.browse"), command=lambda: browse_dir(lib_var)).grid(row=1, column=2)

    tk.Label(win, text=t("paths.gcc")).grid(row=2, column=0, sticky="w", pady=5)
    tk.Entry(win, textvariable=gcc_var, width=40).grid(row=2, column=1, padx=5)
    tk.Button(win, text=t("paths.browse"), command=lambda: browse_file(gcc_var)).grid(row=2, column=2)

    tab_var = tk.StringVar(value=str(config.get("tab_width")))
    tk.Label(win, text=t("paths.tab_width")).grid(row=3, column=0, sticky="w", pady=5)
    tk.Entry(win, textvariable=tab_var, width=5).grid(row=3, column=1, padx=5, sticky="w")

    def save_and_close():
        try:
            tab_width = int(tab_var.get())
            if tab_width < 1 or tab_width > 16:
                raise ValueError
        except ValueError:
            messagebox.showerror(t("paths.tab_invalid_title"), t("paths.tab_invalid"), parent=win)
            return

        config.set("plic_path", plic_var.get())
        config.set("lib_path", lib_var.get())
        config.set("gcc_path", gcc_var.get())
        config.set("tab_width", tab_width)
        try:
            config.save()
        except Exception as e:
            messagebox.showerror(t("paths.save_error_title"), t("paths.save_error", error=e), parent=win)
            return
        win.destroy()
        if on_saved:
            on_saved()

    tk.Button(
        win, text=t("paths.save"), command=save_and_close,
        bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
    ).grid(row=4, column=0, columnspan=3, pady=20)
