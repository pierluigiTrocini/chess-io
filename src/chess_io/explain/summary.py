"""Riassunto della partita: fatti verificabili → testo a template (com'è andata, momenti critici, consigli).

Il punto di vista è quello del giocatore (`player_color`), a cui ci si rivolge con il tu, come nei commenti.
I testi sono nella lingua corrente (`i18n`): le tabelle qui sotto sono in italiano e passano da `tr()`.
"""
import json

from ..i18n import tr
from .templates import _why_best, facts_from_dict

CLASS_IT = {
    "brilliant": "mossa brillante", "great": "ottima mossa", "best": "mossa migliore", "excellent": "ottima",
    "good": "buona", "book": "teoria", "inaccuracy": "imprecisione", "mistake": "errore",
    "blunder": "grave errore", "miss": "occasione persa",
}
PHASE_IT = {"opening": "l'apertura", "middlegame": "il mediogioco", "endgame": "il finale"}
PHASE_TIP = {
    "opening": "ripassa le prime mosse delle tue aperture e punta su sviluppo, centro e arrocco",
    "middlegame": "prima di ogni mossa controlla catture, scacchi e minacce di entrambi",
    "endgame": "nei finali attiva il re e calcola fino in fondo le spinte di pedone",
}
ERRORS = ("inaccuracy", "mistake", "blunder", "miss")
CRITICAL_CLASSES = {"brilliant", "great", "inaccuracy", "mistake", "blunder", "miss"}
DECISIVE = 70.0   # Win% oltre cui un lato è "in vantaggio netto"
TERMINATION_IT = {
    "checkmate": "scacco matto", "stalemate": "stallo", "insufficient": "materiale insufficiente",
    "fifty": "regola delle 50 mosse", "repetition": "ripetizione di posizione", "resign": "abbandono",
    "timeout": "tempo scaduto", "agreement": "patta concordata", "abandoned": "partita interrotta",
    "unterminated": "non terminata",
}


def class_name(cls: str) -> str:
    """Nome della classe in minuscolo ("grave errore", "blunder", "error grave")."""
    return tr(CLASS_IT[cls]) if cls in CLASS_IT else cls


def termination_text(code: str | None) -> str | None:
    """Come è finita la partita, a parole ("abbandono", "resignation", "abandono")."""
    return tr(TERMINATION_IT[code]) if code in TERMINATION_IT else None


def _num(ply: int, san: str) -> str:
    n = ply // 2 + 1
    return f"{n}. {san}" if ply % 2 == 0 else f"{n}... {san}"


