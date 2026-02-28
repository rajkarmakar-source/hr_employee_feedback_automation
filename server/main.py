from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator
from utils import (
    assess_performance,
    avg,
    collect_by_form,
    compute_quarter_score,
    discrepancy_message,
    extract_comment_summary,
    submission_key,
)

app = FastAPI(title="HR Employee Feedback Automation")

FormType = Literal["self", "manager", "client", "peer"]


class FeedbackSubmission(BaseModel):
    employee_id: str = Field(..., min_length=1)
    employee_name: str = Field(..., min_length=1)
    quarter: Literal["Q1", "Q2", "Q3", "Q4"]
    year: int = Field(..., ge=2000, le=2100)
    form_type: FormType
    answers: List[float] = Field(..., min_length=1)
    comments: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scores(self) -> "FeedbackSubmission":
        for score in self.answers:
            if score < 1 or score > 5:
                raise ValueError("All scores must be between 1 and 5")
        return self


class FollowupPlanRequest(BaseModel):
    start_date: date
    deadline: date
    minimum_followups: int = Field(default=5, ge=5)


class PerformanceAssessment(BaseModel):
    level: str
    strengths: List[str]
    improvements: List[str]


class QuarterSummary(BaseModel):
    employee_id: str
    employee_name: str
    year: int
    quarter: str
    average_by_form: Dict[str, float]
    appraisal_score: float
    discrepancy_alert: bool
    discrepancy_message: str | None = None
    performance_level: str
    positive_summary: List[str]
    negative_summary: List[str]


feedback_store: Dict[str, Dict[str, List[FeedbackSubmission]]] = defaultdict(lambda: defaultdict(list))
employee_directory: Dict[str, str] = {}


def _quarter_summary(employee_id: str, year: int, quarter: str) -> QuarterSummary:
    key = submission_key(year, quarter)
    submissions = feedback_store[employee_id].get(key, [])
    if not submissions:
        raise HTTPException(status_code=404, detail="No feedback found for this employee quarter")

    averages_raw = collect_by_form(submissions)
    averages = {form: avg(scores) for form, scores in averages_raw.items()}

    appraisal_score = compute_quarter_score(averages)
    performance = PerformanceAssessment(**assess_performance(appraisal_score))
    discrepancy_msg = discrepancy_message(averages)
    positive_summary, negative_summary = extract_comment_summary(submissions)

    return QuarterSummary(
        employee_id=employee_id,
        employee_name=employee_directory.get(employee_id, "Unknown"),
        year=year,
        quarter=quarter,
        average_by_form=averages,
        appraisal_score=appraisal_score,
        discrepancy_alert=discrepancy_msg is not None,
        discrepancy_message=discrepancy_msg,
        performance_level=performance.level,
        positive_summary=positive_summary,
        negative_summary=negative_summary,
    )


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/feedback")
def submit_feedback(payload: FeedbackSubmission) -> dict:
    key = submission_key(payload.year, payload.quarter)
    feedback_store[payload.employee_id][key].append(payload)
    employee_directory[payload.employee_id] = payload.employee_name

    return {
        "status": "recorded",
        "employee_id": payload.employee_id,
        "key": key,
        "form_type": payload.form_type,
    }


@app.get("/employees/{employee_id}/quarters/{year}/{quarter}", response_model=QuarterSummary)
def get_employee_quarter(employee_id: str, year: int, quarter: Literal["Q1", "Q2", "Q3", "Q4"]) -> QuarterSummary:
    return _quarter_summary(employee_id, year, quarter)


