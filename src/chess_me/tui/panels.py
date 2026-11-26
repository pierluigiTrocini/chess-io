"""Pannelli della revisione: intestazione, barra di valutazione, grafico, lista mosse, commento."""
from rich.style import Style
from rich.text import Text
from textual import events
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from . import theme
from ..i18n import tr
from ..session import Review

BLOCKS = " ▁▂▃▄▅▆▇█"


def badge(cls: str | None) -> Text:
    meta = theme.CLASS_META.get(cls or "")
    if not meta:
        return Text("  ")
    return Text(f"{meta.sym:>2}", Style(color=meta.color, bold=True))


def format_line(rv: Review, sans: list[str], start_ply: int, current: int | None = None, limit: int = 10) -> Text:
    out = Text()
    for i, san in enumerate(sans[:limit]):
        ply = start_ply + i
        num = rv.move_num(ply)
        if ply % 2 == 0:
            out.append(f"{num}. ", Style(color=theme.MUTED))
        elif i == 0:
            out.append(f"{num}... ", Style(color=theme.MUTED))
        out.append(san, Style(reverse=True, bold=True) if i == current else Style())
        out.append(" ")
    if len(sans) > limit:
        out.append("…", Style(color=theme.MUTED))
    return out


def eval_style(rv: Review, cp: int | None, mate: int | None) -> Style:
    w = theme.white_win(cp, mate)
    mine = w if rv.game["player_color"] == "white" else 100 - w
    return Style(color=theme.GOOD if mine >= 55 else theme.BAD if mine <= 45 else None, bold=True)


class GameHeader(Static):
    DEFAULT_CSS = "GameHeader { height: auto; max-height: 4; padding: 0 1; }"

    def show(self, rv: Review, origin: str = "") -> None:
        g, s = rv.game, rv.summary
        me = g["player_color"]
        t = Text()
        for color, dot in (("white", "○"), ("black", "●")):
            name = g[f"{color}_name"] or (tr("Bianco") if color == "white" else tr("Nero"))
            elo = g[f"{color}_elo"]
            st = Style(bold=True, color="#ffffff" if color == "white" else "#b0b0b0")
            t.append(f"{dot} {name}", st)
            if color == me:
                t.append(tr(" (tu)"), Style(color=theme.ACCENT))
            if elo:
                t.append(f" {elo}", Style(color=theme.MUTED))
            if color == "white":
                t.append("  vs  ", Style(color=theme.MUTED))
        code = theme.result_code(g["result"], me)
        t.append(f"   {theme.result_text(g['result'], me)}",
                 Style(bold=True, color=theme.GOOD if code == "win" else theme.BAD if code == "loss" else None))
        t.append(f" · {g['result']}" + (f" · {g['termination_text']}" if g.get("termination_text") else ""), Style(color=theme.MUTED))
        if g.get("opening_name"):
            t.append(f"   {g.get('eco') or ''} {g['opening_name']}".rstrip(), Style(color=theme.MUTED))
        tc = theme.time_class_text(g.get("time_class"))
        if tc:
            t.append(f" · {tc}" + (f" {g['time_control']}" if g.get("time_control") else ""), Style(color=theme.MUTED))
        t.append("\n" + tr("Accuratezza") + "  ", Style(color=theme.MUTED))
        for color, label in (("white", tr("Bianco")), ("black", tr("Nero"))):
            acc, est = s.get(f"accuracy_{color}"), s.get(f"rating_est_{color}")
            t.append(f"{label} ", Style(color=theme.MUTED))
            t.append(f"{acc:.1f}" if acc is not None else "–", Style(bold=True))
            t.append(f" (~{est})   " if est else "   ", Style(color=theme.MUTED))
        t.append(f"{s.get('engine_version') or ''} · " + tr("profondità {depth}", depth=s.get("depth")), Style(color=theme.MUTED))
        if origin:
            t.append(f" · {origin}", Style(color=theme.MUTED))
        self.update(t)


class EvalBar(Widget):
    """Barra verticale: quota del Bianco (in basso se la scacchiera è dal lato del Bianco)."""
    DEFAULT_CSS = "EvalBar { width: 5; height: auto; margin-right: 1; }"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.cp: int | None = 20
        self.mate: int | None = None
        self.white_bottom = True
        self.rows = 8

    def set_eval(self, cp, mate, white_bottom: bool, rows: int) -> None:
        self.cp, self.mate, self.white_bottom, self.rows = cp, mate, white_bottom, rows
        self.refresh(layout=True)

    def get_content_height(self, container, viewport, width: int) -> int:
        return self.rows + 1

    def render(self) -> Text:
        w = theme.white_win(self.cp, self.mate) / 100
        levels = self.rows * 8
        white = round(w * levels)
        t = Text()
        for r in range(self.rows):
            # riga r dall'alto; quota del colore in basso, in ottavi
            from_bottom = self.rows - 1 - r
            bottom_share = white if self.white_bottom else levels - white
            fill = max(0, min(8, bottom_share - from_bottom * 8))
            bot, top = (theme.BAR_WHITE, theme.BAR_BLACK) if self.white_bottom else (theme.BAR_BLACK, theme.BAR_WHITE)
            t.append(" ")
            if fill == 8:   # sfondo invece di █: niente righe tra una linea e l'altra
                t.append("   ", Style(bgcolor=bot))
            else:
                t.append(BLOCKS[fill] * 3, Style(color=bot, bgcolor=top))
            t.append(" \n")
        txt = theme.fmt_eval(self.cp, self.mate)
        t.append(txt.center(5)[:5], Style(bold=True, color=theme.MUTED))
        return t


