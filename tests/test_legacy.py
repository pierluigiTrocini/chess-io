"""Compatibilità con il vecchio nome chess-me: cartella dati e variabili CHESSME_*."""
from chess_io import i18n, runtime


def _xdg(monkeypatch, tmp_path):
    for v in ("CHESSIO_HOME", "CHESSME_HOME"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))


def test_legacy_data_moved_once(monkeypatch, tmp_path):
    _xdg(monkeypatch, tmp_path)
    old = tmp_path / "chess-me"
    (old / "models").mkdir(parents=True)
    (old / "models" / "m.gguf").write_text("x")
    (old / "settings.json").write_text('{"lang": "en"}')
    (old / "venv").mkdir()

    home = runtime.data_home()

    assert home == tmp_path / "chess-io"
    assert (home / "models" / "m.gguf").read_text() == "x"
    assert (home / "settings.json").exists()
    assert not (home / "venv").exists() and (old / "venv").is_dir()   # la vecchia installazione resta


def test_no_migration_when_new_home_exists(monkeypatch, tmp_path):
    _xdg(monkeypatch, tmp_path)
    (tmp_path / "chess-me").mkdir()
    (tmp_path / "chess-me" / "settings.json").write_text("{}")
    (tmp_path / "chess-io").mkdir()

    runtime.data_home()

    assert (tmp_path / "chess-me" / "settings.json").exists()


def test_legacy_env_vars(monkeypatch, tmp_path):
    monkeypatch.delenv("CHESSIO_HOME", raising=False)
    monkeypatch.delenv("CHESSIO_LANG", raising=False)
    monkeypatch.setenv("CHESSME_HOME", str(tmp_path / "custom"))
    monkeypatch.setenv("CHESSME_LANG", "es")

    assert runtime.data_home() == tmp_path / "custom"
    assert i18n.resolve() == "es"

    monkeypatch.setenv("CHESSIO_LANG", "en")
    assert i18n.resolve() == "en"   # il nuovo nome ha la precedenza
