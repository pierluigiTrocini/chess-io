"""Riconoscimento euristico dei sacrifici (per la classe Brilliant)."""
import chess

from . import params as cfg
from .material import balance, value


def capture_net_gain(board: chess.Board, square: chess.Square) -> int:
    """
    Guadagno netto (in punti) per l'avversario di chi possiede il pezzo su `square` se lo cattura
    con l'attaccante più economico, tenendo conto della migliore cattura immediata di risposta
    (ricattura sulla stessa casa o altro bersaglio, es. un pezzo che era inchiodato e si è scoperto).
    """
    piece = board.piece_at(square)
    if piece is None or piece.piece_type == chess.KING:
        return 0
    b = board.copy(stack=False)
    b.turn = not piece.color
    b.ep_square = None
    captures = [m for m in b.legal_moves if m.to_square == square]
    if not captures:
        return 0
    captures.sort(key=lambda m: value(b.piece_type_at(m.from_square)) or 100)
    best_net = 0
    for cap in captures[:2]:
        bb = b.copy(stack=False)
        bb.push(cap)
        reply = 0
        for r in bb.legal_moves:
            if bb.is_capture(r):
                victim = bb.piece_type_at(r.to_square) or chess.PAWN
                reply = max(reply, value(victim) if victim != chess.KING else 0)
            if bb.gives_check(r):
                bb.push(r)
                if bb.is_checkmate():
                    reply = 100
                bb.pop()
        best_net = max(best_net, value(piece.piece_type) - reply)
    return best_net


def _hanging_values(board: chess.Board, color: chess.Color) -> dict[chess.Square, int]:
    out = {}
    for sq, p in board.piece_map().items():
        if p.color == color and p.piece_type not in (chess.KING, chess.PAWN):
            g = capture_net_gain(board, sq)
            if g > 0:
                out[sq] = g
    return out


def sacrifice(board_before: chess.Board, move: chess.Move, refutation_pv: list[chess.Move]) -> tuple[int, int | None]:
    """
    (punti sacrificati, tipo del pezzo sacrificato) giocando `move`; (0, None) se non è un sacrificio.
    Si considerano: il calo del bilancio materiale lungo la linea del motore e i pezzi che
    dopo la mossa restano catturabili con guadagno (anche se il motore non li cattura).
    """
    color = board_before.turn
    if move.promotion:
        return 0, None
    start = balance(board_before, color)
    after = board_before.copy(stack=False)
    after.push(move)

    captured = board_before.piece_type_at(move.to_square)
    captured_val = value(captured) if captured else (1 if board_before.is_en_passant(move) else 0)

    before_h = _hanging_values(board_before, color)
    after_h = _hanging_values(after, color)
    best_piece, best_pts = None, 0
    for sq, g in after_h.items():
        prev = before_h.get(move.from_square if sq == move.to_square else sq, 0)
        pts = g - prev - (captured_val if sq == move.to_square else 0)
        if pts > best_pts:
            best_pts, best_piece = pts, after.piece_type_at(sq)

    b = after.copy(stack=False)
    bals = []
    for mv in refutation_pv[: cfg.SACRIFICE_PV_PLIES]:
        if mv not in b.legal_moves:
            break
        b.push(mv)
        bals.append(balance(b, color))
    # dopo ogni risposta dell'avversario (indici pari); se il giocatore riprende subito
    # il materiale alla mossa successiva è un semplice cambio, non un sacrificio
    worst = start
    for i in range(0, len(bals), 2):
        eff = max(bals[i], bals[i + 1]) if i + 1 < len(bals) else bals[i]
        worst = min(worst, eff)
    dip = start - worst
    if dip > best_pts:
        best_pts, best_piece = dip, board_before.piece_type_at(move.from_square)
    if best_pts < cfg.SACRIFICE_MIN_POINTS:
        return 0, None
    return best_pts, best_piece


def sacrificed_points(board_before: chess.Board, move: chess.Move, refutation_pv: list[chess.Move]) -> int:
    return sacrifice(board_before, move, refutation_pv)[0]
