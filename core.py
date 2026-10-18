from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable


@dataclass(frozen=True)
class RiskAssessment:
    score: float
    level: str
    reasons: tuple[str, ...]


def text_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").strip(), (b or "").strip()).ratio()


def assess_overreliance(
    latency_seconds: float,
    ai_answer: str,
    edited_answer: str,
    action: str,
) -> RiskAssessment:
    """Transparent demonstration heuristic.

    This is intentionally interpretable and is not a validated psychological
    instrument. It is designed to make the prototype logic auditable.
    """
    score = 0.0
    reasons: list[str] = []

    if latency_seconds < 8:
        score += 0.40
        reasons.append("very fast acceptance")
    elif latency_seconds < 20:
        score += 0.20
        reasons.append("fast acceptance")

    similarity = text_similarity(ai_answer, edited_answer)
    if similarity > 0.97:
        score += 0.35
        reasons.append("almost no revision")
    elif similarity > 0.85:
        score += 0.20
        reasons.append("minimal revision")

    if action == "Accept":
        score += 0.20
        reasons.append("explicit acceptance")

    score = min(round(score, 3), 1.0)
    level = "High" if score >= 0.65 else "Medium" if score >= 0.35 else "Low"
    return RiskAssessment(score, level, tuple(reasons))


def should_trigger(condition: str, assessment: RiskAssessment) -> bool:
    if condition == "Static Reflection":
        return True
    if condition == "Adaptive Reflection":
        return assessment.level in {"Medium", "High"}
    return False


def build_reflection_prompt(reasons: Iterable[str]) -> str:
    rationale = ", ".join(reasons) or "limited independent revision"
    return (
        "Before finalizing your decision:\n\n"
        "1. What assumption in the AI response might be wrong?\n"
        "2. What evidence would change your decision?\n"
        "3. Give one alternative answer or counterargument.\n\n"
        f"Trigger rationale: {rationale}."
    )


def revision_delta(ai_answer: str, final_answer: str) -> float:
    """0 means unchanged; 1 means maximally different."""
    return round(1.0 - text_similarity(ai_answer, final_answer), 3)
