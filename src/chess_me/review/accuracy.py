"""Accuratezza della partita (metodo Lichess) e rating stimato."""
import statistics

from . import params as cfg


def game_accuracy(win_white: list[float], move_acc: list[float],
                  first_black: bool = False) -> tuple[float | None, float | None]:
    """
    win_white: Win% (punto di vista del bianco) di tutte le posizioni, iniziale compresa (len = n+1).
    move_acc:  accuratezza di ogni mossa (len = n); la prima è del bianco salvo first_black.
    """
    n = len(move_acc)
    if n == 0:
        return None, None
    ws = max(2, min(8, n // 10))
    ws = min(ws, len(win_white))
    windows = [win_white[:ws]] * max(0, ws - 2)
    windows += [win_white[i:i + ws] for i in range(len(win_white) - ws + 1)]
    weights = []
    for w in windows[:n]:
        sd = statistics.pstdev(w) if len(w) > 1 else 0.5
        weights.append(max(0.5, min(12.0, sd)))
    while len(weights) < n:
        weights.append(0.5)

    out = []
    for color in (0, 1):
        idx = list(range(color ^ int(first_black), n, 2))
        if not idx:
            out.append(None)
            continue
        accs = [move_acc[i] for i in idx]
        ws_ = [weights[i] for i in idx]
        weighted = sum(a * w for a, w in zip(accs, ws_)) / sum(ws_)
        harmonic = len(accs) / sum(1 / max(a, 1.0) for a in accs)
        out.append(round((weighted + harmonic) / 2, 1))
    return out[0], out[1]


def estimated_rating(accuracy: float | None, blunders: int) -> int | None:
    if accuracy is None:
        return None
    table = cfg.RATING_TABLE
    rating = table[-1][1]
    for (a0, r0), (a1, r1) in zip(table, table[1:]):
        if accuracy <= a1:
            rating = r0 + (r1 - r0) * (accuracy - a0) / (a1 - a0)
            break
    rating -= cfg.RATING_BLUNDER_PENALTY * max(0, blunders - 1)
    return int(max(100, round(rating / 25) * 25))
