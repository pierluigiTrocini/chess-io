#!/bin/sh
# Installa (o disinstalla) chess-me.
#
#   ./install.sh                      dal sorgente: pipx se c'è, altrimenti pip in un venv dedicato;
#                                     dalla cartella self-contained estratta: la copia così com'è
#   ./install.sh --llm                in più llama-server e il modello LLM (~1,1 GB)
#   ./install.sh --from <spec>        cosa installare: cartella, .whl, git+https://… (default: questa cartella)
#   ./install.sh --pipx | --pip       forza il metodo
#   ./install.sh --no-setup           non scaricare Stockfish e aperture (es. Stockfish già nel PATH)
#   ./install.sh --prefix DIR         dove installare (bundle: ~/.local/share/chess-me/app, pip: …/venv)
#   ./install.sh --bin-dir DIR        dove mettere il comando chess-me (default ~/.local/bin)
#   ./install.sh --uninstall [--purge]   --purge elimina anche modello LLM e dati scaricati
#
# Variabili: PYTHON (interprete >= 3.12 da usare), CHESSME_HOME (cartella dei dati, default ~/.local/share/chess-me).
set -eu

DATA_HOME="${CHESSME_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/chess-me}"
BIN_DIR="$HOME/.local/bin"
PREFIX=""
FROM=""
METHOD=auto
MODE=install
PURGE=0
LLM=0
SETUP=1
SRC="$(cd "$(dirname "$0")" && pwd)"
MARK=".chess-me-venv"

say() { printf '%s\n' "$*"; }
die() { printf 'install.sh: %s\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --pipx) METHOD=pipx; shift ;;
    --pip) METHOD=pip; shift ;;
    --llm) LLM=1; shift ;;
    --no-setup) SETUP=0; shift ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    --bin-dir) BIN_DIR="$2"; shift 2 ;;
    --uninstall) MODE=uninstall; shift ;;
    --purge) PURGE=1; shift ;;
    -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "opzione sconosciuta: $1 (vedi --help)" ;;
  esac
done

has() { command -v "$1" >/dev/null 2>&1; }
pipx_has_chessme() { has pipx && pipx list --short 2>/dev/null | grep -q '^chess-me '; }

# ---------- disinstallazione ----------
if [ "$MODE" = uninstall ]; then
  if [ -L "$BIN_DIR/chess-me" ]; then rm "$BIN_DIR/chess-me"; fi
  if pipx_has_chessme; then pipx uninstall chess-me; fi
  for d in "${PREFIX:-$DATA_HOME/app}" "${PREFIX:-$DATA_HOME/venv}"; do
    if [ -f "$d/VERSION" ] || [ -f "$d/$MARK" ]; then rm -rf "$d"; fi
  done
  if [ "$PURGE" = 1 ] && [ -d "$DATA_HOME" ]; then
    printf "Elimino anche %s (binari, modello LLM e dati scaricati)? [s/N] " "$DATA_HOME"
    read -r ans
    case "$ans" in s|S|si|sì|y|Y) rm -rf "$DATA_HOME" ;; esac
  fi
  say "chess-me disinstallato."
  exit 0
fi

path_note() {
  case ":$PATH:" in
    *":$1:"*) ;;
    *) say "Nota: $1 non è nel PATH. Aggiungi al tuo ~/.zshrc o ~/.bashrc:"
       say "  export PATH=\"$1:\$PATH\"" ;;
  esac
}

# ---------- 1. cartella self-contained (archivio chess-me-<ver>-<os>-<arch>.tar.gz) ----------
if [ -z "$FROM" ] && [ -x "$SRC/chess-me" ] && [ -f "$SRC/VERSION" ]; then
  PREFIX="${PREFIX:-$DATA_HOME/app}"
  if [ "$SRC" != "$PREFIX" ]; then
    # sostituisce solo una cartella che è davvero un'installazione di chess-me
    if [ -e "$PREFIX" ] && [ ! -f "$PREFIX/VERSION" ]; then
      die "$PREFIX esiste e non è un'installazione di chess-me: scegli un altro --prefix"
    fi
    mkdir -p "$(dirname "$PREFIX")"
    rm -rf "$PREFIX.new"
    cp -R "$SRC" "$PREFIX.new"
    rm -rf "$PREFIX"
    mv "$PREFIX.new" "$PREFIX"
  fi
  if [ "$(uname -s)" = Darwin ]; then
    # binari non firmati: togli la quarantena del download, solo dalla cartella installata
    xattr -dr com.apple.quarantine "$PREFIX" 2>/dev/null || true
  fi
  mkdir -p "$BIN_DIR"
  ln -sf "$PREFIX/chess-me" "$BIN_DIR/chess-me"
  say "chess-me $(cat "$PREFIX/VERSION") installato in $PREFIX"
  say "comando: $BIN_DIR/chess-me"
  path_note "$BIN_DIR"
  if [ "$LLM" = 1 ]; then "$PREFIX/chess-me" setup --llm --yes; else "$PREFIX/chess-me" doctor || true; fi
  exit 0
fi

# ---------- 2. pacchetto Python (pipx o pip in un venv dedicato) ----------
if [ -z "$FROM" ]; then
  [ -f "$SRC/pyproject.toml" ] || die "nessun sorgente qui: usa --from <cartella|wheel|git+https://…>"
  FROM="$SRC"
fi

find_python() {
  for c in ${PYTHON:-} python3.14 python3.13 python3.12 python3; do
    if has "$c" && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
      command -v "$c"; return 0
    fi
  done
  return 1
}
PY="$(find_python)" || die "serve Python >= 3.12 (es. brew install python@3.12 / apt install python3.12), oppure PYTHON=/percorso/python"

if [ "$METHOD" = auto ]; then
  if has pipx; then METHOD=pipx; else METHOD=pip; fi
fi

if [ "$METHOD" = pipx ]; then
  has pipx || die "pipx non trovato (brew install pipx / apt install pipx), oppure usa --pip"
  say "→ pipx install chess-me da $FROM"
  pipx install --force --python "$PY" "$FROM"
  PIPX_BIN="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$HOME/.local/bin")"
  CMD="$PIPX_BIN/chess-me"
  path_note "$PIPX_BIN"
else
  VENV="${PREFIX:-$DATA_HOME/venv}"
  if [ -e "$VENV" ] && [ ! -f "$VENV/$MARK" ]; then
    die "$VENV esiste e non è un venv di chess-me: scegli un altro --prefix"
  fi
  say "→ venv in $VENV ($("$PY" --version))"
  "$PY" -m venv "$VENV"
  touch "$VENV/$MARK"
  "$VENV/bin/python" -m pip install -q --upgrade pip
  say "→ pip install chess-me da $FROM"
  "$VENV/bin/python" -m pip install -q --upgrade "$FROM"
  mkdir -p "$BIN_DIR"
  ln -sf "$VENV/bin/chess-me" "$BIN_DIR/chess-me"
  CMD="$BIN_DIR/chess-me"
  path_note "$BIN_DIR"
fi

say "chess-me $("$CMD" --version | cut -d' ' -f2) installato ($METHOD) · comando: $CMD"
if [ "$SETUP" = 1 ]; then
  # Stockfish e aperture (+ llama-server e modello con --llm) in $DATA_HOME, verificati con SHA256
  if [ "$LLM" = 1 ]; then "$CMD" setup --llm --yes; else "$CMD" setup --yes; fi
else
  "$CMD" doctor || true
fi
