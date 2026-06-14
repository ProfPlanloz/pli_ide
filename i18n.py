"""Lightweight internationalization (i18n).

Language files are plain JSON dictionaries living in the ``lang/`` folder
next to the application (one file per language, e.g. ``en.json``, ``de.json``).
Each file maps string keys to translated text and may contain the special
key ``"_language_name"`` holding the human-readable name shown in menus.

Adding a new language is as simple as dropping another ``<code>.json`` file
into the ``lang/`` folder — it is picked up automatically on the next start.
"""

import json
import os

LANG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang")
DEFAULT_LANGUAGE = "en"
NAME_KEY = "_language_name"


class Translator:
    """Holds the active language and resolves translation keys."""

    def __init__(self, lang_dir=LANG_DIR):
        self.lang_dir = lang_dir
        self._strings = {}        # active language
        self._fallback = {}       # English, used when a key is missing
        self.current = DEFAULT_LANGUAGE
        self._fallback = self._load_file(DEFAULT_LANGUAGE)
        self.set_language(DEFAULT_LANGUAGE)

    # ----------------------------------------------------------- discovery

    def available_languages(self):
        """Return ``{code: display_name}`` for every JSON file in the folder."""
        result = {}
        if os.path.isdir(self.lang_dir):
            for filename in sorted(os.listdir(self.lang_dir)):
                if not filename.endswith(".json"):
                    continue
                code = filename[:-5]
                data = self._load_file(code)
                result[code] = data.get(NAME_KEY, code)
        # Guarantee at least English so the UI is never empty
        result.setdefault(DEFAULT_LANGUAGE, "English")
        return result

    # ------------------------------------------------------------- loading

    def _load_file(self, code):
        path = os.path.join(self.lang_dir, f"{code}.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def set_language(self, code):
        """Switch the active language. Falls back to English if unknown."""
        data = self._load_file(code)
        if data:
            self.current = code
            self._strings = data
        else:
            self.current = DEFAULT_LANGUAGE
            self._strings = self._fallback
        return self.current

    # --------------------------------------------------------- translation

    def t(self, key, **kwargs):
        """Translate ``key``. Missing keys fall back to English, then to the
        key itself. ``kwargs`` are substituted via ``str.format``."""
        text = self._strings.get(key)
        if text is None:
            text = self._fallback.get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
        return text


# Shared module-level instance + convenience wrapper
_translator = Translator()


def t(key, **kwargs):
    return _translator.t(key, **kwargs)


def set_language(code):
    return _translator.set_language(code)


def available_languages():
    return _translator.available_languages()


def current_language():
    return _translator.current
