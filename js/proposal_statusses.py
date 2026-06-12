import logging
import os
import re
from datetime import datetime
from typing import Dict

import git
from bs4 import BeautifulSoup
from bs4.element import Tag
from markdown import markdown
from pydantic import BaseModel


class StageHistoryEvent(BaseModel):
    proposal_id: str
    github_url: str | None
    champions: list[str]
    authors: list[str]
    status: str
    created_at: datetime


class ProposalV1(BaseModel):
    proposal_id: str
    stages: list[StageHistoryEvent]
    meeting_notes_locations: set[str]


meeting_notes_map = {}


def compute_stage_history() -> Dict[str, ProposalV1]:
    """
    Analyzes the history using a local Git repository path using the GitPython library.
    """

    # repo is stored at data, if not found, clone it to there
    repo_path = "./js/output/tc39-proposals"
    if not os.path.exists(repo_path):
        logging.info("Cloning tc39/proposals repo to %s", repo_path)
        git.Repo.clone_from(
            "https://github.com/tc39/proposals.git", repo_path, bare=True
        )

    repo = git.Repo(repo_path)

    prev_stage_map: Dict[str, StageHistoryEvent] = {}
    processed = 0
    events = 0

    proposals = {}

    # Sort commits by date
    commits_data = {}
    for commit in repo.iter_commits():
        sha = commit.hexsha
        timestamp = commit.committed_date
        commits_data[sha] = timestamp
    sorted_shas = sorted(commits_data.keys(), key=lambda sha: commits_data[sha])

    # Loop though all commits in the repo, sorted by date
    for sha in sorted_shas:
        if processed % 50 == 0:
            logging.info(
                f"Processing commit {sha} ({processed + 1}/{len(sorted_shas)})"
            )
        # Build current stage map for this commit
        current_map = {}
        # get all md files in this commit, so not only tracked, everything that ends with .md
        commit = repo.commit(sha)
        md_files = commit.tree.traverse(
            predicate=lambda item, _: item.path.endswith(".md")
        )
        for file in md_files:
            # Access the file at this specific commit tree
            blob = commit.tree / file.path
            md = blob.data_stream.read().decode("utf-8")

            items = parse_markdown(
                file.path, md, created_at=datetime.fromtimestamp(commits_data[sha])
            )
            for item in items:
                current_map[item.proposal_id] = item

        # Compare current_map to prev_stage_map
        for path, event in current_map.items():
            add_event = False
            prev_event = prev_stage_map.get(path)
            if not prev_event:
                add_event = True
            elif prev_event.status != event.status:
                add_event = True

            if add_event:
                if event.proposal_id not in proposals:
                    proposals[event.proposal_id] = ProposalV1(
                        proposal_id=event.proposal_id,
                        stages=[],
                        meeting_notes_locations=set(),
                    )
                proposals[event.proposal_id].stages.append(event)

                events += 1

        prev_stage_map = current_map
        processed += 1
        if processed % 50 == 0:
            logging.info(
                "Processed %d commits, detected %d stage events", processed, events
            )

    for proposal_id, proposal in proposals.items():
        if proposal_id in meeting_notes_map:
            proposal.meeting_notes_locations = meeting_notes_map[proposal_id]

    logging.info(
        "Stage history complete: processed %d commits, detected %d events",
        processed,
        events,
    )

    return proposals


