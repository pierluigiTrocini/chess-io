"""Template in italiano: dai fatti al commento argomentato."""
from dataclasses import fields

from .facts import Facts

SYMBOL = {"brilliant": "!!", "great": "!", "inaccuracy": "?!", "mistake": "?", "blunder": "??", "miss": "?"}


def _join(items: list[str]) -> str:
    items = list(dict.fromkeys(items))
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " e " + items[-1]


def mate_in(n: int) -> str:
    return "il matto alla mossa successiva" if n == 1 else f"il matto in {n} mosse"


def to_mate(n: int) -> str:
    """'al matto ...' (preposizione articolata)."""
    return "al" + mate_in(n)[2:]


def _why_best(f: Facts, with_line: bool = True) -> str:
    """Perché la mossa migliore è migliore (subordinata introdotta da virgola, può essere vuota)."""
    line = f" ({f.best_line})" if f.best_line and with_line else ""
    if f.mate_missed:
        return f", che porta {to_mate(f.mate_missed)}{line}"
    if f.best_fork:
        return f", con una forchetta che attacca {_join(f.best_fork)}{line}"
    if f.best_pin:
        return f", che inchioda {_join(f.best_pin)}{line}"
    if f.best_discovered:
        return f", con un attacco di scoperta contro {_join(f.best_discovered)}{line}"
    if f.threat_san and f.threat_ignored:
        return f", che para la minaccia {f.threat_san}{line}"
    if f.missed_gain or f.best_gain:
        return f", che vince {f.missed_gain or f.best_gain}{line}"
    return line


def _what_goes_wrong(f: Facts) -> list[str]:
    """Frasi che spiegano cosa succede dopo la mossa giocata, in ordine di priorità."""
    out = []
    if f.mate_against:
        kind = " sulla traversa" if f.back_rank else ""
        line = f": {f.refutation_line}" if f.refutation_line else ""
        out.append(f"concede {mate_in(f.mate_against)}{kind}{line}")
        return out
    if f.mate_missed:
        out.append(f"lascia sfuggire {mate_in(f.mate_missed)}")
    if f.threat_san and f.threat_ignored:
        out.append(f"non para la minaccia {f.threat_san}")
    if f.ref_fork and f.refutation_first:
        out.append(f"permette la forchetta {f.refutation_first}, che attacca {_join(f.ref_fork)}")
    elif f.ref_pin and f.refutation_first:
        out.append(f"permette {f.refutation_first}, che inchioda {_join(f.ref_pin)}")
    if f.loss:
        if f.first_capture and f.refutation_first:
            out.append(f"dopo {f.refutation_first} perdi {f.loss} ({f.first_capture} cade)")
        elif f.refutation_line:
            out.append(f"perdi {f.loss}: {f.refutation_line}")
        else:
            out.append(f"perdi {f.loss}")
    elif f.hanging and not out:
        out.append(f"lascia in presa {_join(f.hanging[:2])}")
    elif f.missed_gain and not out:
        out.append(f"lascia sfuggire l'occasione di vincere {f.missed_gain}")
    if not out and f.positional:
        out.append(f.positional[0])
    return out


def render(f: Facts) -> str:
    sym = SYMBOL.get(f.cls, "")
    head = f"{f.san}{sym}"
    best = f.best_san

    if f.cls == "book":
        return f"Mossa di teoria{f' ({f.opening})' if f.opening else ''}."

    if f.cls == "brilliant":
        sac = f"sacrifica {f.sacrificed}" if f.sacrificed else "sacrifica materiale"
        line = f": {f.best_line}" if f.best_line else ""
        tail = f" e porta {to_mate(f.mate_for)}" if f.mate_for else ", ma l'attacco che ne segue compensa ampiamente"
        return f"{head} {sac}{tail}{line}."

    if f.cls == "great":
        alt = f" Le alternative, come {f.second_san}, peggiorano nettamente la posizione." if f.second_san else ""
        winning = (f.ep_after or 0.5) >= 0.65
        what = "l'unica mossa che mantiene il vantaggio" if winning else "l'unica mossa che mantiene l'equilibrio"
        if f.threat_san:
            what = f"l'unica mossa che neutralizza la minaccia {f.threat_san}"
        elif f.played_fork:
            what = f"una forchetta decisiva che attacca {_join(f.played_fork)}"
        elif f.mate_for:
            what = f"l'unica strada verso {mate_in(f.mate_for)}"
        return f"{head} è {what}.{alt}"

    if f.cls in ("best", "excellent"):
        motif = ""
        if f.played_fork:
            motif = f" Forchetta: attacca {_join(f.played_fork)}."
        elif f.played_pin:
            motif = f" Inchioda {_join(f.played_pin)}."
        elif f.played_discovered:
            motif = f" Attacco di scoperta contro {_join(f.played_discovered)}."
        elif f.mate_for:
            motif = f" Porta {to_mate(f.mate_for)}."
        base = "Mossa migliore." if f.cls == "best" else f"Ottima mossa. Il motore preferiva di poco {best}."
        return base + motif

    if f.cls == "good":
        extra = f" ({f.positional[0]})" if f.positional else ""
        return f"Buona mossa{extra}. Era leggermente meglio {best}{_why_best(f)}."

    if f.cls == "miss":
        gain = _why_best(f) if (f.missed_gain or f.best_gain or f.mate_missed or f.best_fork) else ""
        return (f"{head} L'avversario aveva sbagliato, ma questa mossa non ne approfitta. "
                f"Con {best}{gain or ' avresti mantenuto il vantaggio'}.")

    reasons = _what_goes_wrong(f)
    if not reasons:
        reasons = [f"peggiora la posizione (da {f.eval_before} a {f.eval_after})"] if f.eval_before and f.eval_after \
            else ["peggiora la posizione"]
    body = "; ".join(reasons)
    advice = f" Meglio {best}{_why_best(f)}." if best else ""
    return f"{head} {body[0].upper()}{body[1:]}.{advice}"


ERROR_CLASSES = {"inaccuracy", "mistake", "blunder", "miss"}


def facts_from_dict(d: dict) -> Facts:
    names = {fl.name for fl in fields(Facts)}
    return Facts(**{"cls": "", "san": "", "mover": "", **{k: v for k, v in d.items() if k in names}})


def solution_notes(d: dict | None) -> str:
    """La soluzione di Stockfish in frasi brevi, solo con i fatti calcolati: è il materiale che l'LLM
    commenta insieme al commento a template (e su cui viene verificato)."""
    if not d or not d.get("cls") or not d.get("san"):
        return ""
    f = facts_from_dict(d)
    out = []
    if f.cls in ERROR_CLASSES and f.best_san and f.best_san != f.san:
        out.append(f"La mossa migliore era {f.best_san}{_why_best(f, with_line=False)}.")
        if f.best_line:
            out.append(f"Variante del motore: {f.best_line}.")
        if f.refutation_line:
            wrong = _what_goes_wrong(f)
            why = f", e così {wrong[0]}" if wrong and not wrong[0].startswith(("dopo", "perdi")) else ""
            out.append(f"Dopo {f.san} il motore risponde {f.refutation_line}{why}.")
        if f.eval_before and f.eval_after:
            out.append(f"Valutazione prima di {f.san}: {f.eval_before}; dopo: {f.eval_after}.")
    elif f.cls in ("great", "brilliant") and f.best_line:
        out.append(f"Variante del motore: {f.best_line}.")
    return " ".join(out)
