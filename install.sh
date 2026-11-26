#!/usr/bin/env bash
# Installer interattivo di chess-me.
#
#   ./install.sh                  menu interattivo (↑/↓, Spazio, Invio, Esc): scegli cosa installare e scaricare
#   ./install.sh --yes            senza domande: chess-me + Stockfish + aperture (con --llm anche l'LLM)
#   ./install.sh --llm            preseleziona llama-server e il modello LLM (~1,1 GB)
#   ./install.sh --from <spec>    cosa installare: cartella, .whl, git+https://… (default: questa cartella)
#   ./install.sh --pipx | --pip   forza il metodo (pip = venv dedicato)
#   ./install.sh --no-setup       non scaricare nulla oltre al programma (es. Stockfish già nel PATH)
#   ./install.sh --prefix DIR     dove installare (bundle: ~/.local/share/chess-me/app, pip: …/venv)
#   ./install.sh --bin-dir DIR    dove mettere il comando chess-me (default ~/.local/bin)
#   ./install.sh --uninstall [--purge]   --purge elimina anche binari, modello LLM e dati scaricati
#   ./install.sh --lang it|en|es  lingua predefinita di chess-me (e dell'installer); nel menu è la prima scelta
#
# Variabili: PYTHON (interprete >= 3.12 da usare), CHESSME_HOME (cartella dei dati, default ~/.local/share/chess-me).
# Funziona con bash 3.2 (macOS) e richiede curl per mostrare l'avanzamento dei download.
set -eu

# ============================================================ configurazione
DATA_HOME="${CHESSME_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/chess-me}"
BIN_DIR="$HOME/.local/bin"
PREFIX=""
FROM=""
METHOD=auto
MODE=""            # install | uninstall (vuoto = chiedi)
PURGE=0
ASSUME_YES=0
PRESEL_LLM=0
NO_SETUP=0
SRC="$(cd "$(dirname "$0")" && pwd)"
MARK=".chess-me-venv"
MODEL_FILE="Qwen3-1.7B-Q4_K_M.gguf"
# valori di riserva (la fonte è chess_me/llm/server.py, letta dal pacchetto installato quando possibile)
MODEL_URL="https://huggingface.co/unsloth/Qwen3-1.7B-GGUF/resolve/main/$MODEL_FILE"
MODEL_SHA256="b139949c5bd74937ad8ed8c8cf3d9ffb1e99c866c823204dc42c0d91fa181897"
MODEL_SIZE=1107409472
UI_LANG=""         # it | en | es (vuoto = dall'impostazione salvata o dal locale)

# L "italiano" "english" "español": il testo nella lingua scelta
L() { case "$UI_LANG" in en) printf '%s' "$2" ;; es) printf '%s' "$3" ;; *) printf '%s' "$1" ;; esac; }

while [ $# -gt 0 ]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --pipx) METHOD=pipx; shift ;;
    --pip) METHOD=pip; shift ;;
    --llm) PRESEL_LLM=1; shift ;;
    --no-setup) NO_SETUP=1; shift ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    --bin-dir) BIN_DIR="$2"; shift 2 ;;
    --uninstall) MODE=uninstall; shift ;;
    --purge) PURGE=1; shift ;;
    -y|--yes) ASSUME_YES=1; shift ;;
    --lang) UI_LANG="$2"; shift 2 ;;
    -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'install.sh: opzione sconosciuta / unknown option: %s (--help)\n' "$1" >&2; exit 1 ;;
  esac
done

# ------------------------------------------------------------ lingua
lang_ok() { case "$1" in it|en|es) return 0 ;; *) return 1 ;; esac; }
LANG_CHOSEN=0
if [ -n "$UI_LANG" ]; then
  lang_ok "$UI_LANG" || { printf 'install.sh: --lang it|en|es\n' >&2; exit 1; }
  LANG_CHOSEN=1
else
  # impostazione salvata da chess-me (settings.json), altrimenti il locale del sistema
  UI_LANG="$(sed -n 's/.*"lang": *"\([a-z]*\)".*/\1/p' "$DATA_HOME/settings.json" 2>/dev/null | head -n 1)"
  if ! lang_ok "$UI_LANG"; then
    UI_LANG="$(printf '%s' "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" | cut -c1-2 | tr '[:upper:]' '[:lower:]')"
    lang_ok "$UI_LANG" || UI_LANG=it
  fi
fi
lang_name() { case "$1" in en) echo "English" ;; es) echo "Español" ;; *) echo "Italiano" ;; esac; }

INTERACTIVE=1
if [ "$ASSUME_YES" = 1 ] || [ ! -t 0 ] || [ ! -t 1 ]; then INTERACTIVE=0; fi

# ============================================================ aspetto
if [ -t 1 ] && [ "${NO_COLOR:-}" = "" ] && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
  B=$'\033[1m'; D=$'\033[2m'; R=$'\033[0m'
  RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; BLU=$'\033[34m'; CYN=$'\033[36m'
else
  B=""; D=""; R=""; RED=""; GRN=""; YLW=""; BLU=""; CYN=""
fi
EL=$'\033[K'
[ -t 1 ] || EL=""

say()  { printf '%s\n' "$*"; }
info() { printf '%s\n' "  ${D}$*${R}"; }
ok()   { printf '%s\n' "  ${GRN}✓${R} $*"; }
warn() { printf '%s\n' "  ${YLW}!${R} $*"; }
die()  { tui_close; printf '\n%s\n' "  ${RED}✗ $*${R}" >&2; exit 1; }
has()  { command -v "$1" >/dev/null 2>&1; }

cols() { local c; c=$(tput cols 2>/dev/null || echo 80); [ "$c" -gt 20 ] 2>/dev/null || c=80; echo "$c"; }

hsize() {  # byte → "1,1 GB"
  awk -v b="${1:-0}" 'BEGIN{
    split("B KB MB GB TB",u," "); i=1; while (b>=1024 && i<5) { b/=1024; i++ }
    s = (i<=2) ? sprintf("%d %s", b, u[i]) : sprintf("%.1f %s", b, u[i]); gsub(/\./, ",", s); print s }'
}
htime() {  # secondi → "1m 05s"
  local s=${1:-0}
  if [ "$s" -ge 3600 ]; then printf '%dh %02dm' $((s/3600)) $((s%3600/60))
  elif [ "$s" -ge 60 ]; then printf '%dm %02ds' $((s/60)) $((s%60))
  else printf '%ds' "$s"; fi
}

banner() {
  say ""
  say "  ${B}${CYN}♞  chess-me${R} ${D}— installer${R}"
  say "  ${D}$(L "revisione delle partite a scacchi nel terminale" "chess game review in the terminal" "revisión de partidas de ajedrez en la terminal")${R}"
  say ""
}

section() { say ""; say "${B}$*${R}"; }

tildify() { case "$1" in "$HOME"*) printf '~%s' "${1#"$HOME"}" ;; *) printf '%s' "$1" ;; esac; }

# ============================================================ menu a tutto schermo (come la ricerca delle partite)
# ↑/↓ (o j/k) per muoversi, Invio per scegliere, Spazio per spuntare, Esc per tornare indietro, q per uscire.
REV=""; [ -n "$B" ] && REV=$'\033[7m'
TUI_ON=0
MSG=""          # avviso mostrato sotto il menu fino al tasto successivo
MENU_BODY=""    # righe mostrate tra il titolo e le opzioni (es. il riepilogo)
CHOICE=0
KEY=""

