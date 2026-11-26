"""Riassunto discorsivo della partita con l'LLM (su richiesta), verificato blocco per blocco.
I prompt sono in prompts.toml.

Ogni blocco del riassunto a template (com'è andata, ogni momento critico, consigli) viene riscritto con una
chiamata separata e passa lo stesso controllo dei commenti alle mosse (`humanize.check`): mosse, pezzi e
concetti devono comparire già nel testo a template. Se un blocco non passa, per quel blocco resta il template.
"""
from ..i18n import tr
from . import prompts, server
from ..explain.describe import annotate
from .humanize import _clean, check


async def rewrite(kind: str, template: str, cls: str | None = None) -> tuple[str | None, dict]:
    p = prompts.load()["summary"]
    hints = p["instructions"]
    messages = [{"role": "system", "content": p["system"]}]
    for ex in p.get("examples", []):
        messages += [{"role": "user", "content": p["user"].format(istruzione=hints[ex["kind"]], testo=ex["user"])},
                     {"role": "assistant", "content": ex["assistant"]}]
    messages.append({"role": "user", "content": p["user"].format(istruzione=hints[kind], testo=template)})
    raw = await server.chat(messages, max_tokens=380 if kind != "critical" else 240)
    text = _clean(raw)
    result = check(text, template, None, cls)
    if result["passed"]:
        return annotate(text), result
    result["rejected_text"] = text
    return None, result


async def summarize(tpl: dict, progress=None) -> tuple[dict, dict]:
    """tpl = template_summary(...). Restituisce (testo LLM per blocco, verifiche per blocco).
    I blocchi scartati hanno testo None: l'interfaccia mostra il template."""
    jobs = [("overview", None, tpl["overview"], None)]
    jobs += [("critical", i, c["text"], c.get("cls")) for i, c in enumerate(tpl.get("critical", []))]
    if tpl.get("advice"):
        jobs.append(("advice", None, " ".join(tpl["advice"]), None))
    out: dict = {"overview": None, "critical": [None] * len(tpl.get("critical", [])), "advice": None}
    checks: dict = {"overview": None, "critical": [None] * len(tpl.get("critical", [])), "advice": None}
    for n, (kind, idx, template, cls) in enumerate(jobs):
        try:
            text, chk = await rewrite(kind, template, cls)
        except Exception as e:  # noqa: BLE001
            text, chk = None, {"passed": False, "reason": tr("errore LLM: {error}", error=e), "extracted": [], "pieces": [],
                               "regex": "", "allowed": []}
        if idx is None:
            out[kind], checks[kind] = text, chk
        else:
            out[kind][idx], checks[kind][idx] = text, chk
        if progress:
            progress(n + 1, len(jobs))
    return out, checks
