"""LLM dell'utente: servizio compatibile OpenAI, preferenze salvate, comando `chess-io llm`, schermata F3."""
import asyncio
import json
import os
import stat

import httpx
import pytest

from chess_io import cli, i18n, runtime
from chess_io.llm import server


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("CHESSIO_HOME", str(tmp_path))
    for k in ("CHESSIO_LLM_URL", "CHESSIO_LLM_MODEL", "CHESSIO_LLM_API_KEY", "OPENAI_API_KEY",
              "CHESSME_LLM_URL", "CHESSME_LLM_MODEL", "CHESSME_LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(server, "_backend", server.Backend())
    i18n.set_lang("it")
    yield
    i18n.set_lang("it")


class FakeService:
    """Servizio OpenAI finto: registra le richieste, risponde con `replies` (status, json) in ordine."""

    def __init__(self, monkeypatch, replies=None, models=("qwen3:4b", "llama3.2")):
        self.requests: list[httpx.Request] = []
        self.replies = list(replies or [])
        self.models = models
        real = httpx.AsyncClient

        def make(*a, **k):
            k["transport"] = httpx.MockTransport(self.handle)
            return real(*a, **k)
        monkeypatch.setattr(server.httpx, "AsyncClient", make)

        async def no_sleep(_s):
            return None
        monkeypatch.setattr(server.asyncio, "sleep", no_sleep)

        async def no_proc(*_a, **_k):
            raise AssertionError("llama-server non deve partire con un servizio esterno")
        monkeypatch.setattr(server.asyncio, "create_subprocess_exec", no_proc)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": m} for m in self.models]})
        if self.replies:
            code, body = self.replies.pop(0)
            return httpx.Response(code, json=body)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    def payload(self, i: int = -1) -> dict:
        return json.loads(self.requests[i].content)


def test_normalize_and_local_url():
    assert runtime.normalize_url("localhost:11434") == "http://localhost:11434/v1"
    assert runtime.normalize_url("https://openrouter.ai/api/v1/") == "https://openrouter.ai/api/v1"
    assert runtime.is_local_url("http://127.0.0.1:1234/v1") and runtime.is_local_url("mybox.local:8080")
    assert not runtime.is_local_url("https://api.openai.com/v1")


def test_external_chat_payload_and_headers(monkeypatch):
    svc = FakeService(monkeypatch)
    b = server.Backend("http://localhost:11434", "qwen3:4b", "sk-test")
    asyncio.run(server.configure(b))
    assert server.available() and server.model_ready() and server.model_name() == "qwen3:4b"
    out = asyncio.run(server.chat([{"role": "user", "content": "ciao"}], max_tokens=100))
    assert out == "ok"
    req = svc.requests[-1]
    assert str(req.url) == "http://localhost:11434/v1/chat/completions"
    assert req.headers["authorization"] == "Bearer sk-test"
    p = svc.payload()
    assert p["model"] == "qwen3:4b" and p["max_tokens"] == int(100 * server.EXTERNAL_TOKENS_FACTOR)
    assert "cache_prompt" not in p and "chat_template_kwargs" not in p   # estensioni solo di llama.cpp


def test_no_auth_header_without_key(monkeypatch):
    svc = FakeService(monkeypatch)
    asyncio.run(server.chat([{"role": "user", "content": "x"}], backend=server.Backend("localhost:1234", "m")))
    assert "authorization" not in svc.requests[-1].headers


def test_retry_on_rate_limit(monkeypatch):
    svc = FakeService(monkeypatch, replies=[(429, {"error": "slow down"}), (503, {}),
                                            (200, {"choices": [{"message": {"content": "fatto"}}]})])
    b = server.Backend("localhost:11434", "m")
    assert asyncio.run(server.chat([{"role": "user", "content": "x"}], backend=b)) == "fatto"
    assert len(svc.requests) == 3


@pytest.mark.parametrize("code,needle", [(401, "chiave API"), (404, "non trovato"),
                                         (400, "HTTP 400: bad model")])
def test_readable_errors(monkeypatch, code, needle):
    FakeService(monkeypatch, replies=[(code, {"error": {"message": "bad model"}})])
    with pytest.raises(RuntimeError, match=needle):
        asyncio.run(server.chat([{"role": "user", "content": "x"}], backend=server.Backend("localhost:1", "m")))


def test_missing_model_is_an_error(monkeypatch):
    FakeService(monkeypatch)
    with pytest.raises(RuntimeError, match="nome del modello"):
        asyncio.run(server.chat([{"role": "user", "content": "x"}], backend=server.Backend("localhost:1")))


def test_probe_lists_models(monkeypatch):
    FakeService(monkeypatch)
    models, reply = asyncio.run(server.probe(server.Backend("localhost:11434", "qwen3:4b")))
    assert models == ["llama3.2", "qwen3:4b"] and reply == "ok"
    models, reply = asyncio.run(server.probe(server.Backend("localhost:11434")))
    assert reply == ""


def test_settings_precedence_and_secret_file(monkeypatch, tmp_path):
    assert runtime.llm_settings().saved_mode == "off" and not runtime.llm_settings().enabled
    assert runtime.save_llm_settings("external", "http://localhost:11434/v1", "qwen3:4b", "sk-secret")
    s = runtime.llm_settings()
    assert (s.saved_mode, s.external, s.enabled, s.model, s.api_key) == ("external", True, True, "qwen3:4b", "sk-secret")
    assert "sk-secret" not in (tmp_path / runtime.SETTINGS_FILE).read_text()
    assert stat.S_IMODE(os.stat(tmp_path / runtime.SECRETS_FILE).st_mode) == 0o600
    # variabile d'ambiente → flag CLI
    monkeypatch.setenv("CHESSIO_LLM_API_KEY", "sk-env")
    monkeypatch.setenv("CHESSIO_LLM_MODEL", "llama3.2")
    s = runtime.llm_settings()
    assert (s.api_key, s.key_from_env, s.model) == ("sk-env", True, "llama3.2")
    s = runtime.llm_settings(enabled=False, model="phi4")
    assert (s.enabled, s.model) == (False, "phi4")
    # modalità locale salvata: l'URL resta ricordato ma non si usa; un URL da flag invece vince
    runtime.save_llm_settings("local", "http://localhost:11434/v1", "qwen3:4b")
    assert not runtime.llm_settings().external and runtime.llm_settings().enabled
    assert runtime.llm_settings(url="http://localhost:1234/v1").external
    runtime.save_llm_settings("external", "http://localhost:11434/v1", "qwen3:4b", "")
    assert "llm_api_key" not in runtime.load_secrets()


def test_bootstrap_exports_backend_only_when_external(monkeypatch):
    monkeypatch.setattr(os, "environ", dict(os.environ))
    runtime.bootstrap(llm=runtime.LlmSettings("external", "http://localhost:11434/v1", "m", "k", external=True,
                                              enabled=True))
    assert (os.environ["LLM_BASE_URL"], os.environ["LLM_MODEL"], os.environ["LLM_API_KEY"]) == \
        ("http://localhost:11434/v1", "m", "k")
    runtime.bootstrap(llm=runtime.LlmSettings("local", enabled=True))
    assert "LLM_BASE_URL" not in os.environ and "LLM_API_KEY" not in os.environ


def test_cli_llm_command(capsys):
    assert cli.main(["llm", "set", "--url", "localhost:11434", "--model", "qwen3:4b"]) == 0
    out = capsys.readouterr().out
    assert "http://localhost:11434/v1" in out and "qwen3:4b" in out
    assert runtime.load_settings()["llm_mode"] == "external"
    assert cli.main(["llm", "local"]) == 0
    assert runtime.load_settings()["llm_mode"] == "local"
    assert runtime.load_settings()["llm_url"] == "http://localhost:11434/v1"   # ricordato per dopo
    assert cli.main(["llm", "set", "--url", "https://api.openai.com/v1", "--model", "gpt-4.1-mini"]) == 0
    assert "remoto" in capsys.readouterr().out
    cli.main(["doctor"])
    assert "Servizio LLM" in capsys.readouterr().out


def test_cli_llm_flags():
    a = cli.build_parser().parse_args(["-pgn", "x", "--no-llm"])
    assert a.llm is False
    a = cli.build_parser().parse_args(["-pgn", "x", "--llm-url", "localhost:11434", "--llm-model", "m"])
    assert (a.llm, a.llm_url, a.llm_model) == (None, "localhost:11434", "m")
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["-pgn", "x", "--llm", "--no-llm"])