def _fmt_clock(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def _white_win(m: dict) -> float | None:
    w = m.get("win_after")
    if w is None:
        return None
    return w if m["ply"] % 2 == 0 else 100 - w


def summary_facts(game: dict, moves: list[dict], review: dict, termination: str | None = None) -> dict:
    """Raccoglie i fatti su cui si basano sia il template sia la verifica del testo LLM."""
    me = game.get("player_color") or "white"
    opp = "black" if me == "white" else "white"
    is_me = (lambda ply: (ply % 2 == 0) == (me == "white"))
    counts = review.get("counts") or {}
    acc = {"white": review.get("accuracy_white"), "black": review.get("accuracy_black")}

    for m in moves:
        if isinstance(m.get("motifs_json"), str):
            m["motifs_json"] = json.loads(m["motifs_json"])

    # andamento: chi era avanti e quando è cambiato
    swings, leader = [], None
    for m in moves:
        w = _white_win(m)
        if w is None:
            continue
        now = "white" if w >= DECISIVE else "black" if w <= 100 - DECISIVE else leader if leader and abs(w - 50) > 10 else None
        if now != leader:
            if now is not None:
                swings.append({"ply": m["ply"], "san": m["san"], "leader": now, "by_me": is_me(m["ply"])})
            leader = now

    # fasi: accuratezza ed errori del giocatore
    phases: dict[str, dict] = {}
    for m in moves:
        if not is_me(m["ply"]) or m.get("classification") in (None, "book"):
            continue
        p = phases.setdefault(m.get("phase") or "middlegame", {"moves": 0, "acc_sum": 0.0, "errors": 0})
        p["moves"] += 1
        p["acc_sum"] += m.get("accuracy") or 0
        p["errors"] += m.get("classification") in ERRORS
    for p in phases.values():
        p["accuracy"] = round(p.pop("acc_sum") / p["moves"], 1) if p["moves"] else None

    # schemi ricorrenti negli errori del giocatore
    my_errors = [m for m in moves if is_me(m["ply"]) and m.get("classification") in ERRORS]
    pattern = {"hanging": [], "threat": [], "fork": [], "mate_against": [], "mate_missed": [], "miss": [], "other": []}
    for m in my_errors:
        f = m.get("motifs_json") or {}
        tag = _num(m["ply"], m["san"])
        if f.get("mate_against"):
            pattern["mate_against"].append(tag)
        elif f.get("mate_missed"):
            pattern["mate_missed"].append(tag)
        elif m["classification"] == "miss":
            pattern["miss"].append(tag)
        elif f.get("threat_ignored") and f.get("threat_san"):
            pattern["threat"].append(tag)
        elif f.get("ref_fork"):
            pattern["fork"].append(tag)
        elif f.get("loss") and f.get("first_capture"):
            pattern["hanging"].append(tag)
        elif m["classification"] in ("mistake", "blunder"):
            pattern["other"].append(tag)

    # soluzione di Stockfish per ogni errore, citata negli esempi dei consigli
    best = {}
    for m in my_errors:
        b = _better(m)
        if b:
            best[_num(m["ply"], m["san"])] = b

    # tempo: errori con l'orologio quasi a zero
    time_trouble = []
    base = (game.get("time_initial_s") or 0) * 1000
    if base:
        limit = max(10_000, base // 10)
        time_trouble = [_num(m["ply"], m["san"]) for m in my_errors
                        if m.get("clock_ms") is not None and m["clock_ms"] < limit]

    key = set(review.get("key_moments") or [])
    critical = []
    by_ply = {m["ply"]: m for m in moves}
    for ply in sorted(key):
        m = by_ply.get(ply)
        if not m or not m.get("comment") or m.get("classification") not in CRITICAL_CLASSES:
            continue
        critical.append({"ply": ply, "san": m["san"], "cls": m["classification"], "mine": is_me(ply),
                         "comment": m["comment"], "label": _num(ply, m["san"])})
    # al massimo 4: prima i più pesanti
    if len(critical) > 4:
        weight = {c["ply"]: (by_ply[c["ply"]].get("delta_ep") or 0) for c in critical}
        critical = sorted(sorted(critical, key=lambda c: -weight[c["ply"]])[:4], key=lambda c: c["ply"])

    return {
        "me": me, "opp": opp,
        "opponent": game.get(f"{opp}_name") or (tr("il nero") if opp == "black" else tr("il bianco")),
        "opponent_elo": game.get(f"{opp}_elo"),
        "opening": game.get("opening_name"), "eco": game.get("eco"),
        "result": game.get("result"), "termination": termination, "termination_code": game.get("termination"),
        "accuracy_me": acc[me], "accuracy_opp": acc[opp],
        "counts_me": counts.get(me, {}), "counts_opp": counts.get(opp, {}),
        "moves": (len(moves) + 1) // 2,
        "swings": swings[-4:], "phases": phases, "patterns": pattern, "best": best, "time_trouble": time_trouble,
        "time_limit": _fmt_clock(max(10_000, base // 10)) if base else None,
        "critical": critical,
    }


def _outcome(f: dict) -> str:
    """'draw' | 'win' | 'loss' | 'unfinished', dal punto di vista del giocatore."""
    r = f["result"]
    if r == "1/2-1/2":
        return "draw"
    if r in ("1-0", "0-1"):
        return "win" if (r == "1-0") == (f["me"] == "white") else "loss"
    return "unfinished"


OUTCOME_IT = {"draw": "patta", "win": "vittoria", "loss": "sconfitta"}


def _ending(f: dict) -> str:
    """" per abbandono": come è finita, se è un dato utile."""
    if f["termination"] and f.get("termination_code") != "unterminated":
        return tr(" per {how}", how=f["termination"])
    return ""


def _overview(f: dict) -> str:
    color = tr("il bianco") if f["me"] == "white" else tr("il nero")
    opp = f["opponent"] + (f" ({f['opponent_elo']})" if f["opponent_elo"] else "")
    parts = [tr("Hai giocato con {color} contro {opponent}", color=color, opponent=opp)
             + (tr(", nella {opening}", opening=f["opening"]) if f["opening"] else "") + "."]
    if f["accuracy_me"] is not None and f["accuracy_opp"] is not None:
        parts.append(tr("La tua accuratezza è stata del {me:.0f}%, quella dell'avversario del {opp:.0f}%.",
                        me=f["accuracy_me"], opp=f["accuracy_opp"]))
    sw = f["swings"]
    if not sw:
        parts.append(tr("La partita è rimasta in equilibrio per quasi tutto il tempo."))
    else:
        first, last = sw[0], sw[-1]
        who = lambda s: tr("tu") if s["leader"] == f["me"] else tr("l'avversario")  # noqa: E731
        move_no = lambda s: s["ply"] // 2 + 1  # noqa: E731
        if len(sw) == 1:
            parts.append(tr("L'equilibrio si è rotto alla mossa {n} ({move}): da lì in avanti è stato in vantaggio {who}.",
                            n=move_no(first), move=first["san"], who=who(first)))
        else:
            parts.append(tr("Alla mossa {n} ({move}) è passato in vantaggio {who}, ma la partita è cambiata ancora: "
                            "dalla mossa {n2} ({move2}) è stato in vantaggio {who2}.",
                            n=move_no(first), move=first["san"], who=who(first),
                            n2=move_no(last), move2=last["san"], who2=who(last)))
    out = _outcome(f)
    if out != "unfinished":
        parts.append(tr("Risultato: {outcome}{ending}, dopo {moves} mosse.",
                        outcome=tr(OUTCOME_IT[out]), ending=_ending(f), moves=f["moves"]))
    else:
        parts.append(tr("La partita non è terminata (dopo {moves} mosse).", moves=f["moves"]))
    return " ".join(parts)


def _critical_text(c: dict) -> str:
    who = tr("mossa tua") if c["mine"] else tr("mossa dell'avversario")
    return f"{c['label']} ({class_name(c['cls'])}, {who}). {c['comment']}"


def _better(m: dict) -> str | None:
    """"Be3, che vince un pedone": la soluzione di Stockfish per un errore, dai fatti della mossa."""
    d = m.get("motifs_json") or {}
    best = d.get("best_san")
    if not best or best == m.get("san"):
        return None
    try:
        why = _why_best(facts_from_dict({"cls": m.get("classification") or "", "san": m.get("san") or "", **d}),
                        with_line=False)
    except Exception:  # noqa: BLE001  (fatti incompleti: basta la mossa)
        why = ""
    return f"{best}{why}"


def _with_best(tags: list[str], best: dict | None) -> list[str]:
    """Etichette con la mossa migliore: "14. Bf4, dove era meglio Be3, che vince un pedone".
    Il motivo si aggiunge solo al primo esempio, per non allungare troppo."""
    out = []
    for i, t in enumerate(tags):
        b = (best or {}).get(t)
        if b and i > 0:
            b = b.split(",")[0]
        out.append(tr("{move}, dove era meglio {best}", move=t, best=b) if b else t)
    return out


def _examples(tags: list[str], best: dict | None = None) -> str:
    if not tags:
        return ""
    items = _with_best(tags[:2], best)
    sep = "; " if any("," in i for i in items) else ", "
    return tr(" (per esempio {items})", items=sep.join(items))


def _times(n: int) -> str:
    return tr("Una volta") if n == 1 else tr("{n} volte", n=n)


def _advice_ranked(f: dict) -> list[tuple[int, str, str]]:
    """Consigli ordinati: (priorità, testo, lezione in poche parole per il riassunto breve)."""
    out: list[tuple[int, str, str]] = []
    p = f["patterns"]
    best = f.get("best")
    if p["mate_against"]:
        out.append((100, tr("Hai concesso il matto{examples}: quando il tuo re è esposto, prima di ogni mossa guarda gli "
                            "scacchi che può dare l'avversario.", examples=_examples(p["mate_against"], best)),
                    tr("proteggi il re dagli scacchi")))
    if p["hanging"]:
        n = len(p["hanging"])
        when = tr("Una volta") if n == 1 else tr("In {n} occasioni", n=n)
        out.append((80 + n, tr("{when} hai perso materiale per un pezzo rimasto senza difesa{examples}: prima di muovere "
                               "controlla quali pezzi restano indifesi.", when=when, examples=_examples(p["hanging"], best)),
                    tr("controlla i pezzi indifesi")))
    if p["threat"]:
        n = len(p["threat"])
        out.append((70 + n, tr("{when} non hai parato la minaccia dell'avversario{examples}: dopo ogni sua mossa chiediti "
                               "che cosa vuole fare.", when=_times(n), examples=_examples(p["threat"], best)),
                    tr("chiediti cosa minaccia l'avversario")))
    if p["fork"]:
        n = len(p["fork"])
        what = tr("Hai concesso una forchetta") if n == 1 else tr("Hai concesso {n} forchette", n=n)
        out.append((75 + n, tr("{what}{examples}: prima di muovere guarda da quali case un pezzo avversario potrebbe "
                               "attaccarne due dei tuoi insieme.", what=what, examples=_examples(p["fork"], best)),
                    tr("attento alle forchette")))
    if p["other"]:
        what = tr("L’errore più pesante è stato") if len(p["other"]) == 1 else tr("Gli errori più pesanti sono stati")
        out.append((40, tr("{what} {moves}: prima di muovere confronta almeno due mosse candidate e chiediti qual è la "
                           "risposta più forte dell'avversario.", what=what, moves="; ".join(_with_best(p["other"][:2], best))),
                    tr("confronta più mosse candidate")))
    if p["mate_missed"]:
        out.append((65, tr("Ti è sfuggito un matto{examples}: quando il re avversario è esposto, prova sempre prima gli "
                           "scacchi.", examples=_examples(p["mate_missed"], best)),
                    tr("cerca gli scacchi al re avversario")))
    if p["miss"]:
        n = len(p["miss"])
        out.append((60 + n, tr("{when} non hai approfittato di un errore dell'avversario{examples}: quando l'avversario "
                               "sbaglia, cerca catture e scacchi.", when=_times(n), examples=_examples(p["miss"], best)),
                    tr("punisci gli errori dell'avversario")))
    if f["time_trouble"]:
        n = len(f["time_trouble"])
        what = tr("Uno dei tuoi errori è arrivato") if n == 1 else tr("{n} dei tuoi errori sono arrivati", n=n)
        out.append((55 + n, tr("{what} con meno di {limit} sull'orologio{examples}: dosa meglio il tempo nelle fasi "
                               "tranquille.", what=what, limit=f["time_limit"], examples=_examples(f["time_trouble"], best)),
                    tr("gestisci meglio il tempo")))
    phases = [(k, v) for k, v in f["phases"].items() if v["moves"] >= 4 and v["accuracy"] is not None]
    if len(phases) >= 2:
        k, v = min(phases, key=lambda kv: kv[1]["accuracy"])
        if v["accuracy"] < 85 and v["errors"]:
            out.append((50, tr("La fase più difficile è stata {phase} (accuratezza {acc:.0f}%): {tip}.",
                               phase=tr(PHASE_IT[k]), acc=v["accuracy"], tip=tr(PHASE_TIP[k])),
                        tr("cura {phase}", phase=tr(PHASE_IT[k]))))
    if not out:
        cm = f["counts_me"]
        if not any(cm.get(c) for c in ERRORS):
            out.append((10, tr("Partita molto pulita, senza errori: continua a giocare così e prova ad alzare il livello "
                               "degli avversari."), tr("continua così")))
        else:
            out.append((10, tr("Hai commesso solo piccole imprecisioni ({n}): rivedi i momenti critici e confronta la tua "
                               "mossa con quella del motore.", n=cm.get("inaccuracy", 0)),
                        tr("rivedi le piccole imprecisioni")))
    return sorted(out, key=lambda x: -x[0])


def _advice(f: dict) -> list[str]:
    return [t for _, t, _ in _advice_ranked(f)[:3]]


def _brief(f: dict) -> str:
    """Il riassunto del riassunto, in tre righe: esito e accuratezza, momento decisivo, lezione principale."""
    out = _outcome(f)
    if out != "unfinished":
        first = tr("{outcome}{ending} in {moves} mosse", outcome=tr(OUTCOME_IT[out]).capitalize(), ending=_ending(f),
                   moves=f["moves"])
    else:
        first = tr("Non terminata dopo {moves} mosse", moves=f["moves"])
    if f["accuracy_me"] is not None and f["accuracy_opp"] is not None:
        first += tr(" · accuratezza {me:.0f}% contro {opp:.0f}%", me=f["accuracy_me"], opp=f["accuracy_opp"])
    lines = [first + "."]
    mine = [c for c in f["critical"] if c["mine"] and c["cls"] in ERRORS]
    if mine:
        worst = next((c for cls in ("blunder", "miss", "mistake", "inaccuracy") for c in mine if c["cls"] == cls))
        lines.append(tr("Momento chiave: {move} ({cls}).", move=worst["label"], cls=class_name(worst["cls"])))
    elif f["swings"]:
        s = f["swings"][-1]
        lines.append(tr("Svolta: {move}, poi in vantaggio {who}.", move=_num(s["ply"], s["san"]),
                        who=tr("tu") if s["leader"] == f["me"] else tr("l’avversario")))
    else:
        lines.append(tr("Partita in equilibrio, senza svolte nette."))
    ranked = _advice_ranked(f)
    if ranked:
        lines.append(tr("Da ricordare: {lesson}.", lesson=ranked[0][2]))
    return "\n".join(lines)


def template_summary(f: dict) -> dict:
    return {
        "overview": _overview(f),
        "critical": [{"ply": c["ply"], "cls": c["cls"], "mine": c["mine"], "text": _critical_text(c)} for c in f["critical"]],
        "advice": _advice(f),
        "brief": _brief(f),
    }


def summary_from(game: dict, moves: list[dict], review: dict) -> dict:
    """Riassunto a template da partita, mosse analizzate e revisione (counts / key_moments già decodificati)."""
    return template_summary(summary_facts(game, moves, review, termination_text(game.get("termination"))))
