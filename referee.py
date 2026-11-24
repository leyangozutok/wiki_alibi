"""The Referee: plain Python, no LLM. Checks cases, redacts leaks, scores games."""
import re
from models import Case

GENERIC_WORDS = {"tower", "battle", "war", "city", "river", "mount", "mountain", "empire",
                 "island", "bridge", "museum", "republic", "university", "great", "kingdom",
                 "world", "state", "states", "united", "national", "history"}

MAX_QUESTIONS = 5          # FR5: up to 5 questions for each case
MAX_INPUT_CHARS = 200      # NFR privacy: player text limited to 200 characters
FREE_SEARCHES = 3
FREE_QUESTIONS = 3
BET = {"low": (0, 0), "medium": (15, 10), "high": (30, 25)}   # (bonus if right, penalty if wrong)
RANKS = [(0, "Rookie"), (150, "Detective"), (400, "Inspector"), (800, "Chief Inspector")]


# ---------- text helpers ----------
def _norm(text: str) -> str:
    return re.sub(r"(?<=\d),(?=\d{3})", "", text)          # 1,200 -> 1200


def clean_text(text: str) -> str:
    """Player text: single spaces, max 200 characters."""
    return " ".join(str(text).split())[:MAX_INPUT_CHARS]


def numbers_in(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", _norm(text))


def contains_value(text: str, value: str) -> bool:
    """Whole-number match for numbers, whole-word match (case-insensitive) for text."""
    value = value.strip()
    if not value:
        return False
    if re.fullmatch(r"[\d.,]+", value):
        v = _norm(value)
        return re.search(r"(?<![\d.])" + re.escape(v) + r"(?!\d)", _norm(text)) is not None
    return re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", text, re.IGNORECASE) is not None


def title_terms(title: str) -> list[str]:
    base = re.sub(r"\s*\([^)]*\)", "", title).strip() or title     # "Python (programming language)" -> "Python"
    terms = [base]
    for tok in re.findall(r"[^\W\d_]{5,}", base):
        if tok.lower() not in GENERIC_WORDS and tok != base:
            terms.append(tok)
    return terms


def leaks_title(text: str, title: str) -> bool:
    return any(contains_value(text, t) for t in title_terms(title))


def redact_title(text: str, title: str) -> str:
    for t in sorted(title_terms(title), key=len, reverse=True):
        text = re.sub(r"(?<!\w)" + re.escape(t) + r"(?!\w)", "[REDACTED]", text, flags=re.I)
    return text


# ---------- FR3: case validation ----------
def validate_case(case: Case, article: str) -> list[str]:
    errors = []
    if len(case.clues) != 5 or sorted(c.id for c in case.clues) != [1, 2, 3, 4, 5]:
        errors.append("FR1: a case needs exactly 5 clues with ids 1 to 5")
    false = [c for c in case.clues if c.is_false]
    if len(false) != 1:
        errors.append("FR3a: exactly 1 false clue is required")
    for c in case.clues:
        if leaks_title(c.text, case.wiki_title):
            errors.append(f"FR3b: clue {c.id} contains the article title")
        if not c.is_false:
            for n in numbers_in(c.text):
                if not contains_value(article, n):
                    errors.append(f"FR3c: number {n} of true clue {c.id} is not in the article")
            if contains_value(c.text, case.false_value):
                errors.append(f"FR3c: true clue {c.id} contains the false value")
    if case.original_sentence not in article:
        errors.append("FR3d: original_sentence is not in the article")
    if not contains_value(article, case.original_value):
        errors.append("FR3d: original value is not in the article")
    if contains_value(article, case.false_value):
        errors.append("FR3d: false value already appears in the article")
    if not contains_value(case.original_sentence, case.original_value):
        errors.append("original_sentence does not contain original_value")
    if not contains_value(case.false_sentence, case.false_value):
        errors.append("false_sentence does not contain false_value")
    if len(false) == 1 and not contains_value(false[0].text, case.false_value):
        errors.append("the false clue does not contain the false value")
    return errors


def false_clue_id(case: Case) -> int:
    return next(c.id for c in case.clues if c.is_false)


# ---------- FR7: scoring (+ confidence bet and ranks) ----------
def score_game(case: Case, accused_id: int, n_searches: int, n_questions: int,
               confidence: str = "low") -> dict:
    correct = accused_id == false_clue_id(case)
    base = 100 if correct else 0
    sp = 5 * max(0, n_searches - FREE_SEARCHES)
    qp = 5 * max(0, n_questions - FREE_QUESTIONS)
    score = max(0, base - sp - qp)
    bonus, penalty = BET[confidence]
    bet_delta = bonus if correct else -penalty
    return {"correct": correct, "score": score, "search_penalty": sp, "question_penalty": qp,
            "confidence": confidence, "bet_delta": bet_delta, "xp": score + bet_delta}


def rank_for(xp: int) -> str:
    name = RANKS[0][1]
    for threshold, rank in RANKS:
        if xp >= threshold:
            name = rank
    return name


def next_rank(xp: int):
    """(name, xp needed) of the next rank, or None at the top."""
    for threshold, name in RANKS:
        if xp < threshold:
            return name, threshold
    return None


def make_log(case: Case, result: dict, player: str, nickname: str, accused_id: int,
             n_searches: int, n_questions: int, seconds: float,
             title_redactions: int = 0) -> dict:
    import datetime as dt
    return {"case_id": case.case_id, "category": case.category, "tamper_type": case.tamper_type,
            "player": player, "nickname": nickname, "accused_id": accused_id,
            "correct": result["correct"], "confidence": result["confidence"],
            "score": result["score"], "xp": result["xp"], "n_searches": n_searches,
            "n_questions": n_questions, "seconds": round(seconds, 1),
            "title_redactions": title_redactions,
            "timestamp": dt.datetime.now().isoformat(timespec="seconds")}
