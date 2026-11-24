"""Test che richiedono Stockfish (saltati se manca; tutti eseguiti nell'immagine di test)."""
import asyncio
import shutil

import chess
import pytest

from chess_me import config

pytestmark = pytest.mark.skipif(shutil.which(config.STOCKFISH_PATH) is None, reason="stockfish non disponibile")


def _analyse(moves):
    from chess_me.review.analyzer import analyse_game
    from chess_me.engine import analysis_engine

    async def run():
        try:
            return await analyse_game(0, moves, depth=12)
        finally:
            await analysis_engine.close()

    return asyncio.run(run())


def _uci(sans):
    b = chess.Board()
    out = []
    for s in sans:
        mv = b.parse_san(s)
        out.append(mv.uci())
        b.push(mv)
    return out


def test_queen_blunder_is_explained():
    res = _analyse(_uci(["e4", "e5", "Nf3", "Qh4"]))
    m = res["moves"][3]
    assert m["classification"] == "blunder"
    assert "donna" in m["comment"]
    assert "Meglio" in m["comment"]


def test_scholars_mate_blunder_mentions_mate():
    res = _analyse(_uci(["e4", "e5", "Qh5", "Nc6", "Bc4", "Nf6", "Qxf7#"]))
    nf6 = res["moves"][5]
    assert nf6["classification"] == "blunder"
    assert "matto" in nf6["comment"]
    assert res["moves"][6]["comment"].endswith("Scacco matto!")


def test_book_moves():
    res = _analyse(_uci(["e4", "e5", "Nf3", "Nc6", "Bb5"]))
    assert all(m["classification"] == "book" for m in res["moves"])
    assert "Ruy Lopez" in (res["review"]["opening_name"] or "") or "Spanish" in (res["review"]["opening_name"] or "")


FOOLS_MATE = """[Event "Test"]
[White "io_test"]
[Black "rival"]
[Result "0-1"]

1. f3 e5 2. g4 Qh4# 0-1
"""


def test_full_game_in_memory():
    from chess_me import session
    from chess_me.engine import analysis_engine

    async def run():
        loaded = await session.load(pgn=FOOLS_MATE)
        try:
            return await session.analyse(loaded.valid[0], "white", 12)
        finally:
            await analysis_engine.close()

    rv = asyncio.run(run())
    assert rv.moves[2]["classification"] == "blunder"  # g4??
    assert rv.summary["accuracy_white"] < rv.summary["accuracy_black"]
    text = rv.summary["text"]
    assert "Hai giocato con il bianco contro rival" in text["overview"]
    assert any(c_["ply"] == 2 for c_ in text["critical"])     # g4 è un momento critico
    assert text["advice"]


def test_engine_closes():
    from chess_me.engine import analysis_engine
    from chess_me.review.analyzer import analyse_position

    async def run():
        await analyse_position(chess.Board(), 6)
        assert analysis_engine.engine is not None
        await analysis_engine.close()
        assert analysis_engine.engine is None

    asyncio.run(run())
