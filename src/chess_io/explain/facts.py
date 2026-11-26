"""Raccolta di fatti verificabili su una mossa, a partire dalle linee del motore."""
from dataclasses import dataclass, field, asdict

import chess

from ..i18n import piece_on, piece_the, tr
from ..review.material import balance, describe_points, value
from . import motifs


@dataclass
class Facts:
    cls: str
    san: str
    mover: str                         # "white" | "black"
    best_san: str | None = None
    best_line: str | None = None       # variante migliore in notazione con numeri di mossa
    refutation_line: str | None = None
    refutation_first: str | None = None
    second_san: str | None = None
    mate_against: int | None = None    # dopo la mossa l'avversario dà matto in N
    mate_for: int | None = None        # dopo la mossa il giocatore dà matto in N
    mate_missed: int | None = None     # con la mossa migliore c'era matto in N
    loss: str | None = None            # materiale perso rispetto alla posizione attuale
    loss_points: int = 0
    missed_gain: str | None = None     # materiale che la mossa migliore avrebbe vinto in più
    first_capture: str | None = None   # es. "l'alfiere in f4" (nella lingua dell'analisi)
    best_gain: str | None = None       # materiale vinto con la mossa migliore
    sacrificed: str | None = None
    threat_san: str | None = None
    threat_ignored: bool = False
    ref_fork: list[str] = field(default_factory=list)      # forchetta avversaria nella confutazione
    ref_pin: list[str] = field(default_factory=list)
    best_fork: list[str] = field(default_factory=list)
    best_pin: list[str] = field(default_factory=list)
    best_discovered: list[str] = field(default_factory=list)
    played_fork: list[str] = field(default_factory=list)
    played_pin: list[str] = field(default_factory=list)
    played_discovered: list[str] = field(default_factory=list)
    hanging: list[str] = field(default_factory=list)
    back_rank: bool = False
    positional: list[str] = field(default_factory=list)
    opening: str | None = None
    eval_before: str | None = None
    eval_after: str | None = None
    ep_after: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def fmt_eval(cp: int | None, mate: int | None) -> str | None:
    if mate is not None:
        return f"#{mate}" if mate > 0 else f"#-{abs(mate)}"
    if cp is None:
        return None
    return f"{cp / 100:+.1f}"


def _play(board: chess.Board, moves: list[chess.Move]) -> tuple[chess.Board, list[chess.Move]]:
    b = board.copy()
    played = []
    for mv in moves:
        if mv not in b.legal_moves:
            break
        b.push(mv)
        played.append(mv)
    return b, played


def _line(board: chess.Board, moves: list[chess.Move], n: int) -> str | None:
    _, ok = _play(board, moves[:n])
    return board.variation_san(ok) if ok else None


def settled_balance(board: chess.Board, pv: list[chess.Move], min_plies: int, color: chess.Color) -> int:
    """Bilancio materiale dopo `min_plies` semimosse della linea, proseguendo finché ci sono catture
    (così non si misura a metà di un cambio)."""
    b = board.copy(stack=False)
    for i, mv in enumerate(pv):
        if mv not in b.legal_moves:
            break
        if i >= min_plies and not b.is_capture(mv):
            break
        b.push(mv)
    return balance(b, color)


def _first_capture_by(board: chess.Board, moves: list[chess.Move], color: chess.Color) -> tuple[str, str, int] | None:
    b = board.copy()
    for mv in moves:
        if mv not in b.legal_moves:
            return None
        if b.turn == color and b.is_capture(mv):
            sq = mv.to_square
            victim = b.piece_type_at(sq)
            if victim is None:  # en passant
                victim = chess.PAWN
            san = b.san(mv)
            return piece_on(victim, sq), san, value(victim)
        b.push(mv)
    return None


