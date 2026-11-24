from chess_me.llm.humanize import _clean, check

TPL = "Bf4?? Dopo exf4 perdi un alfiere (l'alfiere in f4 cade). Meglio Be3 (12. Be3 Nf6 13. O-O)."
FACTS = {"san": "Bf4", "best_san": "Be3", "refutation_first": "exf4", "best_line": "12. Be3 Nf6 13. O-O"}


def test_faithful_rewrite_passes():
    r = check("Bf4 è un grave errore: con exf4 l'avversario ti porta via l'alfiere. Meglio Be3.", TPL, FACTS)
    assert r["passed"], r
    assert {e["san"] for e in r["extracted"]} == {"Bf4", "exf4", "Be3"}


def test_invented_move_is_rejected():
    r = check("Bf4 è un errore: dopo exf4 e poi Qh5 perdi tutto. Meglio Be3.", TPL, FACTS)
    assert not r["passed"]
    assert r["reason"] == "cita mosse non presenti nei fatti"
    assert any(e["san"] == "Qh5" and not e["ok"] for e in r["extracted"])


def test_invented_piece_is_rejected():
    r = check("Bf4 perde la donna dopo exf4. Meglio Be3.", TPL, FACTS)
    assert not r["passed"]
    assert r["reason"] == "nomina pezzi non presenti nel commento"


def test_too_long_is_rejected():
    r = check("Bf4 " + "molto " * 200, TPL, FACTS)
    assert not r["passed"]


def test_clean_strips_think_and_quotes():
    assert _clean('<think>\n\n</think>\n"Ottima mossa, Rd1!"') == "Ottima mossa, Rd1!"


def test_invented_concept_is_rejected():
    tpl = "Nf6?! Peggiora la posizione (da +1.3 a +2.1). Meglio Qf6 (6...Qf6 7. Qb3)."
    r = check("Nf6 è un'imprecisione: peggiora la posizione. Meglio Qf6, che mantiene il vantaggio.", tpl, None, "inaccuracy")
    assert not r["passed"] and "vantaggio" in r["reason"]


def test_wrong_class_term_is_rejected():
    tpl = "Nf6?! Peggiora la posizione (da +1.3 a +2.1). Meglio Qf6."
    r = check("Nf6 è un errore: peggiora la posizione. Meglio Qf6.", tpl, None, "inaccuracy")
    assert not r["passed"] and "classe" in r["reason"]
    ok = check("Nf6 è un'imprecisione: la posizione peggiora. Meglio Qf6.", tpl, None, "inaccuracy")
    assert ok["passed"], ok


def test_summary_rewrite_keeps_only_verified_blocks(monkeypatch):
    import asyncio
    from chess_me.llm import server, summarize

    tpl = {
        "overview": "Hai giocato con il bianco contro rival. L'equilibrio si è rotto alla mossa 3 (Bf4).",
        "critical": [{"ply": 4, "cls": "blunder", "mine": True,
                      "text": "3. Bf4 (grave errore, mossa tua). Bf4?? Dopo exf4 perdi un alfiere. Meglio Be3."}],
        "advice": ["Prima di muovere controlla quali pezzi restano indifesi."],
    }
    replies = iter([
        "Contro rival, con il bianco, la partita è girata alla mossa 3 con Bf4.",          # ok
        "Con Bf4 hai commesso un grave errore: dopo exf4 e Qh5 perdi la donna.",          # mossa e pezzo inventati
        "Ricordati sempre di controllare quali pezzi restano indifesi prima di muovere.",  # ok
    ])

    async def fake_chat(messages, max_tokens=160, temperature=0.3):
        return next(replies)
    monkeypatch.setattr(server, "chat", fake_chat)
    text, checks = asyncio.run(summarize.summarize(tpl))
    assert text["overview"] and text["advice"]
    assert text["critical"] == [None] and not checks["critical"][0]["passed"]
    assert checks["critical"][0]["rejected_text"].startswith("Con Bf4")


def test_prompts_file_override(monkeypatch, tmp_path):
    from chess_me import config
    from chess_me.llm import prompts

    assert prompts.load()["humanize"]["system"].startswith("Sei un istruttore")
    (tmp_path / "prompts.toml").write_text('[humanize]\nsystem = "prova"\nuser = "{classe}: {commento}"\n')
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    assert prompts.path() == tmp_path / "prompts.toml"
    assert prompts.load()["humanize"]["system"] == "prova"


def test_solution_allows_motif_and_text_is_annotated(monkeypatch):
    import asyncio
    from chess_me.llm import humanize, server

    facts = {"cls": "mistake", "san": "Bf4", "mover": "white", "best_san": "Be3", "best_line": "12. Be3 Nf6",
             "best_fork": ["la torre", "il re"], "refutation_line": "12...exf4", "refutation_first": "exf4"}
    tpl = "Bf4? Peggiora la posizione. Meglio Be3."
    _, reference = humanize.build_messages(tpl, "mistake", facts)
    assert "forchetta" in reference
    reply = "Bf4 è un errore. Con Be3 avresti avuto una forchetta sulla torre, e dopo Nf6 la posizione era migliore."
    assert not check(reply, tpl, facts, "mistake")["passed"]   # senza soluzione la forchetta è inventata

    async def fake_chat(messages, max_tokens=160, temperature=0.3):
        assert "Soluzione del motore:" in messages[-1]["content"]
        return reply
    monkeypatch.setattr(server, "chat", fake_chat)
    text, chk = asyncio.run(humanize.humanize(tpl, "mistake", facts))
    assert chk["passed"], chk
    assert text.startswith("L'alfiere in f4 (Bf4) è un errore") and "l'alfiere in e3 (Be3)" in text
