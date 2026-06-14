# PL/I IDE

A lightweight, cross-platform IDE for **PL/I**, built with Python and Tkinter.
It is designed around the [Iron Spring PL/I](http://www.iron-spring.com/)
compiler (`plic`) on Linux, linked with `gcc -m32`, and bundles an editor with
syntax highlighting, a static checker, a find-and-replace tool, an optional
AI assistant, and a fully translatable interface.

> No third-party Python packages required — everything runs on the standard
> library plus Tkinter.

## Features

- **Editor** with line numbers, PL/I syntax highlighting (~150 keywords plus a
  separate color category for builtin functions), auto-indentation and
  configurable tab width.
- **One-click compile & run**: compiles with `plic`, links with `gcc`, and runs
  either in an external terminal (for interactive `GET` input) or streamed live
  into the IDE output panel.
- **Static checker** that flags trailing whitespace and unbalanced brackets.
- **Clickable error messages**: line references in the output jump straight to
  the line in the editor and flash it.
- **Find & Replace** (Ctrl+F / Ctrl+H) with live match highlighting, optional
  case sensitivity, wrap-around search and "replace all" as a single undo step.
- **AI assistant** (F8) for debugging help and code generation, with selectable
  backends: local **Ollama**, the **Anthropic** API, or any **OpenAI-compatible**
  endpoint (OpenAI, Groq, Mistral, LM Studio, ...).
- **Multilingual UI**: language is chosen from the menu and switched live.
  Translations are plain JSON files, so adding a language needs no code changes.
- **Safe editing**: unsaved-changes warnings, a dirty-state marker in the title,
  and encoding-tolerant loading (UTF-8 with a Latin-1 fallback).

## Requirements

- Python 3.8+
- Tkinter (ships with most Python installs; on Debian/Ubuntu/Mint install via
  `sudo apt install python3-tk`)
- For compiling and running PL/I programs: the
  [Iron Spring PL/I](http://www.iron-spring.com/) compiler (`plic`) and `gcc`
  with 32-bit support (`gcc-multilib` on Debian-based systems)
- *(Optional)* For the AI assistant: a running [Ollama](https://ollama.com/)
  instance, or an API key for Anthropic / an OpenAI-compatible provider

The editor, checker, find-and-replace and AI assistant work without the PL/I
toolchain — you only need `plic`/`gcc` to compile and run.

## Installation

```bash
git clone https://github.com/ProfPlanloz/pli_ide.git
cd pli-ide
python3 main.py
```

That's it — there is nothing to build or install.

## Usage

1. Start the IDE with `python3 main.py`.
2. Open the **Settings -> Configure paths** dialog and point the IDE at your
   `plic` binary, the Iron Spring `lib` folder (the one containing `libprf.a`),
   and `gcc`. You can also set the tab width here.
3. Open a `.pli` file (Ctrl+O), edit it, and:
   - **F5** to compile & link
   - **F6** to run
   - **Ctrl+S** to save
   - **F8** to open the AI assistant

Output files (`.o` and the executable) are written next to the source file.
Use the *Run in external terminal* checkbox to toggle between an external
terminal window and live output inside the IDE.

### AI assistant

Open **AI -> Configure AI** and pick a backend:

| Provider    | API key | Notes                                                       |
| ----------- | ------- | ----------------------------------------------------------- |
| `ollama`    | no      | Local. Default model `llama3.2`; run `ollama pull <model>`. |
| `anthropic` | yes     | Claude via the Anthropic API.                               |
| `openai`    | varies  | OpenAI and any OpenAI-compatible server, set via base URL.  |

The assistant can include your current editor code and the latest output/error
messages in the request (toggleable). **AI -> Debug code & errors** does both in
one step. Code blocks from the answer can be inserted at the cursor.

> **Warning:** The API key is stored **unencrypted** in `pli_ide_config.json`.
> That file is git-ignored by default — do not commit it.

## Languages

The UI language is selected from the **Language** menu and applied immediately
(the window rebuilds while your code and output are preserved); the choice is
remembered across restarts.

Bundled languages: **English** (`en`, default), **German** (`de`), **Spanish**
(`es`), **French** (`fr`), **Japanese** (`jp`), **Korean** (`kr`), **Polish**
(`pl`), **Portuguese** (`pt`), **Romanian** (`ro`), **Russian** (`ru`) and
**Thai** (`th`).

### Adding a language

Each language is a single JSON file in the `lang/` folder mapping string keys
to translations. To add one:

1. Copy `lang/en.json` to `lang/<code>.json` (e.g. `lang/fr.json`).
2. Set the special key `"_language_name"` to the name shown in the menu
   (e.g. `"Francais"`).
3. Translate the values, leaving the keys and any `{placeholders}` unchanged.
4. Restart the IDE — the language appears in the menu automatically.

Missing keys fall back to English, so partial translations work fine.
Contributions of new languages are welcome via pull request.

## Project structure

```
pli-ide/
├── main.py              # Entry point
├── app.py               # Main application: menu, shortcuts, wiring
├── editor.py            # Editor widget: line numbers, indenting, dirty tracking
├── syntax.py            # PL/I syntax highlighting
├── checker.py           # Static checks (GUI-independent)
├── build.py             # Compile (plic + gcc) and run
├── config.py            # Configuration (JSON, next to the script)
├── fileio.py            # Encoding-tolerant file I/O
├── settings_dialog.py   # Paths & tab-width dialog
├── search_dialog.py     # Find & Replace
├── ai_client.py         # AI backends (stdlib only)
├── ai_dialog.py         # AI assistant window + AI settings
├── i18n.py              # Translation loader
└── lang/                # One <code>.json per UI language
    ├── en.json          # English        ├── pt.json   # Portuguese
    ├── de.json          # German         ├── ro.json   # Romanian
    ├── es.json          # Spanish        ├── ru.json   # Russian
    ├── fr.json          # French         ├── th.json   # Thai
    ├── jp.json          # Japanese       ├── kr.json   # Korean
    └── pl.json          # Polish
```

The non-GUI modules (`checker.py`, `build.py`, `config.py`, `fileio.py`,
`ai_client.py`) have no Tkinter dependencies and can be tested in isolation.

## Configuration file

Settings are stored in `pli_ide_config.json` next to the script: tool paths,
tab width, run mode, UI language and AI settings (including the API key). The
file is created on first save and is intentionally listed in `.gitignore`.

## Contributing

Issues and pull requests are welcome — especially new language files and
additional PL/I keywords/builtins for the highlighter (in `syntax.py`). Please
keep the non-GUI modules free of Tkinter imports so they stay testable.

## License

This project is licensed under the **GNU General Public License v3.0**.
See the [LICENSE](LICENSE) file for the full text.

## Acknowledgements

Built for use with the [Iron Spring PL/I](http://www.iron-spring.com/)
compiler. PL/I is a registered trademark of its respective owners; this project
is an independent tool and is not affiliated with or endorsed by them.
