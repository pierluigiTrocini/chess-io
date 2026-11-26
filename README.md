# chess-io

Review your chess games in the terminal. Give it a Lichess / chess.com link or a PGN: the game is analysed locally with Stockfish and you review it in a colour TUI, with move classification, accuracy, reasoned comments, best lines and refutations, and a **final summary** with the critical moments and advice (also shown briefly under the board). Interface, comments and summary are available in **Italian, English or Spanish**. Nothing is saved: the analysis stays in memory while the TUI is open.

## Installation

Requires Python ≥ 3.12 (except for the self-contained folder). Three ways, from the simplest:

**`install.sh`**: an interactive terminal installer with full-screen menus (↑/↓ to move, Space to tick, Enter to confirm, Esc to go back, q to quit). The first screen asks for the default language (Italiano, English, español), which the rest of the installer also uses. It shows what is already present and what is missing, lets you pick the components (Stockfish, openings database, local LLM: llama-server + model) with their download sizes and the method (pipx or a dedicated venv), and checks disk space. During installation it shows the current step out of the total and, for each download, a bar with percentage, speed and ETA; archives are verified with SHA256 and an interrupted download resumes where it stopped. If chess-io is already installed it offers to update or uninstall it.

```bash
./install.sh                    # interactive menu
./install.sh --yes              # no questions: chess-io + Stockfish + openings
./install.sh --yes --llm        # plus llama-server (~17 MB) and the LLM model (~1.1 GB)
./install.sh --yes --llm-url http://localhost:11434/v1 --llm-model qwen3:4b   # or use your own LLM, nothing to download
./install.sh --yes --lang en    # English as default language (without --lang: the saved one or the system's)
./install.sh --uninstall [--purge]
```

Other options: `--pipx` / `--pip` to force the method, `--from <folder|.whl|git+https://…>` to install something else, `--no-setup` to download nothing (e.g. Stockfish already on `PATH`), `--prefix`, `--bin-dir` (default `~/.local/bin`). Run `./install.sh --help` for the full list.

**pipx / pip** (by hand):

```bash
pipx install .                       # or: pipx install dist/chess_io-0.1.0-py3-none-any.whl
pip install .                        # in a venv of your choice
chess-io setup                       # downloads Stockfish (~115 MB) and the openings database
chess-io setup --llm                 # plus llama-server and the model
chess-io doctor
```

`chess-io setup` downloads Stockfish sf_18 and llama.cpp b12359 from the official GitHub releases into `~/.local/share/chess-io`, verifying their SHA256 ([`src/chess_io/data/binaries.toml`](src/chess_io/data/binaries.toml): macOS arm64 and Linux x86_64). If Stockfish is already on `PATH` (e.g. `brew install stockfish`) that one is used. The wheel built with `packaging/wheel.sh` already includes the openings database. To update: run `./install.sh` again (or `pipx install --force .`); to uninstall: `./install.sh --uninstall` (or `pipx uninstall chess-io`), with `--purge` to also delete binaries and model.

**Self-contained folder** (macOS arm64, Linux x86_64, no Python needed): the `chess-io-<ver>-<os>-<arch>.tar.gz` archive contains the executable with Python and its libraries (`_internal/`), Stockfish and llama-server (`bin/`) and the openings database (`share/`). The same `install.sh` recognises it and copies it to `~/.local/share/chess-io/app`:

```bash
tar xzf chess-io-0.1.0-macos-arm64.tar.gz && ./chess-io/install.sh
```

On macOS the binaries are not signed: `install.sh` removes the quarantine flag from the installed folder.

Resources are looked up in this order: environment variable (`STOCKFISH_PATH`, `LLM_SERVER_PATH`, `OPENINGS_DB`, `LLM_MODEL_PATH`) → bundle folder → `~/.local/share/chess-io` (or `$CHESSIO_HOME`) → package data → `PATH`.

## Usage

