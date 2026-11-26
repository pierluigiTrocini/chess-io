"""`chess-me setup`: scarica e verifica (SHA256) Stockfish, llama-server e il database delle aperture in
~/.local/share/chess-me, per chi installa con pip/pipx invece di usare la cartella self-contained.
Gli URL e gli hash sono in data/binaries.toml."""
import hashlib
import platform
import shutil
import stat
import tarfile
import tempfile
import tomllib
from pathlib import Path

import httpx

from . import runtime
from .i18n import tr

MANIFEST = Path(__file__).with_name("data") / "binaries.toml"


class SetupError(Exception):
    pass


def platform_key() -> str:
    machine = platform.machine().lower()
    machine = {"aarch64": "arm64", "amd64": "x86_64"}.get(machine, machine)
    return f"{platform.system().lower()}-{machine}"


def manifest() -> dict:
    with MANIFEST.open("rb") as f:
        return tomllib.load(f)


def entry(kind: str, key: str | None = None) -> dict | None:
    return manifest().get(kind, {}).get(key or platform_key())


def download(url: str, dest: Path, sha256: str | None, label: str, echo=print) -> Path:
    """Scarica in `dest` verificando l'hash; il file resta solo se l'hash coincide."""
    h = hashlib.sha256()
    part = dest.with_name(dest.name + ".part")
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=httpx.Timeout(60, read=120),
                          headers={"User-Agent": "chess-me-cli"}) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length") or 0)
            done, last = 0, -1
            with part.open("wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    pct = 100 * done // total if total else -1
                    if pct != last and pct % 10 == 0:
                        echo(f"  {label}: {pct}%" if pct >= 0 else f"  {label}: {done >> 20} MB")
                        last = pct
    except httpx.HTTPError as e:
        part.unlink(missing_ok=True)
        raise SetupError(tr("{label}: download non riuscito ({error})", label=label, error=e))
    if sha256 and h.hexdigest() != sha256:
        part.unlink(missing_ok=True)
        raise SetupError(tr("{label}: SHA256 diverso da quello atteso, file scartato", label=label))
    part.replace(dest)
    return dest


def _make_executable(p: Path) -> None:
    p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _extract(archive: Path, into: Path) -> None:
    with tarfile.open(archive) as t:
        t.extractall(into, filter="data")


def _find(root: Path, name: str) -> Path | None:
    return next((p for p in root.rglob(name) if p.is_file()), None)


def install_stockfish(echo=print) -> Path:
    e = entry("stockfish")
    if e is None:
        raise SetupError(tr("nessun Stockfish precompilato per {platform}: installalo e mettilo nel PATH", platform=platform_key()))
    home = runtime.data_home()
    (home / "bin").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="chess-me-dl-") as tmp:
        tmp = Path(tmp)
        arc = download(e["url"], tmp / "stockfish.tar", e["sha256"], "Stockfish", echo)
        _extract(arc, tmp / "x")
        src = _find(tmp / "x", e["member"])
        if src is None:
            raise SetupError(tr("Stockfish: eseguibile non trovato nell'archivio"))
        dest = home / "bin" / "stockfish"
        shutil.copyfile(src, dest)
        _make_executable(dest)
    return dest


def install_llama(echo=print) -> Path:
    e = entry("llama")
    if e is None:
        raise SetupError(tr("nessun llama-server precompilato per {platform}: installalo e mettilo nel PATH", platform=platform_key()))
    home = runtime.data_home()
    with tempfile.TemporaryDirectory(prefix="chess-me-dl-") as tmp:
        tmp = Path(tmp)
        arc = download(e["url"], tmp / "llama.tar.gz", e["sha256"], "llama-server", echo)
        _extract(arc, tmp / "x")
        src = _find(tmp / "x", e["member"])
        if src is None:
            raise SetupError(tr("llama-server: eseguibile non trovato nell'archivio"))
        dest_dir = home / "bin" / "llama"
        shutil.rmtree(dest_dir, ignore_errors=True)
        shutil.copytree(src.parent, dest_dir, symlinks=True)   # llama-server + librerie accanto
    dest = dest_dir / e["member"]
    _make_executable(dest)
    return dest


def install_openings(echo=print) -> Path:
    from .build_openings import download_and_build
    home = runtime.data_home()
    home.mkdir(parents=True, exist_ok=True)
    echo(tr("  aperture: scarico i TSV e costruisco il database…"))
    download_and_build(str(home / "openings.sqlite"))
    return home / "openings.sqlite"


async def install_model(echo=print) -> Path:
    from .llm import server
    await server.ensure_model()
    return server.MODEL_PATH
