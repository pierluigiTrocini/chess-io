import chess

from chess_me.review.accuracy import estimated_rating, game_accuracy
from chess_me.explain import motifs
from chess_me.review.material import describe_points
from chess_me.review.sacrifice import sacrificed_points
from chess_me.review.winprob import move_accuracy, win_percent
from chess_me.review.classify import MoveEval, classify


def test_win_percent_symmetry():
    assert abs(win_percent(0) - 50) < 1e-9
    assert abs(win_percent(300) + win_percent(-300) - 100) < 1e-9
    assert win_percent(10000) > 99.9


def test_move_accuracy():
    assert move_accuracy(60, 60) > 99.9
    assert move_accuracy(60, 60) <= 100
    assert move_accuracy(80, 20) < 10


def test_game_accuracy_perfect_and_bad():
    wins = [50.0] * 21
    accs = [100.0] * 20
    w, b = game_accuracy(wins, accs)
    assert w == 100.0 and b == 100.0
    w, b = game_accuracy(wins, [100.0, 10.0] * 10)
    assert w > 95 and b < 20


def test_rating_monotonic():
    assert estimated_rating(60, 0) < estimated_rating(80, 0) < estimated_rating(95, 0)
    assert estimated_rating(80, 4) < estimated_rating(80, 0)


def test_describe_points():
    assert describe_points(1) == "un pedone"
    assert describe_points(5) == "una torre"


def test_fork_detected():
    # cavallo bianco in c7 forchetta re e8 e torre a8
    board = chess.Board("r3k3/2N5/8/8/8/8/8/4K3 b - - 0 1")
    targets = motifs.fork_targets(board, chess.C7)
    assert any("re" in t for t in targets) and any("torre" in t for t in targets)


def test_hanging_piece():
    board = chess.Board()
    for san in ["e4", "e5", "Nf3", "Qh4"]:
        board.push_san(san)
    hanging = motifs.hanging_after(board, chess.BLACK)
    assert any("donna" in h for h in hanging)


def test_legal_mate_is_sacrifice():
    board = chess.Board()
    for san in ["e4", "e5", "Nf3", "d6", "Bc4", "Bg4", "Nc3", "g6"]:
        board.push_san(san)
    move = board.parse_san("Nxe5")
    after = board.copy()
    after.push(move)
    pv = []
    b = after.copy()
    for san in ["Bxd1", "Bxf7+", "Ke7", "Nd5#"]:
        mv = b.parse_san(san)
        pv.append(mv)
        b.push(mv)
    assert sacrificed_points(board, move, pv) >= 2


def test_pinned_pawn_capture_is_not_sacrifice():
    # Nd4 "in presa" del pedone c5, ma c5 è inchiodato alla donna e7 dalla donna a3: non è un sacrificio
    board = chess.Board("6k1/4qppp/8/2p5/8/Q3PN2/5PPP/6K1 w - - 0 1")
    move = board.parse_san("Nd4")
    assert sacrificed_points(board, move, []) == 0


def test_normal_trade_is_not_sacrifice():
    board = chess.Board()
    for san in ["e4", "d5"]:
        board.push_san(san)
    move = board.parse_san("exd5")
    after = board.copy()
    after.push(move)
    pv = [after.parse_san("Qxd5")]
    assert sacrificed_points(board, move, pv) == 0


def test_classify_thresholds():
    board = chess.Board()
    mv = chess.Move.from_uci("e2e4")
    other = chess.Move.from_uci("d2d4")
    base = dict(ply=0, board_before=board, move=mv, best_move=other, ep_second=None)
    assert classify(MoveEval(**base, ep_best=0.55, ep_after=0.54))[0] == "excellent"
    assert classify(MoveEval(**base, ep_best=0.55, ep_after=0.51))[0] == "good"
    assert classify(MoveEval(**base, ep_best=0.55, ep_after=0.47))[0] == "inaccuracy"
    assert classify(MoveEval(**base, ep_best=0.55, ep_after=0.40))[0] == "mistake"
    assert classify(MoveEval(**base, ep_best=0.55, ep_after=0.20))[0] == "blunder"
    assert classify(MoveEval(**base, ep_best=0.55, ep_after=0.52, is_book=True))[0] == "book"
    # una "mossa di libro" che perde molto non è nascosta come book
    assert classify(MoveEval(**base, ep_best=0.55, ep_after=0.20, is_book=True))[0] == "blunder"
    # miss: l'avversario aveva sbagliato e il vantaggio viene sprecato
    assert classify(MoveEval(**base, ep_best=0.85, ep_after=0.70, opp_prev_delta=0.3))[0] == "miss"


def test_exchange_is_not_hanging():
    board = chess.Board()
    for san in ["e4", "e5", "Nf3", "d6", "d4", "Bg4", "dxe5"]:
        board.push_san(san)
    mv = board.parse_san("Bxf3")
    after = board.copy()
    after.push(mv)
    assert motifs.hanging_after(after, chess.BLACK, mv, 3) == []


