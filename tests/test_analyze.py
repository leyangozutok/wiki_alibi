import json
import pytest
pd = pytest.importorskip("pandas")
pytest.importorskip("matplotlib")
import analyze


def test_analysis_makes_all_charts(tmp_path):
    logs = tmp_path / "g.jsonl"
    rows = []
    for i in range(24):
        rows.append({"case_id": "c", "category": "France", "tamper_type": analyze.TYPES[i % 4],
                     "player": "human" if i < 18 else "bot", "nickname": f"p{i % 3}", "correct": i % 3 != 0,
                     "confidence": analyze.CONF[i % 3], "n_searches": i % 5, "n_questions": i % 6,
                     "seconds": 30 + i, "title_redactions": 0})
    logs.write_text("\n".join(json.dumps(r) for r in rows))
    survey = tmp_path / "s.csv"
    survey.write_text("Timestamp,nickname,I enjoyed the game,I learned something,easy to use,the witness,play again\n"
                      "t,p0,5,4,4,3,5\nt,p1,4,5,5,4,4\n")
    analyze.main(["--logs", str(logs), "--survey", str(survey), "--out", str(tmp_path / "out")])
    names = {p.name for p in (tmp_path / "out").iterdir()}
    assert {"1_overall_accuracy.png", "2_accuracy_by_tamper_type.png", "3_confidence_vs_accuracy.png",
            "4_effort_searches_questions.png", "5_searches_vs_accuracy.png", "6_survey.png",
            "summary.csv"} <= names


def test_wilson_interval_is_sane():
    lo, hi = analyze.wilson(5, 10)
    assert 0.2 < lo < 0.5 < hi < 0.8 and analyze.wilson(0, 0) == (0.0, 0.0)
