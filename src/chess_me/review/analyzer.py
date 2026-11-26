"""Pipeline di analisi di una partita: motore → classificazione → accuratezza → spiegazioni."""
import json
import logging
from dataclasses import dataclass
from typing import Callable

import chess
import chess.engine

from .. import config, openings
from ..engine import analysis_engine
from . import params as cfg
from .accuracy import estimated_rating, game_accuracy
from .classify import CLASSES, MoveEval, classify, phase_of
from ..explain.facts import build_facts, fmt_eval
from ..explain.templates import mate_comment, render
from .winprob import expected_points, move_accuracy, win_percent

log = logging.getLogger(__name__)
MATE_CP = 10000


@dataclass
class PosInfo:
    terminal: str | None = None              # "checkmate" | "draw" | None
    cp: int | None = None                    # pov di chi muove
    mate: int | None = None                  # pov di chi muove
    best: chess.Move | None = None
    pv: list[chess.Move] | None = None
    second: chess.Move | None = None
    second_cp: int | None = None

    def cp_value(self) -> int:
        """Valutazione in cp dal punto di vista di chi muove (posizioni terminali comprese)."""
        if self.terminal == "checkmate":
            return -MATE_CP           # chi deve muovere ha subito matto
        if self.terminal == "draw":
            return 0
        return self.cp or 0


def _terminal(board: chess.Board) -> str | None:
    if board.is_checkmate():
        return "checkmate"
    if board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves() \
            or board.is_fivefold_repetition():
        return "draw"
    return None


async def analyse_position(board: chess.Board, depth: int, multipv: int = 2, tag: str | None = None,
                           max_time: float | None = None) -> PosInfo:
    term = _terminal(board)
    if term:
        return PosInfo(terminal=term)
    n = min(multipv, board.legal_moves.count())

    async def fn(engine):
        return await engine.analyse(board, chess.engine.Limit(depth=depth, time=max_time), multipv=n, game=tag)

    infos = await analysis_engine.run(fn)
    if isinstance(infos, dict):
        infos = [infos]
    first = infos[0]
    score = first["score"].pov(board.turn)
    pi = PosInfo(cp=score.score(mate_score=MATE_CP), mate=score.mate(),
                 pv=list(first.get("pv", [])))
    pi.best = pi.pv[0] if pi.pv else None
    if len(infos) > 1 and infos[1].get("pv"):
        pi.second = infos[1]["pv"][0]
        pi.second_cp = infos[1]["score"].pov(board.turn).score(mate_score=MATE_CP)
    return pi


async def analyse_lines(board: chess.Board, depth: int, multipv: int = 3) -> list[dict]:
    """Le migliori `multipv` linee, valutazioni dal punto di vista del bianco (per la scacchiera libera)."""
    n = min(multipv, board.legal_moves.count())

    async def fn(engine):
        return await engine.analyse(board, chess.engine.Limit(depth=depth, time=2.0), multipv=n)

    infos = await analysis_engine.run(fn)
    if isinstance(infos, dict):
        infos = [infos]
    out = []
    for info in infos:
        pv = list(info.get("pv", []))[:10]
        if not pv:
            continue
        sc = info["score"].white()
        out.append({"cp": sc.score(), "mate": sc.mate(), "pv_uci": [m.uci() for m in pv], "pv_san": _san_list(board, pv)})
    return out


async def find_threat(board: chess.Board, base_cp_mover: int) -> chess.Move | None:
    """Minaccia avversaria: cosa giocherebbe l'avversario se potesse muovere due volte (null move)."""
    if board.is_check():
        return None
    b = board.copy(stack=False)       # "null move" senza storia (così l'engine riceve solo la FEN)
    b.turn = not b.turn
    b.ep_square = None
    if _terminal(b) or not any(b.legal_moves):
        return None
    info = await analyse_position(b, config.THREAT_DEPTH, multipv=1, max_time=0.2)
    if info.best is None:
        return None
    # valutazione per il giocatore se l'avversario esegue la minaccia
    gain_for_opp = info.cp_value() - (-base_cp_mover)
    if gain_for_opp >= 150 and (b.is_capture(info.best) or b.gives_check(info.best) or (info.mate or 0) > 0):
        return info.best
    return None


def _white_cp(cp_mover: int, turn: chess.Color) -> int:
    return cp_mover if turn == chess.WHITE else -cp_mover


def _white_mate(mate_mover: int | None, turn: chess.Color) -> int | None:
    if mate_mover is None:
        return None
    return mate_mover if turn == chess.WHITE else -mate_mover


