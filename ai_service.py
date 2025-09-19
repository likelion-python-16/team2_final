from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List


def recommend_workout_plan(user_id: int, start: date | None = None, weeks: int = 1) -> Dict[str, Any]:
    """Return a simple, deterministic AI-like workout plan suggestion.

    This is a placeholder to be replaced with a real LLM or model call.
    """
    start = start or date.today()
    days = [start + timedelta(days=i) for i in range(7 * weeks)]
    items: List[Dict[str, Any]] = []
    for i, d in enumerate(days):
        if i % 2 == 0:
            items.append({
                "scheduled_date": d,
                "exercise": {"name": "Running", "category": "cardio"},
                "duration_min": 30,
                "intensity": "moderate",
                "notes": "Easy pace",
                "recommended": True,
                "order": 1,
            })
        else:
            items.append({
                "scheduled_date": d,
                "exercise": {"name": "Push-ups", "category": "strength"},
                "sets": 3,
                "reps": 12,
                "intensity": "medium",
                "notes": "Rest 60s",
                "recommended": True,
                "order": 1,
            })
    return {
        "title": "AI Recommended Plan",
        "ai_model": "stub-v1",
        "ai_explanation": "Alternating cardio and strength for balanced progression.",
        "ai_confidence": 0.85,
        "items": items,
    }


def analyze_feedback(text: str) -> Dict[str, Any]:
    """Return a simple analysis for a piece of feedback.

    Placeholder for an AI classifier/summarizer.
    """
    score = 80 if "good" in text.lower() else 60
    summary = text[:140]
    return {
        "ai_model": "stub-v1",
        "ai_explanation": "Heuristic sentiment proxy and short summary.",
        "ai_confidence": 0.7,
        "summary": summary,
        "health_score": score,
    }