def test_settings_screen_saves_external_service(monkeypatch, tmp_path):
    pytest.importorskip("textual")
    from textual.widgets import Input, OptionList, RadioButton, Static
    from chess_io.tui.app import ChessIoApp
    from chess_io.tui.screens import LlmSettingsScreen
    FakeService(monkeypatch)

    async def run():
        app = ChessIoApp(None, None, None, 16, False)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            await pilot.press("f3")
            await pilot.pause()
            scr = app.screen
            assert isinstance(scr, LlmSettingsScreen) and scr.mode == "off"
            scr.query_one("#mode-external", RadioButton).value = True
            await pilot.pause()
            assert scr.query_one("#llm-ext").display and not scr.query_one("#llm-local").display
            scr.query_one("#ext-url", Input).value = "localhost:11434"
            await scr._probe()
            await pilot.pause()
            ol = scr.query_one("#ext-models", OptionList)
            assert ol.display and ol.option_count == 2
            assert "scegli un modello" in str(scr.query_one("#ext-status", Static).render())
            scr.query_one("#ext-model", Input).value = "qwen3:4b"
            scr.query_one("#ext-key", Input).value = "sk-x"
            scr.action_save()
            await pilot.pause()
            await app.workers.wait_for_complete()
            assert not isinstance(app.screen, LlmSettingsScreen)
            assert app.llm and server.external() and server.backend().model == "qwen3:4b"
    asyncio.run(run())
    s = runtime.llm_settings()
    assert (s.saved_mode, s.url, s.model, s.api_key) == ("external", "http://localhost:11434/v1", "qwen3:4b", "sk-x")


def test_settings_screen_requires_url_and_model():
    pytest.importorskip("textual")
    from textual.widgets import RadioButton, Static
    from chess_io.tui.app import ChessIoApp
    from chess_io.tui.screens import LlmSettingsScreen

    async def run():
        app = ChessIoApp(None, None, None, 16, False)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            await pilot.press("f3")
            await pilot.pause()
            scr = app.screen
            scr.query_one("#mode-external", RadioButton).value = True
            await pilot.pause()
            scr.action_save()
            await pilot.pause()
            assert isinstance(app.screen, LlmSettingsScreen)
            assert "servono indirizzo" in str(scr.query_one("#ext-status", Static).render())
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, LlmSettingsScreen)
    asyncio.run(run())
    assert "llm_mode" not in runtime.load_settings()
