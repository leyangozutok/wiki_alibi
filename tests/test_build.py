import csv
from collections import Counter
import pytest

import agents
import build_cases as bc
from agents import build_case, CaseBuildError
from llm import LLMLimitReached, LLMUnavailable
from models import CaseRecord
from storage import load_cases, DATA

DEMO = load_cases()[0]
CORE = DEMO.case.model_dump(exclude={"case_id", "wiki_title", "category"})


# ---------- topics file ----------
def test_topics_csv_matches_the_pdf():
    topics = bc.read_topics()
    assert len(topics) == 100 and len({t["title"] for t in topics}) == 100
    cats = Counter(t["category"] for t in topics)
    assert set(cats) == {"Korea", "France", "computing and electronics basics", "history", "science",
                         "famous people", "famous mysteries and investigations"}
    assert all(14 <= n <= 15 for n in cats.values())


# ---------- Case Builder + Referee loop ----------
@pytest.fixture
def llm_on(monkeypatch):
    monkeypatch.setattr(agents, "llm_available", lambda: True)


def test_build_case_valid_first_time(llm_on, monkeypatch):
    monkeypatch.setattr(agents, "call_llm", lambda *a, **k: CORE)
    stats = {}
    rec = build_case("Marie Curie", DEMO.article, "date", "famous people", stats=stats)
    assert isinstance(rec, CaseRecord) and stats["attempts"] == 1 and stats["valid"] == 1


def test_build_case_retries_after_a_bad_answer(llm_on, monkeypatch):
    answers = iter([{"nonsense": True}, CORE])                     # bad JSON schema, then good
    monkeypatch.setattr(agents, "call_llm", lambda *a, **k: next(answers))
    stats = {}
    build_case("Marie Curie", DEMO.article, "date", stats=stats)
    assert stats["attempts"] == 2 and stats["valid"] == 1


def test_build_case_gives_up_after_two_retries(llm_on, monkeypatch):
    bad = dict(CORE, false_value="1903")                            # fails the Referee (FR3d)
    calls = {"n": 0}
    def fake(*a, **k): calls["n"] += 1; return bad
    monkeypatch.setattr(agents, "call_llm", fake)
    with pytest.raises(CaseBuildError):
        build_case("Marie Curie", DEMO.article, "date")
    assert calls["n"] == 3                                          # 1 try + 2 retries


def test_build_case_stops_at_daily_limit_and_in_mock_mode(llm_on, monkeypatch):
    def limit(*a, **k): raise LLMLimitReached("limit")
    monkeypatch.setattr(agents, "call_llm", limit)
    with pytest.raises(LLMLimitReached):
        build_case("Marie Curie", DEMO.article, "date")
    monkeypatch.setattr(agents, "llm_available", lambda: False)
    with pytest.raises(CaseBuildError):
        build_case("Marie Curie", DEMO.article, "date")


# ---------- the plan: 100 articles -> 150 cases ----------
def test_plan_has_150_cases_balanced_and_spread():
    topics = bc.read_topics()
    jobs = bc.plan_jobs(topics, [])
    assert len(jobs) == 150
    first = {j.title: j.tamper for j in jobs if j.pass_no == 1}
    second = [j for j in jobs if j.pass_no == 2]
    assert len(first) == 100 and len(second) == 50
    assert all(j.tamper != first[j.title] for j in second)          # a different trick
    types = Counter(j.tamper for j in jobs)
    assert max(types.values()) - min(types.values()) <= 2 and set(types) == set(bc.TYPES)
    per_cat = Counter(j.category for j in second)
    assert len(per_cat) == 7 and min(per_cat.values()) >= 7


def test_plan_ignores_demo_cases_and_resumes():
    topics = bc.read_topics()
    assert len(bc.plan_jobs(topics, load_cases())) == 150           # 4 demo cases do not count
    done = [r.model_copy(update={"case": r.case.model_copy(update={"case_id": f"r{i}", "wiki_title": topics[i]["title"]})})
            for i, r in enumerate(load_cases())]
    assert len(bc.plan_jobs(topics, done)) == 150 - len(done)


# ---------- running the plan (fake Wikipedia + fake builder) ----------
def fake_builder(fail_titles=(), bad_type=None, stop_after=None):
    state = {"n": 0}
    def build(title, article, ty, category="general", stats=None):
        state["n"] += 1
        if stop_after and state["n"] > stop_after:
            raise LLMLimitReached("Daily limit reached")
        stats["attempts"] += 1
        if title in fail_titles or ty == bad_type:
            raise CaseBuildError("referee said no")
        stats["valid"] += 1
        case = DEMO.case.model_copy(update={"case_id": f"n{state['n']}", "wiki_title": title,
                                            "category": category, "tamper_type": ty})
        return CaseRecord(case=case, article=article)
    return build


def run(jobs, builder, articles=lambda t: "text", **kw):
    saved = []
    rep = bc.run_build(jobs, [], build_fn=builder, article_fn=articles, save_fn=lambda r: saved.append(len(r)),
                       sleep=0, log=lambda *_: None, **kw)
    return rep, saved


def test_run_build_report_and_progress_saving():
    jobs = bc.plan_jobs(bc.read_topics(), [])[:20]
    rep, saved = run(jobs, fake_builder())
    assert rep["built"] == 20 and rep["validation_rate"] == 1.0 and rep["meets_90_percent_goal"]
    assert saved == list(range(1, 21))                              # saved after every single case


def test_run_build_wikipedia_timeouts_are_skipped_not_fatal():
    from wiki import WikiError
    jobs = bc.plan_jobs(bc.read_topics(), [])[:10]
    bad = jobs[3].title
    def articles(t):
        if t == bad: raise WikiError("timeout")
        return "text"
    rep, _ = run(jobs, fake_builder(), articles)
    assert rep["built"] == 9 and rep["failed"][0]["title"] == bad


def test_run_build_falls_back_to_another_trick_type():
    jobs = bc.plan_jobs(bc.read_topics(), [])[:12]
    rep, _ = run(jobs, fake_builder(bad_type="person"))
    assert rep["built"] == 12 and "person" not in rep["types"]


def test_run_build_validation_rate_is_below_goal_when_many_fail():
    jobs = bc.plan_jobs(bc.read_topics(), [])[:10]
    rep, _ = run(jobs, fake_builder(fail_titles={j.title for j in jobs[:5]}))
    assert rep["validation_rate"] < 0.9 and rep["meets_90_percent_goal"] is False


def test_run_build_stops_cleanly_at_the_daily_limit():
    jobs = bc.plan_jobs(bc.read_topics(), [])[:10]
    rep, _ = run(jobs, fake_builder(stop_after=3))
    assert rep["built"] == 3 and "limit" in rep["stopped"].lower()


def test_dry_run_needs_no_api(capsys):
    assert bc.main(["--dry-run"]) == 0
    assert "still to build" in capsys.readouterr().out