tui_open() {
  [ "$TUI_ON" = 1 ] && return 0
  tput smcup 2>/dev/null || true
  tput civis 2>/dev/null || true
  stty -echo 2>/dev/null || true
  TUI_ON=1
}
tui_close() {
  [ "$TUI_ON" = 1 ] || return 0
  stty echo 2>/dev/null || true
  tput cnorm 2>/dev/null || true
  tput rmcup 2>/dev/null || true
  TUI_ON=0
}
quit_tui() { tui_close; say "  $(L "Uscita: nessuna modifica." "Exit: nothing changed." "Salida: ningún cambio.")"; exit 0; }

row() { printf '%s%s\n' "$*" "$EL"; }
key() { printf '%s %s %s %s  ' "$REV" "$1" "$R" "$2"; }

tui_top() {  # tui_top "titolo" "sottotitolo"
  printf '\033[H'
  row ""
  row "  ${B}${CYN}♞  chess-me${R} ${D}— installer · $PLAT${R}"
  row ""
  row "  ${B}$1${R}"
  [ -n "$2" ] && row "  ${D}$2${R}"
  row ""
  if [ -n "$MENU_BODY" ]; then
    printf '%s\n' "$MENU_BODY" | while IFS= read -r l; do row "$l"; done
    row ""
  fi
}
tui_bottom() {  # tui_bottom "tasti"
  if [ -n "$MSG" ]; then row ""; row "  ${YLW}! $MSG${R}"; fi
  printf '\033[J'
  printf '\033[%d;1H%s%s' "$(tput lines 2>/dev/null || echo 24)" "$1" "$EL"
  MSG=""
}

read_key() {  # imposta KEY: up down space enter esc quit eof 1-9 other
  local k="" k2="" k3=""
  IFS= read -rsn1 k || { KEY=eof; return 0; }
  case "$k" in
    $'\033')
      IFS= read -rsn1 -t 1 k2 || k2=""
      if [ "$k2" = "[" ] || [ "$k2" = O ]; then
        IFS= read -rsn1 -t 1 k3 || k3=""
        case "$k3" in A) KEY=up ;; B) KEY=down ;; *) KEY=other ;; esac
      elif [ -z "$k2" ]; then KEY=esc
      else KEY=other; fi ;;
    "") KEY=enter ;;
    " ") KEY=space ;;
    k|K) KEY=up ;;
    j|J) KEY=down ;;
    q|Q) KEY=quit ;;
    [1-9]) KEY="$k" ;;
    *) KEY=other ;;
  esac
}

# menu_select "titolo" "sottotitolo" predefinito "etichetta|descrizione"… → CHOICE (1…n, 0 = Esc/indietro)
menu_select() {
  local title="$1" sub="$2" cur=$(($3 - 1)) i lab desc
  shift 3
  local n=$#
  local -a opts
  opts=("$@")
  tui_open
  while :; do
    tui_top "$title" "$sub"
    for ((i = 0; i < n; i++)); do
      lab="${opts[i]%%|*}"; desc="${opts[i]#*|}"; [ "$desc" = "${opts[i]}" ] && desc=""
      if [ "$i" = "$cur" ]; then row "  ${CYN}${B}❯ $lab${R}   ${D}$desc${R}"
      else row "    $lab   ${D}$desc${R}"; fi
    done
    tui_bottom "$(key '↑↓' "$(L muovi move mover)")$(key "$(L invio enter intro)" "$(L scegli choose elegir)")$(key esc "$(L indietro back atrás)")$(key q "$(L esci quit salir)")"
    read_key
    case "$KEY" in
      up) cur=$(((cur - 1 + n) % n)) ;;
      down) cur=$(((cur + 1) % n)) ;;
      enter|space) CHOICE=$((cur + 1)); MENU_BODY=""; return 0 ;;
      esc) CHOICE=0; MENU_BODY=""; return 0 ;;
      quit|eof) quit_tui ;;
      [1-9]) if [ "$KEY" -le "$n" ]; then cur=$((KEY - 1)); fi ;;
    esac
  done
}

# ============================================================ processi in background, Ctrl-C
BG_PID=""
LOG="$(mktemp -t chess-me-install.XXXXXX)"
cleanup() {
  tui_close
  [ -n "$BG_PID" ] && kill "$BG_PID" 2>/dev/null || true
  rm -f "$LOG"
  [ -t 1 ] && tput cnorm 2>/dev/null || true
}
on_int() {
  cleanup
  printf '\n\n%s\n' "  ${YLW}$(L "Interrotto." "Interrupted." "Interrumpido.")${R} $(L "I download parziali (.part) vengono ripresi al prossimo avvio." "Partial downloads (.part) resume on the next run." "Las descargas parciales (.part) se reanudan en la próxima ejecución.")" >&2
  exit 130
}
trap cleanup EXIT
trap on_int INT TERM

# ============================================================ avanzamento complessivo
STEP_N=0
STEP_TOT=0
step() {  # step "titolo"
  STEP_N=$((STEP_N + 1))
  local w=$(( $(cols) - 22 )); [ "$w" -gt 30 ] && w=30
  local fill=$(( w * (STEP_N - 1) / STEP_TOT )) pct=$(( 100 * (STEP_N - 1) / STEP_TOT ))
  local bar; bar="$(printf '%*s' "$fill" '' | tr ' ' '#')$(printf '%*s' $((w - fill)) '' | tr ' ' '.')"
  say ""
  say "${B}${BLU}[$STEP_N/$STEP_TOT]${R} ${B}$1${R}   ${D}$(L totale total total) ${bar} ${pct}%${R}"
}

