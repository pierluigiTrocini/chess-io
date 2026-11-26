import asyncio

import chess
import httpx
import pytest

from chess_me import pgn as pgn_parse, sources
from chess_me.pgn import parse_many, parse_time_control

LICHESS_PGN = """[Event "Rated Blitz game"]
[Site "https://lichess.org/AbCdEfGh"]
[Date "2025.03.14"]
[White "alice_l"]
[Black "bob_l"]
[Result "1-0"]
[UTCDate "2025.03.14"]
[UTCTime "18:02:11"]
[WhiteElo "1712"]
[BlackElo "1650"]
[Variant "Standard"]
[TimeControl "180+2"]
[ECO "C50"]
[Opening "Italian Game"]
[Termination "Normal"]

1. e4 { [%eval 0.2] [%clk 0:03:00] } 1... e5 { [%eval 0.2] [%clk 0:03:00] } 2. Nf3 { [%clk 0:02:59] } 2... Nc6 { [%clk 0:02:58] }
3. Bc4 { [%clk 0:02:58] } 3... Nf6 { [%clk 0:02:55] } 4. Ng5 { [%clk 0:02:56] } 4... d5 { [%clk 0:02:50] } 1-0
"""

CHESSCOM_PGN = """[Event "Let's Play!"]
[Site "Chess.com"]
[Date "2025.02.01"]
[Round "-"]
[White "Carol_C"]
[Black "dave_c"]
[Result "0-1"]
[CurrentPosition "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"]
[Timezone "UTC"]
[ECO "C00"]
[ECOUrl "https://www.chess.com/openings/Barnes-Defense"]
[UTCDate "2025.02.01"]
[UTCTime "10:00:00"]
[WhiteElo "800"]
[BlackElo "820"]
[TimeControl "1/86400"]
[Termination "dave_c won by checkmate"]
[Link "https://www.chess.com/game/daily/987654321"]

1. f3 {[%clk 23:59:00]} 1... e5 {[%clk 23:59:00]} 2. g4 {[%clk 23:58:00]} 2... Qh4# {[%clk 23:57:00]} 0-1
"""

FEN_BLACK = """[Event "Studio"]
[White "W"]
[Black "B"]
[Result "*"]
[SetUp "1"]
[FEN "4k3/8/8/8/8/8/4P3/4K3 b - - 0 40"]

40... Kd7 41. e4 Kc6 *
"""

CHESS960 = """[Event "960"]
[Variant "Chess960"]
[SetUp "1"]
[FEN "bbqnnrkr/pppppppp/8/8/8/8/PPPPPPPP/BBQNNRKR w HFhf - 0 1"]
[Result "*"]

1. e4 *
"""

ILLEGAL = """[Event "x"]
[Result "*"]

1. e4 e5 2. Ke3 Qxe3 *
"""


def test_parse_lichess():
    [c] = parse_many(LICHESS_PGN)
    assert c.error is None
    assert (c.source, c.source_id, c.source_url) == ("lichess", "AbCdEfGh", "https://lichess.org/AbCdEfGh")
    assert c.white == "alice_l" and c.white_elo == 1712 and c.black_elo == 1650
    assert c.played_at == "2025-03-14 18:02:11"
    assert (c.time_initial_s, c.time_increment_s, c.time_class) == (180, 2, "blitz")
    assert c.plies == 8 and c.moves[0].clock_ms == 180_000 and c.moves[7].clock_ms == 170_000
    assert c.termination == "resign" and c.result == "1-0"
    assert c.opening.startswith("Italian Game")


def test_lichess_site_with_game_prefix():
    pgn = LICHESS_PGN.replace('[Site "https://lichess.org/AbCdEfGh"]', '[Site "https://lichess.org/game/HqjDTU4A"]\n[GameId "HqjDTU4A"]')
    [c] = parse_many(pgn)
    assert (c.source, c.source_id) == ("lichess", "HqjDTU4A")


def test_parse_chesscom_daily_and_multi():
    cands = parse_many(LICHESS_PGN + "\n\n" + CHESSCOM_PGN)
    assert len(cands) == 2
    c = cands[1]
    assert (c.source, c.source_id) == ("chesscom", "daily/987654321")
    assert c.time_class == "daily" and c.time_initial_s is None
    assert c.termination == "checkmate"
    assert c.opening and c.eco


def test_termination_texts():
    b = chess.Board()
    for text, res, code in [("Time forfeit", "1-0", "timeout"), ("Abandoned", "0-1", "abandoned"),
                            ("x won by resignation", "1-0", "resign"), ("x won on time", "0-1", "timeout"),
                            ("Game drawn by repetition", "1/2-1/2", "repetition"),
                            ("Game drawn by agreement", "1/2-1/2", "agreement"),
                            ("Game drawn by timeout vs insufficient material", "1/2-1/2", "timeout"),
                            ("Game drawn by stalemate", "1/2-1/2", "stalemate"),
                            ("Normal", "1/2-1/2", "agreement"), ("", "*", "unterminated")]:
        assert pgn_parse.map_termination({"Termination": text}, b, res) == code, text