```bash
chess-io                                         # search: platform + username → list of games
chess-io -l https://lichess.org/abcd1234        # or chess.com/game/live/… or /daily/…
chess-io -u lichess username                     # pick one of their last 50 games
chess-io -u chess.com username
chess-io -pgn game.pgn                           # .pgn file
chess-io -pgn '1. e4 e5 2. Nf3 Nc6 …'            # pasted PGN
pbpaste | chess-io -pgn -                        # PGN from stdin
chess-io -pgn game.pgn --color black --depth 18 --llm
chess-io -pgn game.pgn --llm-url http://localhost:11434/v1 --llm-model qwen3:4b   # your own LLM, just this once
chess-io --lang en -u lichess username           # in English, just this once
```

| Option | Meaning |
|---|---|
| `-l`, `--link` | link to a lichess.org or chess.com game |
| `-u`, `--user PLATFORM USER` | interactive list of the user's last 50 games (`lichess` or `chess.com`): pick the one to analyse; your colour is taken from the name |
| `-pgn`, `-p`, `--pgn` | file, PGN text, or `-` for stdin |
| `-c`, `--color white\|black\|auto` | your colour; with `auto` it is taken from the Lichess link or asked |
| `-d`, `--depth N` | Stockfish depth per position (default 16) |
| `-g`, `--game N` | PGN with several games: analyse the Nth (otherwise you pick on screen) |
| `--llm` / `--no-llm` | comments and summary rewritten by the LLM (local Qwen3 or your own service), then verified; `--no-llm` turns off a saved choice for one run |
| `--llm-url URL`, `--llm-model NAME` | use this OpenAI-compatible service for this run only (implies `--llm`) |
| `--lang it\|en\|es` | interface and comment language for this run only (help `-h` included) |

Other commands: `chess-io doctor` (where Stockfish, openings, the LLM backend are, plus the language), `chess-io setup [--llm] [--yes]` (downloads what is missing, for pip/pipx installs), `chess-io remove-model`, `chess-io lang [it|en|es]` (shows or sets the default language), `chess-io llm [show|off|local|set|test]` (LLM settings, see below).

## Using your own LLM

Instead of downloading llama-server and Qwen3 1.7B you can point chess-io at any service with an **OpenAI-compatible API** (`<url>/chat/completions`): Ollama, LM Studio, vLLM, a llama.cpp server you already run, OpenAI, OpenRouter, Groq, Mistral and so on. Every rewritten comment goes through the same check as with the local model: if it mentions moves, pieces or ideas that are not in the original comment, it is discarded and the template comment is shown.

**Interactive:** press **F3** in the search screen (or **o** during the review) to open *LLM settings* and pick one of:

- **Off**: no LLM unless you start with `--llm` (local model).
- **Local**: llama-server + Qwen3 1.7B on your computer; the screen shows what is missing and downloads it with a progress bar (or deletes the model).
- **My own service**: base address, model name and an optional API key. *Test connection* lists the models the service offers (pick one from the list) and sends a tiny request. A remote address shows a warning, because the moves and comments of your games are sent there.

Saving takes effect immediately (the current review is rewritten with the new backend) and, unless you chose *Off*, the LLM is on by default from then on.

**From the command line** (same settings, handy for scripts):

```bash
chess-io llm                                                     # show the settings
chess-io llm set --url http://localhost:11434/v1 --model qwen3:4b  # Ollama
chess-io llm set --url https://openrouter.ai/api/v1 --model <model> --ask-key   # asks for the API key
chess-io llm test                                                # lists models and sends a test request
chess-io llm local                                               # back to llama-server + Qwen3
chess-io llm off
```

Where things are stored: mode, address and model in `~/.local/share/chess-io/settings.json`; the API key in `secrets.json` next to it, readable only by you (`0600`). Environment variables take precedence: `CHESSIO_LLM_URL`, `CHESSIO_LLM_MODEL`, `CHESSIO_LLM_API_KEY` (or `OPENAI_API_KEY`). `LLM_MAX_TOKENS_FACTOR` (default 4) gives "thinking" models more room for their answer and `LLM_TIMEOUT` (default 180 s) sets the per-request timeout. Rate limits (HTTP 429) and temporary errors are retried twice. The prompts in `prompts*.toml` were tuned for a small model; larger models usually do better with them.
