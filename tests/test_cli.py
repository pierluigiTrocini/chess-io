"""CLI chess-io: argomenti, input PGN, risorse, manifest dei binari, TUI (con una revisione sintetica)."""
import asyncio
import io
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from cli_fixtures import PGN, fake_review  # noqa: E402

from chess_io import config  # noqa: E402
from chess_io import cli as cli_main, downloads as install, runtime, session  # noqa: E402

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


def test_parser_source_optional_but_exclusive(capsys):
    a = cli_main.build_parser().parse_args([])           # nessuna sorgente: schermata di ricerca
    assert (a.link, a.pgn, a.user) == (None, None, None)
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


def test_user_option_and_color_from_username(monkeypatch):
    a = cli_main.build_parser().parse_args(["-u", "lichess", "magnus_fan"])
    assert a.user == ["lichess", "magnus_fan"] and a.link is None and a.pgn is None
    two = PGN + "\n\n" + PGN.replace("magnus_fan", "altro")

    async def fake_fetch(platform, user, n=50, client=None):
        return two
    monkeypatch.setattr(session.sources, "fetch_user_games", fake_fetch)
    loaded = asyncio.run(session.load(user=("lichess", "MAGNUS_FAN")))
    assert loaded.username == "MAGNUS_FAN" and session.pick(loaded, None) is None
    first, second = loaded.candidates
    assert loaded.color_for(first) == ("white" if first.white == "magnus_fan" else "black")
    assert loaded.color_for(second) is None          # l'utente non gioca: si chiede il colore
    assert cli_main.main(["-u", "fics", "x"]) == 2


# ---------- risorse ----------
def test_resolve_prefers_user_data(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    sf = home / "bin" / "stockfish"
    sf.write_text("#!/bin/sh\n")
    (home / "openings.sqlite").write_text("")
    monkeypatch.setenv("CHESSIO_HOME", str(home))
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
    from chess_io.tui.app import ChessIoApp
    return ChessIoApp(session.Loaded([c], None, "test.pgn"), c, "white", 16, False, review=rv)


def test_tui_navigation_variation_and_summary():
    from chess_io.tui.board import BoardView
    from chess_io.tui.panels import CommentPanel
    from chess_io.tui.review import ReviewScreen
    from chess_io.tui.screens import SummaryScreen

    async def run():
        rv, c = fake_review()
        app = _app(rv, c)
        async with app.run_test(size=(110, 34)) as pilot:
            await pilot.pause()
            scr = app.screen
            assert isinstance(scr, ReviewScreen) and scr.idx == -1          # si parte dall'inizio
            brief = scr.query_one("#brief")
            assert brief.display and "In breve" in str(brief.render())       # riassunto breve sotto la scacchiera
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


def test_tui_search_screen_to_game_list(monkeypatch, tmp_path):
    from textual.widgets import Input
    from chess_io import pgn as pgn_parse
    from chess_io.tui.app import ChessIoApp
    from chess_io.tui.screens import PickScreen, SearchScreen

    calls = []

    async def fake_load(user=None, **kw):
        calls.append(user)
        if user[1] == "nessuno":
            raise session.InputError("Lichess, utente nessuno: non trovato")
        return session.Loaded(pgn_parse.parse_many(PGN + "\n" + PGN), None, "Lichess · Tu", "Tu")
    monkeypatch.setattr(session, "load", fake_load)
    monkeypatch.setenv("CHESSIO_HOME", str(tmp_path))

    async def run():
        app = ChessIoApp(None, None, None, 16, False)
        async with app.run_test(size=(120, 34)) as pilot:
            await pilot.pause()
            scr = app.screen
            assert isinstance(scr, SearchScreen)
            await pilot.press("x", "enter")                      # nome troppo corto
            await pilot.pause()
            assert "non valido" in str(scr.query_one("#status").render()) and not calls
            scr.query_one("#username", Input).value = "nessuno"
            await pilot.press("enter")
            await pilot.pause()
            assert "non trovato" in str(scr.query_one("#status").render())
            assert not scr.query_one("#username").disabled
            scr.query_one("#username", Input).value = "Tu"
            await pilot.press("enter")
            await pilot.pause()
            assert calls[-1] == ("lichess", "Tu")
            assert isinstance(app.screen, PickScreen)
            await pilot.press("escape")                          # torna alla ricerca
            await pilot.pause()
            assert app.screen is scr and app.is_running
    asyncio.run(run())
    assert runtime.load_last_search() == ("lichess", "Tu")   # salvata solo la ricerca riuscita


def test_tui_search_screen_prefills_last_search(monkeypatch, tmp_path):
    from textual.widgets import Input, RadioSet
    from chess_io.tui.app import ChessIoApp
    monkeypatch.setenv("CHESSIO_HOME", str(tmp_path))
    runtime.save_last_search("chesscom", "Hikaru")

    async def run():
        app = ChessIoApp(None, None, None, 16, False)
        async with app.run_test(size=(120, 34)) as pilot:
            await pilot.pause()
            scr = app.screen
            assert scr.query_one("#username", Input).value == "Hikaru"
            assert scr.query_one("#platform", RadioSet).pressed_button.id == "chesscom"
            assert scr.platform == "chesscom"
    asyncio.run(run())


def test_last_search_corrupt_file_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setenv("CHESSIO_HOME", str(tmp_path))
    (tmp_path / runtime.LAST_SEARCH_FILE).write_text("{non json")
    assert runtime.load_last_search() is None


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
    from chess_io.engine import analysis_engine

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


def test_board_fit_and_contrast():
    from chess_io.tui import board, theme
    assert board.fit_cell(150 - 52, 29) == (7, 3) and board.fit_cell(40, 30) == (3, 1)
    assert theme.ink(theme.LAST_LIGHT) == "#111111" and theme.ink("#3a2020") == "#ffffff"
    assert theme.contrast("#ffffff", "#000000") > 20
