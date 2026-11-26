"""Converte i TSV di lichess-org/chess-openings in una tabella SQLite.

    python -m chess_io.build_openings <dest.sqlite>            scarica i TSV e genera il database
    python -m chess_io.build_openings <cartella-tsv> <dest>    da TSV già scaricati

Per ogni linea si registrano tutte le posizioni intermedie (prefissi): una mossa è "di libro"
se la posizione risultante compare in una qualsiasi linea. Il nome è quello della linea più
lunga che termina esattamente in quella posizione (o, per i prefissi, il più corto che la contiene).
"""
import io
import sqlite3
import sys
from pathlib import Path

import chess
import chess.pgn


def main(src: str, dst: str) -> None:
    positions: dict[str, tuple[int, str, str]] = {}  # epd -> (priority, eco, name)
    for tsv in sorted(Path(src).glob("*.tsv")):
        for line in tsv.read_text(encoding="utf-8").splitlines()[1:]:
            if not line.strip():
                continue
            eco, name, pgn = line.split("\t")[:3]
            game = chess.pgn.read_game(io.StringIO(pgn))
            board = game.board()
            moves = list(game.mainline_moves())
            for i, mv in enumerate(moves):
                board.push(mv)
                epd = board.epd()
                exact = i == len(moves) - 1
                # le posizioni finali di una linea battono i prefissi
                prio = 1000 + len(moves) if exact else -len(moves)
                cur = positions.get(epd)
                if cur is None or prio > cur[0]:
                    positions[epd] = (prio, eco, name)
    Path(dst).unlink(missing_ok=True)
    conn = sqlite3.connect(dst)
    conn.execute("CREATE TABLE openings (epd TEXT PRIMARY KEY, eco TEXT, name TEXT, named INTEGER)")
    conn.executemany(
        "INSERT INTO openings VALUES (?,?,?,?)",
        [(epd, eco, name, int(prio >= 1000)) for epd, (prio, eco, name) in positions.items()],
    )
    conn.commit()
    conn.close()
    print(f"openings: {len(positions)} posizioni")


def download_and_build(dst: str) -> None:
    import tempfile

    from . import APP_NAME
    from .downloads import download, manifest
    o = manifest()["openings"]
    with tempfile.TemporaryDirectory(prefix=f"{APP_NAME}-op-") as tmp:
        for f in o["files"]:
            download(o["base"] + f, Path(tmp) / f, None, f"aperture {f}", lambda *_: None)
        main(tmp, dst)


if __name__ == "__main__":
    if len(sys.argv) == 2:
        download_and_build(sys.argv[1])
    elif len(sys.argv) == 3:
        main(sys.argv[1], sys.argv[2])
    else:
        sys.exit(__doc__)