def test_time_control():
    assert parse_time_control("60+0") == (60, 0, "bullet")
    assert parse_time_control("600") == (600, 0, "rapid")
    assert parse_time_control("5400+30")[2] == "classical"
    assert parse_time_control("-") == (None, None, None)


def test_rejects_variants_and_illegal():
    [c960] = parse_many(CHESS960)
    assert c960.error and "variante" in c960.error
    [bad] = parse_many(ILLEGAL)
    assert bad.error
    [badfen] = parse_many('[SetUp "1"]\n[FEN "6k1/8/8/8/8/8/8/3r2K1 b - - 0 1"]\n\n1... Kg7 *')
    assert badfen.error and "FEN" in badfen.error


def test_parse_url():
    assert sources.parse_url("https://lichess.org/AbCdEfGh/black#12") == \
        {"source": "lichess", "id": "AbCdEfGh", "kind": None, "color_hint": "black"}
    assert sources.parse_url("lichess.org/AbCdEfGh1234")["id"] == "AbCdEfGh"
    assert sources.parse_url("https://lichess.org/game/HqjDTU4A")["id"] == "HqjDTU4A"
    assert sources.parse_url("https://www.chess.com/game/live/123456")["kind"] == "live"
    assert sources.parse_url("https://www.chess.com/game/daily/77")["kind"] == "daily"
    assert sources.parse_url("https://www.chess.com/analysis/game/live/55?tab=review")["id"] == "55"
    with pytest.raises(sources.FetchError):
        sources.parse_url("https://lichess.org/study/abcdefgh")
    with pytest.raises(sources.FetchError):
        sources.parse_url("https://example.com/game/1")


def _mock(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_fetch_lichess_game():
    def handler(req: httpx.Request):
        assert req.url.path == "/game/export/AbCdEfGh" and req.url.params["clocks"] == "true"
        return httpx.Response(200, text=LICHESS_PGN)

    async def run():
        async with _mock(handler) as c:
            return await sources.fetch_url("https://lichess.org/AbCdEfGh/white", c)
    text, hint = asyncio.run(run())
    assert hint == "white" and "alice_l" in text


def test_fetch_chesscom_game_via_monthly_archive():
    def handler(req: httpx.Request):
        if req.url.host == "www.chess.com":
            assert req.url.path == "/callback/daily/game/987654321"
            return httpx.Response(200, json={"game": {"pgnHeaders": {"White": "Carol_C", "Black": "dave_c",
                                                                     "Date": "2025.02.01"}}})
        if req.url.path == "/pub/player/carol_c/games/2025/02":
            return httpx.Response(200, json={"games": [
                {"url": "https://www.chess.com/game/daily/1", "pgn": "x"},
                {"url": "https://www.chess.com/game/daily/987654321", "pgn": CHESSCOM_PGN}]})
        return httpx.Response(404)

    async def run():
        async with _mock(handler) as c:
            return await sources.fetch_url("https://www.chess.com/game/daily/987654321", c)
    text, _ = asyncio.run(run())
    assert "Qh4#" in text


def test_fetch_errors_are_italian():
    def handler(req):
        return httpx.Response(429)

    async def run():
        async with _mock(handler) as c:
            await sources.fetch_lichess_game("AbCdEfGh", c)
    with pytest.raises(sources.FetchError, match="troppe richieste"):
        asyncio.run(run())


def test_fetch_lichess_user_games():
    def handler(req: httpx.Request):
        assert req.url.path == "/api/games/user/alice_l" and req.url.params["max"] == "50"
        assert "chess960" not in req.url.params["perfType"]
        return httpx.Response(200, text=LICHESS_PGN)

    async def run():
        async with _mock(handler) as c:
            return await sources.fetch_user_games("Lichess", "alice_l", client=c)
    assert "alice_l" in asyncio.run(run())


def test_fetch_chesscom_user_games_newest_first_and_standard_only():
    base = "https://api.chess.com/pub/player/carol_c/games"

    def handler(req: httpx.Request):
        if req.url.path.endswith("/archives"):
            return httpx.Response(200, json={"archives": [f"{base}/2025/01", f"{base}/2025/02"]})
        if req.url.path.endswith("/2025/02"):
            return httpx.Response(200, json={"games": [
                {"end_time": 1, "rules": "chess", "pgn": "VECCHIA"},
                {"end_time": 2, "rules": "chess960", "pgn": "960"},
                {"end_time": 3, "rules": "chess", "pgn": "NUOVA"}]})
        return httpx.Response(200, json={"games": [{"end_time": 0, "rules": "chess", "pgn": "GENNAIO"}]})

    async def run(n):
        async with _mock(handler) as c:
            return await sources.fetch_user_games("chess.com", "Carol_C", n, client=c)
    assert asyncio.run(run(2)) == "NUOVA\n\nVECCHIA"
    assert asyncio.run(run(5)).endswith("GENNAIO") and "960" not in asyncio.run(run(5))


def test_user_args_are_validated():
    with pytest.raises(sources.FetchError, match="piattaforma"):
        sources.normalize_platform("fics")
    with pytest.raises(sources.FetchError, match="nome utente"):
        sources.check_username("../etc")
    assert sources.normalize_platform("Chess.com") == "chesscom"
