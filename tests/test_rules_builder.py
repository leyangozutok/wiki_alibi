"""Offline Case Builder (no LLM): every case it makes must pass the Referee."""
import pytest

import build_cases as bc
from models import CaseBuildError
from referee import validate_case, leaks_title, contains_value
from rules_builder import build_case_rules, clean_article, split_sentences, neutralize
from storage import load_cases

RECS = load_cases()
TYPES = ["date", "number", "place", "person"]


def all_cases():
    for r in RECS:
        for ty in TYPES:
            try:
                yield r, ty, build_case_rules(r.case.wiki_title, r.article, ty, r.case.category)
            except CaseBuildError:
                pass


def test_every_generated_case_passes_the_referee():
    n = 0
    for r, ty, rec in all_cases():
        c = rec.case
        n += 1
        assert validate_case(c, rec.article) == []
        assert c.tamper_type == ty and sum(k.is_false for k in c.clues) == 1
        assert rec.case.original_sentence in rec.article
        assert not any(leaks_title(k.text, c.wiki_title) for k in c.clues)
        assert contains_value(next(k.text for k in c.clues if k.is_false), c.false_value)
        assert not any(contains_value(k.text, c.original_value) for k in c.clues if not k.is_false)
    assert n >= 30


def test_most_articles_give_at_least_one_case():
    ok = {r.case.wiki_title for r, _, _ in all_cases()}
    assert len(ok) >= 12


def test_builder_is_deterministic_for_a_given_seed():
    a = build_case_rules("Mars", RECS[10].article, "number", seed="s1")
    b = build_case_rules("Mars", RECS[10].article, "number", seed="s1")
    assert [c.text for c in a.case.clues] == [c.text for c in b.case.clues]


def test_a_too_short_text_is_refused():
    with pytest.raises(CaseBuildError):
        build_case_rules("X", "One short sentence here. Another one.", "date")


def test_wikipedia_text_is_cleaned():
    raw = "Marie Curie (/ˈkjʊəri/; 7 November 1867 – 4 July 1934) was a scientist.[1]\n\n== Early life ==\nShe was born in Warsaw."
    t = clean_article(raw)
    assert "==" not in t and "[1]" not in t and "ˈkjʊəri" not in t and "Early life" not in t
    assert neutralize("Marie Curie was born in 1867.", "Marie Curie") == "The subject was born in 1867."


def test_sentences_keep_exact_text():
    text = clean_article("Alpha is a long enough sentence to keep here. Beta is another long enough sentence here.")
    assert all(s in text for s in split_sentences(text))


def test_builder_plugs_into_the_pipeline_offline():
    by_title = {r.case.wiki_title: r.article for r in RECS}
    topics = [{"title": r.case.wiki_title, "category": r.case.category} for r in RECS]
    jobs = bc.plan_jobs(topics, [], n_second=5)
    rep = bc.run_build(jobs, [], build_fn=build_case_rules, article_fn=lambda t: by_title[t],
                       save_fn=lambda r: None, sleep=0, log=lambda *_: None)
    assert rep["built"] >= 15 and rep["validation_rate"] > 0
    assert set(rep["types"]) <= set(TYPES)


def test_narrator_step_is_called_and_limit_is_handled():
    from llm import LLMLimitReached
    by_title = {r.case.wiki_title: r.article for r in RECS}
    topics = [{"title": r.case.wiki_title, "category": r.case.category} for r in RECS][:6]
    jobs = bc.plan_jobs(topics, [], n_second=0)
    saved = []
    rep = bc.run_build(jobs, [], build_fn=build_case_rules, article_fn=lambda t: by_title[t],
                       save_fn=saved.append, sleep=0, log=lambda *_: None, narrator_fn=lambda c: "A story.")
    assert rep["built"] > 0 and all(r.case.briefing == "A story." for r in saved[-1])
    def limit(c): raise LLMLimitReached("limit")
    rep = bc.run_build(jobs, [], build_fn=build_case_rules, article_fn=lambda t: by_title[t],
                       save_fn=lambda r: None, sleep=0, log=lambda *_: None, narrator_fn=limit)
    assert rep["built"] == 1 and "limit" in rep["stopped"]
