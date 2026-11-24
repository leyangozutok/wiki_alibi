"""Pydantic schemas: every LLM answer is validated with these before it is used."""
from typing import Literal
from pydantic import BaseModel, Field

TamperType = Literal["date", "number", "place", "person"]
Confidence = Literal["low", "medium", "high"]


class Clue(BaseModel):
    id: int
    text: str
    is_false: bool


class LLMCase(BaseModel):
    """What the Case Builder agent must return (the code adds case_id etc.)."""
    tamper_type: TamperType
    clues: list[Clue]
    original_sentence: str
    false_sentence: str
    original_value: str   # exact value in the article (e.g. "1911")
    false_value: str      # the changed value (e.g. "1921")
    explanation: str


class Case(LLMCase):
    case_id: str
    wiki_title: str
    category: str = "general"
    briefing: str = ""          # story introduction (Narrator agent); empty = template story


class CaseRecord(BaseModel):
    """A case saved on disk together with its article text (for offline play)."""
    case: Case
    article: str


class WitnessAnswer(BaseModel):
    answer: str
    clue_ids_used: list[int] = []
    redacted: bool = False      # set by the Referee when the title had to be hidden


class BotGuess(BaseModel):
    accused_id: int = Field(ge=1, le=5)
    confidence: Confidence = "medium"
    reason: str = ""


class CoachNote(BaseModel):
    """Debrief written by the Coach agent after the verdict."""
    summary: str
    tip: str


class CaseBuildError(Exception):
    pass
