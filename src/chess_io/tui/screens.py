"""Schermate di supporto: ricerca per utente, analisi in corso, scelta del colore / della partita, conferme, aiuto, riassunto."""
from dataclasses import replace

from rich.style import Style
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Input, Label, OptionList, ProgressBar, RadioButton, RadioSet, Static
from textual.widgets.option_list import Option

from . import theme
from .. import i18n, runtime, sources
from ..i18n import tr
from ..session import Review


def localize_bindings(node) -> None:
    """Traduce descrizioni e tasti mostrati nel footer (BINDINGS sono scritti in italiano a livello di classe).
    Si può richiamare dopo un cambio di lingua: parte sempre dagli originali."""
    orig = getattr(node, "_bindings_it", None)
    if orig is None:
        orig = {k: list(v) for k, v in node._bindings.key_to_bindings.items()}
        node._bindings_it = orig
    node._bindings.key_to_bindings = {
        k: [replace(b, description=tr(b.description) if b.description else b.description,
                    key_display=tr(b.key_display) if b.key_display else b.key_display) for b in v]
        for k, v in orig.items()
    }

MODAL_CSS = """
ModalScreen { align: center middle; }
#dialog { width: 64; height: auto; padding: 1 2; border: round #5b8bb0; background: $surface; }
#dialog Label { width: 100%; margin-bottom: 1; }
#dialog Horizontal { height: auto; align: center middle; }
#dialog Button { margin: 0 1; }
#dialog OptionList { height: auto; max-height: 20; }
"""


class SearchScreen(Screen):
    """`chess-io` senza opzioni: lingua, piattaforma + nome utente → elenco delle ultime partite."""
    DEFAULT_CSS = """
    SearchScreen { align: center middle; }
    #box { width: 64; height: auto; padding: 1 2; border: round #5b8bb0; }
    #box > Static, #box RadioSet, #box Input { margin-bottom: 1; }
    #box > #langlabel { margin-bottom: 0; }
    #box RadioSet { width: 100%; layout: horizontal; }
    #box Horizontal { height: auto; align: center middle; }
    """
    BINDINGS = [Binding("escape", "app.quit", "Esci"), Binding("f2", "next_lang", "Lingua")]

    class Submitted(Message):
        def __init__(self, platform: str, username: str):
            super().__init__()
            self.platform, self.username = platform, username

    def __init__(self):
        super().__init__()
        localize_bindings(self)
        self.busy = False

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(id="title")
            yield Static(id="langlabel")
            with RadioSet(id="lang"):
                for code in i18n.LANGS:
                    yield RadioButton(i18n.NAMES[code], value=code == i18n.lang(), id=f"lang-{code}")
            with RadioSet(id="platform"):
                yield RadioButton("Lichess", value=True, id="lichess")
                yield RadioButton("chess.com", id="chesscom")
            yield Input(id="username")
            with Horizontal():
                yield Button("", id="search", variant="primary")
            yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.relabel()
        last = runtime.load_last_search()
        if last:
            platform, username = last
            if platform in ("lichess", "chesscom"):
                self.query_one(f"#{platform}", RadioButton).value = True
            inp = self.query_one("#username", Input)
            inp.value = username
            inp.cursor_position = len(username)
        self.query_one("#username", Input).focus()

    def relabel(self) -> None:
        """Testi della schermata nella lingua corrente."""
        self.query_one("#title", Static).update(Text(tr("chess-io · cerca le partite di un utente"), Style(bold=True)))
        self.query_one("#langlabel", Static).update(Text(tr("Lingua di interfaccia e commenti (F2 per cambiarla)"),
                                                         Style(color=theme.MUTED)))
        self.query_one("#username", Input).placeholder = tr("nome utente")
        self.query_one("#search", Button).label = tr("Cerca")
        if not self.busy:
            self._status(tr("Invio per cercare le ultime 50 partite."), theme.MUTED)

    def set_language(self, code: str) -> None:
        if code == i18n.lang():
            return
        i18n.set_lang(code)
        i18n.save(code)       # la scelta diventa la nuova lingua predefinita
        localize_bindings(self)
        self.refresh_bindings()
        self.relabel()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id == "lang" and event.pressed.id:
            self.set_language(event.pressed.id.removeprefix("lang-"))

    def action_next_lang(self) -> None:
        if self.busy:
            return
        code = i18n.LANGS[(i18n.LANGS.index(i18n.lang()) + 1) % len(i18n.LANGS)]
        self.query_one(f"#lang-{code}", RadioButton).value = True   # → on_radio_set_changed

    @property
    def platform(self) -> str:
        pressed = self.query_one("#platform", RadioSet).pressed_button
        return pressed.id if pressed else "lichess"

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        for w in self.query("#lang, #platform, #username, #search"):
            w.disabled = busy

    def _status(self, msg: str, color: str) -> None:
        self.query_one("#status", Static).update(Text(msg, Style(color=color)))

    def submit(self) -> None:
        try:
            platform = sources.normalize_platform(self.platform)
            username = sources.check_username(self.query_one("#username", Input).value)
        except sources.FetchError as e:
            self._status(str(e).capitalize(), theme.BAD)
            return
        self._set_busy(True)
        self._status(tr("Scarico le ultime partite di {user}…", user=username), theme.MUTED)
        self.post_message(self.Submitted(platform, username))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.submit()

    def error(self, msg: str) -> None:
        self.ready()
        self._status(msg[:1].upper() + msg[1:], theme.BAD)

    def ready(self) -> None:
        self._set_busy(False)
        self._status(tr("Invio per cercare le ultime 50 partite."), theme.MUTED)
        self.query_one("#username", Input).focus()


