"""App Textual: (ricerca utente) → (scelta partita) → (colore) → analisi con barra di avanzamento → revisione."""
import asyncio

from textual.app import App
from textual.binding import Binding

from .. import runtime, session
from ..i18n import tr
from ..llm import jobs as llm_jobs
from ..session import Loaded, Review
from .review import ReviewScreen
from .screens import AnalysisScreen, ColorScreen, ConfirmScreen, PickScreen, SearchScreen


class ChessIoApp(App):
    TITLE = "chess-io"
    CSS = "Screen { background: #1e1f22; }"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [Binding("ctrl+c", "quit", "Esci", show=False, priority=True)]

    def __init__(self, loaded: Loaded | None, candidate, color: str | None, depth: int, llm: bool,
                 review: Review | None = None):
        super().__init__()
        self.loaded = loaded
        self.candidate = candidate
        self.color = color
        self.depth = depth
        self.llm = llm
        self.review: Review | None = review   # già pronta (test): si salta l'analisi
        self._color_ready = asyncio.Event()
        self.review_screen: ReviewScreen | None = None
        self.exit_code = 0
        self.search_screen: SearchScreen | None = SearchScreen() if loaded is None else None

    def on_mount(self) -> None:
        if self.search_screen is not None:
            self.push_screen(self.search_screen)
        elif self.review is not None:
            self.show_review()
        elif self.candidate is None:
            self.push_screen(PickScreen(self.loaded.candidates, self.loaded.username), self._picked)
        else:
            self.start()

    def on_search_screen_submitted(self, msg: SearchScreen.Submitted) -> None:
        self.run_worker(self._search(msg.platform, msg.username), exclusive=True, group="search")

    async def _search(self, platform: str, username: str) -> None:
        try:
            self.loaded = await session.load(user=(platform, username))
        except session.InputError as e:
            self.search_screen.error(str(e))
            return
        runtime.save_last_search(platform, username)
        self.push_screen(PickScreen(self.loaded.candidates, self.loaded.username), self._picked)

    def _picked(self, index: int | None) -> None:
        if index is None:
            if self.search_screen is not None:   # si torna alla ricerca
                self.search_screen.ready()
            else:
                self.exit()
            return
        self.candidate = self.loaded.candidates[index]
        self.start()

    def start(self) -> None:
        c = self.candidate
        self.color = self.color or self.loaded.color_for(c)
        title = f"chess-io · {c.white}{f' ({c.white_elo})' if c.white_elo else ''} vs " \
                f"{c.black}{f' ({c.black_elo})' if c.black_elo else ''}"
        self.analysis_screen = AnalysisScreen(title, f"{self.loaded.origin} · " + tr("{n} semimosse", n=c.plies) + " · "
                                              + tr("profondità {depth}", depth=self.depth))
        self.push_screen(self.analysis_screen)
        if self.color:
            self._color_ready.set()
        else:
            self.push_screen(ColorScreen(c.white, c.black), self._color_chosen)
        self.run_worker(self._analyse(), exclusive=True, group="analysis")

    def _color_chosen(self, color: str | None) -> None:
        self.color = color or "white"
        self._color_ready.set()

    async def _analyse(self) -> None:
        try:
            rv = await session.analyse(self.candidate, self.color or "white", self.depth,
                                       self.analysis_screen.progress)
        except Exception as e:  # noqa: BLE001
            self.analysis_screen.error(str(e) or e.__class__.__name__)
            self.exit_code = 1
            return
        await self._color_ready.wait()
        if rv.game["player_color"] != self.color:
            rv.set_color(self.color)
        self.review = rv
        self.show_review()

    def show_review(self) -> None:
        self.review_screen = ReviewScreen(self.review, self.loaded.origin, llm_enabled=self.llm)
        self.switch_screen(self.review_screen) if len(self.screen_stack) > 1 else self.push_screen(self.review_screen)
        if self.llm:
            self.start_llm()

    def start_llm(self) -> None:
        rv = self.review
        if not llm_jobs.available():
            rv.llm_status, rv.llm_error = "error", tr("llama-server non trovato (vedi chess-io doctor)")
            self.review_screen.refresh_llm_status()
            return
        if llm_jobs.model_ready():
            self._run_llm()
            return

        def answer(ok: bool | None) -> None:
            if ok:
                self._run_llm()
            else:
                rv.llm_status, rv.llm_error = "error", tr("modello non scaricato")
                self.review_screen.refresh_llm_status()
        self.push_screen(ConfirmScreen(tr(
            "Per i commenti LLM serve il modello Qwen3 1.7B ({size:.1f} GB), da scaricare una volta sola da Hugging Face. "
            "Scaricarlo ora?", size=llm_jobs.MODEL_SIZE_GB)), answer)

    def _run_llm(self) -> None:
        screen = self.review_screen
        self.run_worker(llm_jobs.run(self.review, screen.llm_updated), group="llm")
        self.set_interval(1.0, lambda: self.review.llm_status == "downloading" and screen.refresh_llm_status())

    async def on_unmount(self) -> None:
        from ..engine import analysis_engine
        await analysis_engine.close()
        await llm_jobs.shutdown()
