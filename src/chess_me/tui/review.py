"""Schermata di revisione: scacchiera, barra, lista mosse, grafico e commento; navigazione come nel web."""
import textwrap
from dataclasses import dataclass

import chess
from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from . import theme
from ..i18n import tr
from ..session import Review
from .board import BoardView, fit_cell
from .panels import CommentPanel, EvalBar, EvalGraph, GameHeader, MoveList
from .screens import HelpScreen, SummaryScreen, localize_bindings

AUTOPLAY_S = 1.4
SIDE_MIN = 44        # colonne lasciate a mosse e commento accanto alla scacchiera
BOARD_CHROME = 8     # barra di valutazione (5 + 1 di margine) e padding della colonna


@dataclass
class Variation:
    title: str
    fens: list[str]
    ucis: list[str]
    sans: list[str]
    start_ply: int
    i: int = 0


class ReviewScreen(Screen):
    DEFAULT_CSS = """
    #top { height: 1fr; }
    #boardcol { width: auto; height: auto; padding: 0 1; }
    #boardrow { width: auto; height: auto; }
    #brief { height: auto; margin-top: 1; }
    #side { width: 1fr; height: 100%; padding-right: 1; }
    #movestitle { height: 1; color: #8a8a8a; }
    #llmstatus { height: 1; color: #8a8a8a; }
    #side MoveList { height: 1fr; min-height: 4; }
    #side CommentPanel { max-height: 60%; }
    EvalGraph { margin: 1 1 0 1; }
    """
    BINDINGS = [
        Binding("left", "step(-1)", "Mossa", key_display="←/→"),
        Binding("right", "step(1)", "", show=False),
        Binding("home", "go_start", "", show=False),
        Binding("end", "go_end", "", show=False),
        Binding("space", "toggle_play", "Autoplay", key_display="spazio"),
        Binding("n", "critical(1)", "Critico", key_display="n/N"),
        Binding("N", "critical(-1)", "", show=False),
        Binding("b", "variation('best')", "Migliore"),
        Binding("r", "variation('refute')", "Confutazione"),
        Binding("escape", "leave_variation", "", show=False),
        Binding("s", "summary", "Riassunto"),
        Binding("l", "toggle_llm", "LLM"),
        Binding("f", "flip", "Gira"),
        Binding("c", "change_color", "", show=False),
        Binding("question_mark", "help", "Aiuto", key_display="?"),
        Binding("q", "app.quit", "Esci"),
    ]

    def __init__(self, rv: Review, origin: str = "", llm_enabled: bool = False):
        super().__init__()
        localize_bindings(self)
        self.rv = rv
        self.origin = origin
        self.llm_enabled = llm_enabled
        self.use_llm = llm_enabled
        self.fens = rv.fens()
        self.idx = -1                  # -1 = posizione iniziale; i = dopo la mossa i
        self.variation: Variation | None = None
        self.playing = False
        self.paused_on_salient = False
        self._timer = None

    def compose(self) -> ComposeResult:
        yield GameHeader(id="header")
        with Horizontal(id="top"):
            with Vertical(id="boardcol"):
                with Horizontal(id="boardrow"):
                    yield EvalBar(id="evalbar")
                    yield BoardView(id="board")
                yield Static(id="brief")
            with Vertical(id="side"):
                yield Static(Text(tr("Mosse"), Style(bold=True)), id="movestitle")
                yield MoveList(id="moves")
                yield Static(id="llmstatus")
                yield CommentPanel(id="comment")
        yield EvalGraph(id="graph")
        yield Footer()

    def on_mount(self) -> None:
        board = self.query_one(BoardView)
        board.orientation = chess.WHITE if self.rv.game["player_color"] == "white" else chess.BLACK
        self.query_one(GameHeader).show(self.rv, self.origin)
        self.query_one(MoveList).set_review(self.rv)
        self.query_one(EvalGraph).set_data(self.rv)
        self.refresh_llm_status()
        self.render_brief()
        self.render_state()

    def brief_lines(self) -> list[str]:
        return [l for l in ((self.rv.summary.get("text") or {}).get("brief") or "").split("\n") if l]

    def render_brief(self) -> None:
        """Il riassunto del riassunto sotto la scacchiera (s per quello completo)."""
        t = Text()
        lines = self.brief_lines()
        if lines:
            t.append(tr("In breve") + "\n", Style(bold=True, color=theme.MUTED))
            t.append("\n".join(lines))
        self.query_one("#brief", Static).update(t)

    def on_resize(self) -> None:
        self.render_state()

    def fit_board(self) -> None:
        """Case più grandi possibile nello spazio tra intestazione e grafico, lasciando posto alle mosse."""
        w, h = self.app.size
        header = self.query_one(GameHeader).outer_size.height or 2
        graph = self.query_one(EvalGraph).outer_size.height or 5
        avail_w, avail_h = w - SIDE_MIN - BOARD_CHROME, h - header - graph - 1
        lines = self.brief_lines()
        cell, brief = fit_cell(avail_w, avail_h), self.query_one("#brief", Static)
        for _ in range(3):   # il riassunto va a capo in base alla larghezza della scacchiera, che dipende dallo spazio
            width = 2 + 8 * cell[0] + BOARD_CHROME - 2
            rows = 2 + sum(len(textwrap.wrap(l, width)) or 1 for l in lines) if lines else 0
            new = fit_cell(avail_w, avail_h - rows)
            if new == cell:
                break
            cell = new
        brief.display = bool(lines) and 8 * cell[1] + 1 + rows <= avail_h
        brief.styles.width = width
        self.query_one(BoardView).set_cell(cell)

    # ---------- stato ----------
    def render_state(self) -> None:
        self.fit_board()
        board = self.query_one(BoardView)
        rv = self.rv
        if self.variation:
            v = self.variation
            board.set_position(v.fens[v.i], last=v.ucis[v.i])
        elif self.idx < 0:
            board.set_position(self.fens[0])
        else:
            m = rv.moves[self.idx]
            cls = m.get("classification")
            best = None
            if cls in theme.ERRORS:
                best = m.get("best_uci")
            elif cls in ("good", "excellent") and m.get("best_uci") != m["uci"]:
                best = m.get("best_uci")
            board.set_position(self.fens[self.idx + 1], last=m["uci"], last_cls=cls, best=best)
        if not self.variation:
            m = rv.moves[self.idx] if self.idx >= 0 else None
            self.query_one(EvalBar).set_eval(m["eval_cp"] if m else 20, m["eval_mate"] if m else None,
                                             board.orientation == chess.WHITE, 8 * board.cell()[1])
        moves = self.query_one(MoveList)
        moves.set_index(self.idx)
        self.query_one(EvalGraph).set_cursor(self.idx)
        comment = self.query_one(CommentPanel)
        if self.variation:
            v = self.variation
            comment.show_variation(rv, v.title, v.sans, v.start_ply, v.i)
        elif self.idx < 0:
            comment.show_start()
        else:
            comment.show_move(rv, self.idx, self.use_llm, paused=self.paused_on_salient and not self.playing)

    def refresh_llm_status(self) -> None:
        rv = self.rv
        st = self.query_one("#llmstatus", Static)
        if not self.llm_enabled:
            st.display = False
            return
        done, total = rv.llm_progress
        text = {
            "downloading": tr("⬇ Scarico il modello LLM (una volta sola)…"),
            "running": tr("✍ LLM al lavoro {done}/{total}", done=done, total=total),
            "done": tr("✍ LLM: {mode} (l per cambiare)", mode=tr("attivo") if self.use_llm else tr("template")),
            "error": tr("✍ LLM non disponibile: {error}", error=rv.llm_error),
        }.get(rv.llm_status, "")
        if rv.llm_status == "downloading":
            from ..llm import jobs as llm_jobs
            d = llm_jobs.download_state()
            if d.get("total"):
                text += f" {100 * d['done'] // d['total']}%"
        st.update(text)

    def llm_updated(self) -> None:
        self.refresh_llm_status()
        if not self.variation and self.idx >= 0:
            self.render_state()

    def go(self, i: int, autoplay: bool = False) -> None:
        if not autoplay:
            self.stop_play()
            self.paused_on_salient = False
        self.variation = None
        self.idx = max(-1, min(len(self.rv.moves) - 1, i))
        self.render_state()

    # ---------- azioni ----------
    def action_step(self, d: int) -> None:
        if self.variation:
            v = self.variation
            v.i = max(0, min(len(v.fens) - 1, v.i + d))
            self.render_state()
        else:
            self.go(self.idx + d)

    def action_go_start(self) -> None:
        self.go(-1)

    def action_go_end(self) -> None:
        self.go(len(self.rv.moves) - 1)

    def action_critical(self, d: int) -> None:
        rng = range(self.idx + 1, len(self.rv.moves)) if d > 0 else range(self.idx - 1, -1, -1)
        for i in rng:
            if self.rv.moves[i].get("classification") in theme.SALIENT:
                self.go(i)
                return
        self.notify(tr("Nessun altro momento critico più avanti") if d > 0 else tr("Nessun altro momento critico prima"))

    def action_variation(self, kind: str) -> None:
        if self.idx < 0:
            return
        m = self.rv.moves[self.idx]
        if kind == "best":
            if not m.get("best_pv_uci") or m.get("best_uci") == m["uci"]:
                self.notify(tr("Hai giocato la mossa migliore"))
                return
            title, fen, ucis, start = tr("Migliore: {move}", move=m.get("best_san")), m["fen_before"], m["best_pv_uci"], m["ply"]
        else:
            if m.get("classification") not in theme.ERRORS or not m.get("refutation_pv_uci"):
                self.notify(tr("Nessuna confutazione per questa mossa"))
                return
            title, fen, ucis, start = tr("Confutazione"), self.fens[self.idx + 1], m["refutation_pv_uci"], m["ply"] + 1
        self.stop_play()
        b = chess.Board(fen)
        fens, ok, sans = [], [], []
        for u in ucis:
            mv = chess.Move.from_uci(u)
            if mv not in b.legal_moves:
                break
            sans.append(b.san(mv))
            b.push(mv)
            fens.append(b.fen())
            ok.append(u)
        if not fens:
            return
        self.variation = Variation(title, fens, ok, sans, start)
        self.render_state()

    def action_leave_variation(self) -> None:
        if self.variation:
            self.variation = None
            self.render_state()

    def action_flip(self) -> None:
        self.query_one(BoardView).flip()
        self.render_state()

    def action_toggle_llm(self) -> None:
        if not self.llm_enabled:
            self.notify(tr("Avvia con --llm per i commenti riscritti dall'LLM"))
            return
        self.use_llm = not self.use_llm
        self.refresh_llm_status()
        self.render_state()

    def action_change_color(self) -> None:
        new = "black" if self.rv.game["player_color"] == "white" else "white"
        self.rv.set_color(new)
        self.query_one(BoardView).orientation = chess.WHITE if new == "white" else chess.BLACK
        self.query_one(GameHeader).show(self.rv, self.origin)
        self.render_brief()
        self.notify(tr("Ora sei il Bianco: riassunto ricalcolato") if new == "white"
                    else tr("Ora sei il Nero: riassunto ricalcolato"))
        self.render_state()

    def action_summary(self) -> None:
        self.stop_play()

        def back(i: int | None) -> None:
            if i is not None and i >= 0:
                self.go(i)
        self.app.push_screen(SummaryScreen(self.rv, self.use_llm), back)

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen())

    # ---------- riproduzione automatica ----------
    def action_toggle_play(self) -> None:
        if self.playing:
            self.stop_play()
            self.render_state()
            return
        if self.idx >= len(self.rv.moves) - 1:
            self.go(-1)
        self.playing = True
        self.paused_on_salient = False
        self.variation = None
        self._timer = self.set_interval(AUTOPLAY_S, self._tick)

    def stop_play(self) -> None:
        self.playing = False
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _tick(self) -> None:
        if self.idx >= len(self.rv.moves) - 1:
            self.stop_play()
            self.render_state()
            return
        self.go(self.idx + 1, autoplay=True)
        if self.rv.moves[self.idx].get("classification") in theme.SALIENT:
            self.stop_play()
            self.paused_on_salient = True
            self.render_state()

    # ---------- messaggi dei widget ----------
    def on_move_list_jump(self, msg: MoveList.Jump) -> None:
        self.go(msg.index)

    def on_eval_graph_jump(self, msg: EvalGraph.Jump) -> None:
        self.go(msg.index)
