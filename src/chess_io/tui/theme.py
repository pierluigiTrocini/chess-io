"""Etichette, simboli e colori delle classi di mossa e della scacchiera."""
from dataclasses import dataclass

from ..i18n import tr
from ..review.winprob import win_percent


@dataclass(frozen=True)
class ClassMeta:
    label_it: str
    sym: str
    color: str

    @property
    def label(self) -> str:
        return tr(self.label_it)


CLASS_META: dict[str, ClassMeta] = {
    "brilliant": ClassMeta("Brillante", "!!", "#1baca6"),
    "great": ClassMeta("Ottima", "!", "#5b8bb0"),
    "best": ClassMeta("Migliore", "★", "#81b64c"),
    "excellent": ClassMeta("Eccellente", "✓", "#81b64c"),
    "good": ClassMeta("Buona", "✓", "#95b776"),
    "book": ClassMeta("Teoria", "≡", "#a88865"),
    "inaccuracy": ClassMeta("Imprecisione", "?!", "#e6b23a"),
    "mistake": ClassMeta("Errore", "?", "#e58f2a"),
    "miss": ClassMeta("Occasione persa", "✗", "#e3735e"),
    "blunder": ClassMeta("Grave errore", "??", "#ca3431"),
}
CLASS_ORDER = ["brilliant", "great", "best", "excellent", "good", "book", "inaccuracy", "mistake", "miss", "blunder"]
ERRORS = {"inaccuracy", "mistake", "blunder", "miss"}
SALIENT = ERRORS | {"brilliant", "great"}

LIGHT = "#b8c290"
DARK = "#6f8f50"
LAST_LIGHT = "#f5f682"
LAST_DARK = "#b9ca43"
BEST_LIGHT = "#a9d8a0"
BEST_DARK = "#6fae63"
CHECK = "#e0504d"
WHITE_PIECE = "#ffffff"
BLACK_PIECE = "#111111"
BAR_WHITE = "#f0f0f0"
BAR_BLACK = "#403d39"
GRAPH_WHITE = "#b4b1aa"   # grafico più tenue della barra: non deve dominare lo schermo
GRAPH_BLACK = "#2b2a28"
GRAPH_MID = "#55524d"
ACCENT_LIGHT = "#a3c4de"
GOOD = "#81b64c"
BAD = "#ca3431"
ACCENT = "#5b8bb0"
MUTED = "#8a8a8a"

def luminance(color: str) -> float:
    """Luminanza relativa (WCAG) di un colore #rrggbb."""
    def ch(v: int) -> float:
        x = v / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def ink(bg: str) -> str:
    """Bianco o nero, quello che si legge meglio su bg."""
    return "#ffffff" if contrast("#ffffff", bg) >= contrast("#111111", bg) else "#111111"


PIECES = {"k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}


def fmt_eval(cp: int | None, mate: int | None) -> str:
    if mate is not None:
        return "#" if mate == 0 else f"{'' if mate > 0 else '-'}M{abs(mate)}"
    if cp is None:
        return ""
    return f"{'+' if cp > 0 else ''}{cp / 100:.1f}"


def white_win(cp: int | None, mate: int | None) -> float:
    """Win% del Bianco (0..100), curva Lichess."""
    if mate is not None:
        return 100.0 if mate > 0 or (mate == 0 and (cp or 0) >= 0) else 0.0
    return win_percent(cp or 0)


def result_code(result: str, color: str) -> str:
    """'unfinished' | 'draw' | 'win' | 'loss' dal punto di vista di `color`."""
    if result not in ("1-0", "0-1", "1/2-1/2"):
        return "unfinished"
    if result == "1/2-1/2":
        return "draw"
    return "win" if (result == "1-0") == (color == "white") else "loss"


RESULT_IT = {"unfinished": "Non terminata", "draw": "Patta", "win": "Vittoria", "loss": "Sconfitta"}


def result_text(result: str, color: str) -> str:
    return tr(RESULT_IT[result_code(result, color)])


TIME_CLASS_IT = {"bullet": "Bullet", "blitz": "Blitz", "rapid": "Rapid", "classical": "Classica", "daily": "Daily"}


def time_class_text(tc: str | None) -> str | None:
    return tr(TIME_CLASS_IT[tc]) if tc in TIME_CLASS_IT else None
