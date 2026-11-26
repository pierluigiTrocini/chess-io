chess-me — revisione delle partite a scacchi nel terminale
=========================================================

Installazione:   ./install.sh            (in ~/.local/share/chess-me/app, comando in ~/.local/bin)
Disinstallazione: ./install.sh --uninstall [--purge]
Con il modello LLM: ./install.sh --llm   (oppure scegli i componenti dal menu di ./install.sh)
Senza installare: ./chess-me -l <link>

Uso:
  chess-me -l https://lichess.org/abcd1234
  chess-me -pgn partita.pgn
  pbpaste | chess-me -pgn -
  chess-me -pgn partita.pgn --color black --depth 18 --llm
  chess-me doctor        controlla Stockfish, aperture, llama-server, modello
  chess-me lang en       lingua predefinita: it (italiano), en (English), es (español)
  chess-me --lang es …   un'altra lingua solo per questa volta

Lingua / Language / Idioma: ./install.sh --lang en  ·  chess-me lang es

La cartella contiene tutto: Python e librerie (_internal/), Stockfish e llama-server (bin/), il database
delle aperture (share/). Il modello LLM (~1,1 GB) si scarica solo al primo --llm, in
~/.local/share/chess-me/models (eliminabile con: chess-me remove-model).
Nessuna partita viene salvata: l'analisi resta in memoria finché la TUI è aperta.

Su macOS i binari non sono firmati: se il sistema li blocca, install.sh toglie la quarantena;
senza installare: xattr -dr com.apple.quarantine chess-me
