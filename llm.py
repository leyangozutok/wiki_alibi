"""The ONLY place that talks to an LLM. When the teacher gives the API, change this file only.

Env variables (or .streamlit/secrets.toml, or Streamlit Cloud secrets):
  LLM_PROVIDER    mock (default, fully offline) | openai_compat
  LLM_API_KEY     your key
  LLM_BASE_URL    default https://api.openai.com/v1   (any OpenAI-compatible endpoint)
  LLM_MODEL       default gpt-4o-mini
  LLM_DAILY_LIMIT max API calls per day (default 500)  -> protects your budget (NFR: cost)
"""
import datetime as dt
import json
import os
import re
import time
from pathlib import Path

import requests

USAGE_FILE = Path(__file__).parent / "data" / "llm_usage.json"


class LLMUnavailable(Exception):
    """No LLM configured, API error, bad JSON... the game falls back to offline behavior."""


class LLMLimitReached(LLMUnavailable):
    """The daily call limit is reached."""


def llm_available() -> bool:
    return os.getenv("LLM_PROVIDER", "mock") != "mock" and bool(os.getenv("LLM_API_KEY"))


def daily_limit() -> int:
    try:
        return int(os.getenv("LLM_DAILY_LIMIT", "500"))
    except ValueError:
        return 500


def _read_usage() -> dict:
    try:
        return json.loads(USAGE_FILE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def usage_today() -> dict:
    d = _read_usage().get(str(dt.date.today()), {})
    return {"calls": d.get("calls", 0), "prompt_tokens": d.get("prompt_tokens", 0),
            "completion_tokens": d.get("completion_tokens", 0), "seconds": d.get("seconds", 0.0)}


def _record(calls=0, prompt_tokens=0, completion_tokens=0, seconds=0.0) -> None:
    data = _read_usage()
    day = data.setdefault(str(dt.date.today()), {})
    day["calls"] = day.get("calls", 0) + calls
    day["prompt_tokens"] = day.get("prompt_tokens", 0) + prompt_tokens
    day["completion_tokens"] = day.get("completion_tokens", 0) + completion_tokens
    day["seconds"] = round(day.get("seconds", 0.0) + seconds, 2)
    try:
        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        USAGE_FILE.write_text(json.dumps(data, indent=1), "utf-8")
    except OSError:
        pass          # read-only disk (e.g. cloud): the limit still works for this process run


def call_llm(system: str, user: str, temperature: float = 0.7, timeout: float = 30) -> dict:
    """Send a prompt, get a JSON object back. Raises LLMUnavailable on any problem."""
    if not llm_available():
        raise LLMUnavailable("No LLM configured (LLM_PROVIDER=mock).")
    if usage_today()["calls"] >= daily_limit():
        raise LLMLimitReached(f"Daily limit of {daily_limit()} API calls reached.")
    _record(calls=1)                       # counted before the request, so failures count too
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    body = {"model": os.getenv("LLM_MODEL", "gpt-4o-mini"), "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    t0 = time.time()
    try:
        r = requests.post(f"{base}/chat/completions", json=body, timeout=timeout,
                          headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"})
        r.raise_for_status()
        payload = r.json()
        usage = payload.get("usage", {}) or {}
        _record(prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0), seconds=time.time() - t0)
        text = payload["choices"][0]["message"]["content"]
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        return json.loads(text)
    except (requests.RequestException, KeyError, IndexError, ValueError) as e:
        raise LLMUnavailable(str(e))
