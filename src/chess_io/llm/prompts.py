"""Caricamento dei prompt LLM da prompts.toml (modificabile senza toccare il codice).

Un file per lingua: prompts.toml (italiano), prompts.en.toml, prompts.es.toml. Si usa DATA_DIR/<file> se esiste,
altrimenti il file nei dati del pacchetto. Il file viene riletto
quando cambia (data di modifica), quindi le modifiche valgono dalla richiesta successiva, senza riavvio.
"""
import tomllib
from pathlib import Path

from .. import config, i18n

DATA = Path(__file__).parent.parent / "data"
DEFAULT_PATH = DATA / "prompts.toml"

_cache: dict = {"key": None, "data": None}


def filename(lang: str | None = None) -> str:
    lang = lang or i18n.lang()
    return "prompts.toml" if lang == i18n.DEFAULT else f"prompts.{lang}.toml"


def path(lang: str | None = None) -> Path:
    name = filename(lang)
    override = config.DATA_DIR / name
    return override if override.is_file() else DATA / name


def load(lang: str | None = None) -> dict:
    p = path(lang)
    key = (str(p), p.stat().st_mtime_ns)
    if _cache["key"] != key:
        with p.open("rb") as f:
            _cache["data"] = tomllib.load(f)
        _cache["key"] = key
    return _cache["data"]