class EvalGraph(Widget):
    """Andamento della partita (Win% del Bianco), cursore sulla mossa corrente e pallini sui momenti salienti."""
    DEFAULT_CSS = "EvalGraph { height: 4; }"

    class Jump(Message):
        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def __init__(self, **kw):
        super().__init__(**kw)
        self.points: list[float] = [50.0]
        self.move_classes: list[str | None] = [None]
        self.cursor = 0

    def set_data(self, rv: Review) -> None:
        self.points = [50.0] + [theme.white_win(m["eval_cp"], m["eval_mate"]) for m in rv.moves]
        self.move_classes = [None] + [m.get("classification") for m in rv.moves]
        self.refresh()

    def set_cursor(self, idx: int) -> None:
        self.cursor = idx + 1
        self.refresh()

    def _col_of(self, i: int, width: int) -> int:
        n = len(self.points) - 1
        return 0 if n == 0 else round(i * (width - 1) / n)

    def render(self) -> Text:
        width = max(10, self.size.width)
        rows = max(2, self.size.height - 1)
        n = len(self.points) - 1
        cur_col = self._col_of(self.cursor, width)
        heights = []
        for x in range(width):
            pos = 0.0 if n == 0 else x * n / (width - 1)
            i = min(int(pos), max(0, n - 1))
            frac = pos - i
            v = self.points[i] if n == 0 else self.points[i] * (1 - frac) + self.points[i + 1] * frac
            heights.append(round(v / 100 * rows * 8))
        t = Text()
        mid = rows * 4
        for r in range(rows):
            from_bottom = rows - 1 - r
            for x in range(width):
                fill = max(0, min(8, heights[x] - from_bottom * 8))
                on_cursor = x == cur_col
                bg = theme.ACCENT if on_cursor else theme.GRAPH_BLACK
                fg = theme.ACCENT_LIGHT if on_cursor else theme.GRAPH_WHITE
                if fill == 8:   # casella piena: sfondo, non █, così non restano righe tra una linea e l'altra
                    t.append(" ", Style(bgcolor=fg))
                elif fill == 0 and from_bottom * 8 <= mid < (from_bottom + 1) * 8 and not on_cursor:
                    t.append("─", Style(color=theme.GRAPH_MID, bgcolor=bg))
                else:
                    t.append(BLOCKS[fill], Style(color=fg, bgcolor=bg))
            t.append("\n")
        marks = [" "] * width
        styles: list[Style] = [Style()] * width
        for i, cls in enumerate(self.move_classes):
            if cls in theme.SALIENT:
                c = self._col_of(i, width)
                marks[c], styles[c] = "●", Style(color=theme.CLASS_META[cls].color)
        marks[cur_col], styles[cur_col] = "▲", Style(color=theme.ACCENT, bold=True)
        for ch, st in zip(marks, styles):
            t.append(ch, st)
        return t

    def on_click(self, event: events.Click) -> None:
        n = len(self.points) - 1
        width = max(10, self.size.width)
        i = 0 if n == 0 else round(event.x * n / (width - 1))
        self.post_message(self.Jump(max(0, min(n, i)) - 1))


