"""Lingue: cataloghi completi, tr(), commenti e riassunto in inglese/spagnolo, controllo LLM, CLI e schermata di ricerca."""
import ast
import asyncio
import string
import sys
from pathlib import Path

import chess
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from cli_fixtures import fake_review  # noqa: E402

from chess_io import i18n, runtime  # noqa: E402
from chess_io.locales import en, es  # noqa: E402

SRC = Path(__file__).parent.parent / "src" / "chess_io"
CATALOGS = {"en": en.T, "es": es.T}


@pytest.fixture(autouse=True)
def _italian_after(monkeypatch, tmp_path):
    """Ogni test parte e finisce in italiano, con dati utente in una cartella temporanea."""
    monkeypatch.setenv("CHESSIO_HOME", str(tmp_path))
    monkeypatch.delenv("CHESSIO_LANG", raising=False)
    i18n.set_lang("it")
    yield
    i18n.set_lang("it")


# ---------- cataloghi ----------
def _msgids() -> set[str]:
    """Tutti i testi che passano da tr(): letterali nel codice + tabelle tradotte a runtime + footer della TUI."""
    ids = set()
    for f in SRC.rglob("*.py"):
        if "locales" in f.parts:
            continue
        for n in ast.walk(ast.parse(f.read_text())):
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "tr" and n.args \
                    and isinstance(n.args[0], ast.Constant):
                ctx = next((k.value.value for k in n.keywords if k.arg == "_ctx"), None)
                ids.add(f"{ctx}|{n.args[0].value}" if ctx else n.args[0].value)
    from textual.screen import Screen
    from chess_io.explain import summary
    from chess_io.llm import humanize
    from chess_io.tui import review, screens, theme
    for table in (summary.CLASS_IT, summary.PHASE_IT, summary.PHASE_TIP, summary.TERMINATION_IT, summary.OUTCOME_IT,
                  humanize.CLASS_IT, theme.RESULT_IT, theme.TIME_CLASS_IT):
        ids |= set(table.values())
    ids |= {m.label_it for m in theme.CLASS_META.values()}
    ids |= {x for pair in screens.HELP for x in pair}
    for mod in (screens, review):
        for obj in vars(mod).values():
            if isinstance(obj, type) and issubclass(obj, Screen) and obj.__module__ == mod.__name__:
                ids |= {x for b in obj.BINDINGS for x in (b.description, b.key_display) if x}
    return ids


def _fields(s: str) -> set[str]:
    return {f[1] for f in string.Formatter().parse(s) if f[1]}


@pytest.mark.parametrize("code", ["en", "es"])
def test_catalog_complete_and_placeholders_match(code):
    pytest.importorskip("textual")
    cat, ids = CATALOGS[code], _msgids()
    assert not sorted(ids - set(cat)), "testi senza traduzione"
    assert not sorted(set(cat) - ids), "traduzioni non più usate"
    for k, v in cat.items():
        assert _fields(k.split("|", 1)[1] if "|" in k else k) == _fields(v), k


def test_tr_context_and_fallback():
    assert i18n.tr("{piece} in {square}", piece="l'alfiere", square="f4") == "l'alfiere in f4"
    i18n.set_lang("en")
    assert i18n.tr("{piece} in {square}", piece="the bishop", square="f4") == "the bishop on f4"
    assert i18n.tr("{piece} in {square}", _ctx="move", piece="the bishop", square="f4") == "the bishop to f4"
    assert i18n.tr("testo senza traduzione") == "testo senza traduzione"
    assert i18n.piece_on(chess.KNIGHT, chess.E5) == "the knight on e5"
    assert i18n.join(["a", "b", "c"]) == "a, b and c"
    i18n.set_lang("es")
    assert i18n.piece_on(chess.QUEEN, chess.D1) == "la dama en d1" and i18n.join(["a", "b"]) == "a y b"


