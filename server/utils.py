from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Dict, List

from fastapi import HTTPException


def submission_key(year: int, quarter: str) -> str:
    return f"{year}-{quarter}"


def avg(values: List[float]) -> float:
    return round(mean(values), 2)


def collect_by_form(submissions: List[Any]) -> Dict[str, List[float]]:
    by_form: Dict[str, List[float]] = defaultdict(list)
    for item in submissions:
        by_form[item.form_type].extend(item.answers)
    return by_form


def compute_quarter_score(averages: Dict[str, float]) -> float:
    self_avg = averages.get("self")
    manager_avg = averages.get("manager")
    client_avg = averages.get("client")

    if self_avg is None:
        raise HTTPException(status_code=400, detail="Self feedback missing")
    if manager_avg is None and client_avg is None:
        raise HTTPException(status_code=400, detail="At least one of manager/client feedback is required")

    mgr_client_values = [score for score in [manager_avg, client_avg] if score is not None]
    mgr_client_avg = avg(mgr_client_values)

    return round((self_avg * 0.30) + (mgr_client_avg * 0.70), 2)


def discrepancy_message(averages: Dict[str, float]) -> str | None:
    self_avg = averages.get("self")
    manager_avg = averages.get("manager")
    client_avg = averages.get("client")

    if self_avg is None:
        return None

    alert_msgs: List[str] = []
    if manager_avg is not None and abs(self_avg - manager_avg) > 1:
        alert_msgs.append(f"self vs manager gap is {round(abs(self_avg - manager_avg), 2)}")
    if client_avg is not None and abs(self_avg - client_avg) > 1:
        alert_msgs.append(f"self vs client gap is {round(abs(self_avg - client_avg), 2)}")

    if not alert_msgs:
        return None

    return "Discrepancy alert: " + "; ".join(alert_msgs)


def extract_comment_summary(submissions: List[Any]) -> tuple[List[str], List[str]]:
    positives: List[str] = []
    negatives: List[str] = []

    for item in submissions:
        for raw in item.comments:
            text = raw.strip()
            if not text:
                continue

            lowered = text.lower()
            if any(word in lowered for word in ["improve", "issue", "delay", "weak", "negative", "late", "error"]):
                negatives.append(text)
            else:
                positives.append(text)

    return positives[:8], negatives[:8]


def assess_performance(score: float) -> Dict[str, Any]:
    if score >= 4.5:
        return {
            "level": "Outstanding",
            "strengths": ["Consistent high-quality outcomes", "Strong ownership and collaboration"],
            "improvements": ["Share best practices with peers", "Take stretch goals for the next cycle"],
        }
    if score >= 3.5:
        return {
            "level": "Strong",
            "strengths": ["Reliable execution on core responsibilities", "Healthy team contribution"],
            "improvements": ["Improve speed/consistency on complex tasks", "Increase proactive communication"],
        }
    return {
        "level": "Needs Improvement",
        "strengths": ["Potential to grow with coaching", "Willingness to contribute"],
        "improvements": ["Create a focused improvement plan", "Increase delivery predictability and quality checks"],
    }
