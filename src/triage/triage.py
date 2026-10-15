"""Turn one issue into one validated TriageRecord.

The model is injected as a `Predictor`, so this module never imports DSPy and
can be tested without a network or an API key.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel, Field, ValidationError, field_validator

from triage.schema import Issue, IssueType, Severity, TriageRecord

# Below this, a record is flagged for a human instead of being auto-routed.
REVIEW_THRESHOLD = 0.7
# Long bodies (stack traces, logs) are cut to keep cost bounded.
MAX_BODY_CHARS = 8000


class Predictor(Protocol):
    def __call__(
        self, *, repo: str, title: str, body: str, allowed_components: list[str]
    ) -> Mapping[str, object]: ...


class _ModelOutput(BaseModel):
    """What we accept back from the model. Anything else is a failed triage."""

    issue_type: IssueType
    component: str | None
    severity: Severity
    has_reproduction_steps: bool
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""

    @field_validator("issue_type", "severity", mode="before")
    @classmethod
    def _normalise_label(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


def truncate_body(body: str, limit: int = MAX_BODY_CHARS) -> str:
    if len(body) <= limit:
        return body
    return body[:limit] + "\n\n[... truncated ...]"


def _match_component(raw: str | None, allowed: list[str]) -> str | None:
    if raw is None:
        return None
    wanted = raw.strip().lower()
    return next((name for name in allowed if name.lower() == wanted), None)


def _failed(issue: Issue, model: str, error: str) -> TriageRecord:
    return TriageRecord(
        repo=issue.repo,
        number=issue.number,
        url=issue.url,
        issue_type="unknown",
        component=None,
        severity="unknown",
        has_reproduction_steps=False,
        summary=issue.title[:200],
        confidence=0.0,
        needs_human_review=True,
        rationale="",
        model=model,
        error=error,
    )


def triage(
    issue: Issue, predictor: Predictor, allowed_components: list[str], model: str
) -> TriageRecord:
    """Triage one issue. Never raises on model failure: returns a record flagged for review."""
    try:
        raw = predictor(
            repo=issue.repo,
            title=issue.title,
            body=truncate_body(issue.body),
            allowed_components=allowed_components,
        )
    except Exception as exc:  # any provider/parse failure becomes a review item
        return _failed(issue, model, f"model call failed: {type(exc).__name__}: {exc}")

    try:
        out = _ModelOutput.model_validate(dict(raw))
    except ValidationError as exc:
        return _failed(issue, model, f"model output invalid: {exc.error_count()} error(s)")

    needs_review = out.issue_type == "unknown" or out.confidence < REVIEW_THRESHOLD
    return TriageRecord(
        repo=issue.repo,
        number=issue.number,
        url=issue.url,
        issue_type=out.issue_type,
        component=_match_component(out.component, allowed_components),
        severity=out.severity,
        has_reproduction_steps=out.has_reproduction_steps,
        summary=out.summary.strip(),
        confidence=out.confidence,
        needs_human_review=needs_review,
        rationale=out.rationale.strip(),
        model=model,
    )
