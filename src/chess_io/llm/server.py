"""Backend LLM: llama-server locale con Qwen3 oppure un servizio scelto dall'utente.

Locale: il modello non è nel pacchetto, viene scaricato in LLM_MODEL_PATH (~/.local/share/chess-io/models) al primo
--llm, con verifica SHA256, e si elimina con `chess-io remove-model`. Il processo parte solo quando serve e si
ferma all'uscita della CLI.

Esterno: qualunque servizio con API compatibile OpenAI (`<url>/chat/completions`): Ollama, LM Studio, vLLM,
llama.cpp già avviato, OpenAI, OpenRouter… Nessun processo e nessun download. Si sceglie con LLM_BASE_URL,
LLM_MODEL, LLM_API_KEY (impostate da runtime.bootstrap) oppure a runtime con `configure()`.
"""
import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

from .. import config
from ..runtime import is_local_url, normalize_url  # noqa: F401  (riesportati)
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
LOCAL_URL = f"http://127.0.0.1:{PORT}"
EXTERNAL_TOKENS_FACTOR = float(os.environ.get("LLM_MAX_TOKENS_FACTOR", "4"))  # margine per i modelli "ragionanti"
EXTERNAL_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "180"))
RETRY_STATUS = (429, 500, 502, 503, 504)


@dataclass(frozen=True)
class Backend:
    """url vuoto = llama-server locale; altrimenti servizio compatibile OpenAI."""
    url: str = ""
    model: str = ""
    api_key: str = ""

    def __post_init__(self):
        object.__setattr__(self, "url", normalize_url(self.url))
        object.__setattr__(self, "model", self.model.strip())
        object.__setattr__(self, "api_key", self.api_key.strip())

    @property
    def external(self) -> bool:
        return bool(self.url)

    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}


_backend = Backend(os.environ.get("LLM_BASE_URL", ""), os.environ.get("LLM_MODEL", ""),
                   os.environ.get("LLM_API_KEY", ""))

_proc: asyncio.subprocess.Process | None = None
_lock = asyncio.Lock()
_dl_lock = asyncio.Lock()
_last_used = 0.0
_busy = 0
download: dict = {"status": "idle", "done": 0, "total": 0, "error": None}  # idle | downloading | error


def backend() -> Backend:
    return _backend


def external() -> bool:
    return _backend.external


async def configure(b: Backend) -> None:
    """Cambia backend durante la sessione (schermata delle impostazioni): llama-server si ferma se non serve più."""
    global _backend
    if b.external:
        await stop()
    _backend = b


def model_name() -> str:
    return _backend.model if _backend.external else MODEL_NAME


def available() -> bool:
    """Si può usare l'LLM: servizio esterno configurato, oppure il binario llama-server è stato trovato."""
    return _backend.external or SERVER_PATH.is_file()


def local_available() -> bool:
    return SERVER_PATH.is_file()


def model_ready() -> bool:
    """Niente da scaricare: modello locale presente, oppure servizio esterno."""
    return _backend.external or MODEL_PATH.is_file()


def local_model_ready() -> bool:
    return MODEL_PATH.is_file()


def model_size() -> int:
    return MODEL_PATH.stat().st_size if local_model_ready() else 0


def running() -> bool:
    return _proc is not None and _proc.returncode is None


async def ensure_model(client: httpx.AsyncClient | None = None) -> None:
    """Scarica il modello locale se manca (una sola volta anche con richieste concorrenti)."""
    if local_model_ready():
        return
    async with _dl_lock:
        if local_model_ready():
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
        r = await client.get(f"{LOCAL_URL}/health", timeout=2)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


async def ensure_started(timeout_s: float = 120) -> None:
    global _proc
    if _backend.external:
        return
    if not local_available():
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


def http_error(e: Exception, b: Backend | None = None) -> str:
    """Messaggio leggibile per un errore del servizio LLM."""
    url = (b or _backend).url or LOCAL_URL
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code in (401, 403):
            return tr("chiave API mancante o non valida (HTTP {code})", code=code)
        if code == 404:
            return tr("modello o indirizzo non trovato (HTTP 404 da {url})", url=url)
        detail = ""
        try:
            err = e.response.json().get("error")
            detail = err.get("message", "") if isinstance(err, dict) else str(err or "")
        except (ValueError, AttributeError):
            pass
        return tr("il servizio ha risposto HTTP {code}", code=code) + (f": {detail[:200]}" if detail else "")
    if isinstance(e, httpx.TimeoutException):
        return tr("nessuna risposta da {url} (tempo scaduto)", url=url)
    if isinstance(e, httpx.TransportError):
        return tr("impossibile contattare {url}", url=url)
    return str(e) or e.__class__.__name__


async def _post(client: httpx.AsyncClient, url: str, payload: dict, b: Backend) -> dict:
    """POST con 2 nuovi tentativi su 429/5xx/timeout (servizi remoti con limiti di frequenza)."""
    for attempt in range(3):
        try:
            r = await client.post(url, json=payload, headers=b.headers())
            if r.status_code in RETRY_STATUS and attempt < 2:
                await asyncio.sleep(float(r.headers.get("retry-after") or 0) or 2 ** attempt)
                continue
            r.raise_for_status()
            return r.json()
        except (httpx.TimeoutException, httpx.ConnectError):
            if attempt == 2 or not b.external:
                raise
            await asyncio.sleep(2 ** attempt)
    raise AssertionError("unreachable")


async def chat(messages: list[dict], max_tokens: int = 160, temperature: float = 0.3,
               backend: Backend | None = None) -> str:
    """Una risposta del modello. `backend` serve a provare un servizio prima di salvarlo."""
    global _last_used, _busy
    b = backend or _backend
    _busy += 1
    try:
        payload = {"messages": messages, "temperature": temperature, "top_p": 0.9, "max_tokens": max_tokens}
        if b.external:
            if not b.model:
                raise RuntimeError(tr("manca il nome del modello"))
            payload["model"] = b.model
            payload["max_tokens"] = int(max_tokens * EXTERNAL_TOKENS_FACTOR)
            url, timeout = f"{b.url}/chat/completions", EXTERNAL_TIMEOUT
        else:
            await ensure_started()
            payload["cache_prompt"] = True
            payload["chat_template_kwargs"] = {"enable_thinking": False}  # Qwen3: niente "ragionamento" visibile
            url, timeout = f"{LOCAL_URL}/v1/chat/completions", 180
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                data = await _post(client, url, payload, b)
            except httpx.HTTPError as e:
                raise RuntimeError(http_error(e, b)) from e
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(tr("risposta inattesa dal servizio LLM")) from e
    finally:
        _busy -= 1
        _last_used = asyncio.get_running_loop().time()


async def list_models(b: Backend) -> list[str]:
    """Modelli offerti dal servizio (GET <url>/models); [] se il servizio non li elenca."""
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(f"{b.url}/models", headers=b.headers())
            if r.status_code == 404:
                return []
            r.raise_for_status()
            data = r.json().get("data") or []
        except httpx.HTTPError as e:
            raise RuntimeError(http_error(e, b)) from e
        except (ValueError, AttributeError):
            return []
    return sorted(str(m["id"]) for m in data if isinstance(m, dict) and m.get("id"))


async def probe(b: Backend) -> tuple[list[str], str]:
    """Prova un servizio: (modelli disponibili, risposta a un messaggio brevissimo). Solleva RuntimeError."""
    models = await list_models(b)
    if not b.model:
        return models, ""
    reply = await chat([{"role": "user", "content": "Reply with the single word: ok"}], max_tokens=16,
                       temperature=0, backend=b)
    return models, reply.strip()