class AnalysisScreen(Screen):
    DEFAULT_CSS = """
    AnalysisScreen { align: center middle; }
    #box { width: 76; height: auto; padding: 1 2; border: round #5b8bb0; }
    #box Static { margin-bottom: 1; }
    """
    BINDINGS = [Binding("q", "app.quit", "Esci")]

    def __init__(self, title: str, subtitle: str):
        super().__init__()
        localize_bindings(self)
        self.title_text, self.subtitle = title, subtitle
        self.failed: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(Text(self.title_text, Style(bold=True)))
            yield Static(Text(self.subtitle, Style(color=theme.MUTED)), id="sub")
            yield ProgressBar(total=None, show_eta=False, id="bar")
            yield Static(tr("In attesa di Stockfish…"), id="status")
        yield Footer()

    def progress(self, done: int, total: int) -> None:
        if not self.query("#status"):
            return
        self.query_one("#bar", ProgressBar).update(total=total, progress=done)
        self.query_one("#status", Static).update(tr("Stockfish sta analizzando le posizioni… {done}/{total}",
                                                    done=done, total=total))

    def on_mount(self) -> None:
        if self.failed:
            self.error(self.failed)

    def error(self, msg: str) -> None:
        self.failed = msg
        if self.query("#status"):
            self.query_one("#status", Static).update(Text(tr("Analisi non riuscita: {error}\nPremi q per uscire.", error=msg),
                                                          Style(color=theme.BAD)))


class ColorScreen(ModalScreen[str]):
    DEFAULT_CSS = MODAL_CSS
    BINDINGS = [Binding("w", "pick('white')", "Bianco"), Binding("b", "pick('black')", "Nero")]

    def __init__(self, white: str, black: str):
        super().__init__()
        localize_bindings(self)
        self.white, self.black = white, black

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(tr("Con quale colore hai giocato? (serve per il riassunto e il verso della scacchiera)"))
            with Horizontal():
                yield Button(f"○ {self.white}  [w]", id="white", variant="default")
                yield Button(f"● {self.black}  [b]", id="black", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)

    def action_pick(self, color: str) -> None:
        self.dismiss(color)


