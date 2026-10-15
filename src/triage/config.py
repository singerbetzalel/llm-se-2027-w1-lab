"""Per-repo component vocabularies, read from config/repos.toml."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REPOS_TOML = Path(__file__).resolve().parents[2] / "config" / "repos.toml"


def load_components(path: Path = REPOS_TOML) -> dict[str, list[str]]:
    """Map repo key AND full name (e.g. "hono" and "honojs/hono") to its component names."""
    with path.open("rb") as fh:
        data: dict[str, Any] = tomllib.load(fh)
    out: dict[str, list[str]] = {}
    repos: list[dict[str, Any]] = data.get("repos", [])
    for repo in repos:
        components: dict[str, Any] = repo.get("component_labels", {})
        names = sorted(str(name) for name in components)
        out[str(repo["key"])] = names
        out[str(repo["full_name"])] = names
    return out


def repo_key_for(full_name: str, path: Path = REPOS_TOML) -> str:
    """Return the short key for a known "owner/name", or the full name unchanged."""
    with path.open("rb") as fh:
        data: dict[str, Any] = tomllib.load(fh)
    repos: list[dict[str, Any]] = data.get("repos", [])
    for repo in repos:
        if str(repo["full_name"]).lower() == full_name.lower():
            return str(repo["key"])
    return full_name
