"""Scaricamento delle partite da Lichess e chess.com (API pubbliche, nessuna autenticazione)."""
import re
from urllib.parse import urlparse

import httpx

from .i18n import tr

USER_AGENT = "chess-me-cli/1.0"
TIMEOUT = httpx.Timeout(15.0, connect=10.0)
LICHESS_RESERVED = {"study", "broadcast", "tv", "training", "analysis", "editor", "games", "api", "team", "tournament",
                    "swiss", "simul", "practice", "learn", "paste", "inbox", "streamer", "video"}


class FetchError(Exception):
    pass


def parse_url(url: str) -> dict:
    """{'source': 'lichess'|'chesscom', 'id': ..., 'kind': 'live'|'daily'|None, 'color_hint': ...}."""
    raw = url.strip()
    if not re.match(r"^https?://", raw):
        raw = "https://" + raw
    u = urlparse(raw)
    host = (u.hostname or "").lower()
    parts = [p for p in u.path.split("/") if p]
    if host.endswith("lichess.org"):
        if len(parts) > 1 and parts[0] == "game":  # lichess.org/game/ID (formato del tag Site)
            parts = parts[1:]
        if parts and parts[0] not in LICHESS_RESERVED and re.fullmatch(r"[A-Za-z0-9]{8}|[A-Za-z0-9]{12}", parts[0]):
            hint = parts[1] if len(parts) > 1 and parts[1] in ("white", "black") else None
            return {"source": "lichess", "id": parts[0][:8], "kind": None, "color_hint": hint}
        raise FetchError(tr("link Lichess non riconosciuto: serve il link di una partita (lichess.org/abcd1234)"))
    if host.endswith("chess.com"):
        m = re.search(r"/(?:analysis/)?game/(?:(live|daily)/)?(\d+)", u.path) or \
            re.search(r"/(live|daily)/game/(\d+)", u.path)
        if m:
            return {"source": "chesscom", "id": m.group(2), "kind": m.group(1) or "live", "color_hint": None}
        raise FetchError(tr("link chess.com non riconosciuto: serve il link di una partita (chess.com/game/live/123…)"))
    raise FetchError(tr("sono supportati solo link di lichess.org e chess.com"))


def _client(client: httpx.AsyncClient | None) -> httpx.AsyncClient:
    return client or httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


async def _get(client: httpx.AsyncClient, url: str, what: str, **kw) -> httpx.Response:
    try:
        r = await client.get(url, **kw)
    except httpx.TimeoutException:
        raise FetchError(tr("{what}: il server non risponde, riprova più tardi", what=what))
    except httpx.HTTPError:
        raise FetchError(tr("{what}: impossibile connettersi. C'è accesso a Internet? In alternativa incolla il PGN.",
                            what=what))
    if r.status_code == 404:
        raise FetchError(tr("{what}: non trovato", what=what))
    if r.status_code == 429:
        raise FetchError(tr("{what}: troppe richieste, riprova tra un minuto", what=what))
    if r.status_code >= 400:
        raise FetchError(tr("{what}: errore {code}", what=what, code=r.status_code))
    return r


async def fetch_lichess_game(gid: str, client: httpx.AsyncClient | None = None) -> str:
    c = _client(client)
    try:
        r = await _get(c, f"https://lichess.org/game/export/{gid}", "Lichess",
                       params={"clocks": "true", "evals": "false", "opening": "true"},
                       headers={"Accept": "application/x-chess-pgn"})
        return r.text
    finally:
        if client is None:
            await c.aclose()


def _next_month(y: int, m: int) -> tuple[int, int]:
    return (y + 1, 1) if m == 12 else (y, m + 1)