# Esegue un comando in background mostrando uno spinner, il tempo trascorso e l'ultima riga del log.
run() {  # run "etichetta" comando args…
  local label="$1"; shift
  : >"$LOG"
  "$@" >>"$LOG" 2>&1 &
  BG_PID=$!
  local t0 i=0 last w
  local frames=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)
  t0=$(date +%s)
  [ -t 1 ] && tput civis 2>/dev/null || true
  while kill -0 "$BG_PID" 2>/dev/null; do
    if [ -t 1 ]; then
      w=$(( $(cols) - ${#label} - 16 )); [ "$w" -lt 10 ] && w=10
      last="$(tail -n 1 "$LOG" 2>/dev/null | tr -d '\r' | cut -c1-"$w")"
      printf '\r  %s %s %s %s%s' "${CYN}${frames[$((i % 10))]}${R}" "$label" \
        "${D}$(htime $(( $(date +%s) - t0 )))${R}" "${D}${last}${R}" "$EL"
      i=$((i + 1))
    fi
    sleep 0.15
  done
  local rc=0
  wait "$BG_PID" || rc=$?
  BG_PID=""
  [ -t 1 ] && tput cnorm 2>/dev/null || true
  if [ "$rc" = 0 ]; then
    printf '\r  %s %s %s%s\n' "${GRN}✓${R}" "$label" "${D}($(htime $(( $(date +%s) - t0 ))))${R}" "$EL"
  else
    printf '\r  %s %s%s\n' "${RED}✗${R}" "$label" "$EL"
    say "  ${D}── $(L "ultime righe del log" "last lines of the log" "últimas líneas del log") ──${R}"
    tail -n 15 "$LOG" | sed 's/^/    /'
    return "$rc"
  fi
}

# ============================================================ download con barra di avanzamento
remote_size() {  # Content-Length dopo i redirect (0 se sconosciuto)
  curl -sIL --max-time 20 -A chess-me-installer "$1" 2>/dev/null | tr -d '\r' |
    awk 'tolower($1)=="content-length:"{n=$2} END{print n+0}'
}

fsize() { if [ -f "$1" ]; then wc -c <"$1" | tr -d ' '; else echo 0; fi; }

sha256_of() {
  if has shasum; then shasum -a 256 "$1" | cut -d' ' -f1
  elif has sha256sum; then sha256sum "$1" | cut -d' ' -f1
  else echo ""; fi
}

draw_bar() {  # draw_bar etichetta fatti totale t0 inizio
  local label="$1" done="$2" total="$3" t0="$4" start="$5"
  local el=$(( $(date +%s) - t0 )); [ "$el" -lt 1 ] && el=1
  local speed=$(( (done - start) / el ))
  local w=$(( $(cols) - 58 )); [ "$w" -gt 40 ] && w=40; [ "$w" -lt 10 ] && w=10
  if [ "$total" -gt 0 ]; then
    [ "$done" -gt "$total" ] && done=$total
    local pct=$(( done * 100 / total )) fill=$(( done * w / total )) eta="--"
    [ "$speed" -gt 0 ] && eta="$(htime $(( (total - done) / speed )))"
    printf '\r  %-12.12s %s%s%s%s %3d%%  %9s / %-9s %9s/s  ETA %s%s' "$label" "$GRN" \
      "$(printf '%*s' "$fill" '' | tr ' ' '#')" "$D$(printf '%*s' $((w - fill)) '' | tr ' ' '.')" "$R" \
      "$pct" "$(hsize "$done")" "$(hsize "$total")" "$(hsize "$speed")" "$eta" "$EL"
  else
    printf '\r  %-12.12s %9s  %9s/s%s' "$label" "$(hsize "$done")" "$(hsize "$speed")" "$EL"
  fi
}

# fetch URL DEST SHA256|"" ETICHETTA [DIMENSIONE_ATTESA]: scarica (riprendendo un .part), verifica l'hash.
fetch() {
  local url="$1" dest="$2" sha="$3" label="$4" expect="${5:-0}"
  local part="$dest.part" total start t0 rc=0 size
  total=$(remote_size "$url"); [ "$total" -gt 0 ] || total="$expect"
  mkdir -p "$(dirname "$dest")"
  start=$(fsize "$part")
  if [ "$total" -gt 0 ] && [ "$start" -ge "$total" ]; then rm -f "$part"; start=0; fi
  [ "$start" -gt 0 ] && info "$(L "riprendo il download da" "resuming the download from" "reanudo la descarga desde") $(hsize "$start")"
  t0=$(date +%s)
  curl -fsSL --retry 3 --retry-delay 2 -A chess-me-installer -C - -o "$part" "$url" 2>>"$LOG" &
  BG_PID=$!
  [ -t 1 ] && tput civis 2>/dev/null || true
  while kill -0 "$BG_PID" 2>/dev/null; do
    size=$(fsize "$part")
    [ -t 1 ] && draw_bar "$label" "$size" "$total" "$t0" "$start"
    sleep 0.2
  done
  wait "$BG_PID" || rc=$?
  BG_PID=""
  [ -t 1 ] && tput cnorm 2>/dev/null || true
  size=$(fsize "$part")
  if [ "$rc" != 0 ]; then
    if [ "$rc" = 33 ]; then rm -f "$part"; fi   # il server non accetta la ripresa: si riparte da zero la prossima volta
    printf '\r%s' "$EL"
    die "$label: $(L "download non riuscito (curl, codice $rc). Riprova: il file parziale viene ripreso." "download failed (curl, code $rc). Try again: the partial file is resumed." "la descarga falló (curl, código $rc). Vuelve a intentarlo: el archivo parcial se reanuda.")"
  fi
  [ -t 1 ] && draw_bar "$label" "$size" "${total:-$size}" "$t0" "$start"
  [ -t 1 ] && printf '\n'
  if [ -n "$sha" ]; then
    local got; got="$(sha256_of "$part")"
    if [ -z "$got" ]; then warn "$label: $(L "shasum/sha256sum non trovati, hash non verificato" "shasum/sha256sum not found, hash not checked" "no se encontró shasum/sha256sum, hash sin verificar")"
    elif [ "$got" != "$sha" ]; then rm -f "$part"; die "$label: $(L "SHA256 diverso da quello atteso, file scartato" "SHA256 does not match, file discarded" "el SHA256 no coincide, archivo descartado")"
    else ok "$label: $(hsize "$size") $(L "scaricati, SHA256 verificato" "downloaded, SHA256 verified" "descargados, SHA256 verificado")"; fi
  else
    ok "$label: $(hsize "$size") $(L scaricati downloaded descargados)"
  fi
  mv -f "$part" "$dest"
}

# ============================================================ piattaforma e stato attuale
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m | tr '[:upper:]' '[:lower:]')"
case "$ARCH" in aarch64) ARCH=arm64 ;; amd64) ARCH=x86_64 ;; esac
PLAT="$OS-$ARCH"
case "$PLAT" in darwin-arm64|linux-x86_64) PREBUILT=1 ;; *) PREBUILT=0 ;; esac

BUNDLE=0
if [ -z "$FROM" ] && [ -x "$SRC/chess-me" ] && [ -f "$SRC/VERSION" ]; then BUNDLE=1; fi

find_python() {
  local c
  for c in ${PYTHON:-} python3.14 python3.13 python3.12 python3; do
    if has "$c" && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
      command -v "$c"; return 0
    fi
  done
  return 1
}
pipx_has_chessme() { has pipx && pipx list --short 2>/dev/null | grep -q '^chess-me '; }

existing_cmd() {
  if [ -x "$BIN_DIR/chess-me" ]; then echo "$BIN_DIR/chess-me"; return; fi
  if has chess-me; then command -v chess-me; return; fi
  echo ""
}

dir_size() { du -sk "$1" 2>/dev/null | awk '{print $1 * 1024}'; }

# Stato delle risorse (prima dell'installazione, senza Python): ST_SF, ST_OP, ST_LL, ST_MD = percorso o ""
scan_resources() {
  ST_SF=""; ST_OP=""; ST_LL=""; ST_MD=""
  if [ "$BUNDLE" = 1 ]; then
    [ -x "$SRC/bin/stockfish" ] && ST_SF="$SRC/bin/stockfish ($(L "nel bundle" "in the bundle" "en el bundle"))"
    [ -f "$SRC/share/openings.sqlite" ] && ST_OP="$SRC/share/openings.sqlite ($(L "nel bundle" "in the bundle" "en el bundle"))"
    [ -x "$SRC/bin/llama-server" ] && ST_LL="$SRC/bin/llama-server ($(L "nel bundle" "in the bundle" "en el bundle"))"
  fi
  [ -z "$ST_SF" ] && [ -n "${STOCKFISH_PATH:-}" ] && [ -x "${STOCKFISH_PATH}" ] && ST_SF="$STOCKFISH_PATH"
  [ -z "$ST_SF" ] && [ -x "$DATA_HOME/bin/stockfish" ] && ST_SF="$DATA_HOME/bin/stockfish"
  [ -z "$ST_SF" ] && has stockfish && ST_SF="$(command -v stockfish) ($(L "di sistema" "system" "del sistema"))"
  [ -z "$ST_OP" ] && [ -f "$DATA_HOME/openings.sqlite" ] && ST_OP="$DATA_HOME/openings.sqlite"
  [ -z "$ST_OP" ] && [ "$FROM" = "$SRC" ] && [ -f "$SRC/src/chess_me/data/openings.sqlite" ] && ST_OP="($(L "nel pacchetto Python" "in the Python package" "en el paquete Python"))"
  [ -z "$ST_LL" ] && [ -x "$DATA_HOME/bin/llama/llama-server" ] && ST_LL="$DATA_HOME/bin/llama/llama-server"
  [ -z "$ST_LL" ] && has llama-server && ST_LL="$(command -v llama-server) ($(L "di sistema" "system" "del sistema"))"
  [ -f "$DATA_HOME/models/$MODEL_FILE" ] && ST_MD="$DATA_HOME/models/$MODEL_FILE"
  return 0
}

