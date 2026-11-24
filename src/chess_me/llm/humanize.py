"""Riformulazione "umana" dei commenti con un LLM piccolo, con controllo anti-allucinazioni.
I prompt (system, esempi, messaggio utente) sono in prompts.toml."""
import re

from ..explain.describe import SAN_RE, SAN_REGEX, annotate  # noqa: F401  (SAN_REGEX nei risultati di check)
from ..explain.templates import solution_notes
from . import prompts, server
PIECE_WORDS = ["pedone", "pedoni", "cavallo", "cavalli", "alfiere", "alfieri", "torre", "torri", "donna", "regina", "qualità"]
PIECE_STEM = {"pedoni": "pedone", "cavalli": "cavallo", "alfieri": "alfiere", "torri": "torre", "regina": "donna"}

# Concetti che l'LLM può usare solo se compaiono già nel commento (radice → regex)
CONCEPTS = {
    "vantaggio": r"vantagg", "matto": r"\bmatt[oi]\b", "perdere materiale": r"\bperd", "vincere materiale": r"\bvinc",
    "sacrificio": r"sacrific", "minaccia": r"minacc", "forchetta": r"forchett", "inchiodatura": r"inchiod",
    "scoperta": r"scopert", "pezzo in presa": r"in presa|indifes|senza difesa", "patta": r"\bpatt",
    "teoria": r"teoria", "occasione": r"occasion", "unica mossa": r"\bunic[ao]\b",
}
# Termini delle classi: il testo non deve usare quello di un'altra classe
CLASS_TERMS = {
    "brilliant": r"brillant", "great": r"ottima mossa|mossa giusta|unic", "inaccuracy": r"imprecis",
    "mistake": r"(?<!grave )\berrore\b", "blunder": r"grave errore|errore grave", "miss": r"occasion",
}

# limite di lunghezza del testo LLM rispetto al testo di riferimento (commento + soluzione)
MAX_LEN, LEN_FACTOR = 420, 3.0

ELIGIBLE = {"brilliant", "great", "inaccuracy", "mistake", "blunder", "miss"}
CLASS_IT = {
    "brilliant": "mossa brillante", "great": "ottima mossa", "inaccuracy": "imprecisione",
    "mistake": "errore", "blunder": "grave errore", "miss": "occasione persa",
}

def _norm_san(s: str) -> str:
    return s.rstrip("+#!?")


def allowed_sans(template: str, facts: dict | None) -> set[str]:
    out = {_norm_san(m) for m in SAN_RE.findall(template)}
    if facts:
        for k in ("san", "best_san", "second_san", "threat_san", "refutation_first", "best_line", "refutation_line"):
            v = facts.get(k)
            if v:
                out |= {_norm_san(m) for m in SAN_RE.findall(v)}
    return out


def check(text: str, template: str, facts: dict | None, cls: str | None = None) -> dict:
    """Verifica che il testo dell'LLM citi solo mosse e pezzi presenti nei fatti."""
    allowed = allowed_sans(template, facts)
    extracted = []
    for m in SAN_RE.findall(text):
        extracted.append({"san": m, "ok": _norm_san(m) in allowed})
    lower_t, lower_tpl = text.lower(), template.lower()
    pieces = []
    for w in PIECE_WORDS:
        if re.search(rf"\b{w}\b", lower_t):
            stem = PIECE_STEM.get(w, w)
            ok = bool(re.search(rf"\b({stem}|{w})", lower_tpl)) or (stem == "donna" and "regina" in lower_tpl)
            pieces.append({"word": w, "ok": ok})
    concepts = []
    for name, rx in CONCEPTS.items():
        if re.search(rx, lower_t):
            concepts.append({"word": name, "ok": bool(re.search(rx, lower_tpl))})
    wrong_term = None
    if cls:
        for other, rx in CLASS_TERMS.items():
            if other != cls and re.search(rx, lower_t) and not re.search(rx, lower_tpl) \
                    and not (cls == "blunder" and other == "mistake") and not (cls == "great" and other == "brilliant"):
                wrong_term = other
                break
    reason = None
    if not text.strip():
        reason = "risposta vuota"
    elif any(not e["ok"] for e in extracted):
        reason = "cita mosse non presenti nei fatti"
    elif any(not p["ok"] for p in pieces):
        reason = "nomina pezzi non presenti nel commento"
    elif any(not c["ok"] for c in concepts):
        reason = "introduce concetti non presenti: " + ", ".join(c["word"] for c in concepts if not c["ok"])
    elif wrong_term:
        reason = f"usa il termine di un'altra classe ({wrong_term})"
    elif len(text) > max(MAX_LEN, LEN_FACTOR * len(template)):
        reason = "testo troppo lungo"
    elif len(text) < 15:
        reason = "testo troppo corto"
    elif not SAN_RE.search(text) and SAN_RE.search(template):
        reason = "non cita nessuna mossa"
    return {
        "regex": SAN_REGEX,
        "allowed": sorted(allowed),
        "extracted": extracted,
        "pieces": pieces,
        "concepts": concepts,
        "passed": reason is None,
        "reason": reason,
        "model": server.MODEL_NAME,
    }


def _clean(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = text.replace("**", "").strip().strip('"«»“”').strip()
    return re.sub(r"\s+", " ", text)


def user_message(p: dict, classe: str, commento: str, soluzione: str) -> str:
    """Messaggio utente: la riga della soluzione c'è solo se ci sono dati del motore."""
    tpl = p["user"] if soluzione else p.get("user_no_solution", p["user"])
    return tpl.format(classe=classe, commento=commento, soluzione=soluzione)


def build_messages(template: str, cls: str, facts: dict | None) -> tuple[list[dict], str]:
    """Conversazione inviata al modello e testo di riferimento per il controllo (commento + soluzione)."""
    p = prompts.load()["humanize"]
    messages = [{"role": "system", "content": p["system"]}]
    for ex in p.get("examples", []):
        # formato vecchio (user già scritto per intero) ancora accettato, per le copie in DATA_DIR
        user = ex["user"] if "user" in ex else user_message(p, ex["classe"], ex["commento"], ex.get("soluzione", ""))
        messages += [{"role": "user", "content": user}, {"role": "assistant", "content": ex["assistant"]}]
    solution = solution_notes(facts)
    classe = CLASS_IT.get(cls, cls).capitalize()
    messages.append({"role": "user", "content": user_message(p, classe, template, solution)})
    # anche il nome della classe è un fatto: "occasione persa" ammette la parola "occasione"
    reference = f"{classe}. {template} {solution}".strip()
    return messages, reference


async def humanize(template: str, cls: str, facts: dict | None) -> tuple[str | None, dict]:
    messages, reference = build_messages(template, cls, facts)
    raw = await server.chat(messages, max_tokens=240)
    text = _clean(raw)
    result = check(text, reference, facts, cls)
    if result["passed"]:
        return annotate(text), result
    result["rejected_text"] = text
    return None, result
