"""Gestione di llama-server e del modello.

Il modello non è nel pacchetto: viene scaricato in LLM_MODEL_PATH (~/.local/share/chess-io/models) al primo
--llm, con verifica SHA256, e si elimina con `chess-io remove-model`. Il processo parte solo quando serve e si
ferma all'uscita della CLI.
"""
import asyncio
import hashlib
import logging
import os
from pathlib import Path

import httpx

from .. import config
from ..i18n import tr

log = logging.getLogger(__name__)

SERVER_PATH = Path(os.environ.get("LLM_SERVER_PATH", "/opt/llm/llama-server"))
MODEL_PATH = Path(os.environ.get("LLM_MODEL_PATH", str(config.DATA_DIR / "models" / "Qwen3-1.7B-Q4_K_M.gguf")))
MODEL_URL = os.environ.get(
    "LLM_MODEL_URL", "https://huggingface.co/unsloth/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf")
MODEL_SHA256 = os.environ.get("LLM_MODEL_SHA256", "b139949c5bd74937ad8ed8c8cf3d9ffb1e99c866c823204dc42c0d91fa181897")
MODEL_SIZE = int(os.environ.get("LLM_MODEL_SIZE", "1107409472"))  # byte, per la barra prima che arrivino gli header
PORT = int(os.environ.get("LLM_PORT", "8081"))
THREADS = int(os.environ.get("LLM_THREADS", "4"))
CTX = int(os.environ.get("LLM_CTX", "4096"))
MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "Qwen3 1.7B (Q4_K_M)")
BASE_URL = f"http://127.0.0.1:{PORT}"

_proc: asyncio.subprocess.Process | None = None
_lock = asyncio.Lock()
_dl_lock = asyncio.Lock()
_last_used = 0.0
_busy = 0
download: dict = {"status": "idle", "done": 0, "total": 0, "error": None}  # idle | downloading | error


def available() -> bool:
    """Il binario llama-server è stato trovato (bundle, chess-io setup --llm o PATH)."""
    return SERVER_PATH.is_file()


def model_ready() -> bool:
    return MODEL_PATH.is_file()


def model_size() -> int:
    return MODEL_PATH.stat().st_size if model_ready() else 0


def running() -> bool:
    return _proc is not None and _proc.returncode is None


async def ensure_model(client: httpx.AsyncClient | None = None) -> None:
    """Scarica il modello se manca (una sola volta anche con richieste concorrenti)."""
    if model_ready():
        return
    async with _dl_lock:
        if model_ready():
            return
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = MODEL_PATH.with_suffix(".part")
        download.update(status="downloading", done=0, total=MODEL_SIZE, error=None)
        log.info("scarico il modello da %s", MODEL_URL)
        own = client is None
        c = client or httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(60, read=120))
        try:
            sha = hashlib.sha256()
            async with c.stream("GET", MODEL_URL) as r:
                r.raise_for_status()
                download["total"] = int(r.headers.get("content-length") or MODEL_SIZE)
                with tmp.open("wb") as f:
                    async for chunk in r.aiter_bytes(1 << 20):
                        f.write(chunk)
                        sha.update(chunk)
                        download["done"] += len(chunk)
            if MODEL_SHA256 and sha.hexdigest() != MODEL_SHA256:
                raise RuntimeError(tr("il file scaricato non corrisponde (SHA256 diverso)"))
            tmp.replace(MODEL_PATH)
            download.update(status="idle", error=None)
            log.info("modello salvato in %s", MODEL_PATH)
        except Exception as e:
            tmp.unlink(missing_ok=True)
            msg = tr("download del modello fallito: {error}", error=e)
            download.update(status="error", error=msg)
            raise RuntimeError(msg) from e
        finally:
            if own:
                await c.aclose()


async def delete_model() -> None:
    await stop()
    async with _dl_lock:
        MODEL_PATH.unlink(missing_ok=True)
        MODEL_PATH.with_suffix(".part").unlink(missing_ok=True)


async def _healthy(client: httpx.AsyncClient) -> bool:
    try:
        r = await client.get(f"{BASE_URL}/health", timeout=2)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


async def ensure_started(timeout_s: float = 120) -> None:
    global _proc
    if not available():
        raise RuntimeError(tr("llama-server non trovato"))
    await ensure_model()
    async with _lock:
        if running():
            return
        log.info("avvio llama-server (%s)", MODEL_PATH)
        _proc = await asyncio.create_subprocess_exec(
            str(SERVER_PATH), "-m", str(MODEL_PATH), "--host", "127.0.0.1", "--port", str(PORT),
            "-c", str(CTX), "-t", str(THREADS), "--parallel", "1", "--jinja", "--no-webui",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        async with httpx.AsyncClient() as client:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout_s
            while loop.time() < deadline:
                if _proc.returncode is not None:
                    raise RuntimeError(tr("llama-server terminato (codice {code})", code=_proc.returncode))
                if await _healthy(client):
                    log.info("llama-server pronto")
                    return
                await asyncio.sleep(0.5)
        raise RuntimeError(tr("llama-server non risponde"))


async def stop() -> None:
    global _proc
    async with _lock:
        if running():
            _proc.terminate()
            try:
                await asyncio.wait_for(_proc.wait(), 10)
            except asyncio.TimeoutError:
                _proc.kill()
            log.info("llama-server fermato")
        _proc = None


async def chat(messages: list[dict], max_tokens: int = 160, temperature: float = 0.3) -> str:
    global _last_used, _busy
    _busy += 1
    try:
        await ensure_started()
        payload = {
            "messages": messages,
            "temperature": temperature,
            "top_p": 0.9,
            "max_tokens": max_tokens,
            "cache_prompt": True,
            "chat_template_kwargs": {"enable_thinking": False},  # Qwen3: niente "ragionamento" visibile
        }
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(f"{BASE_URL}/v1/chat/completions", json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"] or ""
    finally:
        _busy -= 1
        _last_used = asyncio.get_running_loop().time()
