import logging
import os
from datetime import datetime
from typing import Dict

import git
from pydantic import BaseModel

from js import proposal_statusses


class ProposalRevision(BaseModel):
    proposal_id: str
    author: str | None
    title: str
    created_at: datetime
    content: str
    implemented_at_version: str | None = None


class ProposalV2(BaseModel):
    proposal_id: str
    stages: list[proposal_statusses.StageHistoryEvent]
    revisions: list[ProposalRevision]
    meeting_notes_locations: set[str]


def fetch_revisions(proposals_v1: Dict[str, proposal_statusses.ProposalV1]):
    total_revisions = 0
    proposals = {}

    total = len(proposals_v1)
    current = 0
    for title, proposal_v1 in proposals_v1.items():
        current += 1
        logging.info("Processing proposal %d/%d: %s", current, total, title)
        revisions = fetch_revision(proposal_v1, title)
        total_revisions += len(revisions)
        proposals[proposal_v1.proposal_id] = ProposalV2(
            proposal_id=proposal_v1.proposal_id,
            stages=proposal_v1.stages,
            revisions=revisions,
            meeting_notes_locations=proposal_v1.meeting_notes_locations,
        )

    logging.info("Total revisions saved: %d", total_revisions)
    return proposals


def fetch_revision(
    proposal_v1: proposal_statusses.ProposalV1, title: str
) -> list[ProposalRevision]:
    repo_url = proposal_v1.stages[0].github_url
    if not repo_url:
        logging.warning("No repo URL for %s; skipping", title)
        return []
    if not repo_url.startswith("https://github.com"):
        logging.warning(
            "Repo URL %s does not start with https://github.com; skipping", repo_url
        )
        return []
    parts = repo_url.replace("https://github.com", "").rstrip("/").split("/")
    if len(parts) != 3:
        logging.warning("Repo URL %s does not have the form owner/repo", repo_url)
        return []
    owner, repo = parts[1], parts[2]
    full = f"{owner}/{repo}"
    clean_repo_url = f"https://github.com/{full}"

    # Clone the repo if not already present in tests/data/repos
    repo_path = f"./js/output/repos/{owner}_{repo}"
    if not os.path.exists(repo_path):
        try:
            logging.info("Cloning repo %s to %s", clean_repo_url, repo_path)
            git.Repo.clone_from(clean_repo_url, repo_path, bare=True)
        except git.GitCommandError:
            tc39_full = f"tc39/{repo}"
            tc39_url = f"https://github.com/{tc39_full}"
            repo_path_tc39 = f"./js/output/repos/tc39_{repo}"
            try:
                logging.info(
                    "Original clone failed; trying %s to %s",
                    tc39_url,
                    repo_path_tc39,
                )
                git.Repo.clone_from(tc39_url, repo_path_tc39, bare=True)
                full = tc39_full
                clean_repo_url = tc39_url
                repo_path = repo_path_tc39
            except git.GitCommandError:
                logging.warning(
                    "Repo not found at %s or %s; skipping proposal %s",
                    clean_repo_url,
                    tc39_url,
                    title,
                )
                return []

    r = git.Repo(repo_path)

    revisions = []
    previous_content = None

    try:
        commits = r.iter_commits(r.head.reference)
    except (AttributeError, ValueError):
        commits = r.iter_commits("HEAD")

    for commit in commits:
        content = get_text_from_commit(commit)

        if content == previous_content:
            continue
        previous_content = content
        revisions.append(
            ProposalRevision(
                proposal_id=proposal_v1.proposal_id,
                title=title,
                created_at=commit.committed_datetime,
                content=content,
                author=commit.author.name,
            )
        )

    if len(revisions) == 0:
        raise RuntimeError(f"No revisions found for proposal {title} in repo {full}")

    return revisions


def get_text_from_commit(commit: git.Commit):
    # exact spec.html
    try:
        blob = commit.tree / "spec.html"
        return blob.data_stream.read().decode("utf-8")
    except KeyError:
        pass

    # exact spec.emu
    try:
        blob = commit.tree / "spec.emu"
        return blob.data_stream.read().decode("utf-8")
    except KeyError:
        pass

    # README file
    for name in ("README.md", "readme.md"):
        try:
            blob = commit.tree / name
            return blob.data_stream.read().decode("latin-1")
        except KeyError:
            pass

    # any .html file
    for item in commit.tree.traverse():
        if isinstance(item, git.Blob) and str(item.path).lower().endswith(".html"):
            return item.data_stream.read().decode("utf-8")

    # any .emu file
    for item in commit.tree.traverse():
        if isinstance(item, git.Blob) and str(item.path).lower().endswith(".emu"):
            return item.data_stream.read().decode("utf-8")

    # any markdown file
    for item in commit.tree.traverse():
        if isinstance(item, git.Blob) and str(item.path).lower().endswith(".md"):
            return item.data_stream.read().decode("latin-1")

    logging.warning(
        "No content found for commit %s in repo %s; returning empty string",
        commit.hexsha,
        commit.repo.git_dir,
    )
    return ""
