import chess

from ..i18n import piece_a, tr
from .params import PIECE_VALUES


def value(piece_type: int) -> int:
    return PIECE_VALUES[piece_type]


def material(board: chess.Board, color: chess.Color) -> int:
    return sum(value(p.piece_type) for p in board.piece_map().values() if p.color == color)


def balance(board: chess.Board, color: chess.Color) -> int:
    return material(board, color) - material(board, not color)


def counts(board: chess.Board, color: chess.Color) -> dict[int, int]:
    return {pt: len(board.pieces(pt, color)) for pt in range(1, 6)}


def describe_loss(before: chess.Board, after: chess.Board, color: chess.Color) -> str | None:
    """Descrive (nella lingua corrente) il materiale netto perso da `color` passando da before ad after."""
    lost = {pt: counts(before, color)[pt] - counts(after, color)[pt] for pt in range(1, 6)}
    won = {pt: counts(before, not color)[pt] - counts(after, not color)[pt] for pt in range(1, 6)}
    # le promozioni aumentano i pezzi: ignorate per la descrizione
    net = sum(value(pt) * max(0, n) for pt, n in lost.items()) - sum(value(pt) * max(0, n) for pt, n in won.items())
    if net <= 0:
        return None
    return describe_points(net, lost, won)


def describe_points(net: int, lost: dict[int, int] | None = None, won: dict[int, int] | None = None) -> str:
    lost = lost or {}
    won = won or {}
    if lost.get(chess.QUEEN, 0) > won.get(chess.QUEEN, 0):
        return tr("la donna")
    if lost.get(chess.ROOK, 0) > won.get(chess.ROOK, 0) and net == 2:
        return tr("la qualità")
    if net == 1:
        return piece_a(chess.PAWN)
    if net == 2:
        return tr("due pedoni")
    if net in (3, 4):
        minor = [pt for pt in (chess.KNIGHT, chess.BISHOP) if lost.get(pt, 0) > won.get(pt, 0)]
        return piece_a(minor[0]) if len(minor) == 1 else tr("un pezzo")
    if net in (5, 6):
        return piece_a(chess.ROOK)
    return tr("molto materiale")
