"""Riconoscimento di motivi tattici e posizionali con python-chess."""
import chess

from ..i18n import piece_on, tr
from ..review.material import value


def _name(board: chess.Board, sq: chess.Square) -> str:
    p = board.piece_at(sq)
    return piece_on(p.piece_type, sq) if p else chess.square_name(sq)


def fork_targets(board_after: chess.Board, sq: chess.Square) -> list[str]:
    """Bersagli di una forchetta del pezzo su `sq` (≥ 2 bersagli: re, pezzi di valore maggiore o indifesi)."""
    piece = board_after.piece_at(sq)
    if piece is None:
        return []
    targets = []
    for t in board_after.attacks(sq):
        victim = board_after.piece_at(t)
        if victim is None or victim.color == piece.color or victim.piece_type == chess.PAWN:
            continue
        if (victim.piece_type == chess.KING
                or value(victim.piece_type) > value(piece.piece_type)
                or not board_after.attackers(victim.color, t)):
            targets.append(t)
    if len(targets) < 2:
        return []
    return [_name(board_after, t) for t in targets]


def new_pins(board_before: chess.Board, board_after: chess.Board, by: chess.Color) -> list[str]:
    """Pezzi avversari che risultano inchiodati al re dopo la mossa e non lo erano prima."""
    out = []
    for sq, p in board_after.piece_map().items():
        if p.color == by or p.piece_type in (chess.KING, chess.PAWN):
            continue
        if board_after.is_pinned(p.color, sq) and not board_before.is_pinned(p.color, sq):
            out.append(_name(board_after, sq))
    return out


def discovered_attack(board_before: chess.Board, move: chess.Move) -> list[str]:
    """Attacchi di scoperta: altri pezzi del giocatore che, liberata la linea, attaccano re o pezzi di valore."""
    color = board_before.turn
    after = board_before.copy(stack=False)
    after.push(move)
    out = []
    for sq, p in after.piece_map().items():
        if p.color != color or sq == move.to_square or p.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
            continue
        new = after.attacks(sq) & ~board_before.attacks(sq)
        for t in new:
            v = after.piece_at(t)
            if v and v.color != color and (v.piece_type == chess.KING or value(v.piece_type) >= 3):
                out.append(_name(after, t))
    return out


def hanging_after(board_after: chess.Board, color: chess.Color, move: chess.Move | None = None,
                  captured_value: int = 0) -> list[str]:
    """Pezzi di `color` (non pedoni) attaccati e indifesi o attaccati da un pezzo di valore minore.
    Il pezzo appena mosso non conta se ha catturato materiale di valore simile (è un cambio)."""
    out = []
    for sq, p in board_after.piece_map().items():
        if p.color != color or p.piece_type in (chess.KING, chess.PAWN):
            continue
        if move is not None and sq == move.to_square and captured_value >= value(p.piece_type) - 1:
            continue
        att = board_after.attackers(not color, sq)
        if not att:
            continue
        defended = bool(board_after.attackers(color, sq))
        cheapest = min(value(board_after.piece_type_at(a)) or 100 for a in att)
        if not defended or cheapest < value(p.piece_type):
            out.append(_name(board_after, sq))
    return out


def back_rank_mate(board: chess.Board) -> bool:
    """La posizione è matto con il re sulla propria traversa di fondo e un pezzo pesante sulla stessa."""
    if not board.is_checkmate():
        return False
    king = board.king(board.turn)
    rank = 0 if board.turn == chess.WHITE else 7
    if king is None or chess.square_rank(king) != rank:
        return False
    checkers = board.checkers()
    return any(chess.square_rank(c) == rank and board.piece_type_at(c) in (chess.ROOK, chess.QUEEN) for c in checkers)


def positional_notes(board_before: chess.Board, move: chess.Move) -> list[str]:
    """Note posizionali semplici, usate quando non c'è un motivo tattico."""
    notes = []
    color = board_before.turn
    piece = board_before.piece_at(move.from_square)
    ply = len(board_before.move_stack)
    if piece is None:
        return notes
    if piece.piece_type == chess.KING and not board_before.is_castling(move) and board_before.has_castling_rights(color):
        notes.append(tr("perdi il diritto di arroccare"))
    if piece.piece_type == chess.QUEEN and ply < 14:
        notes.append(tr("la donna esce troppo presto e può diventare un bersaglio"))
    if ply < 20 and piece.piece_type in (chess.KNIGHT, chess.BISHOP) and not board_before.is_capture(move):
        home = chess.BB_RANK_1 if color == chess.WHITE else chess.BB_RANK_8
        if not (chess.BB_SQUARES[move.from_square] & home):
            undeveloped = [s for s in board_before.pieces(chess.KNIGHT, color) | board_before.pieces(chess.BISHOP, color)
                           if chess.BB_SQUARES[s] & home]
            if len(undeveloped) >= 2:
                notes.append(tr("muovi di nuovo lo stesso pezzo invece di sviluppare gli altri"))
    if piece.piece_type == chess.PAWN and ply < 30:
        king = board_before.king(color)
        if king is not None and abs(chess.square_file(king) - chess.square_file(move.from_square)) <= 1 \
                and chess.square_file(king) in (0, 1, 2, 5, 6, 7):
            notes.append(tr("indebolisci la struttura di pedoni davanti al tuo re"))
    after = board_before.copy(stack=False)
    after.push(move)
    to = move.to_square
    if piece.piece_type != chess.PAWN and piece.piece_type != chess.KING:
        after.turn = color  # mobilità del pezzo come se toccasse di nuovo a noi
        mobility = sum(1 for m in after.pseudo_legal_moves if m.from_square == to)
        if mobility <= 1:
            notes.append(tr("{piece} ha pochissime case a disposizione", piece=piece_on(piece.piece_type, to)))
    return notes
