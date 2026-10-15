"""Fetch a single issue from the GitHub REST API (no shell, no third-party client)."""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

from dotenv import load_dotenv

from triage.config import repo_key_for
from triage.schema import Issue

_ISSUE_URL = re.compile(r"^https://github\.com/([\w.-]+)/([\w.-]+)/issues/(\d+)/?$")


def parse_issue_url(url: str) -> tuple[str, str, int]:
    """Split https://github.com/owner/repo/issues/N into (owner, repo, N)."""
    match = _ISSUE_URL.match(url.strip())
    if match is None:
        raise ValueError(f"not a GitHub issue URL: {url!r}")
    return match.group(1), match.group(2), int(match.group(3))


def fetch_issue(url: str, timeout: float = 15.0) -> Issue:
    owner, name, number = parse_issue_url(url)
    load_dotenv()
    request = urllib.request.Request(
        f"https://api.github.com/repos/{owner}/{name}/issues/{number}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "llm-se-2027-triage"},
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    if "pull_request" in data:
        raise ValueError(f"{url} is a pull request, not an issue")
    return Issue(
        repo=repo_key_for(f"{owner}/{name}"),
        number=number,
        title=str(data.get("title") or ""),
        body=data.get("body") or "",
        url=str(data.get("html_url") or url),
    )