def test_resolve_order_and_save(monkeypatch):
    assert i18n.resolve() == "it" and i18n.saved() is None
    assert i18n.save("es") and i18n.saved() == "es" and i18n.resolve() == "es"
    monkeypatch.setenv("CHESSIO_LANG", "en_US.UTF-8")
    assert i18n.resolve() == "en"
    assert i18n.resolve("it") == "it"                 # --lang vince su tutto
    assert i18n.resolve("fr") == "en"                 # lingua non supportata: si ignora
    assert runtime.load_settings() == {"lang": "es"}


# ---------- commenti e riassunto ----------
def _blunder_facts():
    """3...Nf6?? nel matto del barbiere: concede Qxf7#, la migliore era g6 che para la minaccia."""
    from chess_io.explain.facts import build_facts
    b = chess.Board()
    for s in ("e4", "e5", "Bc4", "Nc6", "Qh5"):
        b.push_san(s)
    mv, best = b.parse_san("Nf6"), b.parse_san("g6")
    after_best = b.copy()
    after_best.push(best)
    after = b.copy()
    after.push(mv)
    null = b.copy()
    null.push(chess.Move.null())
    return build_facts(b, mv, "blunder", best, [best, after_best.parse_san("Qf3")], [after.parse_san("Qxf7#")], None,
                       -1, None, null.parse_san("Qxf7"), 0, None, None, "+0.3", "#-1")


@pytest.mark.parametrize("code, expected", [
    ("it", "Nf6?? Concede il matto alla mossa successiva: 4. Qxf7#. Meglio g6, che para la minaccia Qxf7# (3...g6 4. Qf3)."),
    ("en", "Nf6?? Allows mate on the next move: 4. Qxf7#. Better was g6, which parries the threat Qxf7# (3...g6 4. Qf3)."),
    ("es", "Nf6?? Permite el mate en la jugada siguiente: 4. Qxf7#. Mejor g6, que para la amenaza Qxf7# (3...g6 4. Qf3)."),
])
def test_move_comment_in_each_language(code, expected):
    from chess_io.explain.templates import render
    i18n.set_lang(code)
    assert render(_blunder_facts()) == expected


def test_describe_and_annotate_in_english_and_spanish():
    from chess_io.explain.describe import annotate, describe_san
    i18n.set_lang("en")
    assert describe_san("Nxe5") == "the knight takes on e5" and describe_san("O-O") == "kingside castling"
    assert describe_san("e8=Q+") == "the pawn to e8 promoting to a queen"
    assert annotate("Then Be3 keeps the bishop on f4 safe.") == "Then the bishop to e3 (Be3) keeps the bishop on f4 safe."
    i18n.set_lang("es")
    assert describe_san("bxa6") == "el peón que captura en a6"
    assert annotate("Be3 es mejor (12. Be3 Nf6).") == "El alfil a e3 (Be3) es mejor (12. Be3 Nf6)."


@pytest.mark.parametrize("code, words", [
    ("en", ["You played White against magnus_fan", "Result: loss by checkmate", "Key moment: 4. Nxe5 (blunder)."]),
    ("es", ["Jugaste con blancas contra magnus_fan", "Resultado: derrota por jaque mate", "Momento clave: 4. Nxe5 (error grave)."]),
])
def test_summary_in_each_language(code, words):
    i18n.set_lang(code)
    rv, _ = fake_review()
    t = rv.summary["text"]
    text = t["overview"] + " " + t["brief"] + " " + " ".join(t["advice"])
    for w in words:
        assert w in text
    assert rv.game["termination_text"] == ("checkmate" if code == "en" else "jaque mate")


# ---------- LLM: prompt e controllo per lingua ----------
@pytest.mark.parametrize("code", ["it", "en", "es"])
def test_prompt_examples_pass_the_check(code):
    """Gli esempi dei prompt devono superare il controllo della loro lingua, altrimenti insegnano al modello
    risposte che verrebbero scartate."""
    from chess_io.llm import humanize, prompts
    i18n.set_lang(code)
    p = prompts.load()
    assert prompts.path().name == ("prompts.toml" if code == "it" else f"prompts.{code}.toml")
    cls_of = {i18n.tr(v).capitalize(): k for k, v in humanize.CLASS_IT.items()}
    for ex in p["humanize"]["examples"]:
        ref = f"{ex['classe']}. {ex['commento']} {ex['soluzione']}"
        r = humanize.check(ex["assistant"], ref, None, cls_of[ex["classe"]])
        assert r["passed"], (ex["classe"], r["reason"])
    for ex in p["summary"]["examples"]:
        r = humanize.check(ex["assistant"], ex["user"], None)
        assert r["passed"], (ex["kind"], r["reason"])


