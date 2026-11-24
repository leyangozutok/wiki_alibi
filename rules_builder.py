"""Offline Case Builder: builds Referee-valid cases from a Wikipedia article WITHOUT any LLM.

It is the fallback while no API is available (or to save API calls): it takes real sentences of the
article as clues and changes ONE fact (a year, a number, a place or a person's name) to make the forgery.
The AI Case Builder (agents.build_case) writes more natural clues; both go through the same Referee."""
import random
import re
import time
import uuid

from models import Case, CaseRecord, Clue, CaseBuildError
from referee import validate_case, title_terms, contains_value, leaks_title

CITIES = ["Paris", "London", "Berlin", "Madrid", "Rome", "Vienna", "Prague", "Warsaw", "Moscow", "Cairo",
          "Istanbul", "Athens", "Lisbon", "Dublin", "Oslo", "Stockholm", "Amsterdam", "Brussels", "Geneva",
          "Milan", "Naples", "Venice", "Florence", "Lyon", "Marseille", "Bordeaux", "Tokyo", "Osaka", "Kyoto",
          "Beijing", "Shanghai", "Singapore", "Bangkok", "Mumbai", "Delhi", "Sydney", "Melbourne", "Toronto",
          "Chicago", "Boston", "Seattle", "Houston", "Edinburgh", "Manchester", "Liverpool", "Hamburg",
          "Munich", "Busan", "Seoul", "Pyongyang"]
COUNTRIES = ["France", "Germany", "Italy", "Spain", "Portugal", "Poland", "Russia", "Japan", "China", "India",
             "Brazil", "Canada", "Australia", "Egypt", "Greece", "Sweden", "Norway", "Ireland", "Scotland",
             "Switzerland", "Austria", "Mexico", "Argentina", "Turkey", "Thailand", "Vietnam", "England",
             "Netherlands", "Belgium", "Denmark", "Finland", "Hungary"]
FIRST_NAMES = set("""John William James Robert Charles George Henry Thomas Edward Louis Pierre Jean Marie Anne Mary
Elizabeth Albert Isaac Alan Ada Nikola Leonardo Frank Neil Michael Walter Guido Vincent Richard David Paul Peter
Joseph Francis Samuel Benjamin Alexander Victor Napoleon Catherine Margaret Jane Sarah Hans Otto Karl Carl Max
Wolfgang Ludwig Johann Gustave Claude Marc Jacques Philippe Nelson Martin Winston Abraham Franklin Theodore
Rosalind Marcus Julius Julia Isabella Charlotte Emily Lucy Helen Grace Florence Mahatma Jawaharlal Sejong""".split())
FAKE_PEOPLE = ["Robert Noyce", "Carl Sagan", "Frank Borman", "Henry Ford", "Charles Babbage", "Thomas Edison",
               "Edward Jenner", "George Stephenson", "Walter Gropius", "James Watt", "William Herschel",
               "Samuel Morse", "Victor Hugo", "Louis Pasteur", "Hans Christian", "Albert Camus",
               "Peter Higgs", "Joseph Fourier", "Henry Moseley", "David Hilbert"]
MONTHS = ("January|February|March|April|May|June|July|August|September|October|November|December")


# ---------- reading the article ----------
def clean_article(raw: str, limit: int = 6000) -> str:
    """Plain text: no headings, no brackets, one paragraph."""
    lines = [l.strip() for l in raw.splitlines() if l.strip() and not l.strip().startswith("=")]
    text = " ".join(lines)
    text = re.sub(r"\([^()]*\)", "", text)                 # pronunciations, dates in brackets
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    if len(text) > limit:
        cut = text[:limit]
        text = cut[:cut.rfind(". ") + 1] if ". " in cut else cut
    return text


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [p.strip() for p in parts if 20 <= len(p.strip()) <= 230 and p.strip()[-1] in ".!?"]


def awkward(sentence: str, title: str) -> bool:
    """True if a word of the title is inside another name ('Pierre Curie', 'Gustave Eiffel'):
    hiding it would give 'Pierre the subject', so such sentences are not used."""
    base = re.sub(r"\s*\([^)]*\)", "", title).strip()
    rest = re.sub(r"(?<!\w)" + re.escape(base) + r"(?!\w)", "", sentence, flags=re.I)
    return leaks_title(rest, title)


def neutralize(sentence: str, title: str) -> str:
    """Hide the topic: 'Marie Curie was born...' -> 'The subject was born...'"""
    out = sentence
    for t in sorted(title_terms(title), key=len, reverse=True):
        out = re.sub(r"(?<!\w)" + re.escape(t) + r"(?!\w)", "the subject", out, flags=re.I)
    return out[0].upper() + out[1:]