# ============================================================ disinstallazione
uninstall_found() {
  [ -L "$BIN_DIR/chess-me" ] && return 0
  pipx_has_chessme && return 0
  local d
  for d in "${PREFIX:-$DATA_HOME/app}" "${PREFIX:-$DATA_HOME/venv}"; do
    if [ -f "$d/VERSION" ] || [ -f "$d/$MARK" ]; then return 0; fi
  done
  return 1
}

uninstall_run() {  # uninstall_run 0|1 (1 = elimina anche i dati)
  local purge="$1" d
  section "$(L Disinstallazione Uninstall Desinstalación)"
  if ! uninstall_found && [ ! -d "$DATA_HOME" ]; then say "  $(L "chess-me non risulta installato." "chess-me does not seem to be installed." "chess-me no parece estar instalado.")"; return 0; fi
  STEP_TOT=2; [ "$purge" = 1 ] && STEP_TOT=3
  step "$(L "Comando chess-me" "chess-me command" "Comando chess-me")"
  if [ -L "$BIN_DIR/chess-me" ]; then rm "$BIN_DIR/chess-me"; ok "$(L rimosso removed eliminado) $BIN_DIR/chess-me"; else info "$(L "nessun collegamento in" "no link in" "ningún enlace en") $BIN_DIR"; fi
  step "$(L Programma Program Programa)"
  if pipx_has_chessme; then run "pipx uninstall chess-me" pipx uninstall chess-me; fi
  for d in "${PREFIX:-$DATA_HOME/app}" "${PREFIX:-$DATA_HOME/venv}"; do
    if [ -f "$d/VERSION" ] || [ -f "$d/$MARK" ]; then run "$(L elimino deleting elimino) $d" rm -rf "$d"; fi
  done
  if [ "$purge" = 1 ]; then
    step "$(L "Dati scaricati" "Downloaded data" "Datos descargados")"
    if [ -d "$DATA_HOME" ]; then run "$(L elimino deleting elimino) $DATA_HOME" rm -rf "$DATA_HOME"; fi
  fi
  say ""
  say "  ${GRN}${B}$(L "chess-me disinstallato." "chess-me uninstalled." "chess-me desinstalado.")${R}"
}

# ============================================================ stato iniziale
if [ -z "$FROM" ] && [ "$BUNDLE" = 0 ] && [ -f "$SRC/pyproject.toml" ]; then FROM="$SRC"; fi
PY="$(find_python || true)"

ensure_python() {
  [ "$BUNDLE" = 1 ] && return 0
  [ -n "$FROM" ] || die "$(L "nessun sorgente qui: usa --from <cartella|wheel|git+https://…>" "no source here: use --from <folder|wheel|git+https://…>" "no hay código fuente aquí: usa --from <carpeta|wheel|git+https://…>")"
  [ -n "$PY" ] || die "$(L "serve Python >= 3.12 (es. brew install python@3.12 / apt install python3.12), oppure PYTHON=/percorso/python" "Python >= 3.12 is required (e.g. brew install python@3.12 / apt install python3.12), or PYTHON=/path/to/python" "hace falta Python >= 3.12 (p. ej. brew install python@3.12 / apt install python3.12), o PYTHON=/ruta/python")"
  if [ "$METHOD" = pipx ] && ! has pipx; then die "$(L "pipx non trovato (brew install pipx / apt install pipx), oppure usa --pip" "pipx not found (brew install pipx / apt install pipx), or use --pip" "no se encontró pipx (brew install pipx / apt install pipx), o usa --pip")"; fi
}

SHOW_METHOD=0
if [ "$BUNDLE" = 1 ]; then METHOD=bundle
elif [ "$METHOD" = auto ]; then
  if ! has pipx; then METHOD=pip
  elif [ "$INTERACTIVE" = 1 ]; then SHOW_METHOD=1
  else METHOD=pipx; fi
fi

CUR="$(existing_cmd)"
CURV=""
[ -n "$CUR" ] && CURV="$("$CUR" --version 2>/dev/null | cut -d' ' -f2 || true)"
SHOW_MAIN=0
if [ -z "$MODE" ]; then
  if [ -n "$CUR" ] && [ "$INTERACTIVE" = 1 ]; then SHOW_MAIN=1; else MODE=install; fi
fi

scan_resources
if [ "$OS" = darwin ]; then SF_SIZE=115322880; LL_SIZE=16907811; else SF_SIZE=114401280; LL_SIZE=23311084; fi
OP_SIZE=1500000

# selezione: 1 = scarica
SEL_SF=0; SEL_OP=0; SEL_LLM=0
if [ "$NO_SETUP" = 0 ]; then
  if [ -z "$ST_SF" ] && [ "$PREBUILT" = 1 ]; then SEL_SF=1; fi
  if [ -z "$ST_OP" ]; then SEL_OP=1; fi
  if [ "$PRESEL_LLM" = 1 ]; then SEL_LLM=1; fi
fi

llm_size() {
  local n=0
  [ -z "$ST_LL" ] && n=$((n + LL_SIZE))
  [ -z "$ST_MD" ] && n=$((n + MODEL_SIZE))
  echo "$n"
}

total_download() {
  local n=0
  [ "$SEL_SF" = 1 ] && n=$((n + SF_SIZE))
  [ "$SEL_OP" = 1 ] && n=$((n + OP_SIZE))
  [ "$SEL_LLM" = 1 ] && n=$((n + $(llm_size)))
  echo "$n"
}

state() {
  if [ -n "$1" ]; then printf '%s' "${GRN}$(L "già presente" "already present" "ya presente")${R} ${D}$(tildify "$1")${R}"
  else printf '%s' "${YLW}$(L mancante missing falta)${R}"; fi
}

