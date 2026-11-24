from types import SimpleNamespace as NS
from game_logic import ask, do_search, questions_left
from referee import MAX_QUESTIONS
from wiki import WikiError
from storage import load_cases

REC = load_cases()[0]


def new_game():
    return {"questions": 0, "searches": 0, "chat": [], "results": [], "reading": None,
            "read_error": None, "done": False, "redactions": 0}


def fake_ask(case, article, q, persona):
    return NS(answer="ok", redacted=False)


def test_sixth_question_is_refused():
    g = new_game()
    for i in range(MAX_QUESTIONS):
        assert ask(g, REC.case, REC.article, f"q{i}", "Nervous", fake_ask) is not None
    assert questions_left(g) == 0
    assert ask(g, REC.case, REC.article, "one more", "Nervous", fake_ask) is None
    assert g["questions"] == 5 and len(g["chat"]) == 10


def test_question_is_limited_to_200_characters_and_empty_is_ignored():
    g = new_game(); got = {}
    ask(g, REC.case, REC.article, "x" * 999, "Nervous", lambda c, a, q, p: got.update(q=q) or fake_ask(c, a, q, p))
    assert len(got["q"]) == 200
    assert ask(g, REC.case, REC.article, "   ", "Nervous", fake_ask) is None and g["questions"] == 1


def test_no_questions_after_the_accusation():
    g = new_game(); g["done"] = True
    assert ask(g, REC.case, REC.article, "hello", "Nervous", fake_ask) is None


def test_redactions_are_counted():
    g = new_game()
    ask(g, REC.case, REC.article, "who", "Nervous", lambda *a: NS(answer="[REDACTED]", redacted=True))
    assert g["redactions"] == 1


def test_search_ok_is_counted_and_closes_the_open_article():
    g = new_game(); g["reading"] = ("x", "y")
    assert do_search(g, "eiffel", lambda q: [{"title": "Eiffel Tower", "snippet": "..."}]) == "ok"
    assert g["searches"] == 1 and g["reading"] is None and len(g["results"]) == 1


def test_empty_search_is_still_counted():
    g = new_game()
    assert do_search(g, "zzzzzz", lambda q: []) == "empty" and g["searches"] == 1


def test_wikipedia_timeout_is_not_counted():
    g = new_game()
    def slow(q): raise WikiError("timeout")
    assert do_search(g, "eiffel", slow) == "error" and g["searches"] == 0


def test_search_text_is_cleaned():
    g = new_game(); got = {}
    do_search(g, "y" * 400, lambda q: got.update(q=q) or [])
    assert len(got["q"]) == 200
