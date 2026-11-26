"""Mosse a parole per chi non legge la notazione: "Be3" → "l'alfiere in e3 (Be3)".

Lavora sulla sola SAN: pezzo, presa e casa d'arrivo bastano, la posizione non serve.
`annotate` si applica ai testi LLM già verificati (è deterministica, quindi non passa dal controllo).
"""
import re

import chess

from .. import i18n
from ..i18n import piece_name, piece_the, tr

# Regex SAN mostrata anche in UI ("Mostra verifica SAN")
SAN_REGEX = r"\b(?:O-O-O|O-O|[KQRBN][a-h]?[1-8]?x?[a-h][1-8]|[a-h]x[a-h][1-8](?:=[QRBN])?|[a-h][1-8](?:=[QRBN])?)[+#]?"
SAN_RE = re.compile(SAN_REGEX)

_PIECE = {"K": chess.KING, "Q": chess.QUEEN, "R": chess.ROOK, "B": chess.BISHOP, "N": chess.KNIGHT}
_PIECE_RE = re.compile(r"^([KQRBN])[a-h]?[1-8]?(x?)([a-h][1-8])$")
_PAWN_RE = re.compile(r"^(?:[a-h](x))?([a-h][1-8])(?:=([QRBN]))?$")
# numero di mossa subito prima della SAN: "14. Bf4", "14...Bf4"
_NUM_RE = re.compile(r"\b\d+\.(?:\.\.)?\s*$")
# parole dopo le quali una casa nuda ("in f4") è una casa, non una mossa di pedone
_SQUARE_WORDS = {
    "it": {"in", "su", "da", "a", "verso", "casa", "di", "per", "tra", "fra", "e", "la", "nella", "sulla",
           "della", "dalla", "alla", "colonna", "traversa"},
    "en": {"on", "to", "from", "at", "of", "the", "square", "file", "rank", "and", "in", "into", "onto", "towards",
           "for", "via", "reach", "reaches"},
    "es": {"en", "a", "de", "desde", "hacia", "casilla", "la", "el", "del", "al", "columna", "fila", "y", "por",
           "entre", "sobre", "para"},
}
_LETTERS = "A-Za-zàèéìòùáíóúñü"


def describe_san(san: str) -> str | None:
    """Descrizione a parole della mossa, None se la SAN non è riconosciuta."""
    s = san.rstrip("+#!?")
    if s == "O-O-O":
        return tr("l'arrocco lungo")
    if s == "O-O":
        return tr("l'arrocco corto")
    m = _PIECE_RE.match(s)
    if m:
        name = piece_the(_PIECE[m.group(1)])
        return tr("{piece} che prende in {square}", piece=name, square=m.group(3)) if m.group(2) \
            else tr("{piece} in {square}", _ctx="move", piece=name, square=m.group(3))
    m = _PAWN_RE.match(s)
    if m:
        pawn = piece_the(chess.PAWN)
        base = tr("{piece} che prende in {square}", piece=pawn, square=m.group(2)) if m.group(1) \
            else tr("{piece} in {square}", _ctx="move", piece=pawn, square=m.group(2))
        if m.group(3):
            base += tr(" con promozione a {piece}", piece=piece_name(_PIECE[m.group(3)]))
        return base
    return None


def _in_variation(text: str, pos: int) -> bool:
    """La posizione è dentro una parentesi che contiene solo mosse e numeri, es. "(12. Be3 Nf6 13. O-O)"."""
    open_ = text.rfind("(", 0, pos)
    if open_ < 0 or text.rfind(")", 0, pos) > open_:
        return False
    close = text.find(")", pos)
    inner = text[open_ + 1:close if close >= 0 else len(text)]
    rest = re.sub(r"\d+\.(?:\.\.)?", " ", SAN_RE.sub(" ", inner))
    return not re.search(f"[{_LETTERS}]", rest)


def annotate(text: str) -> str:
    """Mette la mossa a parole davanti alla notazione, alla prima occorrenza di ogni mossa.
    Le mosse dentro una variante tra parentesi restano in notazione."""
    out, last, seen = [], 0, set()
    square_words = _SQUARE_WORDS[i18n.lang()]
    for m in SAN_RE.finditer(text):
        san = m.group(0)
        key = san.rstrip("+#")
        desc = describe_san(san)
        start = m.start()
        if desc is None or key in seen or _in_variation(text, start):
            continue
        before = text[:start]
        prev_word = re.search(f"([{_LETTERS}']+)\\s*$", before)
        if san[0] in "abcdefgh" and "x" not in san and "=" not in san and prev_word and prev_word.group(1).lower().split("'")[-1] in square_words:
            continue  # "l'alfiere in f4": è una casa
        if desc in before[-40:].lower():
            seen.add(key)
            continue  # già descritta dal testo
        seen.add(key)
        num = _NUM_RE.search(before)
        cut = num.start() if num else start
        if not text[:cut].strip() or text[:cut].rstrip()[-1] in ".!?:":
            desc = desc[0].upper() + desc[1:]  # inizio di frase
        if num:
            out.append(text[last:num.start()])
            out.append(f"{desc} ({num.group(0)}{san})")
        else:
            out.append(text[last:start])
            out.append(f"{desc} ({san})")
        last = m.end()
    out.append(text[last:])
    return "".join(out)