class MoveList(VerticalScroll):
    """Lista a due colonne con il simbolo della classe; clic su una mossa per andarci."""
    DEFAULT_CSS = """
    MoveList { width: 1fr; min-width: 30; height: 1fr; }
    MoveList > Static { width: 100%; }
    """

    class Jump(Message):
        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def __init__(self, **kw):
        super().__init__(**kw)
        self.rv: Review | None = None
        self.idx = -1
        self.inner = Static()
        self.slots: list[int | None] = []

    def compose(self):
        yield self.inner

    def set_review(self, rv: Review) -> None:
        self.rv = rv
        pad = 1 if rv.moves and rv.moves[0]["ply"] % 2 == 1 else 0
        self.slots = [None] * pad + list(range(len(rv.moves)))
        self.paint()

    def set_index(self, idx: int) -> None:
        self.idx = idx
        self.paint()
        if idx >= 0 and self.slots:
            row = (idx + (1 if self.slots[0] is None else 0)) // 2
            self.scroll_to(y=max(0, row - self.size.height // 2), animate=False)

    def paint(self) -> None:
        rv = self.rv
        if rv is None:
            return
        t = Text()
        for r in range(0, len(self.slots), 2):
            pair = self.slots[r:r + 2]
            first = next(i for i in pair if i is not None)
            t.append(f"{rv.move_num(rv.moves[first]['ply']):>3}. ", Style(color=theme.MUTED))
            for i in pair:
                if i is None:
                    t.append(f"{'…':<8}   ", Style(color=theme.MUTED))
                    continue
                m = rv.moves[i]
                st = Style(bgcolor="#3a3d44", bold=True) if i == self.idx else Style()
                t.append(f"{m['san']:<8}", st)
                t.append(" ")
                t.append_text(badge(m.get("classification")))
                t.append(" ")
            t.append("\n")
        self.inner.update(t)

    def on_click(self, event: events.Click) -> None:
        if not self.slots:
            return
        y = event.y + round(self.scroll_y)
        x = event.x
        col = 0 if x < 5 + 12 else 1
        k = y * 2 + col
        if 0 <= k < len(self.slots) and self.slots[k] is not None:
            self.post_message(self.Jump(self.slots[k]))


class CommentPanel(Static):
    DEFAULT_CSS = "CommentPanel { height: auto; min-height: 5; padding: 0 1; margin-top: 1; border-top: solid #3a3d44; }"

    def show_start(self) -> None:
        self.update(Text(tr("Posizione iniziale. Usa ← → per scorrere le mosse, n per il prossimo momento critico."),
                         Style(color=theme.MUTED)))

    def show_variation(self, rv: Review, title: str, sans: list[str], start_ply: int, i: int) -> None:
        t = Text()
        t.append(title, Style(bold=True))
        t.append("   " + tr("← → per scorrere · Esc per tornare alla partita") + "\n", Style(color=theme.MUTED))
        t.append_text(format_line(rv, sans, start_ply, current=i, limit=len(sans)))
        self.update(t)

    def show_move(self, rv: Review, i: int, use_llm: bool, paused: bool = False) -> None:
        m = rv.moves[i]
        cls = m.get("classification")
        meta = theme.CLASS_META.get(cls or "")
        t = Text()
        if paused:
            t.append(tr("⏸ Momento saliente: premi spazio per continuare") + "\n", Style(color=theme.ACCENT))
        if meta:
            t.append(f" {meta.sym} ", Style(color="#ffffff", bgcolor=meta.color, bold=True))
            t.append(f" {meta.label}", Style(color=meta.color, bold=True))
            t.append(" · ")
        t.append(rv.label(i), Style(bold=True))
        before = (m.get("best_eval_cp"), m.get("best_eval_mate"))
        after = (m.get("eval_cp"), m.get("eval_mate"))
        t.append("    " + tr("prima") + " ", Style(color=theme.MUTED))
        t.append(theme.fmt_eval(*before) or "–", eval_style(rv, *before))
        t.append(" → " + tr("dopo") + " ", Style(color=theme.MUTED))
        t.append(theme.fmt_eval(*after) or "–", eval_style(rv, *after))
        t.append("\n")
        text = m.get("comment") or ""
        chk = m.get("llm_check_json")
        if use_llm and chk is not None:
            if m.get("comment_llm"):
                text = m["comment_llm"]
                t.append(text + "\n")
                t.append(tr("✍ testo LLM verificato") + "\n", Style(color=theme.MUTED, italic=True))
            else:
                t.append(text + "\n")
                t.append(tr("✍ testo LLM scartato ({reason}): template",
                            reason=chk.get("reason") or tr("controllo non superato")) + "\n",
                         Style(color=theme.MUTED, italic=True))
        else:
            t.append(text + "\n")
        is_err = cls in theme.ERRORS
        if m.get("best_san") and m.get("best_uci") != m["uci"] and cls != "book" and m.get("best_pv_san"):
            t.append(f"{tr('Migliore'):<14}", Style(color=theme.GOOD, bold=True))
            t.append_text(format_line(rv, m["best_pv_san"], m["ply"]))
            t.append("  " + tr("[b] esplora") + "\n", Style(color=theme.MUTED))
        if is_err and m.get("refutation_pv_san"):
            t.append(f"{tr('Confutazione'):<14}", Style(color=theme.BAD, bold=True))
            t.append_text(format_line(rv, m["refutation_pv_san"], m["ply"] + 1))
            t.append("  " + tr("[r] esplora") + "\n", Style(color=theme.MUTED))
        if m.get("threat_san"):
            t.append(f"{tr('Minaccia'):<14}", Style(color=theme.CLASS_META["mistake"].color, bold=True))
            t.append(m["threat_san"] + "\n")
        t.rstrip()
        self.update(t)
