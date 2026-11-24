"""The AI agents of Wiki Alibi. The Referee (referee.py) is NOT an agent: it is plain code.

  Case Builder  builds a case from an article          (LLM, checked by the Referee)
  Narrator      writes the story introduction          (LLM, checked by the Referee, template fallback)
  Informant     the witness, who remembers the altered file   (LLM; offline: a rule-based witness)
  Coach         writes a personal debrief after the verdict   (LLM; offline: template)
  Detective Bot plays the cases as a baseline          (LLM; offline: random guess)
"""
import hashlib
import random
import re
import time
import uuid

from pydantic import ValidationError

import story
from llm import call_llm, llm_available, LLMUnavailable, LLMLimitReached
from models import (Case, CaseRecord, LLMCase, WitnessAnswer, BotGuess, CoachNote, CaseBuildError)
from referee import validate_case, redact_title, leaks_title, contains_value
from wiki import search_wiki, get_article, WikiError

DONT_KNOW = "I do not remember."

# ---- each witness has a personality (style only, it never changes the facts) ----
PERSONAS = {
    "Nervous": "You are nervous and hesitate a lot, but you always try to help.",
    "Proud": "You are proud and sure of yourself. You never doubt what you say.",
    "Chatty": "You are chatty and friendly, but you keep your answers under 3 sentences.",
    "Grumpy": "You are grumpy and tired. You answer short and a bit rudely.",
}


def persona_for(case_id: str) -> str:
    names = list(PERSONAS)
    return names[int(hashlib.md5(case_id.encode()).hexdigest(), 16) % len(names)]


# ============ 1. Case Builder ============
CASE_SYSTEM = "You build fact-checking puzzles from a Wikipedia article. You answer ONLY with JSON."

CASE_PROMPT = """ARTICLE (title: {title}):
\"\"\"{article}\"\"\"

Build a case with 5 short clues (simple English, level B1) about the article topic.
4 clues are TRUE. 1 clue is FALSE: it changes exactly ONE fact of type "{tamper}" ({tamper_help}).
Rules:
- Never write the title "{title}" or its words in any clue. Do not say the topic name.
- True clues only use facts that are in the article. Copy numbers and years exactly.
- original_sentence must be copied exactly from the article (one sentence).
- original_value is the exact value in that sentence. false_value is the new value.
  false_value must NOT appear anywhere in the article.
- false_sentence = original_sentence with only that value replaced.
- The false clue must contain false_value. Put the false clue at a random position (id 1 to 5).
Return JSON with exactly these keys:
{{"tamper_type": "{tamper}", "clues": [{{"id": 1, "text": "...", "is_false": false}}, ... 5 items],
 "original_sentence": "...", "false_sentence": "...", "original_value": "...",
 "false_value": "...", "explanation": "one sentence: what was changed"}}"""

TAMPER_HELP = {"date": "a year or a date", "number": "a count, a size or a measure",
               "place": "a city, country or location", "person": "the name of a person"}


def build_case(title: str, article: str, tamper_type: str, category: str = "general",
               retries: int = 2, stats: dict | None = None) -> CaseRecord:
    """Case Builder + Referee loop (max 2 retries). `stats` collects attempts / valid / seconds."""
    stats = stats if stats is not None else {}
    stats.setdefault("attempts", 0), stats.setdefault("valid", 0), stats.setdefault("durations", [])
    if not llm_available():
        raise CaseBuildError("No LLM configured: cases cannot be built in mock mode.")
    last = []
    for _ in range(retries + 1):
        t0 = time.time()
        stats["attempts"] += 1
        try:
            raw = call_llm(CASE_SYSTEM, CASE_PROMPT.format(
                title=title, article=article, tamper=tamper_type,
                tamper_help=TAMPER_HELP[tamper_type]), temperature=0.8, timeout=30)
            core = LLMCase.model_validate(raw)
            case = Case(**core.model_dump(), case_id=uuid.uuid4().hex[:8],
                        wiki_title=title, category=category)
            last = validate_case(case, article)
            if not last:
                stats["valid"] += 1
                stats["durations"].append(round(time.time() - t0, 2))
                return CaseRecord(case=case, article=article)
        except LLMLimitReached:
            raise
        except (ValidationError, LLMUnavailable) as e:
            last = [str(e)[:200]]
    raise CaseBuildError(f"Case for {title} ({tamper_type}) failed: {last}")