def build_facts(
    board_before: chess.Board,
    move: chess.Move,
    cls: str,
    best_move: chess.Move | None,
    best_pv: list[chess.Move],
    refutation_pv: list[chess.Move],
    second_move: chess.Move | None,
    mate_after_mover: int | None,      # matto dal punto di vista di chi ha mosso (>0 = lui dà matto)
    mate_best_mover: int | None,
    threat: chess.Move | None,
    sacrificed_pts: int,
    sacrificed_piece: int | None,
    opening: str | None,
    eval_before: str | None,
    eval_after: str | None,
    ep_after: float | None = None,
    line_plies: int = 6,
) -> Facts:
    color = board_before.turn
    after = board_before.copy()
    after.push(move)

    f = Facts(cls=cls, san=board_before.san(move), mover="white" if color else "black",
              opening=opening, eval_before=eval_before, eval_after=eval_after, ep_after=ep_after)

    if best_move is not None and best_move in board_before.legal_moves:
        f.best_san = board_before.san(best_move)
        pv = best_pv if best_pv and best_pv[0] == best_move else [best_move]
        f.best_line = _line(board_before, pv, line_plies)
    if second_move is not None and second_move in board_before.legal_moves:
        f.second_san = board_before.san(second_move)

    if refutation_pv:
        f.refutation_line = _line(after, refutation_pv, line_plies)
        if refutation_pv[0] in after.legal_moves:
            f.refutation_first = after.san(refutation_pv[0])

    if mate_after_mover is not None:
        if mate_after_mover < 0:
            f.mate_against = abs(mate_after_mover)
        else:
            f.mate_for = mate_after_mover
    if mate_best_mover is not None and mate_best_mover > 0 and (mate_after_mover is None or mate_after_mover < 0):
        f.mate_missed = mate_best_mover

    # materiale: fine (a riposo) della confutazione contro fine della linea migliore
    start_bal = balance(board_before, color)
    ref_bal = settled_balance(after, refutation_pv, line_plies, color)
    best_bal = settled_balance(board_before, best_pv, line_plies + 1, color) if best_pv else balance(after, color)
    if best_move is not None and move != best_move:
        if start_bal - ref_bal >= 1 and best_bal - ref_bal >= 1:
            f.loss_points = min(start_bal, best_bal) - ref_bal
            if f.loss_points >= 1:
                f.loss = describe_points(f.loss_points)
        # il "guadagno mancato" è affidabile solo quando la perdita di valutazione è netta
        if not f.loss and best_bal - ref_bal >= 1 and cls in ("mistake", "blunder", "miss"):
            f.missed_gain = describe_points(best_bal - ref_bal)
    if best_pv and best_bal - start_bal >= 1 and cls in ("mistake", "blunder", "miss"):
        f.best_gain = describe_points(best_bal - start_bal)
    fc = _first_capture_by(after, refutation_pv[:line_plies], not color)
    if fc and abs(fc[2] - f.loss_points) <= 1:
        f.first_capture = fc[0]

    if sacrificed_pts:
        pt = sacrificed_piece
        if pt == chess.ROOK and sacrificed_pts == 2:
            f.sacrificed = tr("la qualità")
        elif pt is not None and pt != chess.PAWN and sacrificed_pts >= 3:
            f.sacrificed = piece_the(pt)
        else:
            f.sacrificed = describe_points(sacrificed_pts)

    # minaccia (null move): l'avversario la esegue comunque nella confutazione?
    if threat is not None:
        b_null = board_before.copy()
        b_null.push(chess.Move.null())
        if threat in b_null.legal_moves:
            f.threat_san = b_null.san(threat)
            f.threat_ignored = bool(refutation_pv) and refutation_pv[0] == threat

    # motivi tattici della mossa giocata
    f.played_fork = motifs.fork_targets(after, move.to_square)
    f.played_pin = motifs.new_pins(board_before, after, color)
    f.played_discovered = motifs.discovered_attack(board_before, move)

    # motivi della confutazione avversaria (prima risposta)
    if refutation_pv and refutation_pv[0] in after.legal_moves:
        r = refutation_pv[0]
        after_r = after.copy()
        after_r.push(r)
        f.ref_fork = motifs.fork_targets(after_r, r.to_square)
        f.ref_pin = motifs.new_pins(after, after_r, not color)
        ref_end_full, _ = _play(after, refutation_pv)
        f.back_rank = motifs.back_rank_mate(ref_end_full)
    captured = board_before.piece_type_at(move.to_square)
    cap_val = value(captured) if captured else (1 if board_before.is_en_passant(move) else 0)
    f.hanging = motifs.hanging_after(after, color, move, cap_val) if cls in ("mistake", "blunder", "inaccuracy") else []

    # motivi della mossa migliore
    if best_move is not None and best_move != move and best_move in board_before.legal_moves:
        b_best = board_before.copy()
        b_best.push(best_move)
        f.best_fork = motifs.fork_targets(b_best, best_move.to_square)
        f.best_pin = motifs.new_pins(board_before, b_best, color)
        f.best_discovered = motifs.discovered_attack(board_before, best_move)

    if cls in ("inaccuracy", "good", "mistake"):
        f.positional = motifs.positional_notes(board_before, move)
    return f


__all__ = ["Facts", "build_facts", "fmt_eval"]
