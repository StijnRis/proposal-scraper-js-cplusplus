from datetime import datetime
import logging
import os
from typing import Dict

import git
from pydantic import BaseModel

from js import proposal_stages


class ProposalRevision(BaseModel):
    proposal_id: str
    author: str | None
    title: str
    created_at: datetime
    content: str
    implemented_at_version: str | None = None


class ProposalV2(BaseModel):
    proposal_id: str
    stages: list[proposal_stages.StageHistoryEvent]
    revisions: list[ProposalRevision]
    meeting_notes_locations: set[str]


def fetch_revisions(proposals_v1: Dict[str, proposal_stages.ProposalV1]):

    total_revisions = 0

    proposals = {}

    total = len(proposals_v1)
    current = 0
    for title, proposal_v1 in proposals_v1.items():
        current += 1
        logging.info("Processing proposal %d/%d: %s", current, total, title)

        repo_url = proposal_v1.stages[0].github_url
        if not repo_url:
            logging.warning("No repo URL for %s; skipping", title)
            continue
        if not repo_url.startswith("https://github.com"):
            logging.warning(
                "Repo URL %s does not start with https://github.com; skipping", repo_url
            )
            continue
        parts = repo_url.replace("https://github.com", "").split("/")
        if len(parts) != 3:
            logging.warning("Repo URL %s does not have the form owner/repo", repo_url)
            continue
        owner, repo = parts[1], parts[2]
        full = f"{owner}/{repo}"
        clean_repo_url = f"https://github.com/{full}"

        # Clone the repo if not already present in data/repos
        repo_path = f"./js/output/repos/{owner}_{repo}"
        if not os.path.exists(repo_path):
            try:
                logging.info("Cloning repo %s to %s", clean_repo_url, repo_path)
                git.Repo.clone_from(clean_repo_url, repo_path, bare=True)
            except git.GitCommandError:
                # Try the same repo under the tc39 organization
                tc39_full = f"tc39/{repo}"
                tc39_url = f"https://github.com/{tc39_full}"
                repo_path_tc39 = f"./js/output/repos/tc39_{repo}"
                try:
                    logging.info(
                        "Original clone failed; trying %s to %s",
                        tc39_url,
                        repo_path_tc39,
                    )
                    git.Repo.clone_from(tc39_url, repo_path_tc39)
                    # switch to tc39 clone
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
                    continue

        r = git.Repo(repo_path)

        # Loop through all commits, check content of file spec.html or spec.emu
        # if it changes, save it. If neither exist, crash
        revisions = []
        previous_content = None
        for commit in r.iter_commits():
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
            total_revisions += 1

        if len(revisions) == 0:
            raise RuntimeError(
                f"No revisions found for proposal {title} in repo {full}"
            )

        proposals[proposal_v1.proposal_id] = ProposalV2(
            proposal_id=proposal_v1.proposal_id,
            revisions=revisions,
            stages=proposal_v1.stages,
            meeting_notes_locations=proposal_v1.meeting_notes_locations,
        )

    logging.info("Total revisions saved: %d", total_revisions)
    return proposals


def get_text_from_commit(commit: git.Commit):
    # exact spec.html
    try:
        blob = commit.tree / "spec.html"
        content = blob.data_stream.read().decode("utf-8")
        return content
    except KeyError:
        pass

    # exact spec.emu
    try:
        blob = commit.tree / "spec.emu"
        content = blob.data_stream.read().decode("utf-8")
        return content
    except KeyError:
        content = None

    # any .html file
    for item in commit.tree.traverse():
        if isinstance(item, git.Blob) and str(item.path).lower().endswith(".html"):
            blob = item
            content = blob.data_stream.read().decode("utf-8")
            return content

    # any .emu file
    for item in commit.tree.traverse():
        if isinstance(item, git.Blob) and str(item.path).lower().endswith(".emu"):
            blob = item
            content = blob.data_stream.read().decode("utf-8")
            return content

    # README variants
    for name in ("README.md", "readme.md"):
        try:
            blob = commit.tree / name
            content = blob.data_stream.read().decode("latin-1")
            return content
        except KeyError:
            blob = None

    # 6) fallback: first markdown file
    for item in commit.tree.traverse():
        if isinstance(item, git.Blob) and str(item.path).lower().endswith(".md"):
            blob = item
            content = blob.data_stream.read().decode("latin-1")
            return content

    logging.warning(
        "No content found for commit %s in repo %s; returning empty string",
        commit.hexsha,
        commit.repo.working_dir,
    )
    return ""
