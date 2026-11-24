# PyInstaller: cartella self-contained (--onedir) di chess-me. Usato da bundle.sh e dallo stage Docker cli-bundle.
import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 (SPECPATH è definito da PyInstaller)
SRC = os.path.join(ROOT, "src")
DATA = os.path.join(SRC, "chess_me", "data")

hidden = collect_submodules("chess_me") + collect_submodules("textual") + collect_submodules("rich")

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],  # noqa: F821
    pathex=[SRC],
    # il database delle aperture va in share/ del bundle, non dentro il pacchetto
    datas=[(os.path.join(DATA, f), os.path.join("chess_me", "data")) for f in ("prompts.toml", "binaries.toml")],
    hiddenimports=hidden,
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="chess-me", console=True, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="chess-me")
