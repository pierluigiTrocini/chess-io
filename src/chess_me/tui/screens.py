"""Schermate di supporto: analisi in corso, scelta del colore / della partita, conferme, aiuto, riassunto."""
from rich.style import Style
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Label, OptionList, ProgressBar, Static
from textual.widgets.option_list import Option

from . import theme
from ..session import Review

MODAL_CSS = """
ModalScreen { align: center middle; }
#dialog { width: 64; height: auto; padding: 1 2; border: round #5b8bb0; background: $surface; }
#dialog Label { width: 100%; margin-bottom: 1; }
#dialog Horizontal { height: auto; align: center middle; }
#dialog Button { margin: 0 1; }
#dialog OptionList { height: auto; max-height: 20; }
"""


class AnalysisScreen(Screen):
    DEFAULT_CSS = """
    AnalysisScreen { align: center middle; }
    #box { width: 76; height: auto; padding: 1 2; border: round #5b8bb0; }
    #box Static { margin-bottom: 1; }
    """
    BINDINGS = [Binding("q", "app.quit", "Esci")]

    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.title_text, self.subtitle = title, subtitle
        self.failed: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(Text(self.title_text, Style(bold=True)))
            yield Static(Text(self.subtitle, Style(color=theme.MUTED)), id="sub")
            yield ProgressBar(total=None, show_eta=False, id="bar")
            yield Static("In attesa di Stockfish…", id="status")
        yield Footer()

    def progress(self, done: int, total: int) -> None:
        if not self.query("#status"):
            return
        self.query_one("#bar", ProgressBar).update(total=total, progress=done)
        self.query_one("#status", Static).update(f"Stockfish sta analizzando le posizioni… {done}/{total}")

    def on_mount(self) -> None:
        if self.failed:
            self.error(self.failed)

    def error(self, msg: str) -> None:
        self.failed = msg
        if self.query("#status"):
            self.query_one("#status", Static).update(Text(f"Analisi non riuscita: {msg}\nPremi q per uscire.",
                                                          Style(color=theme.BAD)))


class ColorScreen(ModalScreen[str]):
    DEFAULT_CSS = MODAL_CSS
    BINDINGS = [Binding("w", "pick('white')", "Bianco"), Binding("b", "pick('black')", "Nero")]

    def __init__(self, white: str, black: str):
        super().__init__()
        self.white, self.black = white, black

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Con quale colore hai giocato? (serve per il riassunto e il verso della scacchiera)")
            with Horizontal():
                yield Button(f"○ {self.white}  [w]", id="white", variant="default")
                yield Button(f"● {self.black}  [b]", id="black", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)

    def action_pick(self, color: str) -> None:
        self.dismiss(color)


class PickScreen(ModalScreen[int]):
    """Il PGN contiene più partite: si sceglie quale analizzare."""
    DEFAULT_CSS = MODAL_CSS
    BINDINGS = [Binding("escape", "app.quit", "Esci")]

    def __init__(self, candidates):
        super().__init__()
        self.candidates = candidates

    def compose(self) -> ComposeResult:
        opts = []
        for c in self.candidates:
            label = f"{c.index + 1:>3}. {c.white} – {c.black}  {c.result}  {c.played_at or ''}  {c.plies} semimosse"
            opts.append(Option(label + (f"  ({c.error})" if c.error else ""), id=str(c.index), disabled=bool(c.error)))
        with Vertical(id="dialog"):
            yield Label(f"Il PGN contiene {len(self.candidates)} partite: quale vuoi analizzare?")
            yield OptionList(*opts)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(int(event.option.id))


class ConfirmScreen(ModalScreen[bool]):
    DEFAULT_CSS = MODAL_CSS
    BINDINGS = [Binding("y,s", "answer(True)", "Sì"), Binding("n,escape", "answer(False)", "No")]

    def __init__(self, question: str):
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self.question)
            with Horizontal():
                yield Button("Sì [s]", id="yes", variant="primary")
                yield Button("No [n]", id="no")

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

    def compose(self) -> ComposeResult:
        t = Table.grid(padding=(0, 2))
        for k, v in HELP:
            t.add_row(Text(k, Style(bold=True, color=theme.ACCENT)), v)
        with Vertical(id="dialog"):
            yield Label("Tasti")
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
        self.rv, self.use_llm = rv, use_llm

    def compose(self) -> ComposeResult:
        yield VerticalScroll(Static(id="table"), id="counts")
        with VerticalScroll(id="text"):
            yield Static(id="overview")
            yield Static(Text("Momenti critici (Invio per andare alla mossa)", Style(bold=True)))
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
        t.add_column("♔ Bianco" + (" (tu)" if me == "white" else ""), justify="right")
        t.add_column("♚ Nero" + (" (tu)" if me == "black" else ""), justify="right")
        t.add_row(Text("Accuratezza", Style(bold=True)), f"{s.get('accuracy_white') or '–'}", f"{s.get('accuracy_black') or '–'}")
        t.add_row("Rating stimato", f"{s.get('rating_est_white') or '–'}", f"{s.get('rating_est_black') or '–'}")
        for c in theme.CLASS_ORDER:
            meta = theme.CLASS_META[c]
            label = Text()
            label.append(f"{meta.sym:>2} ", Style(color=meta.color, bold=True))
            label.append(meta.label)
            t.add_row(label, str(s["counts"].get("white", {}).get(c, 0)), str(s["counts"].get("black", {}).get(c, 0)))
        self.query_one("#table", Static).update(t)
        tpl = s.get("text") or {"overview": "", "critical": [], "advice": []}
        ov = Text()
        ov.append("Com'è andata\n", Style(bold=True))
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
        adv.append("Consigli\n", Style(bold=True))
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
            self.notify("Riassunto LLM non disponibile" + (" (in corso…)" if self.rv.llm_status == "running" else ""))
