"""The real Streamlit app, driven by AppTest (offline: fake Wikipedia, temporary log and player files)."""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import players
import storage
import wiki
from game_logic import NO_RESULT, SEARCH_ERROR, NO_MORE_QUESTIONS

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app.py")
RESULTS = str(ROOT / "pages" / "1_Results.py")


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "LOG_FILE", tmp_path / "games.jsonl")
    monkeypatch.setattr(players, "PLAYERS_FILE", tmp_path / "players.json")
    monkeypatch.setattr(wiki, "search_wiki", lambda q: [])
    return tmp_path


def texts(at):
    return " ".join(m.value for m in at.markdown)


def button(at, label):
    return [b for b in at.button if b.label == label][0]


def home(env):
    return AppTest.from_file(APP, default_timeout=30).run()


def create_profile(at, name="Leyan", pin="1234"):
    at.radio(key="home_mode").set_value("Create profile").run()
    at.text_input(key="new_name").input(name)
    at.text_input(key="new_pin").input(pin)
    button(at, "Create my profile").click().run()
    return at


def sign_in(at, name="Leyan", pin="1234"):
    at.radio(key="home_mode").set_value("Sign in").run()
    at.text_input(key="in_name").input(name)
    at.text_input(key="in_pin").input(pin)
    button(at, "Sign in").click().run()
    return at


def open_case(at):
    button(at, "Open the next case").click().run()
    return at


@pytest.fixture
def guest_game(env):
    at = home(env)
    at.radio(key="home_mode").set_value("Guest").run()
    button(at, "Continue as a guest").click().run()
    return open_case(at)


@pytest.fixture
def player_game(env):
    return open_case(create_profile(home(env)))


def ask(at, q):
    [t for t in at.text_input if t.label == "Question"][0].input(q)
    button(at, "Ask").click().run()


# ---------------- home and profiles ----------------
def test_home_page_tells_the_story(env):
    at = home(env)
    assert not at.exception and "forgery" in texts(at)


def test_profile_is_created_and_progress_survives_a_new_visit(env):
    at = create_profile(home(env))
    assert at.session_state["user"] == "Leyan" and not at.exception
    at2 = sign_in(home(env))                                  # a brand new browser session
    assert at2.session_state["user"] == "Leyan"
    assert "Welcome back" in texts(at2) or "Welcome to the Bureau" in texts(at2)


def test_wrong_pin_and_duplicate_name_are_refused(env):
    create_profile(home(env))
    at = sign_in(home(env), pin="9999")
    assert at.session_state["user"] is None and any("wrong PIN" in e.value for e in at.error)
    at = create_profile(home(env), name="leyan")              # same name, other case
    assert at.session_state["user"] is None and any("already taken" in e.value for e in at.error)


def test_pin_is_never_stored_in_clear(env):
    create_profile(home(env), pin="4321")
    assert "4321" not in (env / "players.json").read_text()


# ---------------- the investigation ----------------
def test_case_screen_has_story_clues_and_witness(guest_game):
    t = texts(guest_game)
    assert not guest_game.exception and "Evidence" in t and "Case file no." in t
    assert "Notebook:" in t


def test_sixth_question_is_blocked_in_the_interface(guest_game):
    for i in range(5):
        ask(guest_game, f"when was she born {i}?")
    assert guest_game.session_state["game"]["questions"] == 5
    assert [t for t in guest_game.text_input if t.label == "Question"][0].disabled
    assert button(guest_game, "Ask").disabled and NO_MORE_QUESTIONS in texts(guest_game)


def test_one_question_counts_once(guest_game):
    ask(guest_game, "when was she born?")
    guest_game.run()                                          # a plain re-run must not ask again
    assert guest_game.session_state["game"]["questions"] == 1


def test_empty_search_is_counted_with_message(guest_game):
    guest_game.text_input(key="s_query").input("zzzz")
    button(guest_game, "Search").click().run()
    assert guest_game.session_state["game"]["searches"] == 1 and NO_RESULT in texts(guest_game)


def test_wikipedia_error_is_not_counted(guest_game, monkeypatch):
    def down(q): raise wiki.WikiError("timeout")
    monkeypatch.setattr(wiki, "search_wiki", down)
    guest_game.run()
    guest_game.text_input(key="s_query").input("eiffel")
    button(guest_game, "Search").click().run()
    assert guest_game.session_state["game"]["searches"] == 0
    assert SEARCH_ERROR in " ".join(e.value for e in guest_game.error)


def test_accusation_is_logged_once_for_the_player(player_game, env):
    ask(player_game, "when was she born?")
    button(player_game, "Submit accusation").click().run()
    player_game.run()
    assert not player_game.exception and player_game.session_state["game"]["done"]
    lines = (env / "games.jsonl").read_text().splitlines()
    assert len(lines) == 1
    line = json.loads(lines[0])
    assert line["nickname"] == "Leyan" and line["player"] == "human" and line["seconds"] >= 0
    assert line["n_questions"] == 1 and "title_redactions" in line
    t = texts(player_game)
    assert "Chief Inspector Vale" in t and "Saved in your detective file" in t


def test_guest_games_are_logged_as_guest(guest_game, env):
    button(guest_game, "Submit accusation").click().run()
    assert json.loads((env / "games.jsonl").read_text().splitlines()[0])["nickname"] == "Guest"


# ---------------- no more looping on the same cases ----------------
def test_a_profile_never_sees_the_same_case_twice_until_all_are_played(player_game):
    n_cases = len(storage.load_cases())
    seen = [player_game.session_state["game"]["idx"]]
    for _ in range(n_cases - 1):
        button(player_game, "Submit accusation").click().run()
        button(player_game, "Next case").click().run()
        seen.append(player_game.session_state["game"]["idx"])
    assert len(set(seen)) == n_cases and not player_game.exception


def test_progress_is_remembered_after_leaving_the_game(env):
    at = open_case(create_profile(home(env)))
    first = at.session_state["game"]["idx"]
    button(at, "Submit accusation").click().run()
    at2 = open_case(sign_in(home(env)))                       # new session, same player
    assert at2.session_state["game"]["idx"] != first


# ---------------- detective file ----------------
def test_results_page_in_every_situation(env):
    assert not AppTest.from_file(RESULTS, default_timeout=30).run().exception           # anonymous, no data
    at = open_case(create_profile(home(env)))
    button(at, "Submit accusation").click().run()
    r = AppTest.from_file(RESULTS, default_timeout=30)
    r.session_state["user"] = "Leyan"
    r.run()
    t = " ".join(m.value for m in r.markdown)
    assert not r.exception and "What fools you" in t and "Recent cases" in t and "wa-fill" in t
    r2 = AppTest.from_file(RESULTS, default_timeout=30)
    r2.session_state["user"] = "Nobody"
    r2.run()
    assert "your file is empty" in " ".join(m.value for m in r2.markdown)