# ------------------------------------------------------------ schermata dei componenti
item_label() { case "$1" in 0) echo "Stockfish" ;; 1) L "Database delle aperture" "Openings database" "Base de aperturas" ;; 2) L "LLM locale (--llm)" "Local LLM (--llm)" "LLM local (--llm)" ;; esac; }
item_sel()   { case "$1" in 0) echo "$SEL_SF" ;; 1) echo "$SEL_OP" ;; 2) echo "$SEL_LLM" ;; esac; }
item_size()  { case "$1" in 0) echo "$SF_SIZE" ;; 1) echo "$OP_SIZE" ;; 2) llm_size ;; esac; }
item_short() {
  case "$1" in
    0) [ -n "$ST_SF" ] && L presente present presente || L mancante missing falta ;;
    1) [ -n "$ST_OP" ] && L presente present presente || L mancante missing falta ;;
    2) if [ -n "$ST_LL" ] && [ -n "$ST_MD" ]; then L presente present presente
       elif [ -n "$ST_LL" ] || [ -n "$ST_MD" ]; then L "in parte" partial parcial
       else L mancante missing falta; fi ;;
  esac
}
item_details() {
  case "$1" in
    0) row "  $(L "Il motore che analizza le partite: senza Stockfish chess-me non funziona." "The engine that analyses the games: chess-me does not work without Stockfish." "El motor que analiza las partidas: sin Stockfish chess-me no funciona.")"
       row "  $(L Stato Status Estado): $(state "$ST_SF")"
       if [ "$PREBUILT" = 0 ]; then row "  ${YLW}$(L "Nessun binario precompilato per $PLAT: installalo e mettilo nel PATH." "No prebuilt binary for $PLAT: install it and put it on your PATH." "No hay binario precompilado para $PLAT: instálalo y ponlo en el PATH.")${R}"
       else row "  ${D}$(L "Release ufficiale sf_18 da GitHub, verificata con SHA256" "Official sf_18 release from GitHub, verified with SHA256" "Release oficial sf_18 de GitHub, verificada con SHA256") → $(tildify "$DATA_HOME/bin")${R}"; fi ;;
    1) row "  $(L "Riconosce le aperture (nomi ECO) dai TSV di lichess-org/chess-openings." "Recognises openings (ECO names) from the lichess-org/chess-openings TSV files." "Reconoce las aperturas (nombres ECO) a partir de los TSV de lichess-org/chess-openings.")"
       row "  $(L Stato Status Estado): $(state "$ST_OP")"
       row "  ${D}$(L "Scarica ~1 MB di TSV e costruisce il database" "Downloads ~1 MB of TSV and builds the database" "Descarga ~1 MB de TSV y construye la base de datos") → $(tildify "$DATA_HOME")${R}" ;;
    2) row "  $(L "Commenti e riassunto riscritti da un LLM locale (Qwen3 1.7B con llama.cpp)." "Comments and summary rewritten by a local LLM (Qwen3 1.7B with llama.cpp)." "Comentarios y resumen reescritos por un LLM local (Qwen3 1.7B con llama.cpp).")"
       row "  llama-server: $(state "$ST_LL")"
       row "  $(L "modello:     " "model:       " "modelo:      ") $(state "$ST_MD")"
       row "  ${D}$(L "Si usa con chess-me --llm · il modello si elimina con chess-me remove-model" "Used with chess-me --llm · remove the model with chess-me remove-model" "Se usa con chess-me --llm · el modelo se elimina con chess-me remove-model")${R}" ;;
  esac
}

toggle() {
  case "$1" in
    0) if [ "$PREBUILT" = 0 ]; then MSG="$(L "nessuno Stockfish precompilato per $PLAT" "no prebuilt Stockfish for $PLAT" "no hay Stockfish precompilado para $PLAT")"; return 0; fi
       if [ -n "$ST_SF" ] && [ "$SEL_SF" = 0 ]; then MSG="$(L "Stockfish è già presente: verrà riscaricato in" "Stockfish is already present: it will be downloaded again into" "Stockfish ya está presente: se volverá a descargar en") $(tildify "$DATA_HOME/bin")"; fi
       SEL_SF=$((1 - SEL_SF)) ;;
    1) if [ -n "$ST_OP" ] && [ "$SEL_OP" = 0 ]; then MSG="$(L "il database c'è già: verrà ricostruito" "the database is already there: it will be rebuilt" "la base de datos ya existe: se reconstruirá")"; fi
       SEL_OP=$((1 - SEL_OP)) ;;
    2) if [ -n "$ST_LL" ] && [ -n "$ST_MD" ] && [ "$SEL_LLM" = 0 ]; then MSG="$(L "llama-server e modello sono già presenti" "llama-server and the model are already present" "llama-server y el modelo ya están presentes")"; return 0; fi
       if [ "$PREBUILT" = 0 ] && [ -z "$ST_LL" ] && [ "$SEL_LLM" = 0 ]; then MSG="$(L "nessun llama-server precompilato per $PLAT: installalo nel PATH" "no prebuilt llama-server for $PLAT: install it on your PATH" "no hay llama-server precompilado para $PLAT: instálalo en el PATH")"; fi
       SEL_LLM=$((1 - SEL_LLM)) ;;
  esac
}

choose_components() {  # 0 = continua, 1 = indietro
  local cur=0 i n=3 box mark sz
  tui_open
  while :; do
    tui_top "$(L "Cosa vuoi installare?" "What do you want to install?" "¿Qué quieres instalar?")" "$(L "Spunta i componenti da scaricare; ciò che c'è già non serve riscaricarlo." "Tick the components to download; what is already there need not be downloaded again." "Marca los componentes que descargar; lo que ya está no hace falta volver a descargarlo.")"
    if [ "$METHOD" = bundle ]; then row "    ${GRN}[✓]${R} chess-me                    ${D}$(L "cartella self-contained, sempre" "self-contained folder, always" "carpeta autocontenida, siempre")${R}"
    else row "    ${GRN}[✓]${R} chess-me                    ${D}$(L "programma e dipendenze Python, sempre" "program and Python dependencies, always" "programa y dependencias de Python, siempre")${R}"; fi
    for ((i = 0; i < n; i++)); do
      if [ "$(item_sel $i)" = 1 ]; then box="${GRN}[x]${R}"; else box="[ ]"; fi
      sz="$(hsize "$(item_size $i)")"
      if [ "$i" = "$cur" ]; then mark="${CYN}${B}❯${R}"; else mark=" "; fi
      if [ "$i" = "$cur" ]; then
        row "  $mark $box ${CYN}${B}$(printf '%-26s' "$(item_label $i)")${R}$(printf '%10s' "~$sz")   ${D}$(item_short $i)${R}"
      else
        row "  $mark $box $(printf '%-26s' "$(item_label $i)")$(printf '%10s' "~$sz")   ${D}$(item_short $i)${R}"
      fi
    done
    row ""
    row "  ${D}────────────────────────────────────────────────────────────${R}"
    item_details "$cur"
    row "  ${D}────────────────────────────────────────────────────────────${R}"
    row ""
    row "  $(L "Totale da scaricare" "Total download" "Total a descargar"): ${B}$(hsize "$(total_download)")${R}"
    tui_bottom "$(key '↑↓' "$(L muovi move mover)")$(key "$(L spazio space espacio)" "$(L seleziona select marcar)")$(key "$(L invio enter intro)" "$(L continua continue continuar)")$(key esc "$(L indietro back atrás)")$(key q "$(L esci quit salir)")"
    read_key
    case "$KEY" in
      up) cur=$(((cur - 1 + n) % n)) ;;
      down) cur=$(((cur + 1) % n)) ;;
      space) toggle "$cur" ;;
      [1-3]) cur=$((KEY - 1)); toggle "$cur" ;;
      enter) return 0 ;;
      esc) return 1 ;;
      quit|eof) quit_tui ;;
    esac
  done
}