# ---------- finding a fact to forge ----------
def _forge_date(s, article, rng):
    for m in re.finditer(r"\b(1[0-9]{3}|20[0-2][0-9])\b", s):
        year = int(m.group())
        options = [year + d for d in (-45, -30, -20, -10, -7, -5, 5, 7, 10, 20, 30) if 1000 <= year + d <= 2026]
        rng.shuffle(options)
        for v in options:
            if not contains_value(article, str(v)):
                return m.start(), m.end(), m.group(), str(v)
    return None


def _forge_number(s, article, rng):
    for m in re.finditer(r"\b\d{1,3}(?:,\d{3})+\b|\b\d+\b", s):
        txt = m.group()
        n = int(txt.replace(",", ""))
        before, after = s[:m.start()], s[m.end():]
        if n < 2 or (1000 <= n <= 2029 and "," not in txt):                     # years are dates
            continue
        if re.match(r"\s*(" + MONTHS + r")\b", after) or re.search(r"(" + MONTHS + r")\s*$", before):
            continue                                                            # day of a month
        if re.match(r"\.\d", after) or re.search(r"\d\.$", before):             # decimals
            continue
        for f in rng.sample([2, 0.5, 1.5, 3, 0.75], 5):
            v = round(n * f)
            if v <= 0 or v == n:
                continue
            new = f"{v:,}" if "," in txt else str(v)
            if not contains_value(article, new):
                return m.start(), m.end(), txt, new
    return None


def _forge_place(s, article, rng):
    for group in (CITIES, COUNTRIES):
        for place in sorted(group, key=len, reverse=True):
            m = re.search(r"(?<!\w)" + re.escape(place) + r"(?!\w)", s)
            if m:
                options = [p for p in group if p != place and not contains_value(article, p)]
                if options:
                    return m.start(), m.end(), place, rng.choice(options)
    return None


def _forge_person(s, article, title, rng):
    for m in re.finditer(r"\b([A-Z][a-z]+) ((?:van |von |de |da )?[A-Z][a-z]+)\b", s):
        if m.group(1) in FIRST_NAMES and not leaks_title(m.group(), title):
            options = [p for p in FAKE_PEOPLE if not contains_value(article, p)]
            if options:
                return m.start(), m.end(), m.group(), rng.choice(options)
    return None


# ---------- the builder ----------
def build_case_rules(title: str, article_raw: str, tamper_type: str, category: str = "general",
                     stats: dict | None = None, seed: str | None = None) -> CaseRecord:
    stats = stats if stats is not None else {}
    stats.setdefault("attempts", 0), stats.setdefault("valid", 0), stats.setdefault("durations", [])
    stats["attempts"] += 1
    t0 = time.time()
    rng = random.Random(seed or f"{title}|{tamper_type}")
    article = clean_article(article_raw)
    sentences = split_sentences(article)
    if len(sentences) < 5:
        raise CaseBuildError(f"{title}: not enough usable sentences ({len(sentences)})")

    forged = None
    for s in sentences[:14]:                                   # facts of the introduction come first
        if awkward(s, title):
            continue
        found = {"date": lambda: _forge_date(s, article, rng), "number": lambda: _forge_number(s, article, rng),
                 "place": lambda: _forge_place(s, article, rng),
                 "person": lambda: _forge_person(s, article, title, rng)}[tamper_type]()
        if found:
            a, b, orig, new = found
            forged = (s, s[:a] + new + s[b:], orig, new)
            break
    if not forged:
        raise CaseBuildError(f"{title}: no {tamper_type} found to forge")
    original_sentence, false_sentence, orig, new = forged

    def usable(s):
        n = neutralize(s, title)
        return (s != original_sentence and 25 <= len(s) and not awkward(s, title) and not leaks_title(n, title)
                and not contains_value(n, orig) and not contains_value(n, new))

    candidates = [s for s in sentences if usable(s)]
    candidates.sort(key=lambda s: -(2 * bool(re.search(r"\d", s)) + bool(re.search(r"\b[A-Z][a-z]+", s[1:]))))
    chosen = candidates[:4]
    if len(chosen) < 4:
        raise CaseBuildError(f"{title}: not enough true clues")
    texts = [(neutralize(s, title), False) for s in chosen] + [(neutralize(false_sentence, title), True)]
    rng.shuffle(texts)
    case = Case(case_id=uuid.uuid4().hex[:8], wiki_title=title, category=category, tamper_type=tamper_type,
                clues=[Clue(id=i + 1, text=t, is_false=f) for i, (t, f) in enumerate(texts)],
                original_sentence=original_sentence, false_sentence=false_sentence,
                original_value=orig, false_value=new,
                explanation=f"The file says {new}, but the real {tamper_type} is {orig}.")
    errors = validate_case(case, article)
    if errors:
        raise CaseBuildError(f"{title}: {errors[:2]}")
    stats["valid"] += 1
    stats["durations"].append(round(time.time() - t0, 3))
    return CaseRecord(case=case, article=article)
