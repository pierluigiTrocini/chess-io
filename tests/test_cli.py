"""CLI chess-me: argomenti, input PGN, risorse, manifest dei binari, TUI (con una revisione sintetica)."""
import asyncio
import io
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from cli_fixtures import PGN, fake_review  # noqa: E402

from chess_me import config  # noqa: E402
from chess_me import cli as cli_main, downloads as install, runtime, session  # noqa: E402

textual = pytest.importorskip("textual")


@pytest.fixture(autouse=True)
def _keep_env():
    """main() chiama runtime.bootstrap(), che modifica os.environ: lo si ripristina dopo ogni test."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


# ---------- argomenti ----------
def test_parser_accepts_single_dash_pgn():
    a = cli_main.build_parser().parse_args(["-pgn", "x.pgn", "-c", "black", "-d", "12", "--llm"])
    assert (a.pgn, a.color, a.depth, a.llm, a.link) == ("x.pgn", "black", 12, True, None)
    a = cli_main.build_parser().parse_args(["-l", "https://lichess.org/abcd1234"])
    assert a.link and a.pgn is None


def test_parser_requires_exactly_one_source(capsys):
    with pytest.raises(SystemExit):
        cli_main.build_parser().parse_args([])
    with pytest.raises(SystemExit):
        cli_main.build_parser().parse_args(["-l", "x", "-pgn", "y"])


def test_bad_depth_and_missing_file_exit_2(capsys):
    assert cli_main.main(["-pgn", "x.pgn", "-d", "99"]) == 2
    assert cli_main.main(["-pgn", "manca.pgn"]) == 2
    assert "file non trovato" in capsys.readouterr().err


# ---------- input PGN ----------
def test_read_pgn_from_file_text_and_stdin(tmp_path):
    f = tmp_path / "p.pgn"
    f.write_text(PGN)
    assert session.read_pgn_arg(str(f))[0] == PGN
    assert session.read_pgn_arg(PGN)[1] == "PGN incollato"
    assert session.read_pgn_arg("-", io.StringIO(PGN)) == (PGN, "stdin")
    with pytest.raises(session.InputError):
        session.read_pgn_arg("non/esiste.pgn")


def test_load_and_pick_multiple_games():
    two = PGN + "\n\n" + PGN.replace("magnus_fan", "altro")
    loaded = asyncio.run(session.load(pgn=two))
    assert len(loaded.valid) == 2
    assert session.pick(loaded, None) is None            # scelta a schermo
    assert session.pick(loaded, 2).black == "altro"
    with pytest.raises(session.InputError):
        session.pick(loaded, 3)
    with pytest.raises(session.InputError):
        asyncio.run(session.load(pgn="[Event \"x\"]\n\n*"))


# ---------- risorse ----------
def test_resolve_prefers_user_data(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    sf = home / "bin" / "stockfish"
    sf.write_text("#!/bin/sh\n")
    (home / "openings.sqlite").write_text("")
    monkeypatch.setenv("CHESSME_HOME", str(home))
    for k in ("STOCKFISH_PATH", "OPENINGS_DB", "LLM_SERVER_PATH", "LLM_MODEL_PATH"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(runtime, "package_data", lambda: tmp_path / "nopkg")
    res = runtime.resolve()
    assert res.stockfish == sf
    assert res.openings == home / "openings.sqlite"
    assert res.model == home / "models" / runtime.MODEL_FILE
    assert res.bundle is None


def test_manifest_covers_release_platforms():
    for kind in ("stockfish", "llama"):
        for key in ("darwin-arm64", "linux-x86_64"):
            e = install.entry(kind, key)
            assert e and e["url"].startswith("https://github.com/") and len(e["sha256"]) == 64


def test_download_rejects_wrong_hash(tmp_path, monkeypatch):
    import httpx

    class FakeStream:
        headers = {"content-length": "5"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raise_for_status(self):
            pass

        def iter_bytes(self, n):
            yield b"hello"

    monkeypatch.setattr(httpx, "stream", lambda *a, **k: FakeStream())
    dest = tmp_path / "f"
    with pytest.raises(install.SetupError):
        install.download("https://example.invalid/f", dest, "0" * 64, "test", lambda *_: None)
    assert not dest.exists() and not (tmp_path / "f.part").exists()
    install.download("https://example.invalid/f", dest,
                     "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824", "test", lambda *_: None)
    assert dest.read_bytes() == b"hello"


# ---------- revisione in memoria ----------
def test_merge_builds_review_and_summary():
    rv, _ = fake_review()
    assert len(rv.moves) == 14
    m = rv.moves[6]
    assert (m["san"], m["classification"], rv.label(6)) == ("Nxe5", "blunder", "4. Nxe5")
    assert isinstance(m["best_pv_san"], list) and m["refutation_pv_uci"][0] == "d8g5"
    assert rv.summary["text"]["overview"].startswith("Hai giocato con il bianco")
    assert rv.game["opening_name"] == "Italian Game"
    rv.set_color("black")
    assert rv.summary["text"]["overview"].startswith("Hai giocato con il nero")


# ---------- TUI ----------
def _app(rv, c):
    from chess_me.tui.app import ChessMeApp
    return ChessMeApp(session.Loaded([c], None, "test.pgn"), c, "white", 16, False, review=rv)


def test_tui_navigation_variation_and_summary():
    from chess_me.tui.board import BoardView
    from chess_me.tui.panels import CommentPanel
    from chess_me.tui.review import ReviewScreen
    from chess_me.tui.screens import SummaryScreen

    async def run():
        rv, c = fake_review()
        app = _app(rv, c)
        async with app.run_test(size=(110, 34)) as pilot:
            await pilot.pause()
            scr = app.screen
            assert isinstance(scr, ReviewScreen) and scr.idx == -1          # si parte dall'inizio
            for _ in range(7):
                await pilot.press("right")
            assert scr.idx == 6
            assert "Grave errore" in str(scr.query_one(CommentPanel).render())
            assert scr.query_one(BoardView).best == "f3d4"
            await pilot.press("b")
            assert scr.variation and scr.variation.sans == ["Nxd4"]
            await pilot.press("escape")
            assert scr.variation is None
            await pilot.press("home")
            await pilot.press("n")
            assert rv.moves[scr.idx]["classification"] == "inaccuracy"
            await pilot.press("end")
            assert scr.idx == 13
            await pilot.press("s")
            await pilot.pause()
            assert isinstance(app.screen, SummaryScreen)
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is scr
            await pilot.press("f")
            assert scr.query_one(BoardView).orientation is False
            await pilot.press("q")
    asyncio.run(run())


def test_tui_autoplay_stops_on_salient_move():
    async def run():
        rv, c = fake_review()
        app = _app(rv, c)
        async with app.run_test(size=(110, 34)) as pilot:
            await pilot.pause()
            scr = app.screen
            scr._tick()                         # come il timer, senza attendere
            assert scr.idx == 0
            scr.playing = True
            for _ in range(10):
                if not scr.playing:
                    break
                scr._tick()
            assert scr.idx == 5 and scr.paused_on_salient   # 3... Nd4?! ferma la riproduzione
    asyncio.run(run())


# ---------- analisi vera (serve Stockfish) ----------
@pytest.mark.skipif(shutil.which(config.STOCKFISH_PATH) is None, reason="stockfish non disponibile")
def test_analyse_real_game_in_memory():
    from chess_me.engine import analysis_engine

    async def run():
        loaded = await session.load(pgn=PGN)
        try:
            return await session.analyse(loaded.valid[0], "white", 10)
        finally:
            await analysis_engine.close()

    before = set(os.listdir(config.DATA_DIR))
    rv = asyncio.run(run())
    assert len(rv.moves) == 14
    assert rv.moves[8]["classification"] in ("mistake", "blunder")      # 5. Nxf7?? concede il matto
    assert rv.moves[-1]["comment"].endswith("Scacco matto!")
    assert rv.summary["accuracy_white"] < rv.summary["accuracy_black"]
    assert rv.summary["text"]["critical"]
    assert set(os.listdir(config.DATA_DIR)) == before                    # nessun file scritto
