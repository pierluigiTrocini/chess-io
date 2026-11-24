"""Con --llm: riformulazione verificata di commenti e riassunto, in background, sulla Review in memoria."""
import asyncio
from typing import Callable

from . import humanize as llm_humanize
from . import server as llm_server
from . import summarize as llm_summarize
from ..session import Review

MODEL_SIZE_GB = llm_server.MODEL_SIZE / 1e9


def available() -> bool:
    return llm_server.available()


def model_ready() -> bool:
    return llm_server.model_ready()


def download_state() -> dict:
    return dict(llm_server.download)


def eligible(rv: Review) -> list[dict]:
    return [m for m in rv.moves if m.get("classification") in llm_humanize.ELIGIBLE and m.get("comment")
            and not m["comment"].endswith("Scacco matto!")]


async def run(rv: Review, notify: Callable[[], None]) -> None:
    """Riscrive i commenti idonei e poi il riassunto; `notify` dopo ogni passo (dal loop dell'app)."""
    try:
        if not model_ready():
            rv.llm_status = "downloading"
            notify()
            await llm_server.ensure_model()
        todo = eligible(rv)
        rv.llm_status = "running"
        rv.llm_progress = (0, len(todo) + 1)
        notify()
        for i, m in enumerate(todo):
            try:
                text, chk = await llm_humanize.humanize(m["comment"], m["classification"], m.get("motifs_json"))
            except Exception as e:  # noqa: BLE001
                text, chk = None, {"passed": False, "reason": f"errore LLM: {e}"}
            m["comment_llm"], m["llm_check_json"] = text, chk
            rv.llm_progress = (i + 1, len(todo) + 1)
            notify()
        tpl = rv.summary.get("text")
        if tpl:
            text, checks = await llm_summarize.summarize(tpl)
            rv.summary["llm"], rv.summary["llm_check"] = text, checks
        rv.llm_progress = (len(todo) + 1, len(todo) + 1)
        rv.llm_status = "done"
    except asyncio.CancelledError:
        raise
    except Exception as e:  # noqa: BLE001
        rv.llm_status = "error"
        rv.llm_error = str(e)
    notify()


async def shutdown() -> None:
    await llm_server.stop()
