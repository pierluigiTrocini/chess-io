"""Caricamento dei prompt LLM da prompts.toml (modificabile senza toccare il codice).

Si usa DATA_DIR/prompts.toml se esiste, altrimenti il file accanto a questo modulo. Il file viene riletto
quando cambia (data di modifica), quindi le modifiche valgono dalla richiesta successiva, senza riavvio.
"""
import tomllib
from pathlib import Path

from .. import config

DEFAULT_PATH = Path(__file__).parent.parent / "data" / "prompts.toml"

_cache: dict = {"key": None, "data": None}


def path() -> Path:
    override = config.DATA_DIR / "prompts.toml"
    return override if override.is_file() else DEFAULT_PATH


def load() -> dict:
    p = path()
    key = (str(p), p.stat().st_mtime_ns)
    if _cache["key"] != key:
        with p.open("rb") as f:
            _cache["data"] = tomllib.load(f)
        _cache["key"] = key
    return _cache["data"]