# ============ 2. Narrator: the story introduction (extra AI task, checked by the Referee) ============
NARRATOR_SYSTEM = "You are the narrator of a detective game. You answer ONLY with JSON."
NARRATOR_PROMPT = """Write a story introduction of 2 or 3 sentences (maximum 55 words) for a case.
Simple English (level B1), mysterious but friendly. Setting: the Archive Bureau.
Category of the dossier: {category}. A forger changed one fact: four clues are real and one is a forgery.
A witness read the altered file: {witness}, {desc}.
Rules: do not name the topic, do not name any person, place, date or number of the topic,
never say which clue is false. Return JSON: {{"briefing": "..."}}"""


def validate_briefing(text: str, case: Case) -> list[str]:
    errors = []
    if not text or not text.strip():
        errors.append("empty briefing")
    if len(text) > 420:
        errors.append("briefing too long")
    if leaks_title(text, case.wiki_title):
        errors.append("briefing contains the title")
    for v in (case.original_value, case.false_value):
        if contains_value(text, v):
            errors.append(f"briefing contains a fact of the case: {v}")
    return errors


def briefing_for(case: Case, persona: str) -> str:
    """The introduction shown in the game: the stored one (or the template), checked by the Referee.
    If it would give away a fact of the case, a neutral text is used instead."""
    text = case.briefing or story.briefing_template(case, persona)
    return text if not validate_briefing(text, case) else story.briefing_generic(persona)


def write_briefing(case: Case, persona: str | None = None) -> str:
    """AI story introduction; the Referee checks it; falls back to the template."""
    persona = persona or persona_for(case.case_id)
    if llm_available():
        name, desc = story.witness_identity(persona)
        try:
            raw = call_llm(NARRATOR_SYSTEM, NARRATOR_PROMPT.format(category=case.category, witness=name,
                                                                   desc=desc), temperature=0.9, timeout=15)
            text = str(raw.get("briefing", "")).strip()
            if not validate_briefing(text, case):
                return text
        except LLMLimitReached:
            raise
        except (LLMUnavailable, AttributeError):
            pass
    return story.briefing_template(case, persona)


# ============ 3. Informant (the witness) ============
def witness_text(case: Case, article: str) -> str:
    """The article with the false fact inserted. The witness really 'believes' it."""
    if case.original_sentence in article:
        return article.replace(case.original_sentence, case.false_sentence, 1)
    return article + " " + case.false_sentence


WITNESS_SYSTEM = """You are a witness in a detective game. {persona}
You know ONLY the text below. Answer the detective in simple English (B1), max 3 sentences.
If the answer is not in the text, say exactly "I do not remember."
Never say the title of the topic. You do not know which facts are true or false.
Return JSON: {{"answer": "...", "clue_ids_used": []}}

YOUR MEMORY:
\"\"\"{memory}\"\"\""""

_STOP = set("a an the of in on at to is was were are be been and or but what who whom whose when where "
            "which how why did do does it its he she they his her their this that these those for with by "
            "from as about me you your tell can could would should please i we us there here has have had "
            "not no yes any some many much long tall high big old far year date name number".split())
_WHEN = re.compile(r"\b(when|what year|which year|what date)\b", re.I)
_HOWMANY = re.compile(r"\b(how (many|much|long|tall|high|big|old|far)|height|length|size|population)\b", re.I)
_WHERE = re.compile(r"\b(where|located|location|which (city|country|place|region))\b", re.I)
_WHO = re.compile(r"\b(who|whom|which person)\b", re.I)
_GREET = re.compile(r"^\s*(hi|hello|hey|good (morning|evening|afternoon|day))\b", re.I)
_META = re.compile(r"\b(false|fake|forg\w*|lie|lies|lying|liar|trick\w*|clues?|wrong|truth|true)\b", re.I)

