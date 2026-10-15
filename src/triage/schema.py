"""Data shapes: what goes into triage and what comes out."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

IssueType = Literal["bug", "enhancement", "documentation", "question", "unknown"]
Severity = Literal["critical", "high", "medium", "low", "unknown"]

ISSUE_TYPES: tuple[IssueType, ...] = ("bug", "enhancement", "documentation", "question", "unknown")
SEVERITIES: tuple[Severity, ...] = ("critical", "high", "medium", "low", "unknown")


class Issue(BaseModel):
    """A GitHub issue as triage sees it. Extra fields (labels, gold_*) are ignored."""

    repo: str
    number: int | None = None
    title: str
    body: str = ""
    url: str | None = None

    @field_validator("body", mode="before")
    @classmethod
    def _null_body_is_empty(cls, value: object) -> object:
        # GitHub returns `"body": null` for issues opened with no description.
        return "" if value is None else value


class TriageRecord(BaseModel):
    """One structured record per issue -- the input to routing."""

    repo: str
    number: int | None
    url: str | None
    issue_type: IssueType
    component: str | None = Field(description="From the repo's own component vocabulary, or null.")
    severity: Severity
    has_reproduction_steps: bool
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    needs_human_review: bool
    rationale: str
    model: str
    error: str | None = None
