"""Loading and saving the IDE configuration (paths to plic, lib, gcc)."""

import json
import os


class Config:
    """Manages the settings in a JSON file.

    The configuration file always lives next to the script, not in the
    current working directory, so the IDE finds its settings regardless
    of where it is started from.
    """

    DEFAULTS = {
        "language": "en",        # UI language code (see lang/ folder)
        "plic_path": "./plic",
        "lib_path": "lib",
        "gcc_path": "gcc",
        "tab_width": 4,          # number of spaces per tab/indentation level
        "run_in_terminal": True, # True = external terminal, False = output in IDE window
        # AI assistant
        "ai_provider": "ollama",                  # ollama | anthropic | openai
        "ai_model": "llama3.2",
        "ai_api_key": "",                          # not needed for Ollama
        "ai_base_url": "http://localhost:11434",
    }

    def __init__(self, filename="pli_ide_config.json"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.path = os.path.join(base_dir, filename)
        self.data = self.DEFAULTS.copy()
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                stored = json.load(f)
            # update() instead of replace: new default keys are kept
            # when an older config file is loaded.
            self.data.update(stored)
        except Exception:
            # Broken file -> continue with defaults
            self.data = self.DEFAULTS.copy()

    def save(self):
        """Write the configuration. Raises on error so the caller can
        show a message."""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)

    def get(self, key):
        return self.data.get(key, self.DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
