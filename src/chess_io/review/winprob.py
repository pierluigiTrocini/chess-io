import math


def win_percent(cp: int) -> float:
    """Curva Lichess: centipawn (punto di vista di chi muove) → probabilità di vittoria 0..100."""
    cp = max(-10000, min(10000, cp))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def expected_points(cp: int) -> float:
    return win_percent(cp) / 100


def move_accuracy(win_before: float, win_after: float) -> float:
    """Accuratezza della singola mossa (formula Lichess), input in 0..100."""
    diff = max(0.0, win_before - win_after)
    acc = 103.1668 * math.exp(-0.04354 * diff) - 3.1669
    return max(0.0, min(100.0, acc))
