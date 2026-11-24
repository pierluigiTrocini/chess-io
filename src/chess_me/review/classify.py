"""Classificazione delle mosse basata sulla perdita di expected points (stile Chess.com)."""
from dataclasses import dataclass, field

import chess

from . import params as cfg
from .sacrifice import sacrifice

CLASSES = ["brilliant", "great", "best", "excellent", "good", "book",
           "inaccuracy", "mistake", "miss", "blunder"]


@dataclass
class MoveEval:
    ply: int
    board_before: chess.Board
    move: chess.Move
    best_move: chess.Move | None
    ep_best: float                 # EP della posizione prima (= con la mossa migliore), pov di chi muove
    ep_after: float                # EP dopo la mossa giocata, pov di chi muove
    ep_second: float | None        # EP della seconda migliore mossa
    refutation_pv: list[chess.Move] = field(default_factory=list)
    is_book: bool = False
    opp_prev_delta: float | None = None
    sac_points: int = 0
    sac_piece: int | None = None

    @property
    def played_best(self) -> bool:
        return self.best_move is not None and self.move == self.best_move

    @property
    def delta(self) -> float:
        if self.played_best:
            return 0.0
        return max(0.0, self.ep_best - self.ep_after)


def _is_obvious_recapture(board: chess.Board, move: chess.Move) -> bool:
    if not board.move_stack:
        return False
    last = board.peek()
    return board.is_capture(move) and move.to_square == last.to_square and board.piece_at(last.to_square) is not None


def classify(m: MoveEval) -> tuple[str, int]:
    """Restituisce (classe, punti sacrificati)."""
    d = m.delta
    # una mossa di teoria resta "book" solo se non è un errore evidente
    # (alcune "aperture" del database sono trappole, es. il matto dell'imbecille)
    if m.is_book and d <= cfg.BOOK_MAX_DELTA:
        return "book", 0
    sac = 0

    if d <= cfg.BRILLIANT_MAX_DELTA:
        sac, m.sac_piece = sacrifice(m.board_before, m.move, m.refutation_pv)
        m.sac_points = sac
        if (sac and m.ep_after >= cfg.BRILLIANT_MIN_EP_AFTER
                and m.ep_best <= cfg.BRILLIANT_MAX_EP_BEFORE):
            return "brilliant", sac

    if m.played_best:
        after = m.board_before.copy(stack=False)
        after.push(m.move)
        if after.is_checkmate():
            return "best", sac
        if (m.ep_second is not None and m.ep_best - m.ep_second >= cfg.GREAT_MIN_GAP
                and m.ep_after >= cfg.GREAT_MIN_EP_AFTER
                and m.board_before.legal_moves.count() > 2
                and not _is_obvious_recapture(m.board_before, m.move)):
            return "great", sac
        return "best", sac

    if d <= cfg.EXCELLENT_MAX:
        return "excellent", sac
    if d <= cfg.GOOD_MAX:
        return "good", sac

    if (m.opp_prev_delta is not None and m.opp_prev_delta >= cfg.MISS_OPP_MIN_DELTA
            and m.ep_best >= cfg.MISS_MIN_EP_BEST and d >= cfg.MISS_MIN_DELTA
            and d <= cfg.MISTAKE_MAX):
        return "miss", sac
    if d <= cfg.INACCURACY_MAX:
        return "inaccuracy", sac
    if d <= cfg.MISTAKE_MAX:
        return "mistake", sac
    return "blunder", sac


def phase_of(board: chess.Board) -> str:
    """Fase di gioco della posizione: apertura / mediogioco / finale."""
    non_pawn = sum(
        len(board.pieces(pt, c)) * v
        for pt, v in ((chess.KNIGHT, 3), (chess.BISHOP, 3), (chess.ROOK, 5), (chess.QUEEN, 9))
        for c in (chess.WHITE, chess.BLACK)
    )
    if non_pawn <= 26:
        return "endgame"
    if board.fullmove_number <= 12:
        return "opening"
    return "middlegame"
