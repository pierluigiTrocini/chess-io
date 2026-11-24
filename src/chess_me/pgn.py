"""Parsing dei PGN esportati da Lichess, chess.com o altri programmi."""
import hashlib
import io
import re
from dataclasses import dataclass, field

import chess
import chess.pgn

MAX_GAMES = 100
MAX_PGN_BYTES = 5_000_000

LICHESS_SITE = re.compile(r"lichess\.org/(?:game/(?:export/)?)?([A-Za-z0-9]{8})")
CHESSCOM_LINK = re.compile(r"chess\.com/(?:[a-z]{2}/)?(?:analysis/)?(?:(live|daily)/)?game/(?:(live|daily)/)?(\d+)")

TERMINATION_IT_FROM_BOARD = {
    chess.Termination.CHECKMATE: "checkmate",
    chess.Termination.STALEMATE: "stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient",
    chess.Termination.SEVENTYFIVE_MOVES: "fifty",
    chess.Termination.FIFTY_MOVES: "fifty",
    chess.Termination.FIVEFOLD_REPETITION: "repetition",
    chess.Termination.THREEFOLD_REPETITION: "repetition",
}


@dataclass
class Move:
    move: chess.Move
    clock_ms: int | None


@dataclass
class Candidate:
    index: int
    pgn: str = ""
    white: str = "?"
    black: str = "?"
    white_elo: int | None = None
    black_elo: int | None = None
    played_at: str | None = None
    result: str = "*"
    termination: str | None = None
    time_control: str | None = None
    time_initial_s: int | None = None
    time_increment_s: int | None = None
    time_class: str | None = None
    eco: str | None = None
    opening: str | None = None
    start_fen: str | None = None
    source: str = "pgn"
    source_id: str | None = None
    source_url: str | None = None
    moves: list[Move] = field(default_factory=list)
    error: str | None = None

    @property
    def plies(self) -> int:
        return len(self.moves)

    def summary(self) -> dict:
        return {
            "index": self.index, "pgn": self.pgn, "white": self.white, "black": self.black,
            "white_elo": self.white_elo, "black_elo": self.black_elo, "played_at": self.played_at,
            "result": self.result, "termination": self.termination, "time_control": self.time_control,
            "time_class": self.time_class, "eco": self.eco, "opening": self.opening, "plies": self.plies,
            "start_fen": self.start_fen, "source": self.source, "source_id": self.source_id,
            "source_url": self.source_url, "error": self.error,
        }


def _int(v: str | None) -> int | None:
    try:
        return int(v) if v and v.strip().isdigit() else None
    except ValueError:
        return None


def parse_time_control(tc: str | None) -> tuple[int | None, int | None, str | None]:
    """'600+5' → (600, 5, 'rapid'); '1/86400' → (None, None, 'daily'); '-' → (None, None, None)."""
    if not tc or tc in ("-", "?"):
        return None, None, None
    if "/" in tc:
        return None, None, "daily"
    m = re.fullmatch(r"(\d+)(?:\+(\d+))?", tc.strip())
    if not m:
        return None, None, None
    base, inc = int(m.group(1)), int(m.group(2) or 0)
    est = base + 40 * inc  # stessa stima di Lichess
    cls = "bullet" if est < 180 else "blitz" if est < 480 else "rapid" if est < 1500 else "classical"
    return base, inc, cls


def _played_at(h: chess.pgn.Headers) -> str | None:
    date = h.get("UTCDate") or h.get("Date") or ""
    m = re.fullmatch(r"(\d{4})\.(\d{2})\.(\d{2})", date.strip())
    if not m:
        return None
    out = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    t = h.get("UTCTime") or h.get("StartTime") or ""
    if re.fullmatch(r"\d{2}:\d{2}:\d{2}", t.strip()):
        out += f" {t.strip()}"
    return out


def map_termination(h: chess.pgn.Headers, board: chess.Board, result: str) -> str | None:
    """Traduce Termination di Lichess/chess.com nei codici di review.explain.summary.TERMINATION_IT."""
    if result == "*":
        return "unterminated"
    outcome = board.outcome(claim_draw=True)
    if outcome is not None and outcome.termination == chess.Termination.CHECKMATE:
        return "checkmate"
    t = (h.get("Termination") or "").lower()
    rules = [
        ("checkmate", "checkmate"), ("resign", "resign"), ("abandon", "abandoned"),
        ("stalemate", "stalemate"), ("repetition", "repetition"), ("agreement", "agreement"),
        ("insufficient material", "insufficient"), ("50-move", "fifty"), ("50 move", "fifty"),
        ("time", "timeout"), ("rules infraction", "abandoned"),
    ]
    for needle, code in rules:
        if needle in t:
            # chess.com: "Game drawn by timeout vs insufficient material"
            if code == "insufficient" and "time" in t:
                return "timeout"
            return code
    if outcome is not None:
        return TERMINATION_IT_FROM_BOARD.get(outcome.termination)
    if result == "1/2-1/2":
        return "agreement"
    return "resign"


