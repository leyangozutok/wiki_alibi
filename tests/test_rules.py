"""Referee rules, scoring and the behavior rules of PDF section 2.4."""
import agents
from agents import ask_witness, DONT_KNOW, witness_text
from referee import (validate_case, score_game, false_clue_id, clean_text, leaks_title, redact_title,
                     MAX_QUESTIONS, MAX_INPUT_CHARS, make_log)
from storage import load_cases

RECS = load_cases()
C0 = RECS[0].case


def test_scoring_free_allowance_and_penalties():
    r = false_clue_id(C0)
    assert score_game(C0, r, 3, 3)["score"] == 100                   # 3 searches + 3 questions are free
    assert score_game(C0, r, 4, 3)["score"] == 95                    # 4th search: -5
    assert score_game(C0, r, 3, 4)["score"] == 95                    # 4th question: -5
    assert score_game(C0, r, 6, 5)["score"] == 100 - 15 - 10         # -5 each extra
    assert score_game(C0, r, 200, 200)["score"] == 0                 # minimum 0
    assert score_game(C0, 5 if r != 5 else 4, 0, 0)["score"] == 0    # wrong accusation


def test_confidence_bet_for_every_level():
    r = false_clue_id(C0)
    wrong = 5 if r != 5 else 4
    assert [score_game(C0, r, 0, 0, c)["xp"] for c in ("low", "medium", "high")] == [100, 115, 130]
    assert [score_game(C0, wrong, 0, 0, c)["xp"] for c in ("low", "medium", "high")] == [0, -10, -25]


def test_fr3_each_check_fails_when_it_should():
    r = RECS[0]
    def broken(edit):
        c = r.case.model_copy(deep=True); edit(c); return validate_case(c, r.article)
    assert any("FR1" in e for e in broken(lambda c: c.clues.pop()))                   # 4 clues
    assert any("FR3a" in e for e in broken(lambda c: [setattr(k, "is_false", False) for k in c.clues]))
    assert any("FR3b" in e for e in broken(lambda c: setattr(c.clues[0], "text", "Curie was born in 1867.")))
    assert any("FR3c" in e for e in broken(lambda c: setattr(c.clues[0], "text", "Born in 1999.")))
    assert any("FR3d" in e for e in broken(lambda c: setattr(c, "original_sentence", "Not in the article.")))
    assert any("FR3d" in e for e in broken(lambda c: setattr(c, "false_value", "1903")))


def test_title_never_reaches_the_player():
    assert leaks_title("It was Marie Curie.", "Marie Curie") and leaks_title("Curie again", "Marie Curie")
    assert "Curie" not in redact_title("Pierre Curie and Marie Curie", "Marie Curie")
    assert not leaks_title("The Eiffel structure", "Eiffel Tower") is False


def test_input_limits():
    assert MAX_QUESTIONS == 5 and MAX_INPUT_CHARS == 200
    assert len(clean_text("a" * 500)) == 200
    assert clean_text("  hello \n  world ") == "hello world"


def test_witness_prompt_has_no_answer_key(monkeypatch):
    seen = {}
    def fake(system, user, **kw):
        seen.update(system=system, user=user, **kw)
        return {"answer": "In 1921, I think.", "clue_ids_used": []}
    monkeypatch.setattr(agents, "llm_available", lambda: True)
    monkeypatch.setattr(agents, "call_llm", fake)
    ask_witness(C0, RECS[0].article, "When did she win the chemistry prize?")
    prompt = seen["system"] + seen["user"]
    assert "is_false" not in prompt and C0.explanation not in prompt
    assert C0.original_sentence not in prompt                       # only the false version is known
    assert C0.false_sentence in prompt


def test_llm_answer_with_title_is_redacted_and_flagged(monkeypatch):
    monkeypatch.setattr(agents, "llm_available", lambda: True)
    monkeypatch.setattr(agents, "call_llm", lambda *a, **k: {"answer": "Marie Curie won it in 1921."})
    a = ask_witness(C0, RECS[0].article, "Who won?")
    assert "Curie" not in a.answer and "Marie" not in a.answer and a.redacted


def test_llm_failure_gives_i_do_not_remember(monkeypatch):
    def boom(*a, **k): raise agents.LLMUnavailable("down")
    monkeypatch.setattr(agents, "llm_available", lambda: True)
    monkeypatch.setattr(agents, "call_llm", boom)
    assert ask_witness(C0, RECS[0].article, "When?").answer == DONT_KNOW


def test_log_has_all_fields_of_the_pdf():
    res = score_game(C0, 1, 2, 3, "medium")
    log = make_log(C0, res, "human", "Leyan", 1, 2, 3, 41.26)
    for key in ("case_id", "category", "tamper_type", "accused_id", "correct", "n_searches",
                "n_questions", "seconds", "timestamp"):
        assert key in log
    assert log["seconds"] == 41.3 and log["player"] == "human"
