"""Etichette, simboli e colori delle classi di mossa e della scacchiera."""
from dataclasses import dataclass

from ..review.winprob import win_percent


@dataclass(frozen=True)
class ClassMeta:
    label: str
    sym: str
    color: str


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
GOOD = "#81b64c"
BAD = "#ca3431"
ACCENT = "#5b8bb0"
MUTED = "#8a8a8a"

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


def result_text(result: str, color: str) -> str:
    if result == "*":
        return "Non terminata"
    if result == "1/2-1/2":
        return "Patta"
    return "Vittoria" if (result == "1-0") == (color == "white") else "Sconfitta"


TIME_CLASS_IT = {"bullet": "Bullet", "blitz": "Blitz", "rapid": "Rapid", "classical": "Classica", "daily": "Daily"}