class PickScreen(ModalScreen[int]):
    """Il PGN contiene più partite (o sono le partite recenti di un utente): si sceglie quale analizzare."""
    DEFAULT_CSS = MODAL_CSS + """
    PickScreen #dialog { width: 110; max-width: 100%; }
    PickScreen #dialog OptionList { max-height: 30; }
    """
    BINDINGS = [Binding("escape,q", "close", "Indietro")]

    def __init__(self, candidates, username: str | None = None):
        super().__init__()
        localize_bindings(self)
        self.candidates, self.username = candidates, username

    @staticmethod
    def _who(name: str, elo: int | None) -> str:
        return f"{name} ({elo})" if elo else name

    def _user_label(self, c) -> Text:
        u = self.username.lower()
        if c.white.lower() == u:
            me, opp, opp_elo = "○", c.black, c.black_elo
            outcome = {"1-0": "win", "0-1": "loss", "1/2-1/2": "draw"}.get(c.result, "")
        elif c.black.lower() == u:
            me, opp, opp_elo = "●", c.white, c.white_elo
            outcome = {"0-1": "win", "1-0": "loss", "1/2-1/2": "draw"}.get(c.result, "")
        else:
            me, opp, opp_elo, outcome = " ", f"{c.white} – {c.black}", None, ""
        color = {"win": theme.GOOD, "loss": theme.BAD}.get(outcome, theme.MUTED)
        letter = {"win": tr("V"), "loss": tr("P"), "draw": "="}.get(outcome, "·")
        t = Text()
        t.append(f"{c.index + 1:>3}. ")
        t.append(f"{(c.played_at or '')[:10]:<10}  ", Style(color=theme.MUTED))
        t.append(f"{letter} ", Style(color=color, bold=True))
        t.append(f"{me} vs {self._who(opp, opp_elo):<28.28} ")
        t.append(f"{(c.time_class or c.time_control or ''):<14.14} ", Style(color=theme.MUTED))
        t.append(f"{(c.opening or c.eco or ''):<34.34} ")
        t.append(f"{c.plies:>3} {tr('sm')}", Style(color=theme.MUTED))
        if c.error:
            t.append(f"  ({c.error})", Style(color=theme.BAD))
        return t

    def compose(self) -> ComposeResult:
        opts = []
        for c in self.candidates:
            if self.username:
                label = self._user_label(c)
            else:
                label = f"{c.index + 1:>3}. {c.white} – {c.black}  " \
                        f"{c.result}  {c.played_at or ''}  " + tr("{n} semimosse", n=c.plies) \
                        + (f"  ({c.error})" if c.error else "")
            opts.append(Option(label, id=str(c.index), disabled=bool(c.error)))
        with Vertical(id="dialog"):
            if self.username:
                yield Label(tr("Ultime {n} partite di {user} (○ bianco, ● nero · V vinta, P persa, = patta): "
                               "quale vuoi analizzare?", n=len(self.candidates), user=self.username))
            else:
                yield Label(tr("Il PGN contiene {n} partite: quale vuoi analizzare?", n=len(self.candidates)))
            yield OptionList(*opts)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(int(event.option.id))

    def action_close(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    DEFAULT_CSS = MODAL_CSS
    BINDINGS = [Binding("y,s", "answer(True)", "Sì"), Binding("n,escape", "answer(False)", "No")]

    def __init__(self, question: str):
        super().__init__()
        localize_bindings(self)
        self.question = question

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.question)
            with Horizontal():
                yield Button(tr("Sì [s]"), id="yes", variant="primary")
                yield Button(tr("No [n]"), id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_answer(self, value: bool) -> None:
        self.dismiss(value)


HELP = [
    ("← →", "mossa precedente / successiva"), ("Home End", "inizio / fine partita"),
    ("spazio", "riproduzione automatica (si ferma sui momenti salienti)"),
    ("n  N", "momento critico successivo / precedente"),
    ("b", "esplora la variante migliore"), ("r", "esplora la confutazione"), ("Esc", "torna alla partita"),
    ("s", "riassunto della partita"), ("l", "commenti template ↔ LLM (con --llm)"),
    ("f", "gira la scacchiera"), ("c", "cambia il tuo colore"), ("q", "esci"),
]


class HelpScreen(ModalScreen[None]):
    DEFAULT_CSS = MODAL_CSS
    BINDINGS = [Binding("escape,question_mark,q", "close", "Chiudi")]

    def __init__(self):
        super().__init__()
        localize_bindings(self)

    def compose(self) -> ComposeResult:
        t = Table.grid(padding=(0, 2))
        for k, v in HELP:
            t.add_row(Text(tr(k), Style(bold=True, color=theme.ACCENT)), tr(v))
        with Vertical(id="dialog"):
            yield Label(tr("Tasti"))
            yield Static(t)

    def action_close(self) -> None:
        self.dismiss(None)


class SummaryScreen(Screen[int | None]):
    """Riassunto: accuratezza, conteggi per classe, com'è andata, momenti critici (Invio per andarci), consigli."""
    DEFAULT_CSS = """
    SummaryScreen { layout: horizontal; }
    #counts { width: 46; padding: 1 2; }
    #text { width: 1fr; padding: 1 2; }
    #text Static { margin-bottom: 1; }
    #critical { height: auto; max-height: 12; margin-bottom: 1; }
    """
    BINDINGS = [Binding("escape,s,q", "close", "Torna alla revisione"), Binding("l", "toggle_llm", "Template/LLM")]

    def __init__(self, rv: Review, use_llm: bool):
        super().__init__()
        localize_bindings(self)
        self.rv, self.use_llm = rv, use_llm

    def compose(self) -> ComposeResult:
        yield VerticalScroll(Static(id="table"), id="counts")
        with VerticalScroll(id="text"):
            yield Static(id="overview")
            yield Static(Text(tr("Momenti critici (Invio per andare alla mossa)"), Style(bold=True)))
            yield OptionList(id="critical")
            yield Static(id="advice")
        yield Footer()

    def on_mount(self) -> None:
        self.paint()

    def _block(self, kind: str, i: int | None, template: str) -> str:
        llm = self.rv.summary.get("llm") if self.use_llm else None
        if not llm:
            return template
        v = llm.get(kind)
        if i is not None:
            v = v[i] if v and i < len(v) else None
        return v or template

    def paint(self) -> None:
        rv, s, g = self.rv, self.rv.summary, self.rv.game
        me = g["player_color"]
        t = Table(box=None, padding=(0, 1), show_edge=False)
        t.add_column("", no_wrap=True)
        you = tr(" (tu)")
        t.add_column("♔ " + tr("Bianco") + (you if me == "white" else ""), justify="right")
        t.add_column("♚ " + tr("Nero") + (you if me == "black" else ""), justify="right")
        t.add_row(Text(tr("Accuratezza"), Style(bold=True)), f"{s.get('accuracy_white') or '–'}", f"{s.get('accuracy_black') or '–'}")
        t.add_row(tr("Rating stimato"), f"{s.get('rating_est_white') or '–'}", f"{s.get('rating_est_black') or '–'}")
        for c in theme.CLASS_ORDER:
            meta = theme.CLASS_META[c]
            label = Text()
            label.append(f"{meta.sym:>2} ", Style(color=meta.color, bold=True))
            label.append(meta.label)
            t.add_row(label, str(s["counts"].get("white", {}).get(c, 0)), str(s["counts"].get("black", {}).get(c, 0)))
        self.query_one("#table", Static).update(t)
        tpl = s.get("text") or {"overview": "", "critical": [], "advice": []}
        ov = Text()
        ov.append(tr("Com'è andata") + "\n", Style(bold=True))
        ov.append(self._block("overview", None, tpl["overview"]))
        self.query_one("#overview", Static).update(ov)
        ol = self.query_one("#critical", OptionList)
        ol.clear_options()
        by_ply = {m["ply"]: i for i, m in enumerate(rv.moves)}
        for k, c in enumerate(tpl.get("critical", [])):
            meta = theme.CLASS_META.get(c["cls"])
            line = Text()
            if meta:
                line.append(f"{meta.sym:>2} ", Style(color=meta.color, bold=True))
            line.append(self._block("critical", k, c["text"]))
            ol.add_option(Option(line, id=str(by_ply.get(c["ply"], -1))))
        adv = Text()
        adv.append(tr("Consigli") + "\n", Style(bold=True))
        llm_adv = self.rv.summary.get("llm", {}).get("advice") if self.use_llm and self.rv.summary.get("llm") else None
        if llm_adv:
            adv.append(llm_adv)
        else:
            for a in tpl.get("advice", []):
                adv.append(f"• {a}\n")
        self.query_one("#advice", Static).update(adv)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(int(event.option.id))

    def action_close(self) -> None:
        self.dismiss(None)

    def action_toggle_llm(self) -> None:
        if self.rv.summary.get("llm"):
            self.use_llm = not self.use_llm
            self.paint()
        else:
            self.notify(tr("Riassunto LLM non disponibile") + (tr(" (in corso…)") if self.rv.llm_status == "running" else ""))
