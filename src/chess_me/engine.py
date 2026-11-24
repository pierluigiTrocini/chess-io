"""Processo Stockfish per l'analisi: avviato alla prima posizione, chiuso all'uscita della CLI."""
import asyncio
import logging

import chess
import chess.engine

from . import config

log = logging.getLogger(__name__)


class ManagedEngine:
    def __init__(self, name: str, options: dict):
        self.name = name
        self.options = options
        self.engine: chess.engine.UciProtocol | None = None
        self.lock = asyncio.Lock()
        self.version = "?"
        self.last_used = 0.0

    async def _start(self) -> chess.engine.UciProtocol:
        _, engine = await chess.engine.popen_uci(config.STOCKFISH_PATH)
        opts = {k: v for k, v in self.options.items() if k in engine.options}
        await engine.configure(opts)
        self.version = engine.id.get("name", "Stockfish")
        log.info("engine %s avviato: %s %s", self.name, self.version, opts)
        return engine

    async def get(self) -> chess.engine.UciProtocol:
        if self.engine is None or self.engine.returncode.done():
            self.engine = await self._start()
        return self.engine

    async def run(self, fn):
        """Esegue fn(engine) in esclusiva, riavviando il motore se è crashato."""
        async with self.lock:
            try:
                for attempt in range(2):
                    engine = await self.get()
                    try:
                        return await fn(engine)
                    except (chess.engine.EngineTerminatedError, chess.engine.EngineError):
                        log.exception("engine %s errore (tentativo %d)", self.name, attempt + 1)
                        self.engine = None
                        if attempt == 1:
                            raise
            finally:
                self.last_used = asyncio.get_running_loop().time()

    async def close(self):
        if self.engine is not None:
            try:
                await self.engine.quit()
            except Exception:
                pass
            self.engine = None
            log.info("engine %s chiuso", self.name)



analysis_engine = ManagedEngine(
    "analysis",
    {"Threads": config.ANALYSIS_THREADS, "Hash": config.ANALYSIS_HASH_MB, "UCI_ShowWDL": True},
)


async def shutdown():
    await analysis_engine.close()


def score_cp(score: chess.engine.PovScore, color: chess.Color) -> int:
    return score.pov(color).score(mate_score=10000)
