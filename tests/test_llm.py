import json
import pytest
import llm


class FakeResp:
    def __init__(self, content, usage=None):
        self._p = {"choices": [{"message": {"content": content}}], "usage": usage or {}}
    def raise_for_status(self): pass
    def json(self): return self._p


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "USAGE_FILE", tmp_path / "usage.json")
    monkeypatch.setenv("LLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_DAILY_LIMIT", "3")


def test_mock_mode_is_the_default_and_offline(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert not llm.llm_available()
    with pytest.raises(llm.LLMUnavailable):
        llm.call_llm("s", "u")


def test_json_is_parsed_and_markdown_fences_are_removed(configured, monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResp('```json\n{"a": 1}\n```',
                                                                     {"prompt_tokens": 10, "completion_tokens": 5}))
    assert llm.call_llm("s", "u") == {"a": 1}
    u = llm.usage_today()
    assert u["calls"] == 1 and u["prompt_tokens"] == 10 and u["completion_tokens"] == 5


def test_daily_limit_stops_the_calls(configured, monkeypatch):
    n = {"posts": 0}
    def post(*a, **k): n["posts"] += 1; return FakeResp('{"ok": true}')
    monkeypatch.setattr(llm.requests, "post", post)
    for _ in range(3):
        llm.call_llm("s", "u")
    with pytest.raises(llm.LLMLimitReached):
        llm.call_llm("s", "u")
    assert n["posts"] == 3                                  # the 4th request was never sent
    assert issubclass(llm.LLMLimitReached, llm.LLMUnavailable)


def test_bad_json_and_http_errors_become_llm_unavailable(configured, monkeypatch):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResp("not json at all"))
    with pytest.raises(llm.LLMUnavailable):
        llm.call_llm("s", "u")
    def timeout(*a, **k): raise llm.requests.Timeout("slow")
    monkeypatch.setattr(llm.requests, "post", timeout)
    with pytest.raises(llm.LLMUnavailable):
        llm.call_llm("s", "u")
    assert llm.usage_today()["calls"] == 2                  # failed calls count too (budget safety)
