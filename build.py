"""Compiling (Iron Spring plic + gcc) and running in an external terminal.

Completely GUI-independent: messages go through an output callback
(output(message, is_error)) implemented thread-safely in the app.
"""

import os
import platform
import shutil
import subprocess

from i18n import t


class Builder:
    def __init__(self, config, output, output_plain=None):
        """
        config:       Config object with plic_path, lib_path, gcc_path
        output:       Callable(message: str, is_error: bool) — status messages
        output_plain: Callable(message: str) — raw program output without prefix
        """
        self.config = config
        self.output = output
        self.output_plain = output_plain or (lambda msg: output(msg, False))

    @staticmethod
    def _resolve_exe(path):
        """Let bare program names ('gcc') be resolved via PATH; make anything
        with a path component ('./plic') absolute, so a changed working
        directory (cwd) of the subprocesses cannot break things."""
        if os.path.basename(path) == path:
            return path
        return os.path.abspath(path)

    def compile(self, source_path):
        """Compile and link the source file.

        Returns the absolute path to the produced executable, or None on error.

        Output files (.o / executable) always land in the directory of the
        source file — not in the (arbitrary) working directory the IDE was
        started from.
        """
        source_path = os.path.abspath(source_path)
        src_dir = os.path.dirname(source_path)
        base_name = os.path.splitext(os.path.basename(source_path))[0]
        o_file = os.path.join(src_dir, base_name + ".o")
        exe_file = os.path.join(src_dir, base_name)

        plic_exe = self._resolve_exe(self.config.get("plic_path"))
        gcc_exe = self._resolve_exe(self.config.get("gcc_path"))
        lib_dir = os.path.abspath(self.config.get("lib_path"))

        self.output("\n" + "=" * 50, False)
        self.output(t("compile.header", path=source_path), False)

        # Step 1: compile with plic
        plic_cmd = [plic_exe, source_path, "-o", o_file]
        self.output("\n" + t("compile.step1", cmd=" ".join(plic_cmd)), False)
        try:
            result_plic = subprocess.run(plic_cmd, capture_output=True, text=True, cwd=src_dir)
        except FileNotFoundError:
            self.output(t("compile.not_found", exe=plic_exe), True)
            return None

        if result_plic.returncode != 0:
            self.output(t("compile.plic_error", code=result_plic.returncode), True)
            if result_plic.stdout:
                self.output(result_plic.stdout.strip(), True)
            if result_plic.stderr:
                self.output(result_plic.stderr.strip(), True)
            return None

        self.output(t("compile.plic_ok"), False)

        # Check early whether the Iron Spring library is really there
        if not os.path.isfile(os.path.join(lib_dir, "libprf.a")):
            self.output(t("compile.lib_not_found", dir=lib_dir), True)
            return None

        # Step 2: link with gcc
        gcc_cmd = [
            gcc_exe, "-m32", o_file, f"-L{lib_dir}", "-lprf", "-no-pie",
            "-Wl,--allow-multiple-definition", "-o", exe_file, "-lpthread",
        ]
        self.output("\n" + t("compile.step2", cmd=" ".join(gcc_cmd)), False)
        try:
            result_gcc = subprocess.run(gcc_cmd, capture_output=True, text=True, cwd=src_dir)
        except FileNotFoundError:
            self.output(t("compile.not_found", exe=gcc_exe), True)
            return None

        if result_gcc.returncode != 0:
            self.output(t("compile.link_error", code=result_gcc.returncode), True)
            if result_gcc.stdout:
                self.output(result_gcc.stdout.strip(), True)
            if result_gcc.stderr:
                self.output(result_gcc.stderr.strip(), True)
            return None

        self.output(t("compile.linked_ok", exe=exe_file), False)
        return exe_file

    def run_captured(self, exe_path):
        """Run the executable and stream its output live into the IDE output
        panel. stdin is closed — interactive programs (GET) get EOF instead
        of hanging."""
        abs_exe_path = os.path.abspath(exe_path)
        work_dir = os.path.dirname(abs_exe_path)

        self.output("\n" + t("run.captured_header", exe=abs_exe_path), False)
        self.output(t("run.captured_no_input"), False)

        proc = subprocess.Popen(
            [abs_exe_path],
            cwd=work_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,  # line-buffered so output appears live
        )
        for line in proc.stdout:
            self.output_plain(line.rstrip("\n"))
        proc.stdout.close()
        returncode = proc.wait()

        self.output(t("run.finished", code=returncode), returncode != 0)

    def run_in_terminal(self, exe_path):
        """Launch the executable in an external terminal window."""
        abs_exe_path = os.path.abspath(exe_path)
        work_dir = os.path.dirname(abs_exe_path)

        self.output("\n" + t("run.terminal_header", exe=abs_exe_path), False)

        system = platform.system()
        exit_label = t("run.exit_label")

        if system == "Windows":
            subprocess.Popen(
                ["cmd.exe", "/c", f'start cmd /k "{abs_exe_path}"'], cwd=work_dir
            )

        elif system == "Linux":
            bash_command = f'"{abs_exe_path}"; echo ""; echo "{exit_label}"; read'
            if shutil.which("gnome-terminal"):
                subprocess.Popen(["gnome-terminal", "--", "bash", "-c", bash_command], cwd=work_dir)
            elif shutil.which("xterm"):
                subprocess.Popen(["xterm", "-e", "bash", "-c", bash_command], cwd=work_dir)
            elif shutil.which("konsole"):
                subprocess.Popen(["konsole", "-e", "bash", "-c", bash_command], cwd=work_dir)
            else:
                self.output(t("run.no_terminal"), True)
                return

        elif system == "Darwin":  # macOS
            bash_command = f'clear; cd \\"{work_dir}\\"; \\"{abs_exe_path}\\"; echo; echo done'
            osascript_cmd = f'tell application "Terminal" to do script "{bash_command}"'
            subprocess.Popen(["osascript", "-e", osascript_cmd])

        else:
            self.output(t("run.unknown_os", system=system), True)
            subprocess.Popen([abs_exe_path], cwd=work_dir)

        self.output(t("run.in_separate_window"), False)
        self.output(t("run.can_input"), False)
