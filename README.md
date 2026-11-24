# chess-me

Revisione delle tue partite a scacchi nel terminale. Dai un link di Lichess / chess.com o un PGN: la partita viene analizzata in locale con Stockfish e la rivedi in una TUI a colori, con classificazione delle mosse, accuratezza, commenti argomentati in italiano, varianti migliori e confutazioni, e un **riassunto finale** con i momenti critici e i consigli. Nulla viene salvato: l'analisi resta in memoria finché la TUI è aperta.

## Uso

```bash
chess-me -l https://lichess.org/abcd1234        # oppure chess.com/game/live/… o /daily/…
chess-me -pgn partita.pgn                        # file .pgn
chess-me -pgn '1. e4 e5 2. Nf3 Nc6 …'            # PGN incollato
pbpaste | chess-me -pgn -                        # PGN da stdin
chess-me -pgn partita.pgn --color black --depth 18 --llm
```

| Opzione | Significato |
|---|---|
| `-l`, `--link` | link a una partita di lichess.org o chess.com |
| `-pgn`, `-p`, `--pgn` | file, testo PGN, oppure `-` per stdin |
| `-c`, `--color white\|black\|auto` | il tuo colore; con `auto` si ricava dal link Lichess o viene chiesto |
| `-d`, `--depth N` | profondità di Stockfish per posizione (default 16) |
| `-g`, `--game N` | PGN con più partite: analizza la N-esima (altrimenti si sceglie a schermo) |
| `--llm` | commenti e riassunto riscritti dall'LLM locale, verificati |

