"""Partita in memoria: caricamento (link / PGN / stdin), analisi con Stockfish, riassunto. Nessun database."""
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import chess

from . import pgn as pgn_parse, sources
from .pgn import Candidate
from .explain.summary import TERMINATION_IT, summary_from

JSON_FIELDS = ("best_pv_san", "best_pv_uci", "refutation_pv_san", "refutation_pv_uci", "motifs_json")


class InputError(Exception):
    """Errore dell'utente (link, PGN, opzioni): messaggio da mostrare così com'è."""


@dataclass
class Loaded:
    candidates: list[Candidate]
    color_hint: str | None = None
    origin: str = ""

    @property
    def valid(self) -> list[Candidate]:
        return [c for c in self.candidates if not c.error]


def read_pgn_arg(arg: str, stdin=None) -> tuple[str, str]:
    """(testo PGN, descrizione dell'origine): '-' = stdin, un file esistente, altrimenti il testo stesso."""
    if arg == "-":
        return (stdin or sys.stdin).read(), "stdin"
    p = Path(arg).expanduser()
    try:
        is_file = len(arg) < 4096 and "\n" not in arg and p.is_file()
    except OSError:
        is_file = False
    if is_file:
        try:
            return p.read_text(encoding="utf-8", errors="replace"), p.name
        except OSError as e:
            raise InputError(f"impossibile leggere {arg}: {e.strerror}")
    looks_like_path = "\n" not in arg and "[" not in arg and " " not in arg.strip() and \
        (arg.lower().endswith(".pgn") or "/" in arg or "." not in arg)
    if looks_like_path:
        raise InputError(f"file non trovato: {arg}")
    return arg, "PGN incollato"


async def load(link: str | None = None, pgn: str | None = None, stdin=None) -> Loaded:
    hint = None
    if link:
        try:
            text, hint = await sources.fetch_url(link)
        except sources.FetchError as e:
            raise InputError(str(e))
        origin = link
    else:
        text, origin = read_pgn_arg(pgn or "", stdin)
    try:
        cands = pgn_parse.parse_many(text)
    except ValueError as e:
        raise InputError(str(e))
    if not cands:
        raise InputError("nessuna partita valida nel PGN")
    loaded = Loaded(cands, hint, origin)
    if not loaded.valid:
        raise InputError(cands[0].error or "nessuna partita valida nel PGN")
    return loaded


def pick(loaded: Loaded, game_no: int | None) -> Candidate | None:
    """La partita da analizzare: --game N (1 = la prima del PGN), l'unica valida, oppure None (scelta nella TUI)."""
    if game_no is not None:
        if not 1 <= game_no <= len(loaded.candidates):
            raise InputError(f"il PGN contiene {len(loaded.candidates)} partite: --game va da 1 a {len(loaded.candidates)}")
        c = loaded.candidates[game_no - 1]
        if c.error:
            raise InputError(f"partita {game_no}: {c.error}")
        return c
    valid = loaded.valid
    return valid[0] if len(valid) == 1 else None


def game_dict(c: Candidate, color: str) -> dict:
    """Metadati della partita usati da revisione e riassunto."""
    return {
        "player_color": color, "white_name": c.white, "black_name": c.black,
        "white_elo": c.white_elo, "black_elo": c.black_elo, "result": c.result,
        "termination": c.termination, "termination_it": TERMINATION_IT.get(c.termination or ""),
        "time_control": c.time_control, "time_initial_s": c.time_initial_s, "time_increment_s": c.time_increment_s,
        "time_class": c.time_class, "eco": c.eco, "opening_name": c.opening, "start_fen": c.start_fen,
        "played_at": c.played_at, "source": c.source, "source_url": c.source_url,
    }


@dataclass
class Review:
    """Partita analizzata, tutta in memoria: metadati, mosse con analisi, riassunto."""
    game: dict
    moves: list[dict]
    summary: dict
    llm_status: str = "none"          # none | downloading | running | done | error
    llm_progress: tuple[int, int] = (0, 0)
    llm_error: str | None = None
    extra: dict = field(default_factory=dict)

    @property
    def start_fen(self) -> str:
        return self.game.get("start_fen") or chess.STARTING_FEN

    @property
    def num_base(self) -> int:
        """Numero di mossa iniziale - 1 (partite da FEN)."""
        try:
            return max(0, int(self.start_fen.split()[5]) - 1)
        except (IndexError, ValueError):
            return 0

    def move_num(self, ply: int) -> int:
        return self.num_base + ply // 2 + 1

    def label(self, i: int) -> str:
        m = self.moves[i]
        return f"{self.move_num(m['ply'])}{'.' if m['ply'] % 2 == 0 else '...'} {m['san']}"

    def fens(self) -> list[str]:
        """fens[0] = posizione iniziale, fens[i+1] = dopo la mossa i."""
        out = [self.start_fen]
        b = chess.Board(self.start_fen)
        for m in self.moves:
            b.push_uci(m["uci"])
            out.append(b.fen())
        return out

    def set_color(self, color: str) -> None:
        self.game["player_color"] = color
        self.summary["text"] = summary_from(self.game, self.moves, self.summary)
        self.summary["llm"] = None
        self.summary["llm_check"] = None


def merge(c: Candidate, color: str, result: dict) -> Review:
    """Unisce la partita (SAN, UCI, orologio) all'output di analyse_game e calcola il riassunto."""
    board = chess.Board(c.start_fen) if c.start_fen else chess.Board()
    moves = []
    for pm, am in zip(c.moves, result["moves"]):
        d = dict(am)
        d.update(san=board.san(pm.move), uci=pm.move.uci(), fen_before=board.fen(), clock_ms=pm.clock_ms,
                 comment_llm=None, llm_check_json=None)
        for k in JSON_FIELDS:
            if isinstance(d.get(k), str):
                d[k] = json.loads(d[k])
        board.push(pm.move)
        moves.append(d)
    rv = dict(result["review"])
    g = game_dict(c, color)
    g["eco"] = rv.get("eco") or g["eco"]
    g["opening_name"] = rv.get("opening_name") or g["opening_name"]
    summary = {k: rv[k] for k in ("accuracy_white", "accuracy_black", "rating_est_white", "rating_est_black",
                                  "engine_version", "depth")}
    summary["counts"] = json.loads(rv["counts_json"])
    summary["key_moments"] = json.loads(rv["key_moments_json"])
    summary["text"] = summary_from(g, moves, summary)
    summary["llm"] = None
    summary["llm_check"] = None
    return Review(g, moves, summary)


async def analyse(c: Candidate, color: str, depth: int, progress: Callable[[int, int], None] | None = None) -> Review:
    from .review.analyzer import analyse_game
    uci = [m.move.uci() for m in c.moves]
    result = await analyse_game(0, uci, depth, progress, start_fen=c.start_fen)
    return merge(c, color, result)
