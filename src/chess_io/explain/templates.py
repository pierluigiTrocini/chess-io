"""Template (italiano, inglese, spagnolo): dai fatti al commento argomentato."""
from dataclasses import fields

from ..i18n import join as _join, tr
from .facts import Facts

SYMBOL = {"brilliant": "!!", "great": "!", "inaccuracy": "?!", "mistake": "?", "blunder": "??", "miss": "?"}


def mate_in(n: int) -> str:
    return tr("il matto alla mossa successiva") if n == 1 else tr("il matto in {n} mosse", n=n)


def to_mate(n: int) -> str:
    """'al matto ...' (dopo "porta")."""
    return tr("al matto alla mossa successiva") if n == 1 else tr("al matto in {n} mosse", n=n)


def _why_best(f: Facts, with_line: bool = True) -> str:
    """Perché la mossa migliore è migliore (subordinata introdotta da virgola, può essere vuota)."""
    line = f" ({f.best_line})" if f.best_line and with_line else ""
    if f.mate_missed:
        return tr(", che porta {mate}", mate=to_mate(f.mate_missed)) + line
    if f.best_fork:
        return tr(", con una forchetta che attacca {targets}", targets=_join(f.best_fork)) + line
    if f.best_pin:
        return tr(", che inchioda {targets}", targets=_join(f.best_pin)) + line
    if f.best_discovered:
        return tr(", con un attacco di scoperta contro {targets}", targets=_join(f.best_discovered)) + line
    if f.threat_san and f.threat_ignored:
        return tr(", che para la minaccia {threat}", threat=f.threat_san) + line
    if f.missed_gain or f.best_gain:
        return tr(", che vince {gain}", gain=f.missed_gain or f.best_gain) + line
    return line


def _reasons(f: Facts) -> list[tuple[str, str]]:
    """(tipo, frase) che spiegano cosa succede dopo la mossa giocata, in ordine di priorità.
    Il tipo "loss" indica le frasi sul materiale perso (già dette dalla variante della confutazione),
    "positional" le note posizionali (in seconda persona: "indebolisci…")."""
    out = []
    if f.mate_against:
        kind = tr(" sulla traversa") if f.back_rank else ""
        line = f": {f.refutation_line}" if f.refutation_line else ""
        out.append(("mate", tr("concede {mate}", mate=mate_in(f.mate_against)) + kind + line))
        return out
    if f.mate_missed:
        out.append(("mate_missed", tr("lascia sfuggire {mate}", mate=mate_in(f.mate_missed))))
    if f.threat_san and f.threat_ignored:
        out.append(("threat", tr("non para la minaccia {threat}", threat=f.threat_san)))
    if f.ref_fork and f.refutation_first:
        out.append(("fork", tr("permette la forchetta {move}, che attacca {targets}",
                               move=f.refutation_first, targets=_join(f.ref_fork))))
    elif f.ref_pin and f.refutation_first:
        out.append(("pin", tr("permette {move}, che inchioda {targets}", move=f.refutation_first, targets=_join(f.ref_pin))))
    if f.loss:
        if f.first_capture and f.refutation_first:
            out.append(("loss", tr("dopo {move} perdi {loss} ({piece} cade)",
                                   move=f.refutation_first, loss=f.loss, piece=f.first_capture)))
        elif f.refutation_line:
            out.append(("loss", tr("perdi {loss}: {line}", loss=f.loss, line=f.refutation_line)))
        else:
            out.append(("loss", tr("perdi {loss}", loss=f.loss)))
    elif f.hanging and not out:
        out.append(("hanging", tr("lascia in presa {pieces}", pieces=_join(f.hanging[:2]))))
    elif f.missed_gain and not out:
        out.append(("missed_gain", tr("lascia sfuggire l'occasione di vincere {gain}", gain=f.missed_gain)))
    if not out and f.positional:
        out.append(("positional", f.positional[0]))
    return out


def _what_goes_wrong(f: Facts) -> list[str]:
    """Frasi che spiegano cosa succede dopo la mossa giocata, in ordine di priorità."""
    return [text for _kind, text in _reasons(f)]


