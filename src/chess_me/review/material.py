import chess

from .params import PIECE_VALUES

PIECE_NAMES_IT = {
    chess.PAWN: "pedone", chess.KNIGHT: "cavallo", chess.BISHOP: "alfiere",
    chess.ROOK: "torre", chess.QUEEN: "donna", chess.KING: "re",
}
PIECE_ARTICLE_IT = {
    chess.PAWN: "il pedone", chess.KNIGHT: "il cavallo", chess.BISHOP: "l'alfiere",
    chess.ROOK: "la torre", chess.QUEEN: "la donna", chess.KING: "il re",
}


def value(piece_type: int) -> int:
    return PIECE_VALUES[piece_type]


def material(board: chess.Board, color: chess.Color) -> int:
    return sum(value(p.piece_type) for p in board.piece_map().values() if p.color == color)


def balance(board: chess.Board, color: chess.Color) -> int:
    return material(board, color) - material(board, not color)


def counts(board: chess.Board, color: chess.Color) -> dict[int, int]:
    return {pt: len(board.pieces(pt, color)) for pt in range(1, 6)}


def describe_loss(before: chess.Board, after: chess.Board, color: chess.Color) -> str | None:
    """Descrive in italiano il materiale netto perso da `color` passando da before ad after."""
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
        return "la donna"
    if lost.get(chess.ROOK, 0) > won.get(chess.ROOK, 0) and net == 2:
        return "la qualità"
    if net == 1:
        return "un pedone"
    if net == 2:
        return "due pedoni"
    if net in (3, 4):
        minor = [pt for pt in (chess.KNIGHT, chess.BISHOP) if lost.get(pt, 0) > won.get(pt, 0)]
        return f"un {PIECE_NAMES_IT[minor[0]]}" if len(minor) == 1 else "un pezzo"
    if net in (5, 6):
        return "una torre"
    if net >= 9:
        return "molto materiale"
    return "molto materiale"
