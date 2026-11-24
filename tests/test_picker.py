import random
from types import SimpleNamespace as NS
from picker import pick_case


def rec(i, t="date", c="France"):
    return NS(case=NS(case_id=f"c{i}", tamper_type=t, category=c))


def test_no_repeat_until_all_played():
    cases = [rec(i) for i in range(6)]
    seen, got = [], []
    rng = random.Random(0)
    for _ in range(6):
        i = pick_case(cases, seen, [], rng)
        seen.append(cases[i].case.case_id)
        got.append(i)
    assert sorted(got) == list(range(6))


def test_after_everything_no_immediate_repeat():
    cases = [rec(i) for i in range(5)]
    seen = [f"c{i}" for i in range(5)]
    rng = random.Random(1)
    for _ in range(50):
        i = pick_case(cases, seen, [], rng)
        assert cases[i].case.case_id not in seen[-3:]
        seen.append(cases[i].case.case_id)


def test_prefers_types_not_played_recently():
    cases = [rec(0, "date"), rec(1, "place", "Korea")]
    hist = [("date", "France")] * 8
    rng = random.Random(2)
    picks = [pick_case(cases, [], hist, rng) for _ in range(200)]
    assert picks.count(1) > 150


def test_favorite_topics_are_more_likely():
    cases = [rec(0, "date", "Korea"), rec(1, "date", "France")]
    rng = random.Random(3)
    picks = [pick_case(cases, [], [], rng, favorites=["Korea"]) for _ in range(300)]
    assert picks.count(0) > 170


def test_the_weakest_kind_of_forgery_is_trained_more():
    cases = [rec(0, "date"), rec(1, "place")]
    hist = [("date", "France", True), ("place", "France", False)] * 6      # same variety, different success
    rng = random.Random(4)
    picks = [pick_case(cases, [], hist, rng) for _ in range(300)]
    assert picks.count(1) > 185