@app.get("/employees/{employee_id}/yearly/{year}")
def get_employee_yearly(employee_id: str, year: int) -> dict:
    quarter_scores: Dict[str, float] = {}
    quarter_summaries: Dict[str, dict] = {}

    for quarter in ["Q1", "Q2", "Q3", "Q4"]:
        try:
            summary = _quarter_summary(employee_id, year, quarter)
        except HTTPException:
            continue
        quarter_scores[quarter] = summary.appraisal_score
        quarter_summaries[quarter] = summary.model_dump()

    if not quarter_scores:
        raise HTTPException(status_code=404, detail="No yearly data found")

    yearly_score = avg(list(quarter_scores.values()))
    performance = PerformanceAssessment(**assess_performance(yearly_score))

    hr_email = {
        "to": "hr-team@company.com",
        "subject": f"{year} Annual Performance Report: {employee_directory.get(employee_id, employee_id)} ({employee_id})",
        "body": (
            f"Yearly score: {yearly_score}/5. "
            f"Performance level: {performance.level}. "
            f"Key strengths: {', '.join(performance.strengths)}. "
            f"Improvement areas: {', '.join(performance.improvements)}."
        ),
    }

    return {
        "employee_id": employee_id,
        "employee_name": employee_directory.get(employee_id, "Unknown"),
        "year": year,
        "quarter_scores": quarter_scores,
        "yearly_score": yearly_score,
        "performance_assessment": performance.model_dump(),
        "quarter_summaries": quarter_summaries,
        "hr_email_preview": hr_email,
    }


@app.post("/followups/plan")
def generate_followup_plan(payload: FollowupPlanRequest) -> dict:
    if payload.deadline <= payload.start_date:
        raise HTTPException(status_code=400, detail="deadline must be after start_date")

    total_days = (payload.deadline - payload.start_date).days
    slots = payload.minimum_followups + 1
    gap = max(total_days // slots, 1)

    followup_dates = [
        payload.start_date + timedelta(days=gap * i)
        for i in range(1, payload.minimum_followups + 1)
    ]

    followup_dates = [d for d in followup_dates if d < payload.deadline]

    while len(followup_dates) < payload.minimum_followups:
        candidate = payload.deadline - timedelta(days=(payload.minimum_followups - len(followup_dates)))
        if candidate <= payload.start_date:
            candidate = payload.start_date + timedelta(days=len(followup_dates) + 1)
        if candidate not in followup_dates and candidate < payload.deadline:
            followup_dates.append(candidate)
        else:
            break

    followup_dates = sorted(followup_dates)[: payload.minimum_followups]

    return {
        "start_date": payload.start_date,
        "deadline": payload.deadline,
        "minimum_followups": payload.minimum_followups,
        "planned_followup_dates": followup_dates,
    }


@app.get("/employees/{employee_id}/alerts/{year}/{quarter}")
def get_quarter_alert(employee_id: str, year: int, quarter: Literal["Q1", "Q2", "Q3", "Q4"]) -> dict:
    summary = _quarter_summary(employee_id, year, quarter)

    if not summary.discrepancy_alert:
        return {
            "alert_required": False,
            "message": "No discrepancy alert needed",
        }

    return {
        "alert_required": True,
        "to": "hr-team@company.com",
        "subject": f"Rating discrepancy alert for {summary.employee_name} ({employee_id})",
        "message": summary.discrepancy_message,
    }


@app.get("/employees/{employee_id}/quarters/{year}/{quarter}/hr-mail")
def get_quarter_hr_mail(employee_id: str, year: int, quarter: Literal["Q1", "Q2", "Q3", "Q4"]) -> dict:
    summary = _quarter_summary(employee_id, year, quarter)

    return {
        "to": "hr-team@company.com",
        "subject": f"Quarterly Performance Report {year}-{quarter}: {summary.employee_name} ({employee_id})",
        "body": (
            f"Appraisal score: {summary.appraisal_score}/5. "
            f"Performance level: {summary.performance_level}. "
            f"Discrepancy alert: {summary.discrepancy_alert}. "
            f"Positive highlights: {', '.join(summary.positive_summary) if summary.positive_summary else 'None'}. "
            f"Improvement highlights: {', '.join(summary.negative_summary) if summary.negative_summary else 'None'}."
        ),
    }


@app.get("/employees/{employee_id}/yearly/{year}/hr-mail")
def get_yearly_hr_mail(employee_id: str, year: int) -> dict:
    yearly_data = get_employee_yearly(employee_id, year)
    return yearly_data["hr_email_preview"]