def test_llm_check_english_vocabulary():
    from chess_io.llm.humanize import check
    i18n.set_lang("en")
    tpl = "Bf4?? After exf4 you lose a bishop (the bishop on f4 falls). Better was Be3."
    assert check("Bf4 is a blunder: after exf4 the bishop is gone. Be3 was the move.", tpl, None, "blunder")["passed"]
    r = check("Bf4 is a blunder: after exf4 you lose the queen. Be3 was better.", tpl, None, "blunder")
    assert not r["passed"] and r["reason"] == "names pieces that are not in the comment"
    r = check("Bf4 is a blunder that walks into a fork after exf4. Better was Be3.", tpl, None, "blunder")
    assert not r["passed"] and "fork" in r["reason"]


# ---------- CLI ----------
def test_cli_lang_command_and_option(capsys):
    from chess_io import cli
    assert cli.main(["lang"]) == 0 and capsys.readouterr().out.startswith("it")
    assert cli.main(["lang", "es"]) == 0
    assert "Español" in capsys.readouterr().out and i18n.saved() == "es"
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    assert "Analiza una partida" in capsys.readouterr().out          # lingua salvata
    with pytest.raises(SystemExit):
        cli.main(["--lang", "en", "--help"])
    assert "Analyse a game" in capsys.readouterr().out               # --lang solo per questa volta
    assert i18n.saved() == "es"
    assert cli.main(["--lang", "en", "-pgn", "manca.pgn"]) == 2
    assert "file not found" in capsys.readouterr().err


# ---------- TUI ----------
def test_search_screen_language_switch():
    pytest.importorskip("textual")
    from textual.widgets import Button, Input
    from chess_io.tui.app import ChessIoApp
    from chess_io.tui.screens import SearchScreen

    async def run():
        app = ChessIoApp(None, None, None, 16, False)
        async with app.run_test(size=(120, 34)) as pilot:
            await pilot.pause()
            scr = app.screen
            assert isinstance(scr, SearchScreen) and scr.query_one("#search", Button).label.plain == "Cerca"
            await pilot.press("f2")                                  # it → en
            await pilot.pause()
            assert i18n.lang() == "en" and scr.query_one("#search", Button).label.plain == "Search"
            assert scr.query_one("#username", Input).placeholder == "username"
            assert any(b.description == "Language" for b in scr._bindings.key_to_bindings["f2"])
            await pilot.press("f2")                                  # en → es
            await pilot.pause()
            assert scr.query_one("#search", Button).label.plain == "Buscar"
            assert any(b.description == "Salir" for b in scr._bindings.key_to_bindings["escape"])
    asyncio.run(run())
    assert i18n.saved() == "es"                                      # diventa la lingua predefinita


def test_review_screen_in_english():
    pytest.importorskip("textual")
    from chess_io import session
    from chess_io.tui.app import ChessIoApp
    i18n.set_lang("en")
    rv, c = fake_review()

    async def run():
        app = ChessIoApp(session.Loaded([c], None, "test.pgn"), c, "white", 16, False, review=rv)
        async with app.run_test(size=(110, 34)) as pilot:
            await pilot.pause()
            await pilot.press("end")
            await pilot.pause()
            assert "Accuracy" in str(app.screen.query_one("#header").render())
            assert "before" in str(app.screen.query_one("#comment").render())
            assert "In short" in str(app.screen.query_one("#brief").render())
            assert any(b.description == "Summary" for b in app.screen._bindings.key_to_bindings["s"])
    asyncio.run(run())