def detect_source(h: chess.pgn.Headers) -> tuple[str, str | None, str | None]:
    """(source, source_id, source_url) dalle intestazioni."""
    for key in ("Site", "Link", "GameURL"):
        v = h.get(key) or ""
        m = LICHESS_SITE.search(v)
        if m:
            gid = h.get("GameId") if re.fullmatch(r"[A-Za-z0-9]{8}", h.get("GameId") or "") else m.group(1)
            return "lichess", gid, f"https://lichess.org/{gid}"
    for key in ("Link", "Site"):
        v = h.get(key) or ""
        m = CHESSCOM_LINK.search(v)
        if m:
            kind = m.group(1) or m.group(2) or "live"
            return "chesscom", f"{kind}/{m.group(3)}", f"https://www.chess.com/game/{kind}/{m.group(3)}"
    return "pgn", None, None


def _opening(h: chess.pgn.Headers) -> str | None:
    if h.get("Opening") and h.get("Opening") != "?":
        return h["Opening"]
    url = h.get("ECOUrl") or ""
    if "/openings/" in url:
        return url.rsplit("/openings/", 1)[1].replace("-", " ").strip() or None
    return None


def _from_game(index: int, game: chess.pgn.Game) -> Candidate:
    h = game.headers
    c = Candidate(index=index)
    c.white, c.black = h.get("White", "?") or "?", h.get("Black", "?") or "?"
    c.white_elo, c.black_elo = _int(h.get("WhiteElo")), _int(h.get("BlackElo"))
    c.played_at = _played_at(h)
    c.time_control = h.get("TimeControl")
    c.time_initial_s, c.time_increment_s, c.time_class = parse_time_control(c.time_control)
    c.eco = h.get("ECO") if h.get("ECO") not in (None, "?") else None
    c.opening = _opening(h)
    c.source, c.source_id, c.source_url = detect_source(h)
    result = h.get("Result", "*")
    c.result = result if result in ("1-0", "0-1", "1/2-1/2") else "*"

    variant = (h.get("Variant") or "standard").lower()
    if variant not in ("standard", "chess", "from position", "normal"):
        c.error = f"variante non supportata ({h.get('Variant')})"
        return c
    board = game.board()
    if type(board) is not chess.Board or board.chess960:
        c.error = "variante non supportata (Chess960 o simili)"
        return c
    if game.errors:
        c.error = f"PGN non valido: {game.errors[0]}"
        return c
    if board.fen() != chess.STARTING_FEN:
        if not board.is_valid():
            c.error = "posizione iniziale (FEN) non valida"
            return c
        c.start_fen = board.fen()
    node = game
    while node.variations:
        node = node.variations[0]
        if not board.is_legal(node.move):
            c.error = "mossa illegale nel PGN"
            return c
        clk = node.clock()
        c.moves.append(Move(node.move, int(round(clk * 1000)) if clk is not None else None))
        board.push(node.move)
    if not c.moves:
        c.error = "la partita non contiene mosse"
        return c
    if c.start_fen is None:
        from . import openings  # nome uniforme dal nostro database (Lichess chess-openings)
        eco, name, _ = openings.identify([m.move for m in c.moves])
        if name:
            c.eco, c.opening = eco, name
    c.termination = map_termination(h, board, c.result)
    if c.result == "*":
        outcome = board.outcome(claim_draw=True)
        if outcome is not None:
            c.result = outcome.result()
            c.termination = TERMINATION_IT_FROM_BOARD.get(outcome.termination)
    if c.source_id is None:
        digest = hashlib.sha1("|".join([c.white, c.black, c.played_at or "", c.start_fen or "",
                                        " ".join(m.move.uci() for m in c.moves)]).encode()).hexdigest()
        c.source_id = digest[:20]
    exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
    c.pgn = game.accept(exporter)
    return c


def parse_many(text: str, limit: int = MAX_GAMES) -> list[Candidate]:
    if len(text.encode()) > MAX_PGN_BYTES:
        raise ValueError("file troppo grande (massimo 5 MB)")
    text = text.lstrip("﻿")
    stream = io.StringIO(text)
    out: list[Candidate] = []
    while len(out) < limit:
        game = chess.pgn.read_game(stream)
        if game is None:
            break
        if not game.variations and not game.errors and all(v in ("?", "*", "????.??.??", "") for v in game.headers.values()):
            continue  # residui senza contenuto
        out.append(_from_game(len(out), game))
    return out


def parse_one(text: str) -> Candidate:
    cands = parse_many(text, limit=1)
    if not cands:
        c = Candidate(index=0)
        c.error = "PGN non valido"
        return c
    return cands[0]