def _summary_fixture():
    """Partita fittizia: il bianco (io) sbaglia gravemente alla mossa 3 lasciando un alfiere in presa."""
    moves = []
    wins = [55, 50, 52, 50, 10, 92, 8, 93]   # win% di chi muove, dopo la mossa
    for ply, w in enumerate(wins):
        cls = "blunder" if ply == 4 else "best"
        motifs = {"loss": "un alfiere", "first_capture": "l'alfiere in f4", "best_san": "Be3"} if ply == 4 else {}
        moves.append({"ply": ply, "san": ["e4", "e5", "Nf3", "Nc6", "Bf4", "exf4", "d4", "Qh4"][ply],
                      "classification": cls, "win_after": w, "accuracy": 20 if ply == 4 else 100,
                      "phase": "opening", "delta_ep": 0.4 if ply == 4 else 0, "clock_ms": None,
                      "comment": "Bf4?? Dopo exf4 perdi un alfiere (l'alfiere in f4 cade). Meglio Be3." if ply == 4 else "ok",
                      "motifs_json": motifs})
    game = {"player_color": "white", "black_name": "rival", "black_elo": 1500, "opening_name": "Italian Game",
            "result": "0-1", "time_initial_s": None}
    review = {"accuracy_white": 61.2, "accuracy_black": 90.1, "counts": {"white": {"blunder": 1}, "black": {}},
              "key_moments": [4]}
    return game, moves, review


def test_template_summary_mentions_critical_blunder_and_advice():
    from chess_me.explain.summary import summary_facts, template_summary
    game, moves, review = _summary_fixture()
    f = summary_facts(game, moves, review, "abbandono")
    t = template_summary(f)
    assert t["overview"].startswith("Hai giocato con il bianco contro rival (1500), nella Italian Game.")
    assert "61%" in t["overview"] and "sconfitta per abbandono" in t["overview"]
    assert "l'avversario" in t["overview"]                 # chi è passato in vantaggio
    assert [c["ply"] for c in t["critical"]] == [4] and t["critical"][0]["mine"]
    assert "3. Bf4 (grave errore, mossa tua)" in t["critical"][0]["text"]
    assert any("senza difesa" in a and "3. Bf4, dove era meglio Be3" in a for a in t["advice"])
    assert t["brief"].split("\n") == [
        "Sconfitta per abbandono in 4 mosse · accuratezza 61% contro 90%.",
        "Momento chiave: 3. Bf4 (grave errore).",
        "Da ricordare: controlla i pezzi indifesi.",
    ]


def test_template_summary_clean_game():
    from chess_me.explain.summary import summary_facts, template_summary
    game, moves, review = _summary_fixture()
    for m in moves:
        m["classification"], m["motifs_json"], m["win_after"] = "best", {}, 50
    review["key_moments"], review["counts"] = [], {"white": {}, "black": {}}
    t = template_summary(summary_facts(game, moves, review))
    assert "equilibrio" in t["overview"] and t["critical"] == []
    assert t["brief"].endswith("Partita in equilibrio, senza svolte nette.\nDa ricordare: continua così.")
    assert t["advice"] == ["Partita molto pulita, senza errori: continua a giocare così e prova ad alzare il livello degli avversari."]


def test_describe_san():
    from chess_me.explain.describe import describe_san
    assert describe_san("Nf3") == "il cavallo in f3"
    assert describe_san("Bxf6+") == "l'alfiere che prende in f6"
    assert describe_san("Nbd2") == "il cavallo in d2"
    assert describe_san("exd5") == "il pedone che prende in d5"
    assert describe_san("e4") == "il pedone in e4"
    assert describe_san("O-O") == "l'arrocco corto" and describe_san("O-O-O#") == "l'arrocco lungo"
    assert describe_san("e8=Q") == "il pedone in e8 con promozione a donna"
    assert describe_san("Kxe2") == "il re che prende in e2"


def test_annotate_moves_but_not_variations_or_squares():
    from chess_me.explain.describe import annotate
    t = annotate("Bf4 è un grave errore: con exf4 cade l'alfiere in f4. Meglio Be3 (12. Be3 Nf6 13. O-O).")
    assert t.startswith("L'alfiere in f4 (Bf4) è un grave errore")
    assert "con il pedone che prende in f4 (exf4)" in t
    assert "l'alfiere in f4." in t                         # casa, non mossa
    assert "Meglio l'alfiere in e3 (Be3) (12. Be3 Nf6 13. O-O)." in t
    assert annotate("Con 14. Bf4 e poi Bf4 ancora.") == "Con l'alfiere in f4 (14. Bf4) e poi Bf4 ancora."


def test_solution_notes():
    from chess_me.explain.templates import solution_notes
    d = {"cls": "mistake", "san": "Bf4", "mover": "white", "best_san": "Be3", "best_line": "12. Be3 Nf6",
         "refutation_line": "12...exf4", "refutation_first": "exf4", "best_fork": ["la torre", "il re"],
         "eval_before": "+0.3", "eval_after": "-1.9"}
    s = solution_notes(d)
    assert "La mossa migliore era Be3, con una forchetta che attacca la torre e il re." in s
    assert "Variante del motore: 12. Be3 Nf6." in s
    assert "Dopo Bf4 il motore risponde 12...exf4" in s
    assert "+0.3" in s and "-1.9" in s
    assert solution_notes({"cls": "best", "san": "e4"}) == "" and solution_notes(None) == ""
