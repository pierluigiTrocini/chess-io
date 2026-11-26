"""Dove stanno le risorse della CLI (Stockfish, llama-server, aperture, modello) e configurazione dell'ambiente.

È l'unico modulo che conosce i percorsi. Va chiamato `bootstrap()` PRIMA di importare qualunque altro modulo
`chess_io.*`, perché `chess_io.config` e `chess_io.llm.server` leggono le variabili d'ambiente all'import.

Ordine di ricerca: variabile d'ambiente esplicita → cartella del bundle (eseguibile PyInstaller) →
dati utente (~/.local/share/chess-io) → dati del pacchetto (wheel) → PATH di sistema.
"""
import atexit
import os
import shutil
import socket
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import APP_NAME
from .i18n import tr

MODEL_FILE = "Qwen3-1.7B-Q4_K_M.gguf"
PROMPT_FILES = ("prompts.toml", "prompts.en.toml", "prompts.es.toml")   # it, en, es
_EXE = ".exe" if os.name == "nt" else ""


LEGACY_NAME = "chess-me"           # nome precedente: cartella dati e variabili CHESSME_* ancora riconosciute
_INSTALL_DIRS = ("venv", "app")    # installazione del vecchio pacchetto: resta dov'è (la rimuove install.sh --uninstall)


def env(name: str) -> str | None:
    """Variabile CHESSIO_<name>, o la vecchia CHESSME_<name> se manca."""
    return os.environ.get(f"CHESSIO_{name}") or os.environ.get(f"CHESSME_{name}")


def _migrate_legacy(legacy: Path, home: Path) -> None:
    """Sposta una volta sola i dati di chess-me (binari, modello, impostazioni, prompt) nella nuova cartella."""
    try:
        home.mkdir(parents=True)
        for entry in legacy.iterdir():
            if entry.name not in _INSTALL_DIRS:
                entry.rename(home / entry.name)
    except OSError:
        pass   # migrazione parziale o impossibile: al peggio si riscarica


def data_home() -> Path:
    """Cartella dei dati utente: binari scaricati, modello LLM, prompt personalizzati."""
    if explicit := env("HOME"):
        return Path(explicit).expanduser()
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share").expanduser()
    home = base / APP_NAME
    if not home.exists() and (base / LEGACY_NAME).is_dir():
        _migrate_legacy(base / LEGACY_NAME, home)
    return home


LAST_SEARCH_FILE = "last_search.json"


