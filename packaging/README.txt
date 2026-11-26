chess-io — revisione delle partite a scacchi nel terminale
=========================================================

Installazione:   ./install.sh            (in ~/.local/share/chess-io/app, comando in ~/.local/bin)
Disinstallazione: ./install.sh --uninstall [--purge]
Con il modello LLM: ./install.sh --llm   (oppure scegli i componenti dal menu di ./install.sh)
Senza installare: ./chess-io -l <link>

Uso:
  chess-io -l https://lichess.org/abcd1234
  chess-io -pgn partita.pgn
  pbpaste | chess-io -pgn -
  chess-io -pgn partita.pgn --color black --depth 18 --llm
  chess-io doctor        controlla Stockfish, aperture, llama-server, modello
  chess-io lang en       lingua predefinita: it (italiano), en (English), es (español)
  chess-io --lang es …   un'altra lingua solo per questa volta

Lingua / Language / Idioma: ./install.sh --lang en  ·  chess-io lang es

La cartella contiene tutto: Python e librerie (_internal/), Stockfish e llama-server (bin/), il database
delle aperture (share/). Il modello LLM (~1,1 GB) si scarica solo al primo --llm, in
~/.local/share/chess-io/models (eliminabile con: chess-io remove-model).
Nessuna partita viene salvata: l'analisi resta in memoria finché la TUI è aperta.

Su macOS i binari non sono firmati: se il sistema li blocca, install.sh toglie la quarantena;
senza installare: xattr -dr com.apple.quarantine chess-io
