import os
from pathlib import Path

STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "stockfish")
DATA_DIR = Path(os.environ.get("DATA_DIR", "."))  # la CLI la imposta a una cartella temporanea
OPENINGS_DB = Path(os.environ.get("OPENINGS_DB", "./openings.sqlite"))

ANALYSIS_DEPTH = int(os.environ.get("ANALYSIS_DEPTH", "16"))
ANALYSIS_THREADS = int(os.environ.get("ANALYSIS_THREADS", str(max(1, (os.cpu_count() or 2) - 1))))
ANALYSIS_HASH_MB = int(os.environ.get("ANALYSIS_HASH_MB", "64"))
ANALYSIS_MAX_TIME_S = float(os.environ.get("ANALYSIS_MAX_TIME_S", "0.4"))  # tetto per posizione
THREAT_DEPTH = int(os.environ.get("THREAT_DEPTH", "10"))

