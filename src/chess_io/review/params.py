"""Soglie della revisione. Si possono calibrare confrontando con partite revisionate su Chess.com."""

# Perdita di expected points (0..1) per classe
EXCELLENT_MAX = 0.02
GOOD_MAX = 0.05
INACCURACY_MAX = 0.10
MISTAKE_MAX = 0.20

# Una mossa di libro che perde più di così viene classificata normalmente
BOOK_MAX_DELTA = 0.10

# Great: mossa migliore e "unica" (gap tra 1a e 2a linea MultiPV)
GREAT_MIN_GAP = 0.15
GREAT_MIN_EP_AFTER = 0.35          # non "great" se si resta comunque persi

# Brilliant
BRILLIANT_MAX_DELTA = EXCELLENT_MAX
BRILLIANT_MIN_EP_AFTER = 0.5
BRILLIANT_MAX_EP_BEFORE = 0.85        # già nettamente vincenti → niente brilliant
SACRIFICE_MIN_POINTS = 2           # valore minimo del materiale sacrificato
SACRIFICE_PV_PLIES = 6

# Miss: si spreca l'errore dell'avversario
MISS_OPP_MIN_DELTA = 0.10
MISS_MIN_EP_BEST = 0.70
MISS_MIN_DELTA = 0.10

# Livelli in cui si calcola la minaccia (null move)
THREAT_CLASSES = {"inaccuracy", "mistake", "blunder", "miss"}

# Accuratezza → rating stimato (interpolazione lineare)
RATING_TABLE = [
    (0, 100), (40, 300), (50, 500), (60, 800), (70, 1200),
    (80, 1600), (88, 2000), (93, 2400), (97, 2800), (100, 3200),
]
RATING_BLUNDER_PENALTY = 30

PIECE_VALUES = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9, 6: 0}  # P N B R Q K