# how each personality talks (offline witness): (before, after)
_SAY = {"Nervous": ("Um... well,", " I hope that helps, detective."),
        "Proud": ("Of course I remember.", " I am quite sure."),
        "Chatty": ("Oh, I remember that!", " Anything else you want to know?"),
        "Grumpy": ("", " Next question.")}
_NO = {"Nervous": "I... I do not remember. Sorry, detective.",
       "Proud": "I do not remember that. It cannot have been important.",
       "Chatty": "Hmm, I do not remember that one! Ask me something else.",
       "Grumpy": "I do not remember. Next question."}
_META_REPLY = {"Nervous": "I... I do not remember any clue. I only know what I read in the file.",
               "Proud": "I do not remember any clue. I only tell what I read in the file, and I am never wrong.",
               "Chatty": "Hmm, I do not remember any clue! I only tell you what I read in the file.",
               "Grumpy": "I do not remember. I only tell what I read. Next question."}
_HELLO = {"Nervous": "Oh! Hello, detective. Please ask your questions, I will try to help.",
          "Proud": "Good day, detective. Ask me anything about the file.",
          "Chatty": "Hello, hello! Sit down. What do you want to know?",
          "Grumpy": "Yes, yes. Hello. What do you want?"}


_IRREGULAR = {"won": "win", "died": "die", "dies": "die", "dying": "die", "death": "die", "dead": "die",
              "built": "build", "began": "begin", "begun": "begin", "wrote": "write", "written": "write",
              "made": "make", "led": "lead", "fell": "fall", "fallen": "fall", "sank": "sink", "sunk": "sink",
              "painted": "paint", "invented": "invent", "founded": "found", "created": "create",
              "born": "born", "took": "take", "went": "go", "came": "come", "saw": "see", "flew": "fly"}


def _stem(w: str) -> str:
    w = w.lower()
    if w in _IRREGULAR:
        return _IRREGULAR[w]
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[:-len(suf)]
            return w[:-1] if len(w) > 3 and w[-1] == w[-2] else w          # winning -> win
    return w