# ------------------------------------------------------------ riepilogo
summary_text() {
  case "$METHOD" in
    bundle) echo "  • chess-me $(L in in en) $(tildify "${PREFIX:-$DATA_HOME/app}"), $(L "comando in" "command in" "comando en") $(tildify "$BIN_DIR")" ;;
    pipx)   echo "  • chess-me $(L con with con) pipx ($("$PY" --version 2>&1))" ;;
    pip)    echo "  • chess-me $(L "in un venv" "in a venv" "en un venv"): $(tildify "${PREFIX:-$DATA_HOME/venv}") ($("$PY" --version 2>&1)), $(L "comando in" "command in" "comando en") $(tildify "$BIN_DIR")" ;;
  esac
  echo "  • $(L "lingua predefinita" "default language" "idioma predeterminado"): $(lang_name "$UI_LANG")"
  [ "$SEL_SF" = 1 ] && echo "  • Stockfish → $(tildify "$DATA_HOME/bin")"
  [ "$SEL_OP" = 1 ] && echo "  • $(L "database delle aperture" "openings database" "base de datos de aperturas") → $(tildify "$DATA_HOME")"
  if [ "$SEL_LLM" = 1 ]; then
    [ -z "$ST_LL" ] && echo "  • llama-server → $(tildify "$DATA_HOME/bin/llama")"
    [ -z "$ST_MD" ] && echo "  • $(L "modello LLM" "LLM model" "modelo LLM") → $(tildify "$DATA_HOME/models")"
  fi
  if [ "$SEL_SF" = 0 ] && [ -z "$ST_SF" ]; then
    echo "  ${YLW}! $(L "senza Stockfish chess-me non può analizzare: installalo nel PATH o selezionalo" "without Stockfish chess-me cannot analyse: install it on your PATH or select it" "sin Stockfish chess-me no puede analizar: instálalo en el PATH o selecciónalo")${R}"
  fi
  echo ""
  echo "  Download: ${B}$(hsize "$NEED")${R}${FREE:+   ${D}$(L "spazio libero" "free space" "espacio libre"): $(hsize "$FREE")${R}}"
  if [ "$NEED" -gt 0 ] && ! has curl; then
    echo "  ${YLW}! $(L "curl non trovato: i download li farà 'chess-me setup' (avanzamento a scatti del 10%)" "curl not found: 'chess-me setup' will do the downloads (progress in 10% steps)" "no se encontró curl: las descargas las hará 'chess-me setup' (avance en pasos del 10%)")${R}"
  fi
}

compute_space() {
  NEED=$(total_download)
  local dir="$DATA_HOME"
  while [ ! -d "$dir" ]; do dir="$(dirname "$dir")"; done
  FREE=$(df -Pk "$dir" 2>/dev/null | awk 'NR==2{print $4 * 1024}')
  SPACE_OK=1
  if [ -n "$FREE" ] && [ "$FREE" -lt $((NEED + 200 * 1024 * 1024)) ]; then SPACE_OK=0; fi
}

# ============================================================ schermate
PURGE_SEL="$PURGE"
if [ "$INTERACTIVE" = 1 ]; then
  first_stage() {
    if [ "$SHOW_MAIN" = 1 ]; then stage=main
    elif [ "$MODE" = uninstall ]; then stage=uninstall
    elif [ "$SHOW_METHOD" = 1 ]; then stage=method
    else stage=components; fi
  }
  # la lingua è la prima scelta (salvo --lang o disinstallazione); Esc nelle schermate successive torna qui
  if [ "$LANG_CHOSEN" = 0 ] && [ "$MODE" != uninstall ]; then stage=lang; else first_stage; fi
  back_main() {
    if [ "$SHOW_MAIN" = 1 ] && [ "$stage" != main ]; then stage=main
    elif [ "$LANG_CHOSEN" = 0 ] && [ "$MODE" != uninstall ]; then stage=lang
    else quit_tui; fi
  }
  while [ "$stage" != done ]; do
    case "$stage" in
      lang)
        case "$UI_LANG" in en) cur=2 ;; es) cur=3 ;; *) cur=1 ;; esac
        menu_select "Lingua · Language · Idioma" \
          "$(L "Lingua predefinita di chess-me (interfaccia e commenti); si cambia con chess-me lang" "Default chess-me language (interface and comments); change it with chess-me lang" "Idioma predeterminado de chess-me (interfaz y comentarios); se cambia con chess-me lang")" "$cur" \
          "Italiano|it" "English|en" "Español|es"
        case "$CHOICE" in
          1) UI_LANG=it ;; 2) UI_LANG=en ;; 3) UI_LANG=es ;; *) quit_tui ;;
        esac
        scan_resources   # gli stati ("nel bundle", "di sistema") nella nuova lingua
        first_stage ;;
      main)
        menu_select "$(L "chess-me ${CURV:-?} è già installato" "chess-me ${CURV:-?} is already installed" "chess-me ${CURV:-?} ya está instalado")" "$(tildify "$CUR")" 1 \
          "$(L "Aggiorna o aggiungi componenti|reinstalla il programma e scegli cosa scaricare" "Update or add components|reinstall the program and choose what to download" "Actualizar o añadir componentes|reinstala el programa y elige qué descargar")" \
          "$(L "Disinstalla|rimuovi il programma, a scelta anche i dati scaricati" "Uninstall|remove the program, optionally also the downloaded data" "Desinstalar|elimina el programa y, si quieres, también los datos descargados")" \
          "$(L "Esci|" "Quit|" "Salir|")"
        case "$CHOICE" in
          1) MODE=install; ensure_python; if [ "$SHOW_METHOD" = 1 ]; then stage=method; else stage=components; fi ;;
          2) MODE=uninstall; stage=uninstall ;;
          0) back_main ;;
          *) quit_tui ;;
        esac ;;
      uninstall)
        if [ -d "$DATA_HOME" ]; then DSZ="$(hsize "$(dir_size "$DATA_HOME")")"; else DSZ="0 B"; fi
        MENU_BODY="  $(L Programma Program Programa): $(tildify "${CUR:-$(L "non trovato" "not found" "no encontrado")}")
  $(L "Dati scaricati" "Downloaded data" "Datos descargados"): $(tildify "$DATA_HOME") ($DSZ)"
        menu_select "$(L "Disinstalla chess-me" "Uninstall chess-me" "Desinstalar chess-me")" "" $((PURGE + 1)) \
          "$(L "Solo il programma|i dati scaricati restano" "Program only|the downloaded data stay" "Solo el programa|los datos descargados se quedan") ($DSZ)" \
          "$(L "Programma e dati scaricati|elimina anche Stockfish, llama-server, modello e aperture" "Program and downloaded data|also deletes Stockfish, llama-server, model and openings" "Programa y datos descargados|elimina también Stockfish, llama-server, modelo y aperturas") ($DSZ)" \
          "$(L "Annulla|" "Cancel|" "Cancelar|")"
        case "$CHOICE" in
          1) PURGE_SEL=0; stage=done ;;
          2) PURGE_SEL=1; stage=done ;;
          *) back_main ;;
        esac ;;
      method)
        ensure_python
        menu_select "$(L "Come installo il programma?" "How should the program be installed?" "¿Cómo instalo el programa?")" "$("$PY" --version 2>&1) · $(tildify "$FROM")" 1 \
          "pipx|$(L "ambiente isolato gestito da pipx (consigliato)" "isolated environment managed by pipx (recommended)" "entorno aislado gestionado por pipx (recomendado)")" \
          "$(L "venv dedicato" "dedicated venv" "venv dedicado")|$(tildify "${PREFIX:-$DATA_HOME/venv}"), $(L "comando in" "command in" "comando en") $(tildify "$BIN_DIR")"
        case "$CHOICE" in
          1) METHOD=pipx; stage=components ;;
          2) METHOD=pip; stage=components ;;
          *) back_main ;;
        esac ;;
      components)
        ensure_python
        if choose_components; then stage=summary
        elif [ "$SHOW_METHOD" = 1 ]; then stage=method
        else back_main; fi ;;
      summary)
        compute_space
        MENU_BODY="$(summary_text)"
        [ "$SPACE_OK" = 1 ] || MSG="$(L "spazio su disco insufficiente: servono almeno" "not enough disk space: at least this is needed:" "espacio en disco insuficiente: hacen falta al menos") $(hsize $((NEED + 200 * 1024 * 1024)))"
        menu_select "$(L Riepilogo Summary Resumen)" "$(L "Controlla e conferma" "Check and confirm" "Revisa y confirma")" 1 \
          "$(L "Installa|avvia download e installazione" "Install|start downloads and installation" "Instalar|inicia descargas e instalación")" \
          "$(L "Modifica i componenti|" "Change components|" "Cambiar componentes|")" \
          "$(L "Esci|" "Quit|" "Salir|")"
        case "$CHOICE" in
          1) if [ "$SPACE_OK" = 1 ]; then stage=done; fi ;;
          2|0) stage=components ;;
          *) quit_tui ;;
        esac ;;
    esac
  done
  tui_close
