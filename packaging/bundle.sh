#!/bin/sh
# Costruisce la cartella self-contained di chess-me per la macchina corrente (macOS arm64 o Linux x86_64)
# e l'archivio dist/chess-me-<versione>-<os>-<arch>.tar.gz (+ .sha256).
#
#   packaging/bundle.sh
#   PYTHON=python3.12 packaging/bundle.sh
#
# Requisiti: Python >= 3.12, git, cmake, un compilatore C/C++ (Xcode CLT su macOS), curl.
# Stockfish: release ufficiale sf_18 (verificata con SHA256) se disponibile, altrimenti compilato.
# Per Linux x86_64 da qualunque macchina: docker build --platform linux/amd64 --target cli-export --output dist/ .
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
SF_VERSION="${SF_VERSION:-sf_18}"
LLAMA_CPP_VERSION="${LLAMA_CPP_VERSION:-v1.0.0}"
LLAMA_CPP_BUILD="${LLAMA_CPP_BUILD:-12359}"
WORK="$ROOT/build/cli"
DIST="$ROOT/dist"

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"; ARCH="$(uname -m)"
case "$OS-$ARCH" in
  darwin-arm64) SF_ARCH=apple-silicon; NAME_OS=macos ;;
  linux-x86_64) SF_ARCH=x86-64-avx2; NAME_OS=linux ;;
  linux-aarch64) SF_ARCH=armv8-dotprod; NAME_OS=linux; ARCH=arm64 ;;
  *) echo "piattaforma non supportata: $OS-$ARCH" >&2; exit 1 ;;
esac
JOBS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"

mkdir -p "$WORK" "$DIST"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/src/chess_me/__init__.py")"
echo "== chess-me $VERSION per $NAME_OS-$ARCH"

# 1. ambiente Python per PyInstaller
if [ ! -x "$WORK/venv/bin/python" ]; then "$PY" -m venv "$WORK/venv"; fi
"$WORK/venv/bin/pip" install -q --upgrade pip
"$WORK/venv/bin/pip" install -q "$ROOT[bundle]"

# 2. Stockfish: release ufficiale pinnata con SHA256 (src/chess_me/data/binaries.toml) se c'è per questa piattaforma,
#    altrimenti compilato dal sorgente
check_stockfish() {
  out="$( (printf 'uci\nisready\ngo depth 8\n'; sleep 3; printf 'quit\n') | "$1" 2>&1 )"
  if echo "$out" | grep -q "ERROR" || ! echo "$out" | grep -q "^bestmove"; then
    echo "Stockfish non funzionante: $1" >&2; echo "$out" | grep ERROR >&2; return 1
  fi
}
if [ ! -x "$WORK/stockfish" ]; then
  if "$WORK/venv/bin/python" -c \
      "import sys; from chess_me import downloads; sys.exit(0 if downloads.entry('stockfish') else 1)"; then
    rm -rf "$WORK/sfhome"
    CHESSME_HOME="$WORK/sfhome" "$WORK/venv/bin/python" -c \
      "from chess_me import downloads; downloads.install_stockfish()"
    cp "$WORK/sfhome/bin/stockfish" "$WORK/stockfish.tmp"
  else
    rm -rf "$WORK/sf"
    git clone --depth 1 --branch "$SF_VERSION" https://github.com/official-stockfish/Stockfish.git "$WORK/sf"
    (cd "$WORK/sf/src" && make -j"$JOBS" build ARCH="$SF_ARCH" && strip stockfish && cp stockfish "$WORK/stockfish.tmp")
  fi
  check_stockfish "$WORK/stockfish.tmp"
  mv "$WORK/stockfish.tmp" "$WORK/stockfish"
fi

# 3. llama-server (su macOS con Metal)
if [ ! -x "$WORK/llama/llama-server" ]; then
  rm -rf "$WORK/llama.cpp" "$WORK/llama"
  git clone --depth 1 --branch "$LLAMA_CPP_VERSION" https://github.com/ggml-org/llama.cpp.git "$WORK/llama.cpp"
  if [ "$NAME_OS" = linux ] && [ "$ARCH" = arm64 ]; then CPUFLAGS="-DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8.2-a+fp16+dotprod"
  elif [ "$NAME_OS" = linux ]; then CPUFLAGS="-DGGML_NATIVE=OFF"
  else CPUFLAGS=""; fi
  # shellcheck disable=SC2086
  HF_UI_VERSION="b$LLAMA_CPP_BUILD" cmake -S "$WORK/llama.cpp" -B "$WORK/llama.cpp/build" -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF -DLLAMA_BUILD_NUMBER="$LLAMA_CPP_BUILD" $CPUFLAGS \
    -DGGML_OPENMP=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF
  HF_UI_VERSION="b$LLAMA_CPP_BUILD" cmake --build "$WORK/llama.cpp/build" --target llama-server -j"$JOBS"
  mkdir -p "$WORK/llama"
  cp "$WORK/llama.cpp/build/bin/llama-server" "$WORK/llama/"
  strip "$WORK/llama/llama-server" || true
fi

# 4. database delle aperture
if [ ! -f "$WORK/openings.sqlite" ]; then
  "$WORK/venv/bin/python" -m chess_me.build_openings "$WORK/openings.sqlite"
fi

# 5. eseguibile Python (PyInstaller --onedir)
("$WORK/venv/bin/pyinstaller" --noconfirm --clean \
  --distpath "$WORK/pyi-dist" --workpath "$WORK/pyi-work" "$ROOT/packaging/chess-me.spec")

# 6. assemblaggio
OUT="$WORK/chess-me"
rm -rf "$OUT"
cp -R "$WORK/pyi-dist/chess-me" "$OUT"
mkdir -p "$OUT/bin" "$OUT/share"
cp "$WORK/stockfish" "$OUT/bin/stockfish"
cp "$WORK/llama/llama-server" "$OUT/bin/llama-server"
cp "$WORK/openings.sqlite" "$OUT/share/openings.sqlite"
cp "$ROOT/install.sh" "$OUT/install.sh"
cp "$ROOT/packaging/README.txt" "$OUT/README.txt"
echo "$VERSION" > "$OUT/VERSION"

"$OUT/chess-me" doctor
TAR="$DIST/chess-me-$VERSION-$NAME_OS-$ARCH.tar.gz"
tar -C "$WORK" -czf "$TAR" chess-me
(cd "$DIST" && shasum -a 256 "$(basename "$TAR")" > "$(basename "$TAR").sha256")
echo "== $TAR ($(du -h "$TAR" | cut -f1))"
