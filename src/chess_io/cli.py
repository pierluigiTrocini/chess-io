"""Entry point di `chess-io`.

    chess-io                      schermata di ricerca: piattaforma + nome utente → elenco partite
    chess-io -l <link>            partita da lichess.org o chess.com
    chess-io -pgn <file|PGN|->    PGN da file, incollato o da stdin
    chess-io -u <piattaforma> <utente>   scegli tra le ultime partite di un utente (lichess, chess.com)
    chess-io doctor               dove sono Stockfish, aperture, llama-server, modello
    chess-io setup [--llm]        scarica i binari (installazione con pip/pipx)
    chess-io remove-model         elimina il modello LLM scaricato
    chess-io lang [it|en|es]      mostra o imposta la lingua predefinita (anche --lang per una sola volta)
"""
import argparse
import asyncio
import sys

from . import __version__, i18n, runtime
from .i18n import tr

EXIT_INPUT = 2
COMMANDS = ("doctor", "setup", "remove-model", "lang")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="chess-io",
        description=tr("Analizza una partita con Stockfish e la rivedi nel terminale: mosse classificate, "
                       "commenti, varianti migliori e riassunto."),
        epilog=tr("Senza -l/-pgn/-u si apre la ricerca delle partite di un utente. Altri comandi: chess-io doctor · "
                  "chess-io setup [--llm] [--yes] · chess-io remove-model · chess-io lang [it|en|es]"),
    )
    src = p.add_mutually_exclusive_group()  # nessuna sorgente = schermata di ricerca
    src.add_argument("-l", "--link", metavar="LINK", help=tr("link a una partita di lichess.org o chess.com"))
    src.add_argument("-pgn", "-p", "--pgn", dest="pgn", metavar="PGN",
                     help=tr("file .pgn, testo PGN tra virgolette, oppure - per leggerlo da stdin"))
    src.add_argument("-u", "--user", nargs=2, metavar=(tr("PIATTAFORMA"), tr("UTENTE")),
                     help=tr("scegli tra le ultime partite di un utente: piattaforma lichess o chess.com"))
    p.add_argument("-c", "--color", choices=("white", "black", "auto"), default="auto",
                   help=tr("il tuo colore (default: auto, ricavato dal link o dall'utente, altrimenti chiesto)"))
    p.add_argument("-d", "--depth", type=int, default=None, metavar="N",
                   help=tr("profondità di Stockfish per posizione (default 16)"))
    p.add_argument("-g", "--game", type=int, default=None, metavar="N",
                   help=tr("se il PGN (o -u) contiene più partite, analizza la N-esima (default: scelta a schermo)"))
    p.add_argument("--llm", action="store_true", help=tr("commenti e riassunto riscritti dall'LLM locale (verificati)"))
    p.add_argument("--lang", choices=i18n.LANGS, default=None,
                   help=tr("lingua di interfaccia e commenti solo per questa volta (default: quella impostata con "
                           "chess-io lang, ora {lang})", lang=i18n.lang()))
    p.add_argument("--version", action="version", version=f"chess-io {__version__}")
    return p


def _err(msg: str) -> int:
    print(f"chess-io: {msg}", file=sys.stderr)
    return EXIT_INPUT


def _missing(res, llm: bool) -> str | None:
    if res.stockfish is None:
        return tr("Stockfish non trovato. Esegui 'chess-io setup' oppure installalo nel PATH.")
    if llm and res.llama_server is None:
        return tr("llama-server non trovato: esegui 'chess-io setup --llm' oppure avvia senza --llm.")
    return None


def doctor() -> int:
    res = runtime.resolve()
    ok_all = True
    for name, value, ok in res.describe():
        print(f"{'✓' if ok else '✗'} {name:<13} {value}")
        ok_all &= ok or name not in ("Stockfish",)
    print(f"✓ {tr('Lingua'):<13} {i18n.NAMES[i18n.lang()]} ({i18n.lang()})")
    return 0 if ok_all else 1


