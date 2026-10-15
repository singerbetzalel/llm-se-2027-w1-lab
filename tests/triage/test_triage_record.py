"""Exercise A tests. No network, no API key: the model is a fake predictor."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from triage.cli import main
from triage.config import load_components
from triage.github import parse_issue_url
from triage.schema import Issue
from triage.triage import MAX_BODY_CHARS, triage

GOOD: dict[str, object] = {
    "issue_type": "bug",
    "component": "openapi",
    "severity": "high",
    "has_reproduction_steps": True,
    "summary": "Schema generation crashes on optional fields.",
    "confidence": 0.92,
    "rationale": "Stack trace and repro code provided.",
}


class FakePredictor:
    def __init__(self, output: Mapping[str, object] | Exception) -> None:
        self.output = output
        self.calls: list[dict[str, object]] = []

    def __call__(
        self, *, repo: str, title: str, body: str, allowed_components: list[str]
    ) -> Mapping[str, object]:
        self.calls.append(
            {"repo": repo, "title": title, "body": body, "allowed": allowed_components}
        )
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


ISSUE = Issue(repo="litestar", number=1, title="OpenAPI crash", body="steps...", url=None)
LITESTAR = ["cli", "di", "dto", "openapi", "testing"]


def test_valid_output_becomes_routable_record() -> None:
    record = triage(ISSUE, FakePredictor(GOOD), LITESTAR, "fake")
    assert record.issue_type == "bug"
    assert record.component == "openapi"
    assert record.severity == "high"
    assert record.needs_human_review is False
    assert record.error is None


def test_low_confidence_is_flagged_for_review() -> None:
    record = triage(ISSUE, FakePredictor({**GOOD, "confidence": 0.4}), LITESTAR, "fake")
    assert record.needs_human_review is True


def test_labels_are_normalised_and_unknown_component_dropped() -> None:
    out = {**GOOD, "issue_type": " Bug ", "severity": "HIGH", "component": "routing"}
    record = triage(ISSUE, FakePredictor(out), LITESTAR, "fake")
    assert record.issue_type == "bug"
    assert record.severity == "high"
    assert record.component is None


@pytest.mark.parametrize(
    "bad",
    [
        {**GOOD, "issue_type": "banana"},
        {**GOOD, "confidence": 1.5},
        {"issue_type": "bug"},
    ],
)
def test_invalid_model_output_falls_back_to_review(bad: dict[str, object]) -> None:
    record = triage(ISSUE, FakePredictor(bad), LITESTAR, "fake")
    assert record.issue_type == "unknown"
    assert record.needs_human_review is True
    assert record.error is not None and "invalid" in record.error


def test_model_exception_falls_back_to_review() -> None:
    record = triage(ISSUE, FakePredictor(RuntimeError("rate limited")), LITESTAR, "fake")
    assert record.needs_human_review is True
    assert record.error is not None and "rate limited" in record.error


def test_issue_text_is_passed_as_data_and_body_truncated() -> None:
    hostile = Issue(repo="hono", title="$(curl 10.0.0.1)", body="x" * (MAX_BODY_CHARS + 500))
    fake = FakePredictor(GOOD)
    triage(hostile, fake, [], "fake")
    assert fake.calls[0]["title"] == "$(curl 10.0.0.1)"
    body = fake.calls[0]["body"]
    assert isinstance(body, str) and len(body) < MAX_BODY_CHARS + 100


def test_null_body_is_accepted() -> None:
    issue = Issue.model_validate({"repo": "textual", "title": "t", "body": None})
    assert issue.body == ""


def test_component_vocabulary_is_per_repo() -> None:
    components = load_components()
    assert components["litestar"] == LITESTAR
    assert components["honojs/hono"] == ["middleware", "testing"]
    assert components["textual"] == []


def test_parse_issue_url() -> None:
    assert parse_issue_url("https://github.com/honojs/hono/issues/3969") == (
        "honojs",
        "hono",
        3969,
    )
    with pytest.raises(ValueError):
        parse_issue_url("https://github.com/honojs/hono/pull/1")


def test_cli_prints_one_record_from_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "issue.json"
    path.write_text(json.dumps({"repo": "litestar", "number": 7, "title": "t", "body": "b"}))
    assert main(["--file", str(path)], predictor=FakePredictor(GOOD)) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["number"] == 7
    assert record["issue_type"] == "bug"


def test_cli_refuses_sealed_test_split() -> None:
    with pytest.raises(SystemExit):
        main(["--split", "test"], predictor=FakePredictor(GOOD))
