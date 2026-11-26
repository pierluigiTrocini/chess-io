import sqlite3
from functools import lru_cache

import chess

from . import config


@lru_cache(maxsize=1)
def _conn() -> sqlite3.Connection | None:
    if not config.OPENINGS_DB.exists():
        return None
    return sqlite3.connect(f"file:{config.OPENINGS_DB}?mode=ro", uri=True, check_same_thread=False)


def lookup(board: chess.Board) -> tuple[str, str, bool] | None:
    """(eco, nome, posizione con nome esatto) se la posizione è nel libro, altrimenti None."""
    conn = _conn()
    if conn is None:
        return None
    row = conn.execute("SELECT eco, name, named FROM openings WHERE epd = ?", (board.epd(),)).fetchone()
    return (row[0], row[1], bool(row[2])) if row else None


def identify(moves: list[chess.Move]) -> tuple[str | None, str | None, int]:
    """Restituisce (eco, nome, n. semimosse di libro consecutive dall'inizio)."""
    board = chess.Board()
    eco = name = None
    book_plies = 0
    for i, mv in enumerate(moves):
        board.push(mv)
        hit = lookup(board)
        if hit is None:
            break
        book_plies = i + 1
        if hit[2] or name is None:
            eco, name = hit[0], hit[1]
    return eco, name, book_plies