Altri comandi: `chess-me doctor` (dove sono Stockfish, aperture, llama-server, modello), `chess-me setup [--llm] [--yes]` (scarica ciò che manca, per l'installazione con pip/pipx), `chess-me remove-model`.

## La revisione

Si parte dalla posizione iniziale. A schermo: scacchiera (ultima mossa colorata secondo la classificazione, mossa migliore in verde), barra di valutazione, lista mosse con i simboli delle classi (`!!` `!` `★` `✓` `≡` `?!` `?` `✗` `??`), grafico dell'andamento con i momenti salienti, commento con valutazione prima/dopo, migliore e confutazione.

| Tasto | Azione |
|---|---|
| `←` `→` · `Home` `End` | mossa precedente / successiva · inizio / fine |
| `spazio` | riproduzione automatica (si ferma sui momenti salienti) |
| `n` / `N` | momento critico successivo / precedente |
| `b` / `r` | esplora la variante migliore / la confutazione (`Esc` per tornare) |
| `s` | riassunto: accuratezza, rating stimato, conteggi per classe, com'è andata, momenti critici (Invio per andarci), consigli |
| `l` | commenti template ↔ LLM (con `--llm`) |
| `f` · `c` | gira la scacchiera · cambia il tuo colore (ricalcola il riassunto) |
| `?` · `q` | aiuto · esci |

Link e PGN: Lichess usa l'API pubblica; per chess.com il link passa da un endpoint non ufficiale (`/callback/...`), se smette di funzionare basta incollare il PGN. Si leggono partite di scacchi standard, anche da posizione (FEN), non Chess960 o altre varianti.

## Installazione

Serve Python ≥ 3.12 (tranne per la cartella self-contained). Tre strade, dalla più semplice:

**`install.sh`** (dal sorgente, sceglie da solo pipx o pip e scarica Stockfish e aperture):

```bash
./install.sh            # pipx se c'è, altrimenti pip in un venv dedicato (~/.local/share/chess-me/venv)
./install.sh --llm      # in più llama-server (~17 MB) e il modello LLM (~1,1 GB)
./install.sh --uninstall [--purge]
```

Altre opzioni: `--pipx` / `--pip` per forzare il metodo, `--from <cartella|.whl|git+https://…>` per installare altro, `--no-setup` per non scaricare nulla (es. Stockfish già nel `PATH`), `--prefix`, `--bin-dir` (default `~/.local/bin`). `./install.sh --help` per tutto.

**pipx / pip** (a mano):

```bash
pipx install .                       # oppure: pipx install dist/chess_me-0.1.0-py3-none-any.whl
pip install .                        # in un venv a tua scelta
chess-me setup                       # scarica Stockfish (~115 MB) e il database delle aperture
chess-me setup --llm                 # in più llama-server e il modello
chess-me doctor
```

`chess-me setup` scarica Stockfish sf_18 e llama.cpp b12359 dalle release ufficiali su GitHub in `~/.local/share/chess-me`, verificandone lo SHA256 ([`src/chess_me/data/binaries.toml`](src/chess_me/data/binaries.toml): macOS arm64 e Linux x86_64). Se Stockfish è già nel `PATH` (es. `brew install stockfish`) viene usato quello. La wheel costruita con `packaging/wheel.sh` contiene già il database delle aperture. Aggiornare: rilancia `./install.sh` (o `pipx install --force .`); disinstallare: `./install.sh --uninstall` (o `pipx uninstall chess-me`), `--purge` per eliminare anche binari e modello.

**Cartella self-contained** (macOS arm64, Linux x86_64, niente Python richiesto): l'archivio `chess-me-<ver>-<os>-<arch>.tar.gz` contiene l'eseguibile con Python e librerie (`_internal/`), Stockfish e llama-server (`bin/`) e il database delle aperture (`share/`). Lo stesso `install.sh` la riconosce e la copia in `~/.local/share/chess-me/app`:

```bash
tar xzf chess-me-0.1.0-macos-arm64.tar.gz && ./chess-me/install.sh
```

Su macOS i binari non sono firmati: `install.sh` toglie la quarantena dalla cartella installata.

Le risorse si cercano in quest'ordine: variabile d'ambiente (`STOCKFISH_PATH`, `LLM_SERVER_PATH`, `OPENINGS_DB`, `LLM_MODEL_PATH`) → cartella del bundle → `~/.local/share/chess-me` (o `$CHESSME_HOME`) → dati del pacchetto → `PATH`.

## LLM (opzionale)

Con `--llm` il modello **Qwen3 1.7B Q4_K_M** (Apache 2.0, ~1,1 GB) servito da `llama-server` riscrive in modo più discorsivo i commenti non banali (imprecisioni, errori, occasioni perse, ottime e brillanti) e il riassunto, in background mentre già navighi la partita. Il modello non è nel pacchetto: al primo uso chiede conferma e lo scarica da Hugging Face in `~/.local/share/chess-me/models`, con verifica SHA256.

Ogni testo dell'LLM viene scartato (e si mostra il template) se cita mosse, pezzi o concetti (vantaggio, matto, minaccia…) assenti dal testo originale, o se usa il nome di un'altra classe. I prompt sono in [`src/chess_me/data/prompts.toml`](src/chess_me/data/prompts.toml); per modificarli copialo in `~/.local/share/chess-me/prompts.toml`, che ha la precedenza.

## Parametri

| Variabile | Default | Significato |
|---|---|---|
| `ANALYSIS_THREADS` | CPU − 1 | thread di Stockfish |
| `ANALYSIS_HASH_MB` | 64 | hash di Stockfish |
| `ANALYSIS_MAX_TIME_S` | 0.4 | tempo massimo per posizione |
| `LLM_THREADS` | 4 | thread di llama-server |

Le soglie della classificazione sono in [`src/chess_me/review/params.py`](src/chess_me/review/params.py).

## Sviluppo

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
chess-me -pgn partita.pgn               # oppure: python -m chess_me -pgn partita.pgn
pytest                                  # i test col motore si saltano se manca Stockfish
```

Test completi (con Stockfish compilato nel container):

```bash
docker build --target test -t chessme-test . && docker run --rm chessme-test
```

Pacchetti (`packaging/`, output in `dist/`):

```bash
packaging/wheel.sh                                                        # wheel + sdist per pip/pipx, aperture incluse
packaging/bundle.sh                                                       # cartella self-contained + tar.gz per la macchina corrente
docker build --platform linux/amd64 --target cli-export --output dist/ .  # cartella self-contained per Linux x86_64
```

## Struttura

```
install.sh             installazione unica: sorgente/wheel (pipx o pip) oppure cartella self-contained
pyproject.toml         pacchetto chess-me, comando `chess-me`, extra [dev] e [bundle]
src/chess_me/
  cli.py               argomenti e comandi (doctor, setup, remove-model)
  runtime.py           dove stanno Stockfish, llama-server, aperture, modello
  downloads.py         download verificati di `chess-me setup`
  session.py           partita in memoria: caricamento, analisi, riassunto
  pgn.py · sources.py  parsing PGN · download da Lichess / chess.com
  engine.py            processo Stockfish
  openings.py          riconoscimento delle aperture (+ build_openings.py che genera il database)
  review/              pipeline di analisi, classificazione (expected points), accuratezza, sacrifici
  explain/             fatti verificabili (linee del motore, motivi tattici) → commenti e riassunto in italiano
  llm/                 llama-server, download del modello, riscrittura verificata, job in background
  tui/                 interfaccia Textual (scacchiera, pannelli, schermate, colori)
  data/                prompts.toml, binaries.toml (+ openings.sqlite se generato)
tests/
packaging/             bundle PyInstaller (bundle.sh, chess-me.spec), wheel.sh, README del bundle
Dockerfile             test e bundle Linux
```