async def fetch_chesscom_game(gid: str, kind: str = "live", client: httpx.AsyncClient | None = None) -> str:
    """Il callback (non ufficiale) dà giocatori e data; il PGN si prende dall'archivio mensile pubblico."""
    c = _client(client)
    try:
        r = await _get(c, f"https://www.chess.com/callback/{kind}/game/{gid}", "chess.com")
        try:
            data = r.json()
            hdr = data["game"]["pgnHeaders"]
            players = [hdr["White"], hdr["Black"]]
            y, m = (int(x) for x in hdr["Date"].split(".")[:2])
        except (ValueError, KeyError, TypeError):
            raise FetchError(tr("chess.com: formato della risposta inatteso. Incolla il PGN da Condividi → PGN"))
        for player in players:
            for (yy, mm) in ((y, m), _next_month(y, m)):
                try:
                    arch = await _get(c, f"https://api.chess.com/pub/player/{player.lower()}/games/{yy}/{mm:02d}",
                                      "chess.com")
                except FetchError:
                    continue
                for g in arch.json().get("games", []):
                    if str(g.get("url", "")).rstrip("/").endswith(f"/{gid}") and g.get("pgn"):
                        return g["pgn"]
        raise FetchError(tr("chess.com: partita non trovata negli archivi pubblici. Incolla il PGN da Condividi → PGN"))
    finally:
        if client is None:
            await c.aclose()


async def fetch_url(url: str, client: httpx.AsyncClient | None = None) -> tuple[str, str | None]:
    """Restituisce (testo PGN, suggerimento di colore)."""
    info = parse_url(url)
    if info["source"] == "lichess":
        return await fetch_lichess_game(info["id"], client), info["color_hint"]
    return await fetch_chesscom_game(info["id"], info["kind"], client), None


# ---------- partite recenti di un utente ----------
PLATFORMS = {"lichess": "lichess", "lichess.org": "lichess",
             "chess.com": "chesscom", "chesscom": "chesscom", "chess": "chesscom"}
USERNAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{1,29}")
USER_GAMES = 50
LICHESS_PERFS = "ultraBullet,bullet,blitz,rapid,classical,correspondence"  # niente varianti


def normalize_platform(name: str) -> str:
    try:
        return PLATFORMS[name.strip().lower()]
    except KeyError:
        raise FetchError(tr("piattaforma sconosciuta: {name} (usa lichess oppure chess.com)", name=name))


def check_username(name: str) -> str:
    if not USERNAME_RE.fullmatch(name.strip()):
        raise FetchError(tr("nome utente non valido: {name}", name=name))
    return name.strip()


async def fetch_lichess_user_games(user: str, n: int = USER_GAMES, client: httpx.AsyncClient | None = None) -> str:
    c = _client(client)
    try:
        r = await _get(c, f"https://lichess.org/api/games/user/{user}", tr("Lichess, utente {user}", user=user),
                       params={"max": str(n), "clocks": "true", "evals": "false", "opening": "true",
                               "perfType": LICHESS_PERFS},
                       headers={"Accept": "application/x-chess-pgn"})
        return r.text
    finally:
        if client is None:
            await c.aclose()


async def fetch_chesscom_user_games(user: str, n: int = USER_GAMES, client: httpx.AsyncClient | None = None) -> str:
    """Archivi mensili pubblici, dal più recente all'indietro, fino a n partite di scacchi standard."""
    c = _client(client)
    what = tr("chess.com, utente {user}", user=user)
    try:
        r = await _get(c, f"https://api.chess.com/pub/player/{user.lower()}/games/archives", what)
        try:
            archives = list(r.json()["archives"])
        except (ValueError, KeyError, TypeError):
            raise FetchError(tr("{what}: formato della risposta inatteso", what=what))
        pgns: list[str] = []
        for url in reversed(archives[-24:]):  # al massimo gli ultimi due anni
            month = await _get(c, url, what)
            games = [g for g in month.json().get("games", []) if g.get("rules", "chess") == "chess" and g.get("pgn")]
            games.sort(key=lambda g: g.get("end_time", 0), reverse=True)
            pgns.extend(g["pgn"] for g in games)
            if len(pgns) >= n:
                break
        return "\n\n".join(pgns[:n])
    finally:
        if client is None:
            await c.aclose()


async def fetch_user_games(platform: str, user: str, n: int = USER_GAMES,
                           client: httpx.AsyncClient | None = None) -> str:
    """PGN (più partite, dalla più recente) delle ultime n partite dell'utente."""
    src, user = normalize_platform(platform), check_username(user)
    if src == "lichess":
        return await fetch_lichess_user_games(user, n, client)
    return await fetch_chesscom_user_games(user, n, client)