def setup(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="chess-io setup", description=tr(
        "Scarica le risorse mancanti in {path} (Stockfish, aperture; con --llm anche llama-server e modello).",
        path=runtime.data_home()))
    p.add_argument("--llm", action="store_true", help=tr("anche llama-server e il modello Qwen3 1.7B (~1,1 GB)"))
    p.add_argument("--yes", "-y", action="store_true", help=tr("non chiedere conferma"))
    a = p.parse_args(argv)
    res = runtime.resolve()
    todo = []
    if res.stockfish is None:
        todo.append(("Stockfish", "stockfish"))
    if res.openings is None:
        todo.append((tr("database delle aperture"), "openings"))
    if a.llm and res.llama_server is None:
        todo.append(("llama-server", "llama"))
    if a.llm and not res.model.is_file():
        todo.append((tr("modello LLM (1,1 GB)"), "model"))
    if not todo:
        print(tr("Tutto già presente."))
        return doctor()
    print(tr("Da scaricare in {path}: {items}", path=runtime.data_home(), items=", ".join(t[0] for t in todo)))
    if not a.yes and input(tr("Procedo? [s/N] ")).strip().lower() not in ("s", "si", "sì", "y", "yes"):
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
        print(tr("Eliminato {path}", path=res.model))
    else:
        print(tr("Nessun modello da eliminare."))
    return 0


def lang_cmd(argv: list[str]) -> int:
    """`chess-io lang` mostra la lingua predefinita, `chess-io lang en` la imposta."""
    p = argparse.ArgumentParser(prog="chess-io lang", description=tr(
        "Mostra o imposta la lingua predefinita di interfaccia e commenti."))
    p.add_argument("code", nargs="?", choices=i18n.LANGS, metavar="it|en|es",
                   help=" · ".join(f"{c} = {i18n.NAMES[c]}" for c in i18n.LANGS))
    a = p.parse_args(argv)
    if a.code is None:
        print(f"{i18n.lang()}  {i18n.NAMES[i18n.lang()]}")
        return 0
    if not i18n.save(a.code):
        return _err(tr("impossibile salvare l'impostazione in {path}", path=runtime.data_home()))
    i18n.set_lang(a.code)
    print(tr("Lingua predefinita: {name} ({code})", name=i18n.NAMES[a.code], code=a.code))
    return 0


def _lang_arg(argv: list[str]) -> str | None:
    """--lang letto prima del parser, così anche l'aiuto (-h) è nella lingua scelta."""
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--lang="):
            return a.split("=", 1)[1]
    return None


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    i18n.set_lang(i18n.resolve(_lang_arg(argv)))
    if argv and argv[0] in COMMANDS:
        cmd, rest = argv[0], argv[1:]
        if cmd == "lang":
            return lang_cmd(rest)
        return doctor() if cmd == "doctor" else setup(rest) if cmd == "setup" else remove_model()
    args = build_parser().parse_args(argv)
    if args.depth is not None and not 4 <= args.depth <= 30:
        return _err(tr("--depth va da 4 a 30"))

    res = runtime.bootstrap(depth=args.depth)
    # solo ora: config legge le variabili d'ambiente impostate da bootstrap()
    from . import config
    from . import session, sources
    from .tui.app import ChessIoApp

    color = None if args.color == "auto" else args.color
    if not (args.link or args.pgn or args.user):   # schermata di ricerca
        if err := _missing(res, args.llm):
            return _err(err)
        app = ChessIoApp(None, None, color, config.ANALYSIS_DEPTH, args.llm)
        app.run()
        return app.exit_code

    if args.user:
        try:
            sources.normalize_platform(args.user[0])
            sources.check_username(args.user[1])
        except sources.FetchError as e:
            return _err(str(e))
        print(tr("Scarico le ultime partite di {user}…", user=args.user[1]), file=sys.stderr)
    elif args.link:
        print(tr("Scarico la partita…"), file=sys.stderr)
    try:
        loaded = asyncio.run(session.load(link=args.link, pgn=args.pgn, user=args.user))
        candidate = session.pick(loaded, args.game)
    except session.InputError as e:
        return _err(str(e))
    if err := _missing(res, args.llm):
        return _err(err)
    app = ChessIoApp(loaded, candidate, color, config.ANALYSIS_DEPTH, args.llm)
    app.run()
    return app.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
