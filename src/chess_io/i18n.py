"""Lingua dell'interfaccia e dei commenti: italiano (predefinito), inglese, spagnolo.

I testi nel codice sono in italiano e passano da `tr()`, che li cerca nei cataloghi `locales/en.py` e
`locales/es.py` (chiave = testo italiano, oppure "contesto|testo" con `_ctx`). I segnaposto sono quelli di `str.format`: `tr("in {sq}", sq="e4")`.
Un testo senza traduzione resta in italiano (un test controlla che non ne manchino).

La lingua si sceglie, in ordine: `--lang` → variabile CHESSIO_LANG → impostazione salvata
(`chess-io lang`, installer, schermata di ricerca) → italiano. Va scelta prima dell'analisi: commenti e
riassunto si scrivono nella lingua corrente al momento dell'analisi.
"""
import os

import chess

LANGS = ("it", "en", "es")
DEFAULT = "it"
NAMES = {"it": "Italiano", "en": "English", "es": "Español"}

_lang = DEFAULT


def normalize(code: str | None) -> str | None:
    """'en_US.UTF-8' → 'en'; None se la lingua non è supportata."""
    if not code:
        return None
    c = code.strip().lower().replace("-", "_").split("_")[0].split(".")[0]
    return c if c in LANGS else None


def lang() -> str:
    return _lang


def set_lang(code: str | None) -> str:
    global _lang
    _lang = normalize(code) or DEFAULT
    return _lang


def saved() -> str | None:
    """Lingua salvata come predefinita (None se non è mai stata scelta)."""
    from . import runtime
    return normalize(runtime.load_settings().get("lang"))


def save(code: str) -> bool:
    from . import runtime
    c = normalize(code)
    if c is None:
        return False
    return runtime.save_settings(lang=c)


def resolve(cli: str | None = None) -> str:
    """Lingua da usare: opzione della CLI, CHESSIO_LANG, impostazione salvata, italiano."""
    return normalize(cli) or normalize(os.environ.get("CHESSIO_LANG")) or saved() or DEFAULT


def _catalog(code: str) -> dict[str, str]:
    if code == "en":
        from .locales.en import T
    elif code == "es":
        from .locales.es import T
    else:
        return {}
    return T


def tr(msg: str, /, _ctx: str | None = None, **kw) -> str:
    """Traduce un testo italiano nella lingua corrente e ne riempie i segnaposto.
    `_ctx` distingue due usi dello stesso testo italiano che in altre lingue si traducono diversamente
    (nel catalogo la chiave è "contesto|testo")."""
    if _lang == DEFAULT:
        out = msg
    else:
        out = _catalog(_lang).get(f"{_ctx}|{msg}" if _ctx else msg, msg)
    return out.format(**kw) if kw else out


# ---------- pezzi: la grammatica cambia da lingua a lingua ----------
_P, _N, _B, _R, _Q, _K = chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING
PIECE_NAMES = {
    "it": {_P: "pedone", _N: "cavallo", _B: "alfiere", _R: "torre", _Q: "donna", _K: "re"},
    "en": {_P: "pawn", _N: "knight", _B: "bishop", _R: "rook", _Q: "queen", _K: "king"},
    "es": {_P: "peón", _N: "caballo", _B: "alfil", _R: "torre", _Q: "dama", _K: "rey"},
}
PIECE_THE = {   # con l'articolo determinativo
    "it": {_P: "il pedone", _N: "il cavallo", _B: "l'alfiere", _R: "la torre", _Q: "la donna", _K: "il re"},
    "en": {_P: "the pawn", _N: "the knight", _B: "the bishop", _R: "the rook", _Q: "the queen", _K: "the king"},
    "es": {_P: "el peón", _N: "el caballo", _B: "el alfil", _R: "la torre", _Q: "la dama", _K: "el rey"},
}
PIECE_A = {     # con l'articolo indeterminativo
    "it": {_P: "un pedone", _N: "un cavallo", _B: "un alfiere", _R: "una torre", _Q: "una donna", _K: "un re"},
    "en": {_P: "a pawn", _N: "a knight", _B: "a bishop", _R: "a rook", _Q: "a queen", _K: "a king"},
    "es": {_P: "un peón", _N: "un caballo", _B: "un alfil", _R: "una torre", _Q: "una dama", _K: "un rey"},
}


def piece_name(pt: int) -> str:
    return PIECE_NAMES[_lang][pt]


def piece_the(pt: int) -> str:
    return PIECE_THE[_lang][pt]


def piece_a(pt: int) -> str:
    return PIECE_A[_lang][pt]


def piece_on(pt: int, square: int) -> str:
    """"l'alfiere in f4" · "the bishop on f4" · "el alfil en f4"."""
    return tr("{piece} in {square}", piece=piece_the(pt), square=chess.square_name(square))


def join(items: list[str]) -> str:
    """"a, b e c" nella lingua corrente (senza doppioni)."""
    items = list(dict.fromkeys(items))
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + tr(" e ") + items[-1]
