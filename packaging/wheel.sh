#!/bin/sh
# Costruisce la wheel (e l'sdist) con dentro il database delle aperture, pronta per pip/pipx.
# Senza binari: Stockfish e llama-server li scarica `chess-me setup`.
#   packaging/wheel.sh  ->  dist/chess_me-<versione>-py3-none-any.whl
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
WORK="$ROOT/build/wheel"
DB="$ROOT/src/chess_me/data/openings.sqlite"
mkdir -p "$WORK" "$ROOT/dist"
if [ ! -x "$WORK/venv/bin/python" ]; then "$PY" -m venv "$WORK/venv"; fi
"$WORK/venv/bin/pip" install -q --upgrade pip build
if [ ! -f "$DB" ]; then
  "$WORK/venv/bin/pip" install -q "chess>=1.11,<2" "httpx>=0.27,<1"
  PYTHONPATH="$ROOT/src" "$WORK/venv/bin/python" -m chess_me.build_openings "$DB"
fi
"$WORK/venv/bin/python" -m build --outdir "$ROOT/dist" "$ROOT"
rm -rf "$ROOT/src"/*.egg-info
ls -1 "$ROOT/dist"/chess_me-*