def parse_markdown(
    file: str, md_text: str, created_at: datetime
) -> list[StageHistoryEvent]:
    """Generic parser: convert markdown to HTML

    returns stage events
    """
    if md_text.strip() == "":
        return []

    html = markdown(md_text, extensions=["tables"])
    soup = BeautifulSoup(html, "html.parser")
    # save html soup to file
    # with open("soup.html", "w", encoding="utf-8") as f:
    #     f.write(soup.prettify())
    results = []

    # Parse all tables
    tables = soup.find_all("table")
    NO_TABLES = set(
        ["README.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "ISSUE_TEMPLATE.md"]
    )
    if len(tables) == 0 and file not in NO_TABLES:
        raise RuntimeError(
            f"No tables found in markdown file {file}, cannot parse stage events"
        )

    for table in tables:
        events = parse_table(table, created_at)
        results.extend(events)

    return results


NOT_PARSEABLE = set()


def parse_table(table: Tag, created_at: datetime) -> list[StageHistoryEvent]:
    """
    Parses a table with dynamic columns.
    Possible columns: Proposal, Champions, Authors, Stage.
    Program checks header row to determine column indices, then extracts data accordingly.
    """

    stage_events = []

    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
    col_indices = {name: idx for idx, name in enumerate(headers)}

    for row in table.find_all("tr")[1:]:  # skip header
        cells = row.find_all("td")
        if len(cells) < len(col_indices):
            continue  # skip malformed rows

        link = cells[col_indices["proposal"]].find("a")
        if not link:
            github_url = None
        else:
            github_url = str(link["href"])

        proposal_id = cells[col_indices["proposal"]].get_text(strip=True)

        if proposal_id == "":
            continue  # skip rows without proposal ID

        champions = []
        options = ["champion", "champions", "champion(s)"]
        for option in options:
            if option in col_indices:
                champions = re.split(
                    r"[,&\n]", cells[col_indices[option]].get_text(strip=True)
                )
                champions = [c.strip() for c in champions if c.strip()]
                break
        else:
            raise RuntimeError(
                f"Could not find champion column for proposal {proposal_id}"
            )

        authors = (
            re.split(r"[,&\n]", cells[col_indices["authors"]].get_text(strip=True))
            if "authors" in col_indices
            else []
        )
        authors = [a.strip() for a in authors if a.strip()]

        meeting_notes_names = [
            "tc39 meeting notes",
            "meeting notes",
            "notes",
            "last presented",
        ]
        for name in meeting_notes_names:
            if name in col_indices:
                meeting_notes_cell = cells[col_indices[name]]
                if proposal_id not in meeting_notes_map:
                    meeting_notes_map[proposal_id] = set()
                links = meeting_notes_cell.find_all("a")
                for link in links:
                    href = link.get("href", "")
                    #'https://github.com/tc39/tc39-notes/blob/master/es7/2016-07/jul-27.md#9ii-ecma-402-formattoparts'
                    # only keep 20xx/... parts of the url
                    # should be general do with regex
                    match = re.search(r"20\d{2}-\d{2}\/\w+-\d{1,2}\.md#.+", href)
                    if match:
                        item = match.group(0)
                        meeting_notes_map[proposal_id].add(item)
                    elif href not in NOT_PARSEABLE:
                        logging.warning(
                            "Could not parse meeting notes link %s for proposal %s",
                            href,
                            proposal_id,
                        )
                        NOT_PARSEABLE.add(href)
                break

        stage = None
        if "stage" in col_indices:
            stage = "Stage " + cells[col_indices["stage"]].get_text(strip=True)
        else:
            possible_stages = [
                r"stage 0",
                r"stage 1",
                r"stage 2\.7",
                r"stage 2",
                r"stage 3",
                r"stage 4",
                r"inactive proposals",
            ]
            # Find closest text stage x in text before this row
            prev_text = row.find_previous(
                string=re.compile("|".join(possible_stages), re.IGNORECASE)
            )
            if prev_text:
                stage_match = re.search(
                    "|".join(possible_stages), prev_text, re.IGNORECASE
                )
                if stage_match:
                    stage = stage_match.group(0).title()
        if not stage:
            raise RuntimeError(f"Could not determine stage for proposal {proposal_id}")

        stage_events.append(
            StageHistoryEvent(
                proposal_id=proposal_id,
                github_url=github_url,
                champions=champions,
                authors=authors,
                status=stage,
                created_at=created_at,
            )
        )

    return stage_events
