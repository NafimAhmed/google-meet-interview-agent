"""Domain models used by the interview workflow."""

from dataclasses import dataclass
from typing import Any, Dict, List, TypedDict


@dataclass(frozen=True)
class InterviewProfile:
    candidate_name: str
    role: str
    level: str
    interview_type: str
    language: str
    total_questions: int


class Evaluation(TypedDict):
    score: int
    feedback: str
    correct_answer: str
    is_follow_up_needed: bool
    follow_up_question: str


class HistoryItem(TypedDict):
    question_no: int
    question: str
    answer: str
    score: int
    feedback: str
    correct_answer: str


Report = Dict[str, Any]
History = List[HistoryItem]
