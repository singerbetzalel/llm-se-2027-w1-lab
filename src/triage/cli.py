"""Command line: read an issue, print its triage record as JSON.

    uv run python -m triage.cli --url https://github.com/honojs/hono/issues/3969
    uv run python -m triage.cli --file issue.json        # one issue object; "-" = stdin
    uv run python -m triage.cli --split dev --repo hono --number 3969
    uv run python -m triage.cli --split dev --limit 20   # JSON Lines, one record per issue

The sealed test split is deliberately not accepted.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from triage.config import load_components
from triage.schema import Issue
from triage.triage import Predictor, triage

SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "snapshot"
OPEN_SPLITS = ("train", "dev")


def _load_split(split: str) -> list[Issue]:
    if split not in OPEN_SPLITS:
        raise ValueError(f"split {split!r} is not allowed (test is sealed)")
    rows: list[dict[str, Any]] = json.loads(
        (SNAPSHOT_DIR / f"{split}.json").read_text(encoding="utf-8")
    )
    return [Issue.model_validate(row) for row in rows]


def _select(issues: list[Issue], repo: str | None, number: int | None) -> list[Issue]:
    return [
        i
        for i in issues
        if (repo is None or i.repo == repo) and (number is None or i.number == number)
    ]


def _read_issues(args: argparse.Namespace) -> list[Issue]:
    if args.url:
        from triage.github import fetch_issue

        return [fetch_issue(args.url)]
    if args.file:
        text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text("utf-8")
        return [Issue.model_validate_json(text)]
    issues = _select(_load_split(args.split), args.repo, args.number)
    if not issues:
        raise ValueError("no matching issue in the snapshot")
    if args.number is None:
        return issues[: args.limit]
    return issues[:1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="triage", description="Triage a GitHub issue.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url", help="GitHub issue URL to fetch")
    source.add_argument("--file", help="JSON file with one issue object, or - for stdin")
    source.add_argument("--split", choices=OPEN_SPLITS, help="read from data/snapshot")
    parser.add_argument("--repo", help="with --split: filter by repo key")
    parser.add_argument("--number", type=int, help="with --split: pick one issue number")
    parser.add_argument("--limit", type=int, default=1, help="with --split: how many issues")
    parser.add_argument("--model", help="override LLM_MODEL")
    return parser


def main(argv: Sequence[str] | None = None, predictor: Predictor | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        issues = _read_issues(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    model = args.model or "unknown"
    if predictor is None:
        from triage.extract import DSPyPredictor

        dspy_predictor = DSPyPredictor(args.model)
        predictor, model = dspy_predictor, dspy_predictor.model

    components = load_components()
    many = len(issues) > 1
    for issue in issues:
        record = triage(issue, predictor, components.get(issue.repo, []), model)
        print(record.model_dump_json() if many else record.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
