"""The storytelling layer: codenames, briefings, witnesses, verdict and coaching texts.
Everything here works offline (templates). The AI agents (Narrator, Coach) can replace these texts."""
import hashlib

from models import CoachNote

ADJECTIVES = ["Silent", "Crimson", "Midnight", "Hollow", "Ivory", "Broken", "Hidden", "Velvet",
              "Golden", "Forgotten", "Whispering", "Scarlet"]
NOUNS = ["Archive", "Compass", "Lantern", "Ledger", "Telegram", "Cipher", "Mirror", "Key",
         "Manuscript", "Clock", "Signature", "Envelope"]

# The witness for each personality (same names as agents.PERSONAS)
WITNESSES = {
    "Nervous": ("Mr. Albright", "a nervous archive clerk who copied the file by hand"),
    "Proud": ("Dr. Voss", "a proud scholar who is never wrong, he says"),
    "Chatty": ("Mrs. Delacroix", "a chatty librarian who loves to talk"),
    "Grumpy": ("Mr. Kessler", "a grumpy night guard who read the file during his shift"),
}

CATEGORY_HOOKS = {
    "Korea": "The dossier came from the Korea desk of the Archive Bureau.",
    "France": "The dossier arrived in a sealed envelope with a French stamp.",
    "computing and electronics basics": "The dossier was found on an old computer in the Bureau's basement.",
    "history": "The dossier was taken from the oldest shelf of the Archive Bureau.",
    "science": "The dossier was sent by a laboratory that wants an answer before Monday.",
    "famous people": "The dossier is a biography that is about to be published.",
    "famous mysteries and investigations": "The dossier is about an old mystery that people still argue about.",
}

TIPS = {
    "date": "Dates are the easiest fact to forge. Search for the year and compare it with the timeline of the article.",
    "number": "Forgers like to change a number a little. Check units and sizes: is the number realistic?",
    "place": "A forged place is often real, but in the wrong city or country. Check a map or the article's location.",
    "person": "A forged name is often a real person from a similar field. Check who really did what.",
}
TYPE_WORDS = {"date": "dates", "number": "numbers", "place": "places", "person": "names"}


def codename(case_id: str) -> str:
    h = int(hashlib.md5(case_id.encode()).hexdigest(), 16)
    return f"The {ADJECTIVES[h % len(ADJECTIVES)]} {NOUNS[(h // len(ADJECTIVES)) % len(NOUNS)]}"


def witness_identity(persona: str) -> tuple[str, str]:
    return WITNESSES.get(persona, WITNESSES["Nervous"])


def briefing_template(case, persona: str) -> str:
    """Spoiler-free story introduction (no title, no fact of the case)."""
    name, desc = witness_identity(persona)
    hook = CATEGORY_HOOKS.get(case.category, "A dossier reached the Archive Bureau this morning.")
    return (f"{hook} Someone changed one fact before it was filed: four clues are authentic and one is a "
            f"forgery. {name}, {desc}, read the altered file and is waiting in the interview room. "
            f"Find the forgery before the dossier is published.")


def briefing_generic(persona: str) -> str:
    """Last-resort introduction: contains no fact at all."""
    name, desc = witness_identity(persona)
    return (f"A dossier reached the Archive Bureau this morning. Someone changed one fact: four clues are authentic "
            f"and one is a forgery. {name}, {desc}, is waiting in the interview room. Find the forgery.")


def verdict_text(case, correct: bool, accused_id: int, false_id: int) -> str:
    if correct:
        return f"Case closed. Clue {false_id} was the forgery. {case.explanation}"
    return (f"The forger walks free this time. You accused clue {accused_id}, "
            f"but the forgery was clue {false_id}. {case.explanation}")


def coach_template(case, correct: bool, searches: int, questions: int, name: str,
                   weak_type: str | None = None) -> CoachNote:
    """Offline Coach: advice that depends on what the player really did."""
    if correct and searches == 0:
        s = f"{name}, sharp instinct: you found the forgery without searching. A good guess is not proof, so next time verify it."
    elif correct:
        s = f"{name}, well done. You checked the facts before you accused, which is exactly what a fact-checker does."
    elif searches == 0:
        s = f"{name}, you accused without checking the archive. One Wikipedia search would have exposed the change."
    else:
        s = f"{name}, you checked, but the altered fact slipped through. It happens to the best inspectors."
    if not correct and questions >= 3:
        s += " Remember that the witness read the altered file too, so a repeated clue proves nothing."
    tip = TIPS[case.tamper_type]
    if weak_type == case.tamper_type and not correct:
        tip += f" Forged {TYPE_WORDS[weak_type]} are your hardest kind so far, so give them extra time."
    return CoachNote(summary=s, tip=tip)


def greeting(name: str, played: int) -> str:
    if played == 0:
        return f"Welcome to the Bureau, {name}. Your first case is waiting."
    return f"Welcome back, {name}. The Bureau kept your desk ready."


def stamp(correct: bool) -> str:
    return "SOLVED" if correct else "UNSOLVED"