fi

banner
info "$(L sistema system sistema): $PLAT · $(L dati data datos): $DATA_HOME"

if [ "$MODE" = uninstall ]; then uninstall_run "$PURGE_SEL"; exit 0; fi

ensure_python
compute_space
section "$(L Riepilogo Summary Resumen)"
summary_text
[ "$SPACE_OK" = 1 ] || die "$(L "spazio su disco insufficiente" "not enough disk space" "espacio en disco insuficiente")"

# ------------------------------------------------------------ piano dei passi
STEP_TOT=1
[ "$METHOD" = pip ] && STEP_TOT=$((STEP_TOT + 1))
[ "$SEL_SF" = 1 ] && STEP_TOT=$((STEP_TOT + 1))
[ "$SEL_OP" = 1 ] && STEP_TOT=$((STEP_TOT + 1))
[ "$SEL_LLM" = 1 ] && [ -z "$ST_LL" ] && STEP_TOT=$((STEP_TOT + 1))
[ "$SEL_LLM" = 1 ] && [ -z "$ST_MD" ] && STEP_TOT=$((STEP_TOT + 1))
STEP_TOT=$((STEP_TOT + 1))   # verifica finale
T_START=$(date +%s)

path_note() {
  case ":$PATH:" in
    *":$1:"*) ;;
    *) warn "$1 $(L "non è nel PATH. Aggiungi al tuo ~/.zshrc o ~/.bashrc:" "is not on your PATH. Add to your ~/.zshrc or ~/.bashrc:" "no está en el PATH. Añade a tu ~/.zshrc o ~/.bashrc:")"
       say "      export PATH=\"$1:\$PATH\"" ;;
  esac
}

# ============================================================ 1. programma
CMD=""
case "$METHOD" in
  bundle)
    step "$(L "Installo chess-me (cartella self-contained)" "Installing chess-me (self-contained folder)" "Instalo chess-me (carpeta autocontenida)")"
    PREFIX="${PREFIX:-$DATA_HOME/app}"
    if [ "$SRC" != "$PREFIX" ]; then
      if [ -e "$PREFIX" ] && [ ! -f "$PREFIX/VERSION" ]; then
        die "$PREFIX $(L "esiste e non è un'installazione di chess-me: scegli un altro --prefix" "exists and is not a chess-me installation: choose another --prefix" "existe y no es una instalación de chess-me: elige otro --prefix")"
      fi
      mkdir -p "$(dirname "$PREFIX")"
      rm -rf "$PREFIX.new"
      run "$(L "copio i file in" "copying the files to" "copio los archivos en") $PREFIX" cp -R "$SRC" "$PREFIX.new"
      rm -rf "$PREFIX"
      mv "$PREFIX.new" "$PREFIX"
    fi
    if [ "$OS" = darwin ]; then
      # binari non firmati: togli la quarantena del download, solo dalla cartella installata
      xattr -dr com.apple.quarantine "$PREFIX" 2>/dev/null || true
      ok "$(L "quarantena di macOS rimossa" "macOS quarantine removed" "cuarentena de macOS eliminada")"
    fi
    mkdir -p "$BIN_DIR"
    ln -sf "$PREFIX/chess-me" "$BIN_DIR/chess-me"
    CMD="$BIN_DIR/chess-me"
    ok "$(L comando command comando): $CMD"
    ;;
  pipx)
    step "$(L "Installo chess-me con pipx" "Installing chess-me with pipx" "Instalo chess-me con pipx")"
    run "pipx install chess-me" pipx install --force --python "$PY" "$FROM"
    PIPX_BIN="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$HOME/.local/bin")"
    CMD="$PIPX_BIN/chess-me"
    ok "$(L comando command comando): $CMD"
    ;;
  pip)
    VENV="${PREFIX:-$DATA_HOME/venv}"
    if [ -e "$VENV" ] && [ ! -f "$VENV/$MARK" ]; then
      die "$VENV $(L "esiste e non è un venv di chess-me: scegli un altro --prefix" "exists and is not a chess-me venv: choose another --prefix" "existe y no es un venv de chess-me: elige otro --prefix")"
    fi
    step "$(L "Ambiente Python" "Python environment" "Entorno Python")"
    run "$(L "creo il venv in" "creating the venv in" "creo el venv en") $VENV" "$PY" -m venv "$VENV"
    touch "$VENV/$MARK"
    run "$(L "aggiorno pip" "upgrading pip" "actualizo pip")" "$VENV/bin/python" -m pip install --upgrade pip
    step "$(L "Installo chess-me e le dipendenze" "Installing chess-me and its dependencies" "Instalo chess-me y sus dependencias")"
    run "pip install chess-me" "$VENV/bin/python" -m pip install --upgrade --progress-bar off "$FROM"
    mkdir -p "$BIN_DIR"
    ln -sf "$VENV/bin/chess-me" "$BIN_DIR/chess-me"
    CMD="$BIN_DIR/chess-me"
    ok "$(L comando command comando): $CMD"
    ;;
esac

# Interprete del pacchetto installato (dallo shebang del comando): da lì leggo URL e hash ufficiali.
CPY=""
if [ "$METHOD" != bundle ]; then
  REAL="$CMD"; [ -L "$REAL" ] && REAL="$(cd "$(dirname "$REAL")" && cd "$(dirname "$(readlink "$REAL")")" && pwd)/$(basename "$(readlink "$REAL")")"
  CPY="$(head -n 1 "$REAL" 2>/dev/null | sed -n 's/^#! *//p' | cut -d' ' -f1)"
  [ -x "$CPY" ] || CPY=""
fi

manifest() {  # manifest stockfish|llama → imposta M_URL M_SHA M_MEMBER
  M_URL=""; M_SHA=""; M_MEMBER=""
  [ -n "$CPY" ] || return 1
  eval "$(CHESSME_HOME="$DATA_HOME" "$CPY" -I -c '
import shlex, sys
from chess_me import downloads
e = downloads.entry(sys.argv[1]) or {}
for k, v in (("M_URL", "url"), ("M_SHA", "sha256"), ("M_MEMBER", "member")):
    print(k + "=" + shlex.quote(str(e.get(v) or "")))
' "$1")"
  [ -n "$M_URL" ]
}

if [ -n "$CPY" ]; then
  eval "$("$CPY" -I -c '
import shlex
from chess_me import runtime
runtime.bootstrap()
from chess_me.llm import server
print(f"MODEL_URL={shlex.quote(server.MODEL_URL)}")
print(f"MODEL_SHA256={shlex.quote(server.MODEL_SHA256)}")
print(f"MODEL_SIZE={server.MODEL_SIZE}")
' 2>/dev/null)" || true
fi