async def analyse_game(game_id: int, uci_moves: list[str], depth: int,
                       progress: Callable[[int, int], None] | None = None, start_fen: str | None = None) -> dict:
    """Analizza la partita e restituisce {'moves': [...], 'review': {...}} pronto per il DB."""
    board = chess.Board(start_fen) if start_fen else chess.Board()
    off = 0 if board.turn == chess.WHITE else 1  # ply % 2 == 0 ⇔ mossa del bianco
    boards = [board.copy()]
    moves: list[chess.Move] = []
    for u in uci_moves:
        mv = chess.Move.from_uci(u)
        board.push(mv)
        moves.append(mv)
        boards.append(board.copy())

    n = len(moves)
    total = n + 1
    infos: list[PosInfo] = []
    for i, b in enumerate(boards):
        infos.append(await analyse_position(b, depth, multipv=2, tag=f"review-{game_id}",
                                            max_time=config.ANALYSIS_MAX_TIME_S))
        if progress:
            progress(i + 1, total)

    eco, opening_name, book_plies = openings.identify(moves) if not start_fen else (None, None, 0)

    out_moves = []
    evals: list[MoveEval] = []
    move_acc: list[float] = []
    for i, mv in enumerate(moves):
        before, after = boards[i], boards[i + 1]
        pi, pa = infos[i], infos[i + 1]
        mover = before.turn
        cp_best = pi.cp_value()
        cp_after = -pa.cp_value()                  # pov di chi ha mosso
        win_before = win_percent(cp_best)
        win_after = win_percent(cp_after)
        me = MoveEval(
            ply=i, board_before=before, move=mv, best_move=pi.best,
            ep_best=expected_points(cp_best), ep_after=expected_points(cp_after),
            ep_second=expected_points(pi.second_cp) if pi.second_cp is not None else None,
            refutation_pv=pa.pv or [], is_book=i < book_plies,
            opp_prev_delta=evals[i - 1].delta if i > 0 else None,
        )
        cls, sac = classify(me)
        evals.append(me)
        acc = 100.0 if me.played_best else move_accuracy(win_before, win_after)
        move_acc.append(acc)

        threat = None
        if cls in cfg.THREAT_CLASSES:
            try:
                threat = await find_threat(before, cp_best)
            except Exception:
                log.exception("minaccia non calcolata")

        mate_after_mover = None
        if pa.terminal == "checkmate":
            mate_after_mover = None
        elif pa.mate is not None:
            mate_after_mover = -pa.mate
        ply_opening = None
        if cls == "book":
            hit = openings.lookup(after)
            ply_opening = hit[1] if hit else opening_name

        facts = build_facts(
            board_before=before, move=mv, cls=cls, best_move=pi.best, best_pv=pi.pv or [],
            refutation_pv=pa.pv or [], second_move=pi.second,
            mate_after_mover=mate_after_mover, mate_best_mover=pi.mate,
            threat=threat, sacrificed_pts=sac, sacrificed_piece=me.sac_piece, opening=ply_opening,
            eval_before=fmt_eval(_white_cp(cp_best, mover), _white_mate(pi.mate, mover)),
            eval_after=fmt_eval(_white_cp(cp_after, mover), _white_mate(mate_after_mover, mover)),
            ep_after=me.ep_after,
        )
        if pa.terminal == "checkmate":
            comment = mate_comment(facts.san)
        else:
            comment = render(facts)

        best_pv = pi.pv or []
        ref_pv = pa.pv or []
        out_moves.append({
            "ply": i + off,
            "eval_cp": _white_cp(cp_after, mover),
            "eval_mate": (0 if pa.terminal == "checkmate" else _white_mate(mate_after_mover, mover)),
            "best_uci": pi.best.uci() if pi.best else None,
            "best_san": facts.best_san,
            "best_pv_san": json.dumps(_san_list(before, best_pv[:10])),
            "best_pv_uci": json.dumps([m.uci() for m in best_pv[:10]]),
            "best_eval_cp": _white_cp(cp_best, mover),
            "best_eval_mate": _white_mate(pi.mate, mover),
            "second_eval_cp": _white_cp(pi.second_cp, mover) if pi.second_cp is not None else None,
            "refutation_pv_san": json.dumps(_san_list(after, ref_pv[:10])),
            "refutation_pv_uci": json.dumps([m.uci() for m in ref_pv[:10]]),
            "threat_san": facts.threat_san,
            "motifs_json": json.dumps(facts.to_dict(), ensure_ascii=False),
            "win_before": round(win_before, 2),
            "win_after": round(win_after, 2),
            "delta_ep": round(me.delta, 4),
            "accuracy": round(acc, 1),
            "classification": cls,
            "phase": phase_of(before),
            "comment": comment,
        })

    win_white = [win_percent(_white_cp(p.cp_value(), b.turn)) for p, b in zip(infos, boards)]
    acc_w, acc_b = game_accuracy(win_white, move_acc, first_black=bool(off))
    counts = {"white": {c: 0 for c in CLASSES}, "black": {c: 0 for c in CLASSES}}
    for m in out_moves:
        counts["white" if m["ply"] % 2 == 0 else "black"][m["classification"]] += 1
    key = sorted((m for m in out_moves if m["delta_ep"] >= cfg.GOOD_MAX or m["classification"] in ("brilliant", "great")),
                 key=lambda m: (m["classification"] in ("brilliant", "great"), m["delta_ep"]), reverse=True)[:5]
    review = {
        "accuracy_white": acc_w,
        "accuracy_black": acc_b,
        "rating_est_white": estimated_rating(acc_w, counts["white"]["blunder"]),
        "rating_est_black": estimated_rating(acc_b, counts["black"]["blunder"]),
        "counts_json": json.dumps(counts),
        "key_moments_json": json.dumps(sorted(m["ply"] for m in key)),
        "engine_version": analysis_engine.version,
        "depth": depth,
        "eco": eco,
        "opening_name": opening_name,
    }
    return {"moves": out_moves, "review": review}


def _san_list(board: chess.Board, moves: list[chess.Move]) -> list[str]:
    b = board.copy()
    out = []
    for m in moves:
        if m not in b.legal_moves:
            break
        out.append(b.san(m))
        b.push(m)
    return out
