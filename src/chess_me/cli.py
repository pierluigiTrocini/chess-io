"""Entry point di `chess-me`.

    chess-me -l <link>            partita da lichess.org o chess.com
    chess-me -pgn <file|PGN|->    PGN da file, incollato o da stdin
    chess-me doctor               dove sono Stockfish, aperture, llama-server, modello
    chess-me setup [--llm]        scarica i binari (installazione con pip/pipx)
    chess-me remove-model         elimina il modello LLM scaricato
"""
import argparse
import asyncio
import sys

from . import __version__, runtime

EXIT_INPUT = 2
COMMANDS = ("doctor", "setup", "remove-model")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="chess-me",
        description="Analizza una partita con Stockfish e la rivedi nel terminale: mosse classificate, "
                    "commenti, varianti migliori e riassunto.",
        epilog="Altri comandi: chess-me doctor · chess-me setup [--llm] [--yes] · chess-me remove-model",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("-l", "--link", metavar="LINK", help="link a una partita di lichess.org o chess.com")
    src.add_argument("-pgn", "-p", "--pgn", dest="pgn", metavar="PGN",
                     help="file .pgn, testo PGN tra virgolette, oppure - per leggerlo da stdin")
    p.add_argument("-c", "--color", choices=("white", "black", "auto"), default="auto",
                   help="il tuo colore (default: auto, chiesto se non si ricava dal link)")
    p.add_argument("-d", "--depth", type=int, default=None, metavar="N",
                   help="profondità di Stockfish per posizione (default 16)")
    p.add_argument("-g", "--game", type=int, default=None, metavar="N",
                   help="se il PGN contiene più partite, analizza la N-esima (default: scelta a schermo)")
    p.add_argument("--llm", action="store_true", help="commenti e riassunto riscritti dall'LLM locale (verificati)")
    p.add_argument("--version", action="version", version=f"chess-me {__version__}")
    return p


def _err(msg: str) -> int:
    print(f"chess-me: {msg}", file=sys.stderr)
    return EXIT_INPUT


def doctor() -> int:
    res = runtime.resolve()
    ok_all = True
    for name, value, ok in res.describe():
        print(f"{'✓' if ok else '✗'} {name:<13} {value}")
        ok_all &= ok or name not in ("Stockfish",)
    return 0 if ok_all else 1


def setup(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="chess-me setup", description="Scarica le risorse mancanti in "
                                f"{runtime.data_home()} (Stockfish, aperture; con --llm anche llama-server e modello).")
    p.add_argument("--llm", action="store_true", help="anche llama-server e il modello Qwen3 1.7B (~1,1 GB)")
    p.add_argument("--yes", "-y", action="store_true", help="non chiedere conferma")
    a = p.parse_args(argv)
    res = runtime.resolve()
    todo = []
    if res.stockfish is None:
        todo.append(("Stockfish", "stockfish"))
    if res.openings is None:
        todo.append(("database delle aperture", "openings"))
    if a.llm and res.llama_server is None:
        todo.append(("llama-server", "llama"))
    if a.llm and not res.model.is_file():
        todo.append(("modello LLM (1,1 GB)", "model"))
    if not todo:
        print("Tutto già presente.")
        return doctor()
    print("Da scaricare in", runtime.data_home(), ":", ", ".join(t[0] for t in todo))
    if not a.yes and input("Procedo? [s/N] ").strip().lower() not in ("s", "si", "sì", "y", "yes"):
        return 1
    runtime.bootstrap()
    from . import downloads
    try:
        for label, kind in todo:
            print(f"→ {label}")
            if kind == "stockfish":
                downloads.install_stockfish()
            elif kind == "openings":
                downloads.install_openings()
            elif kind == "llama":
                downloads.install_llama()
            else:
                asyncio.run(downloads.install_model())
    except (downloads.SetupError, RuntimeError) as e:
        return _err(str(e))
    print()
    return doctor()


def remove_model() -> int:
    res = runtime.resolve()
    if res.model.is_file():
        res.model.unlink()
        print(f"Eliminato {res.model}")
    else:
        print("Nessun modello da eliminare.")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in COMMANDS:
        cmd, rest = argv[0], argv[1:]
        return doctor() if cmd == "doctor" else setup(rest) if cmd == "setup" else remove_model()
    args = build_parser().parse_args(argv)
    if args.depth is not None and not 4 <= args.depth <= 30:
        return _err("--depth va da 4 a 30")

    res = runtime.bootstrap(depth=args.depth)
    # solo ora: config legge le variabili d'ambiente impostate da bootstrap()
    from . import config
    from . import session
    from .tui.app import ChessMeApp

    if args.link:
        print("Scarico la partita…", file=sys.stderr)
    try:
        loaded = asyncio.run(session.load(link=args.link, pgn=args.pgn))
        candidate = session.pick(loaded, args.game)
    except session.InputError as e:
        return _err(str(e))
    if res.stockfish is None:
        return _err("Stockfish non trovato. Esegui 'chess-me setup' oppure installalo nel PATH.")
    if args.llm and res.llama_server is None:
        return _err("llama-server non trovato: esegui 'chess-me setup --llm' oppure avvia senza --llm.")
    color = None if args.color == "auto" else args.color
    app = ChessMeApp(loaded, candidate, color, config.ANALYSIS_DEPTH, args.llm)
    app.run()
    return app.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