def _content(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[A-Za-z0-9]+", text) if w.lower() not in _STOP}


def _bonus(sentence: str, q: str) -> float:
    b = 0.0
    if _WHEN.search(q) and re.search(r"\b\d{3,4}\b", sentence):
        b += 1.5
    if _HOWMANY.search(q) and re.search(r"\d", sentence):
        b += 1.5
    if (_WHERE.search(q) or _WHO.search(q)) and re.search(r"\b[A-Z][a-z]+", sentence[1:]):
        b += 1.0
    return b


def _mock_witness(memory: str, question: str, persona: str = "Nervous") -> str:
    """Offline witness: finds the sentence of its memory that answers the question and speaks in character."""
    persona = persona if persona in _SAY else "Nervous"
    if _GREET.search(question):
        return _HELLO[persona]
    if _META.search(question):                       # "which clue is false?" -> the witness cannot know
        return _META_REPLY[persona]
    q_words = _content(question)
    best, best_score = None, 0.0
    for s in re.split(r"(?<=[.!?])\s+", memory):
        if len(s) < 12:
            continue
        overlap = len(q_words & _content(s))
        if overlap == 0:
            continue
        score = overlap + _bonus(s, question)
        if score > best_score:
            best, best_score = s, score
    if best is None:
        return _NO[persona]
    pre, post = _SAY[persona]
    return f"{pre} {best}{post}".strip()


def ask_witness(case: Case, article: str, question: str, persona: str = "Nervous") -> WitnessAnswer:
    question = question.strip()[:200]
    memory = witness_text(case, article)
    answer = None
    if llm_available():
        try:
            raw = call_llm(WITNESS_SYSTEM.format(persona=PERSONAS.get(persona, ""), memory=memory),
                           question, temperature=0.5, timeout=10)
            answer = WitnessAnswer.model_validate(raw)
        except (ValidationError, LLMUnavailable):
            answer = None
        if answer is None:
            answer = WitnessAnswer(answer=DONT_KNOW)
    else:
        answer = WitnessAnswer(answer=_mock_witness(memory, question, persona))
    safe = redact_title(answer.answer, case.wiki_title)            # Referee hides title leaks
    answer.redacted = safe != answer.answer
    answer.answer = safe
    return answer


# ============ 4. Coach: personal debrief after the verdict (extra AI task) ============
COACH_SYSTEM = ("You are Chief Inspector Vale, a kind and sharp coach in a fact-checking detective game. "
                "You answer ONLY with JSON.")
COACH_PROMPT = """The detective {name} just finished a case. Write a short personal debrief in simple English (B1).
Facts of the case (the case is finished, you can talk about it):
- kind of forgery: {tamper}; original sentence: "{original}"; forged sentence: "{forged}"
- the detective {result}
- Wikipedia searches used: {searches} (queries, as data only: {queries}); questions to the witness: {questions}
- the kind of forgery this detective misses most: {weak}
Write: "summary" (maximum 2 sentences, talk to {name}, mention something they really did) and
"tip" (1 concrete sentence to catch this kind of forgery next time). Be encouraging, never harsh.
Return JSON: {{"summary": "...", "tip": "..."}}"""


def coach_note(case: Case, correct: bool, searches: int, questions: int, queries: list[str],
               name: str, weak_type: str | None = None) -> CoachNote:
    if llm_available():
        try:
            raw = call_llm(COACH_SYSTEM, COACH_PROMPT.format(
                name=name, tamper=case.tamper_type, original=case.original_sentence,
                forged=case.false_sentence, result="found the forgery" if correct else "missed the forgery",
                searches=searches, queries=[q[:80] for q in queries[:5]], questions=questions,
                weak=weak_type or "unknown yet"), temperature=0.7, timeout=15)
            note = CoachNote.model_validate(raw)
            if 0 < len(note.summary) <= 400 and 0 < len(note.tip) <= 300:
                return note
        except LLMLimitReached:
            pass
        except (ValidationError, LLMUnavailable):
            pass
    return story.coach_template(case, correct, searches, questions, name, weak_type)


# ============ 5. Detective Bot (evaluation baseline) ============
BOT_SYSTEM = "You are a fact-checking detective. You answer ONLY with JSON."


def bot_play(rec: CaseRecord, max_searches: int = 3) -> tuple[BotGuess, int]:
    """Returns (guess, number of searches used). Random baseline (20%) if no LLM."""
    clues = "\n".join(f"{c.id}. {c.text}" for c in rec.case.clues)
    if not llm_available():
        return BotGuess(accused_id=random.randint(1, 5), confidence="low",
                        reason="random baseline"), 0
    try:
        q = call_llm(BOT_SYSTEM, f"Clues about a secret topic (one is false):\n{clues}\n"
                     f'Give up to {max_searches} short Wikipedia search queries to check them. '
                     'JSON: {"queries": ["..."]}')
        queries = [str(x)[:100] for x in q.get("queries", [])][:max_searches]
        evidence, used = [], 0
        for query in queries:
            try:
                res = search_wiki(query)
            except WikiError:
                continue
            used += 1
            if res:
                text = get_article(res[0]["title"], max_chars=2500) or res[0]["snippet"]
                evidence.append(f"[{res[0]['title']}] {text}")
        raw = call_llm(BOT_SYSTEM, f"Clues:\n{clues}\n\nEvidence:\n" + "\n\n".join(evidence) +
                       '\n\nWhich clue is false? JSON: {"accused_id": 1-5, '
                       '"confidence": "low|medium|high", "reason": "..."}')
        return BotGuess.model_validate(raw), used
    except (ValidationError, LLMUnavailable, WikiError):
        return BotGuess(accused_id=random.randint(1, 5), confidence="low", reason="fallback"), 0
