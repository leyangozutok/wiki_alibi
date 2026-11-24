"""Game rules that the interface must respect (PDF section 2.4 'Behavior rules').
Pure functions on the game dict, so they can be tested without Streamlit."""
from agents import ask_witness
from referee import MAX_QUESTIONS, clean_text
from wiki import WikiError

NO_MORE_QUESTIONS = "No more questions for this case."
NO_RESULT = "No result, try other words."
SEARCH_ERROR = "Wikipedia did not answer. Try again, this search is not counted."


def questions_left(g: dict) -> int:
    return max(0, MAX_QUESTIONS - g["questions"])


def ask(g: dict, case, article: str, question: str, persona: str, ask_fn=ask_witness):
    """Returns the witness answer, or None if the question is not allowed
    (empty, case finished, or 6th question)."""
    q = clean_text(question)
    if not q or g["done"] or questions_left(g) == 0:
        return None
    g["questions"] += 1
    g["chat"].append({"role": "user", "text": q})
    ans = ask_fn(case, article, q, persona)
    g["chat"].append({"role": "assistant", "text": ans.answer})
    g["redactions"] = g.get("redactions", 0) + int(getattr(ans, "redacted", False))
    return ans


def do_search(g: dict, query: str, search_fn) -> str:
    """Returns 'ok', 'empty' (no result, still counted), 'error' (Wikipedia down or
    slower than 3 s: NOT counted) or 'ignored'."""
    q = clean_text(query)
    if not q or g["done"]:
        return "ignored"
    try:
        results = search_fn(q)
    except WikiError:
        return "error"
    g["results"] = results
    g.setdefault("queries", []).append(q)
    g["searches"] += 1
    g["reading"] = None
    g["read_error"] = None
    return "ok" if results else "empty"
