from agents import witness_text, ask_witness, DONT_KNOW
from referee import (validate_case, score_game, leaks_title, redact_title, rank_for,
                     contains_value, false_clue_id)
from storage import load_cases

RECS = load_cases()


def test_demo_cases_are_valid():
    assert len(RECS) >= 4
    for r in RECS:
        assert validate_case(r.case, r.article) == [], r.case.wiki_title


def test_all_four_tamper_types_in_demo():
    assert {r.case.tamper_type for r in RECS} >= {"date", "number", "place", "person"}


def test_validate_detects_problems():
    r = RECS[0]
    c = r.case.model_copy(deep=True)
    c.clues[0].is_false = True
    assert any("FR3a" in e for e in validate_case(c, r.article))
    c = r.case.model_copy(deep=True)
    c.clues[0].text = "Marie Curie was born in 1867."
    assert any("FR3b" in e for e in validate_case(c, r.article))
    c = r.case.model_copy(deep=True)
    c.clues[0].text = "The subject was born in Warsaw in 1999."
    assert any("FR3c" in e for e in validate_case(c, r.article))
    c = r.case.model_copy(deep=True)
    c.false_value = "1903"
    assert any("FR3d" in e for e in validate_case(c, r.article))


def test_witness_repeats_the_lie():
    r = RECS[0]
    wt = witness_text(r.case, r.article)
    assert "1921" in wt and "1911" not in wt


def test_witness_never_leaks_title():
    r = RECS[0]
    a = ask_witness(r.case, r.article, "Who was the husband and what did she win with Pierre?")
    assert not leaks_title(a.answer, r.case.wiki_title)


def test_witness_does_not_know_which_clue_is_false():
    r = RECS[1]
    assert "I do not remember" in ask_witness(r.case, r.article, "Which clue is false?").answer


def test_scoring():
    case = RECS[0].case
    right = false_clue_id(case)
    assert score_game(case, right, 1, 1)["score"] == 100
    assert score_game(case, right, 5, 5)["score"] == 80      # -10 (2 extra searches) -10 (2 extra questions)
    assert score_game(case, right, 40, 40)["score"] == 0      # minimum 0
    assert score_game(case, 99, 0, 0)["score"] == 0
    assert score_game(case, right, 0, 0, "high")["xp"] == 130
    assert score_game(case, 99, 0, 0, "high")["xp"] == -25


def test_helpers():
    assert contains_value("born in 1,200 BC", "1200")
    assert not contains_value("born in 11911", "1911")
    assert redact_title("Curie won it", "Marie Curie") == "[REDACTED] won it"
    assert rank_for(0) == "Rookie" and rank_for(500) == "Inspector"