def mate_comment(san: str) -> str:
    """Commento della mossa che dà scacco matto (non passa dall'LLM)."""
    return tr("{move} Scacco matto!", move=san)


def render(f: Facts) -> str:
    sym = SYMBOL.get(f.cls, "")
    head = f"{f.san}{sym}"
    best = f.best_san

    if f.cls == "book":
        return tr("Mossa di teoria{opening}.", opening=f" ({f.opening})" if f.opening else "")

    if f.cls == "brilliant":
        sac = tr("sacrifica {what}", what=f.sacrificed) if f.sacrificed else tr("sacrifica materiale")
        line = f": {f.best_line}" if f.best_line else ""
        tail = tr(" e porta {mate}", mate=to_mate(f.mate_for)) if f.mate_for \
            else tr(", ma l'attacco che ne segue compensa ampiamente")
        return f"{head} {sac}{tail}{line}."

    if f.cls == "great":
        alt = tr(" Le alternative, come {move}, peggiorano nettamente la posizione.", move=f.second_san) \
            if f.second_san else ""
        winning = (f.ep_after or 0.5) >= 0.65
        what = tr("l'unica mossa che mantiene il vantaggio") if winning else tr("l'unica mossa che mantiene l'equilibrio")
        if f.threat_san:
            what = tr("l'unica mossa che neutralizza la minaccia {threat}", threat=f.threat_san)
        elif f.played_fork:
            what = tr("una forchetta decisiva che attacca {targets}", targets=_join(f.played_fork))
        elif f.mate_for:
            what = tr("l'unica strada verso {mate}", mate=mate_in(f.mate_for))
        return tr("{move} è {what}.", move=head, what=what) + alt

    if f.cls in ("best", "excellent"):
        motif = ""
        if f.played_fork:
            motif = tr(" Forchetta: attacca {targets}.", targets=_join(f.played_fork))
        elif f.played_pin:
            motif = tr(" Inchioda {targets}.", targets=_join(f.played_pin))
        elif f.played_discovered:
            motif = tr(" Attacco di scoperta contro {targets}.", targets=_join(f.played_discovered))
        elif f.mate_for:
            motif = tr(" Porta {mate}.", mate=to_mate(f.mate_for))
        base = tr("Mossa migliore.") if f.cls == "best" else tr("Ottima mossa. Il motore preferiva di poco {move}.", move=best)
        return base + motif

    if f.cls == "good":
        extra = f" ({f.positional[0]})" if f.positional else ""
        return tr("Buona mossa{note}. Era leggermente meglio {move}{why}.", note=extra, move=best, why=_why_best(f))

    if f.cls == "miss":
        gain = _why_best(f) if (f.missed_gain or f.best_gain or f.mate_missed or f.best_fork) else ""
        return f"{head} " + tr("L'avversario aveva sbagliato, ma questa mossa non ne approfitta. Con {move}{gain}.",
                               move=best, gain=gain or tr(" avresti mantenuto il vantaggio"))

    reasons = _what_goes_wrong(f)
    if not reasons:
        reasons = [tr("peggiora la posizione (da {before} a {after})", before=f.eval_before, after=f.eval_after)] \
            if f.eval_before and f.eval_after else [tr("peggiora la posizione")]
    body = "; ".join(reasons)
    advice = tr(" Meglio {move}{why}.", move=best, why=_why_best(f)) if best else ""
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
        out.append(tr("La mossa migliore era {move}{why}.", move=f.best_san, why=_why_best(f, with_line=False)))
        if f.best_line:
            out.append(tr("Variante del motore: {line}.", line=f.best_line))
        if f.refutation_line:
            wrong = _reasons(f)
            why = tr(", e così {reason}", reason=wrong[0][1]) if wrong and wrong[0][0] not in ("loss", "positional") else ""
            out.append(tr("Dopo {move} il motore risponde {line}{why}.", move=f.san, line=f.refutation_line, why=why))
        if f.eval_before and f.eval_after:
            out.append(tr("Valutazione prima di {move}: {before}; dopo: {after}.",
                          move=f.san, before=f.eval_before, after=f.eval_after))
    elif f.cls in ("great", "brilliant") and f.best_line:
        out.append(tr("Variante del motore: {line}.", line=f.best_line))
    return " ".join(out)
