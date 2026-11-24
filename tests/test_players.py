import json
import pytest
import players


@pytest.fixture(autouse=True)
def tmp_players(monkeypatch, tmp_path):
    monkeypatch.setattr(players, "PLAYERS_FILE", tmp_path / "p.json")


def log(correct, t="date", cat="France", xp=100, case="c1", s=1, q=1, sec=30, name="Leyan"):
    return {"player": "human", "nickname": name, "correct": correct, "tamper_type": t, "category": cat,
            "xp": xp, "case_id": case, "n_searches": s, "n_questions": q, "seconds": sec}


def test_create_and_login_with_a_pin():
    assert players.create_player("Leyan", "1234", ["Korea"]) == (True, "Leyan")
    assert players.check_login("leyan", "1234") and not players.check_login("Leyan", "4321")
    assert players.get_player("LEYAN")["favorites"] == ["Korea"]
    assert "pin_hash" not in players.get_player("Leyan")
    assert "1234" not in (players.PLAYERS_FILE).read_text()


@pytest.mark.parametrize("name,pin", [("ab", "1234"), ("Guest", "1234"), ("DetectiveBot", "1234"),
                                      ("bad/name", "1234"), ("Leyan", "12"), ("Leyan", "abcd"), ("", "1234")])
def test_invalid_profiles_are_refused(name, pin):
    assert players.create_player(name, pin)[0] is False


def test_names_are_unique_whatever_the_case():
    players.create_player("Leyan", "1234")
    assert players.create_player("LEYAN", "5555")[0] is False


def test_stats_streaks_xp_and_types():
    logs = [log(True, xp=130), log(False, "place", xp=-10, case="c2"), log(True, "place", case="c3"),
            log(True, "date", case="c4"), log(True, "date", case="c5", name="Other")]
    s = players.stats_for(logs, "leyan")
    assert s["played"] == 4 and s["solved"] == 3 and s["xp"] == 320
    assert s["streak"] == 2 and s["best_streak"] == 2
    assert s["by_type"]["place"] == [1, 2] and s["by_type"]["date"] == [2, 2]
    assert s["seen_ids"] == ["c1", "c2", "c3", "c4"] and s["rank"] == "Detective"
    assert 0 <= s["progress"] <= 1 and players.weakest_type(s) == "place"


def test_empty_stats_and_bot_logs_are_ignored():
    s = players.stats_for([{"player": "bot", "nickname": "Leyan", "correct": True}], "Leyan")
    assert s["played"] == 0 and s["accuracy"] is None and s["rank"] == "Rookie" and players.weakest_type(s) is None
