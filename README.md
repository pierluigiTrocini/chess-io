# chess-io

Revisione delle tue partite a scacchi nel terminale. Dai un link di Lichess / chess.com o un PGN: la partita viene analizzata in locale con Stockfish e la rivedi in una TUI a colori, con classificazione delle mosse, accuratezza, commenti argomentati, varianti migliori e confutazioni, e un **riassunto finale** con i momenti critici e i consigli (in breve anche sotto la scacchiera). Interfaccia, commenti e riassunto sono in **italiano, inglese o spagnolo** (vedi [Lingua](#lingua)). Nulla viene salvato: l'analisi resta in memoria finché la TUI è aperta.

## Uso

```bash
chess-io                                         # ricerca: piattaforma + nome utente → elenco partite
chess-io -l https://lichess.org/abcd1234        # oppure chess.com/game/live/… o /daily/…
chess-io -u lichess nome_utente                  # scegli tra le sue ultime 50 partite
chess-io -u chess.com nome_utente
chess-io -pgn partita.pgn                        # file .pgn
chess-io -pgn '1. e4 e5 2. Nf3 Nc6 …'            # PGN incollato
pbpaste | chess-io -pgn -                        # PGN da stdin
chess-io -pgn partita.pgn --color black --depth 18 --llm
chess-io --lang en -u lichess nome_utente        # in inglese, solo per questa volta
```

| Opzione | Significato |
|---|---|
| `-l`, `--link` | link a una partita di lichess.org o chess.com |
| `-u`, `--user PIATTAFORMA UTENTE` | elenco interattivo delle ultime 50 partite dell'utente (`lichess` o `chess.com`): si sceglie quella da analizzare; il colore si ricava dal nome |
| `-pgn`, `-p`, `--pgn` | file, testo PGN, oppure `-` per stdin |
| `-c`, `--color white\|black\|auto` | il tuo colore; con `auto` si ricava dal link Lichess o viene chiesto |
| `-d`, `--depth N` | profondità di Stockfish per posizione (default 16) |
| `-g`, `--game N` | PGN con più partite: analizza la N-esima (altrimenti si sceglie a schermo) |
| `--llm` | commenti e riassunto riscritti dall'LLM locale, verificati |
| `--lang it\|en\|es` | lingua di interfaccia e commenti solo per questa esecuzione (anche l'aiuto `-h`) |

Altri comandi: `chess-io doctor` (dove sono Stockfish, aperture, llama-server, modello, e la lingua), `chess-io setup [--llm] [--yes]` (scarica ciò che manca, per l'installazione con pip/pipx), `chess-io remove-model`, `chess-io lang [it|en|es]` (mostra o imposta la lingua predefinita).

## Lingua

Tre lingue: italiano (`it`, predefinita), inglese (`en`), spagnolo (`es`). Valgono per tutto: interfaccia, messaggi, commenti alle mosse, riassunto e, con `--llm`, i testi riscritti dal modello (ogni lingua ha i suoi prompt e il suo vocabolario per il controllo anti-allucinazioni). Le mosse restano in notazione inglese (Nf3, Qxf7#).

La lingua si sceglie:

- **all'installazione**: è la prima schermata di `./install.sh` (oppure `./install.sh --lang en`); da lì in avanti anche l'installer parla quella lingua;
- **prima di cercare la partita**: nella schermata di ricerca (`chess-io` senza opzioni) c'è il selettore della lingua, F2 la cambia al volo; la scelta diventa la nuova predefinita;
- da riga di comando: `chess-io lang es` la imposta come predefinita, `chess-io --lang es …` la usa solo per quella volta.

Ordine di precedenza: `--lang` → variabile `CHESSIO_LANG` → impostazione salvata (`~/.local/share/chess-io/settings.json`) → italiano. I commenti si scrivono al momento dell'analisi, quindi la lingua va scelta prima di aprire la partita.

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

Link e PGN: Lichess usa l'API pubblica (con `-u`, `/api/games/user`, solo varianti standard); chess.com con `-u` legge gli archivi mensili pubblici (`api.chess.com/pub`); per chess.com il link passa da un endpoint non ufficiale (`/callback/...`), se smette di funzionare basta incollare il PGN. Si leggono partite di scacchi standard, anche da posizione (FEN), non Chess960 o altre varianti.

## Installazione

Serve Python ≥ 3.12 (tranne per la cartella self-contained). Tre strade, dalla più semplice:

**`install.sh`**: installer interattivo da terminale, con menu a tutto schermo come la ricerca delle partite (↑/↓ per muoversi, Spazio per spuntare, Invio per confermare, Esc per tornare indietro, q per uscire). La prima schermata chiede la lingua predefinita (italiano, English, español), che vale anche per il resto dell'installer. Mostra cosa è già presente e cosa manca, ti fa scegliere i componenti (Stockfish, database delle aperture, LLM locale: llama-server + modello) con le dimensioni dei download, il metodo (pipx o venv dedicato) e controlla lo spazio su disco. Durante l'installazione mostra il passo corrente sul totale e, per ogni download, una barra con percentuale, velocità ed ETA; gli archivi sono verificati con SHA256 e un download interrotto riprende da dove si era fermato. Se chess-io è già installato propone di aggiornarlo o disinstallarlo.

```bash
./install.sh                    # menu interattivo
./install.sh --yes              # senza domande: chess-io + Stockfish + aperture
./install.sh --yes --llm        # in più llama-server (~17 MB) e il modello LLM (~1,1 GB)
./install.sh --yes --lang en    # lingua predefinita inglese (senza --lang: quella salvata o del sistema)
./install.sh --uninstall [--purge]
```

Altre opzioni: `--pipx` / `--pip` per forzare il metodo, `--from <cartella|.whl|git+https://…>` per installare altro, `--no-setup` per non scaricare nulla (es. Stockfish già nel `PATH`), `--prefix`, `--bin-dir` (default `~/.local/bin`). `./install.sh --help` per tutto.

**pipx / pip** (a mano):

```bash
pipx install .                       # oppure: pipx install dist/chess_io-0.1.0-py3-none-any.whl
pip install .                        # in un venv a tua scelta
chess-io setup                       # scarica Stockfish (~115 MB) e il database delle aperture
chess-io setup --llm                 # in più llama-server e il modello
chess-io doctor
```

`chess-io setup` scarica Stockfish sf_18 e llama.cpp b12359 dalle release ufficiali su GitHub in `~/.local/share/chess-io`, verificandone lo SHA256 ([`src/chess_io/data/binaries.toml`](src/chess_io/data/binaries.toml): macOS arm64 e Linux x86_64). Se Stockfish è già nel `PATH` (es. `brew install stockfish`) viene usato quello. La wheel costruita con `packaging/wheel.sh` contiene già il database delle aperture. Aggiornare: rilancia `./install.sh` (o `pipx install --force .`); disinstallare: `./install.sh --uninstall` (o `pipx uninstall chess-io`), `--purge` per eliminare anche binari e modello.

**Cartella self-contained** (macOS arm64, Linux x86_64, niente Python richiesto): l'archivio `chess-io-<ver>-<os>-<arch>.tar.gz` contiene l'eseguibile con Python e librerie (`_internal/`), Stockfish e llama-server (`bin/`) e il database delle aperture (`share/`). Lo stesso `install.sh` la riconosce e la copia in `~/.local/share/chess-io/app`:

```bash
tar xzf chess-io-0.1.0-macos-arm64.tar.gz && ./chess-io/install.sh
```

Su macOS i binari non sono firmati: `install.sh` toglie la quarantena dalla cartella installata.

Le risorse si cercano in quest'ordine: variabile d'ambiente (`STOCKFISH_PATH`, `LLM_SERVER_PATH`, `OPENINGS_DB`, `LLM_MODEL_PATH`) → cartella del bundle → `~/.local/share/chess-io` (o `$CHESSIO_HOME`) → dati del pacchetto → `PATH`.

## LLM (opzionale)

Con `--llm` il modello **Qwen3 1.7B Q4_K_M** (Apache 2.0, ~1,1 GB) servito da `llama-server` riscrive in modo più discorsivo i commenti non banali (imprecisioni, errori, occasioni perse, ottime e brillanti) e il riassunto, in background mentre già navighi la partita. Il modello non è nel pacchetto: al primo uso chiede conferma e lo scarica da Hugging Face in `~/.local/share/chess-io/models`, con verifica SHA256.

Ogni testo dell'LLM viene scartato (e si mostra il template) se cita mosse, pezzi o concetti (vantaggio, matto, minaccia…) assenti dal testo originale, o se usa il nome di un'altra classe. I prompt sono in [`src/chess_io/data/prompts.toml`](src/chess_io/data/prompts.toml) (italiano), [`prompts.en.toml`](src/chess_io/data/prompts.en.toml) e [`prompts.es.toml`](src/chess_io/data/prompts.es.toml); per modificarne uno copialo in `~/.local/share/chess-io/` con lo stesso nome, che ha la precedenza. Il vocabolario del controllo (pezzi, concetti, termini delle classi) è in `VOCAB` in [`src/chess_io/llm/humanize.py`](src/chess_io/llm/humanize.py).

## Parametri

| Variabile | Default | Significato |
|---|---|---|
| `ANALYSIS_THREADS` | CPU − 1 | thread di Stockfish |
| `ANALYSIS_HASH_MB` | 64 | hash di Stockfish |
| `ANALYSIS_MAX_TIME_S` | 0.4 | tempo massimo per posizione |
| `LLM_THREADS` | 4 | thread di llama-server |

Le soglie della classificazione sono in [`src/chess_io/review/params.py`](src/chess_io/review/params.py).

## Sviluppo

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
chess-io -pgn partita.pgn               # oppure: python -m chess_io -pgn partita.pgn
pytest                                  # i test col motore si saltano se manca Stockfish
```

Testi nuovi: scrivili in italiano dentro `tr("…")` (segnaposto alla `str.format`, `_ctx=` se in un'altra lingua lo stesso testo si traduce in due modi) e aggiungi la traduzione in [`locales/en.py`](src/chess_io/locales/en.py) e [`locales/es.py`](src/chess_io/locales/es.py): `tests/test_i18n.py` fallisce se ne manca una o se i segnaposto non coincidono.

Test completi (con Stockfish compilato nel container):

```bash
docker build --target test -t chessio-test . && docker run --rm chessio-test
```

Pacchetti (`packaging/`, output in `dist/`):

```bash
packaging/wheel.sh                                                        # wheel + sdist per pip/pipx, aperture incluse
packaging/bundle.sh                                                       # cartella self-contained + tar.gz per la macchina corrente
docker build --platform linux/amd64 --target cli-export --output dist/ .  # cartella self-contained per Linux x86_64
```

## Struttura

```
install.sh             installer interattivo: sorgente/wheel (pipx o pip) oppure cartella self-contained
pyproject.toml         pacchetto chess-io, comando `chess-io`, extra [dev] e [bundle]
src/chess_io/
  cli.py               argomenti e comandi (doctor, setup, remove-model)
  runtime.py           dove stanno Stockfish, llama-server, aperture, modello
  downloads.py         download verificati di `chess-io setup`
  session.py           partita in memoria: caricamento, analisi, riassunto
  pgn.py · sources.py  parsing PGN · download da Lichess / chess.com
  engine.py            processo Stockfish
  openings.py          riconoscimento delle aperture (+ build_openings.py che genera il database)
  review/              pipeline di analisi, classificazione (expected points), accuratezza, sacrifici
  i18n.py · locales/   lingua corrente, tr(), pezzi per lingua · cataloghi en.py ed es.py (chiave = testo italiano)
  explain/             fatti verificabili (linee del motore, motivi tattici) → commenti e riassunto nella lingua scelta
  llm/                 llama-server, download del modello, riscrittura verificata, job in background
  tui/                 interfaccia Textual (scacchiera, pannelli, schermate, colori)
  data/                prompts.toml (+ .en, .es), binaries.toml (+ openings.sqlite se generato)
tests/
packaging/             bundle PyInstaller (bundle.sh, chess-io.spec), wheel.sh, README del bundle
Dockerfile             test e bundle Linux
```
