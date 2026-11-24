"""Review sintetica (senza Stockfish) per i test della TUI: la trappola di Blackburne."""
import chess

SANS = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nd4", "Nxe5", "Qg5", "Nxf7", "Qxg2", "Rf1", "Qxe4+", "Be2", "Nf3#"]
CLASSES = ["book", "book", "book", "book", "book", "inaccuracy", "blunder", "great", "blunder", "best",
           "best", "best", "best", "best"]
EVALS = [30, 25, 35, 30, 30, 60, -410, -400, -900, -950, -1000, -1200, -1500, None]

PGN = """[Event "Test"]
[White "Tu"]
[Black "magnus_fan"]
[WhiteElo "1520"]
[BlackElo "1490"]
[Result "0-1"]
[TimeControl "300+0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3# 0-1
"""


def fake_analysis() -> dict:
    """Stessa forma dell'output di analyse_game()."""
    import json
    b = chess.Board()
    moves = []
    for i, (san, cls, ev) in enumerate(zip(SANS, CLASSES, EVALS)):
        mv = b.parse_san(san)
        before = b.copy()
        b.push(mv)
        best = chess.Move.from_uci("f3d4") if san == "Nxe5" else mv
        ref = [chess.Move.from_uci(u) for u in ("d8g5", "e5f7", "g5g2", "h1f1")] if san == "Nxe5" else []
        mate = 0 if b.is_checkmate() else None
        moves.append({
            "ply": i, "eval_cp": ev if ev is not None else -10000, "eval_mate": mate,
            "best_uci": best.uci(), "best_san": before.san(best),
            "best_pv_san": json.dumps([before.san(best)]), "best_pv_uci": json.dumps([best.uci()]),
            "best_eval_cp": 30 if san == "Nxe5" else ev, "best_eval_mate": None, "second_eval_cp": None,
            "refutation_pv_san": json.dumps(["Qg5", "Nxf7", "Qxg2", "Rf1"] if ref else []),
            "refutation_pv_uci": json.dumps([m.uci() for m in ref]),
            "threat_san": None, "motifs_json": json.dumps({"san": san, "best_san": before.san(best)}),
            "win_before": 50.0, "win_after": 40.0 if cls == "blunder" else 50.0,
            "delta_ep": 0.4 if cls == "blunder" else 0.01, "accuracy": 20.0 if cls == "blunder" else 95.0,
            "classification": cls, "phase": "opening",
            "comment": f"{san}: commento di prova per la classe {cls}." + (" Scacco matto!" if mate == 0 else ""),
        })
    counts = {"white": {}, "black": {}}
    for m in moves:
        side = counts["white" if m["ply"] % 2 == 0 else "black"]
        side[m["classification"]] = side.get(m["classification"], 0) + 1
    review = {"accuracy_white": 41.8, "accuracy_black": 93.6, "rating_est_white": 900, "rating_est_black": 2000,
              "counts_json": json.dumps(counts), "key_moments_json": json.dumps([5, 6, 8]),
              "engine_version": "Stockfish 18", "depth": 16, "eco": "C50", "opening_name": "Italian Game"}
    return {"moves": moves, "review": review}


def fake_review(color: str = "white"):
    from chess_me import session
    from chess_me import pgn as pgn_parse
    c = pgn_parse.parse_one(PGN)
    return session.merge(c, color, fake_analysis()), c
