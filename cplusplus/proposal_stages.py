from __future__ import annotations

import datetime
import logging
import os
import re
from typing import Dict, List

import requests
from dotenv import load_dotenv

from cplusplus.models import Proposal, StageEvent

# Load environment variables from a local .env file
load_dotenv()


def _parse_iso(dt: str | None) -> datetime.datetime:
    """Parses GitHub ISO 8601 strings to UTC datetime objects."""
    if not dt:
        return datetime.datetime.fromtimestamp(0, datetime.timezone.utc)
    # Handle the 'Z' suffix by converting it to +00:00 for ISO format compatibility
    return datetime.datetime.fromisoformat(dt.replace("Z", "+00:00"))


def add_proposal_stages_from_github(proposals: dict[str, Proposal]) -> dict[str, Proposal]:
    """
    Fetch issues/PRs from cplusplus/papers and attach StageEvent entries.
    Uses GITHUB_TOKEN from .env to increase rate limits.
    """

    # Authenticate using the token from your .env file
    token = os.environ.get("GITHUB_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        # It's helpful to know if the token didn't load, as unauthenticated
        # requests to the GitHub API are capped at 60 per hour.
        print(
            "Warning: GITHUB_TOKEN not found in environment. Rate limits will be restricted."
        )

    owner = "cplusplus"
    repo = "papers"
    per_page = 100
    page = 1

    events_map: Dict[str, List[StageEvent]] = {}
    # Match proposal IDs starting with P or N (e.g., P1234 or N1234), optionally with a revision like R1
    proposal_id_re = re.compile(r"([PN]\d+)(?:\s*R\d+)?", re.IGNORECASE)

    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = {"state": "all", "per_page": per_page, "page": page}

        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()

        issues = resp.json()
        if not issues:
            break

        for issue in issues:
            title = issue["title"]
            m = proposal_id_re.search(title)
            if not m:
                logging.warning(
                    f"Skipping issue #{issue['number']} with title '{title}' - no proposal ID found"
                )
                continue

            # Normalize base_id to lowercase for consistent mapping (e.g., p1234)
            base_id = m.group(1).lower()

            created_at = _parse_iso(issue["created_at"])
            ev_open = StageEvent(proposal_id=base_id, created_at=created_at, stage="open")
            events_map.setdefault(base_id, []).append(ev_open)

            status = issue["state"]
            if status == "closed":
                closed_at = _parse_iso(issue["closed_at"])
                ev_closed = StageEvent(proposal_id=base_id, created_at=closed_at, stage="closed")
                events_map.setdefault(base_id, []).append(ev_closed)

            if "pull_request" in issue:
                closed_at = _parse_iso(issue["closed_at"])
                ev_closed = StageEvent(proposal_id=base_id, created_at=closed_at, stage="merged")
                events_map.setdefault(base_id, []).append(ev_closed)

        page += 1

    # Update proposal objects with sorted events
    for p in proposals.values():
        pid_key = p.proposal_id.lower()
        if pid_key in events_map:
            # Sort events chronologically: oldest first (history) or newest first
            p.stages = sorted(events_map[pid_key], key=lambda e: e.created_at)

    return proposals


def add_proposal_stages_from_cpp_reference(proposals: dict[str, Proposal]) -> dict[str, Proposal]:
    versions = [11, 14, 17, 20, 23, 26]
    dates = [datetime.datetime(2011, 8, 1), datetime.datetime(2014, 8, 1), datetime.datetime(2017, 12, 1), datetime.datetime(2020, 12, 15), datetime.datetime(2024, 10, 1), datetime.datetime(2026, 3, 1)]

    events_map: Dict[str, List[StageEvent]] = {}
    for version, date in zip(versions, dates):
        # Fetch content
        with open(f"cplusplus/data/cppreference/{version}.html", "r", encoding="utf-8") as f:
            content = f.read()

        # Find all proposal IDs in the content
        # Match proposal IDs starting with P or N (e.g., P1234 or N1234), optionally with a revision like R1
        proposal_id_re = re.compile(r"([PN]\d+)(?:\s*R\d+)?", re.IGNORECASE)
        for match in proposal_id_re.finditer(content):
            base_id = match.group(1).lower()
            ev = StageEvent(
                proposal_id=base_id, created_at=date, stage="accepted"
            )
            events_map.setdefault(base_id, []).append(ev)

    # Update proposal objects with sorted events
    for p in proposals.values():
        pid_key = p.proposal_id.lower()
        if pid_key in events_map:
            # Sort events chronologically: oldest first (history) or newest first
            p.stages = sorted(events_map[pid_key], key=lambda e: e.created_at)

    return proposals

def add_proposal_stages(proposals: dict[str, Proposal]) -> dict[str, Proposal]:
    proposals = add_proposal_stages_from_github(proposals)
    proposals = add_proposal_stages_from_cpp_reference(proposals)
    return proposals