def load_last_search() -> tuple[str, str] | None:
    """Ultima ricerca per utente andata a buon fine (piattaforma, nome), se salvata."""
    import json
    try:
        d = json.loads((data_home() / LAST_SEARCH_FILE).read_text())
        return str(d["platform"]), str(d["username"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_last_search(platform: str, username: str) -> None:
    """Ricorda l'ultima ricerca; un errore di scrittura non deve mai bloccare la TUI."""
    import json
    try:
        home = data_home()
        home.mkdir(parents=True, exist_ok=True)
        (home / LAST_SEARCH_FILE).write_text(json.dumps({"platform": platform, "username": username}))
    except OSError:
        pass


SETTINGS_FILE = "settings.json"


def load_settings() -> dict:
    """Impostazioni salvate (per ora solo la lingua): {} se mancano o sono illeggibili."""
    import json
    try:
        d = json.loads((data_home() / SETTINGS_FILE).read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(**values) -> bool:
    """Aggiorna le impostazioni salvate; False se non si riesce a scrivere (la TUI va avanti comunque)."""
    import json
    try:
        home = data_home()
        home.mkdir(parents=True, exist_ok=True)
        d = load_settings()
        d.update(values)
        (home / SETTINGS_FILE).write_text(json.dumps(d, ensure_ascii=False))
        return True
    except OSError:
        return False


def bundle_root() -> Path | None:
    """Radice della cartella self-contained, se si gira dall'eseguibile PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return None


def package_data() -> Path:
    return Path(__file__).resolve().parent / "data"


@dataclass
class Resources:
    stockfish: Path | None
    llama_server: Path | None
    openings: Path | None
    model: Path
    prompts: list[Path]          # prompt personalizzati (prompts.toml, prompts.en.toml, prompts.es.toml)
    bundle: Path | None
    home: Path

    def describe(self) -> list[tuple[str, str, bool]]:
        def show(p: Path | None, missing: str) -> tuple[str, bool]:
            return (str(p), True) if p else (missing, False)
        return [
            ("Stockfish", *show(self.stockfish, tr("non trovato (chess-io setup)"))),
            (tr("Aperture"), *show(self.openings, tr("non trovate: niente riconoscimento della teoria"))),
            ("llama-server", *show(self.llama_server, tr("non trovato: --llm non disponibile"))),
            (tr("Modello LLM"), str(self.model) if self.model.is_file()
             else tr("{path} (si scarica al primo --llm)", path=self.model), self.model.is_file()),
            (tr("Prompt"), ", ".join(str(p) for p in self.prompts) if self.prompts else tr("predefiniti"), True),
            ("Bundle", str(self.bundle) if self.bundle else tr("no (Python)"), True),
            (tr("Dati utente"), str(self.home), True),
        ]


def _first_file(*cands: Path | None) -> Path | None:
    for c in cands:
        if c is not None and c.is_file():
            return c
    return None


def _env_path(name: str) -> Path | None:
    v = os.environ.get(name)
    if not v:
        return None
    p = Path(v).expanduser()
    if p.is_file():
        return p
    found = shutil.which(v)
    return Path(found) if found else None


def _which(name: str) -> Path | None:
    found = shutil.which(name)
    return Path(found) if found else None


def resolve() -> Resources:
    bundle = bundle_root()
    home = data_home()
    pkg = package_data()
    b = (lambda *p: bundle.joinpath(*p)) if bundle else (lambda *p: None)
    stockfish = _env_path("STOCKFISH_PATH") or _first_file(b("bin", "stockfish" + _EXE),
                                                             home / "bin" / ("stockfish" + _EXE)) or _which("stockfish")
    llama = _env_path("LLM_SERVER_PATH") or _first_file(b("bin", "llama-server" + _EXE),
                                                         home / "bin" / "llama" / ("llama-server" + _EXE),
                                                         home / "bin" / ("llama-server" + _EXE)) or _which("llama-server")
    openings = _first_file(Path(os.environ["OPENINGS_DB"]) if os.environ.get("OPENINGS_DB") else None,
                           b("share", "openings.sqlite"), pkg / "openings.sqlite", home / "openings.sqlite",
                           Path("openings.sqlite"))
    model = Path(os.environ["LLM_MODEL_PATH"]) if os.environ.get("LLM_MODEL_PATH") else home / "models" / MODEL_FILE
    prompts = [p for p in (home / name for name in PROMPT_FILES) if p.is_file()]
    return Resources(stockfish, llama, openings, model, prompts, bundle, home)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def bootstrap(depth: int | None = None) -> Resources:
    """Imposta l'ambiente per i moduli `chess_io.*`. Nessun file persistente: DATA_DIR è temporanea."""
    res = resolve()
    tmp = Path(tempfile.mkdtemp(prefix=f"{APP_NAME}-"))
    atexit.register(shutil.rmtree, tmp, True)
    for p in res.prompts:
        shutil.copyfile(p, tmp / p.name)  # llm.prompts legge DATA_DIR/prompts*.toml
    env = {
        "DATA_DIR": str(tmp),
        "STOCKFISH_PATH": str(res.stockfish or "stockfish"),
        "OPENINGS_DB": str(res.openings or tmp / "no-openings.sqlite"),
        "LLM_SERVER_PATH": str(res.llama_server or tmp / "no-llama-server"),
        "LLM_MODEL_PATH": str(res.model),
        "LLM_PORT": str(_free_port()),
    }
    os.environ.update(env)
    if depth:
        os.environ["ANALYSIS_DEPTH"] = str(depth)
    return res