TMPD="$(mktemp -d -t chess-me-dl.XXXXXX)"
trap 'cleanup; rm -rf "$TMPD"' EXIT

find_member() { find "$1" -type f -name "$2" 2>/dev/null | head -n 1; }

USE_CURL=1; has curl || USE_CURL=0
FALLBACK_SETUP=0

# ============================================================ 2. Stockfish
if [ "$SEL_SF" = 1 ]; then
  step "Stockfish"
  if [ "$USE_CURL" = 1 ] && manifest stockfish; then
    fetch "$M_URL" "$TMPD/stockfish.tar" "$M_SHA" "Stockfish" "$SF_SIZE"
    run "$(L "estraggo l'archivio" "extracting the archive" "extraigo el archivo")" tar -xf "$TMPD/stockfish.tar" -C "$TMPD"
    BIN="$(find_member "$TMPD" "$M_MEMBER")"
    [ -n "$BIN" ] || die "Stockfish: $(L "eseguibile non trovato nell'archivio" "executable not found in the archive" "no se encontró el ejecutable en el archivo")"
    mkdir -p "$DATA_HOME/bin"
    cp -f "$BIN" "$DATA_HOME/bin/stockfish"
    chmod +x "$DATA_HOME/bin/stockfish"
    ok "$(L "installato in" "installed in" "instalado en") $DATA_HOME/bin/stockfish"
  else
    FALLBACK_SETUP=1; info "$(L "lo scarica 'chess-me setup' al passo di verifica" "'chess-me setup' downloads it at the check step" "lo descarga 'chess-me setup' en el paso de verificación")"
  fi
fi

# ============================================================ 3. aperture
if [ "$SEL_OP" = 1 ]; then
  step "$(L "Database delle aperture" "Openings database" "Base de datos de aperturas")"
  if [ -n "$CPY" ]; then
    mkdir -p "$DATA_HOME"
    run "$(L "scarico i TSV di lichess-org/chess-openings e costruisco il database" "downloading the lichess-org/chess-openings TSV files and building the database" "descargo los TSV de lichess-org/chess-openings y construyo la base de datos")" \
      env CHESSME_HOME="$DATA_HOME" "$CPY" -I -m chess_me.build_openings "$DATA_HOME/openings.sqlite"
    ok "$DATA_HOME/openings.sqlite ($(hsize "$(dir_size "$DATA_HOME/openings.sqlite")"))"
  else
    FALLBACK_SETUP=1; info "$(L "lo prepara 'chess-me setup' al passo di verifica" "'chess-me setup' builds it at the check step" "lo prepara 'chess-me setup' en el paso de verificación")"
  fi
fi

# ============================================================ 4. llama-server
if [ "$SEL_LLM" = 1 ] && [ -z "$ST_LL" ]; then
  step "llama-server"
  if [ "$USE_CURL" = 1 ] && manifest llama; then
    fetch "$M_URL" "$TMPD/llama.tar.gz" "$M_SHA" "llama-server" "$LL_SIZE"
    mkdir -p "$TMPD/llama"
    run "$(L "estraggo l'archivio" "extracting the archive" "extraigo el archivo")" tar -xzf "$TMPD/llama.tar.gz" -C "$TMPD/llama"
    BIN="$(find_member "$TMPD/llama" "$M_MEMBER")"
    [ -n "$BIN" ] || die "llama-server: $(L "eseguibile non trovato nell'archivio" "executable not found in the archive" "no se encontró el ejecutable en el archivo")"
    rm -rf "$DATA_HOME/bin/llama"
    mkdir -p "$DATA_HOME/bin"
    cp -R "$(dirname "$BIN")" "$DATA_HOME/bin/llama"   # llama-server + librerie accanto
    chmod +x "$DATA_HOME/bin/llama/$M_MEMBER"
    [ "$OS" = darwin ] && xattr -dr com.apple.quarantine "$DATA_HOME/bin/llama" 2>/dev/null || true
    ok "$(L "installato in" "installed in" "instalado en") $DATA_HOME/bin/llama"
  else
    FALLBACK_SETUP=1; info "$(L "lo scarica 'chess-me setup --llm' al passo di verifica" "'chess-me setup --llm' downloads it at the check step" "lo descarga 'chess-me setup --llm' en el paso de verificación")"
  fi
fi

# ============================================================ 5. modello LLM
if [ "$SEL_LLM" = 1 ] && [ -z "$ST_MD" ]; then
  step "$(L "Modello LLM" "LLM model" "Modelo LLM") (Qwen3 1.7B, $(hsize "$MODEL_SIZE"))"
  if [ "$USE_CURL" = 1 ]; then
    fetch "$MODEL_URL" "$DATA_HOME/models/$MODEL_FILE" "$MODEL_SHA256" "$(L modello model modelo)" "$MODEL_SIZE"
    info "$(L "eliminabile in seguito con: chess-me remove-model" "can be removed later with: chess-me remove-model" "se puede eliminar después con: chess-me remove-model")"
  else
    FALLBACK_SETUP=1; info "$(L "lo scarica 'chess-me setup --llm' al passo di verifica" "'chess-me setup --llm' downloads it at the check step" "lo descarga 'chess-me setup --llm' en el paso de verificación")"
  fi
fi

# ============================================================ verifica finale
step "$(L Verifica Check Verificación)"
if "$CMD" lang "$UI_LANG" >/dev/null 2>&1; then ok "$(L "lingua predefinita" "default language" "idioma predeterminado"): $(lang_name "$UI_LANG")"
else warn "$(L "lingua non salvata: usa chess-me lang" "language not saved: use chess-me lang" "idioma no guardado: usa chess-me lang") $UI_LANG"; fi
if [ "$FALLBACK_SETUP" = 1 ]; then
  if [ "$SEL_LLM" = 1 ]; then "$CMD" setup --llm --yes || true; else "$CMD" setup --yes || true; fi
fi
DOC_RC=0
DOC_OUT="$("$CMD" doctor 2>&1)" || DOC_RC=$?
printf '%s\n' "$DOC_OUT" | sed 's/^/  /'

say ""
VER="$("$CMD" --version 2>/dev/null | cut -d' ' -f2 || echo ?)"
w=$(( $(cols) - 22 )); [ "$w" -gt 30 ] && w=30
say "${B}${BLU}[$STEP_TOT/$STEP_TOT]${R} ${GRN}${B}chess-me $VER $(L installato installed instalado)${R}   ${D}$(L totale total total) $(printf '%*s' "$w" '' | tr ' ' '#') 100% · $(htime $(( $(date +%s) - T_START )))${R}"
case "$METHOD" in pipx) path_note "${PIPX_BIN:-$HOME/.local/bin}" ;; *) path_note "$BIN_DIR" ;; esac
[ "$DOC_RC" = 0 ] || warn "$(L "qualche risorsa manca: rilancia ./install.sh per aggiungerla" "some resources are missing: run ./install.sh again to add them" "faltan algunos recursos: vuelve a ejecutar ./install.sh para añadirlos")"
say ""
say "  $(L "Prova: " "Try:   " "Prueba:") ${B}chess-me -l https://lichess.org/<$(L id-partita game-id id-partida)>${R}"
say "          ${B}chess-me -u lichess <$(L utente user usuario)>${R}"
[ "$SEL_LLM" = 1 ] && say "          ${B}chess-me -pgn $(L partita game partida).pgn --llm${R}"
say "          ${B}chess-me lang it|en|es${R}   ${D}$(L "per cambiare lingua" "to change language" "para cambiar de idioma")${R}"
say ""
