"""Scacchiera a colori: case con sfondo, pezzi Unicode, ultima mossa colorata secondo la classificazione."""
import chess
from rich.color import Color
from rich.style import Style
from rich.text import Text
from textual.widget import Widget

from . import theme


def blend(a: str, b: str, t: float) -> str:
    """Colore a mescolato con b (t = quota di a)."""
    ca, cb = Color.parse(a).get_truecolor(), Color.parse(b).get_truecolor()
    mix = [round(x * t + y * (1 - t)) for x, y in zip(ca, cb)]
    return "#{:02x}{:02x}{:02x}".format(*mix)


class BoardView(Widget):
    DEFAULT_CSS = "BoardView { width: auto; height: auto; }"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.fen = chess.STARTING_FEN
        self.orientation = chess.WHITE
        self.last: str | None = None           # uci
        self.last_cls: str | None = None       # classe della mossa (colore delle case)
        self.best: str | None = None           # uci, case verdi

    def set_position(self, fen: str, last: str | None = None, last_cls: str | None = None,
                     best: str | None = None) -> None:
        self.fen, self.last, self.last_cls, self.best = fen, last, last_cls, best
        self.refresh(layout=True)

    def flip(self) -> None:
        self.orientation = not self.orientation
        self.refresh()

    @property
    def large(self) -> bool:
        w, h = self.app.size
        return h >= 42 and w >= 120

    def cell(self) -> tuple[int, int]:
        return (5, 2) if self.large else (3, 1)

    def get_content_width(self, container, viewport) -> int:
        return 2 + 8 * self.cell()[0]

    def get_content_height(self, container, viewport, width: int) -> int:
        return 8 * self.cell()[1] + 1

    def _bg(self, sq: int, board: chess.Board) -> str:
        light = (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 1
        base = theme.LIGHT if light else theme.DARK
        if board.is_check() and sq == board.king(board.turn):
            return theme.CHECK
        if self.best and sq in (chess.parse_square(self.best[:2]), chess.parse_square(self.best[2:4])):
            return theme.BEST_LIGHT if light else theme.BEST_DARK
        if self.last and sq in (chess.parse_square(self.last[:2]), chess.parse_square(self.last[2:4])):
            meta = theme.CLASS_META.get(self.last_cls or "")
            if meta and self.last_cls not in ("book", "best", "excellent", "good"):
                return blend(meta.color, base, 0.75 if sq == chess.parse_square(self.last[2:4]) else 0.45)
            return theme.LAST_LIGHT if light else theme.LAST_DARK
        return base

    def render(self) -> Text:
        board = chess.Board(self.fen)
        cw, ch = self.cell()
        files = range(8) if self.orientation == chess.WHITE else range(7, -1, -1)
        ranks = range(7, -1, -1) if self.orientation == chess.WHITE else range(8)
        dest = chess.parse_square(self.last[2:4]) if self.last else None
        meta = theme.CLASS_META.get(self.last_cls or "")
        out = Text()
        for r in ranks:
            for line in range(ch):
                out.append(f"{r + 1} " if line == (ch - 1) // 2 else "  ", Style(color=theme.MUTED))
                for f in files:
                    sq = chess.square(f, r)
                    bg = self._bg(sq, board)
                    piece = board.piece_at(sq)
                    if line == (ch - 1) // 2 and piece:
                        fg = theme.WHITE_PIECE if piece.color == chess.WHITE else theme.BLACK_PIECE
                        glyph = theme.PIECES[piece.symbol().lower()]
                        pad = (cw - 1) // 2
                        out.append(" " * pad, Style(bgcolor=bg))
                        out.append(glyph, Style(color=fg, bgcolor=bg, bold=True))
                        out.append(" " * (cw - pad - 1), Style(bgcolor=bg))
                    elif self.large and line == 1 and sq == dest and meta:
                        out.append(meta.sym[:2].rjust(cw), Style(color="#ffffff", bgcolor=bg, bold=True))
                    else:
                        out.append(" " * cw, Style(bgcolor=bg))
                out.append("\n")
        out.append("  ")
        for f in files:
            out.append(chess.FILE_NAMES[f].center(cw), Style(color=theme.MUTED))
        return out
