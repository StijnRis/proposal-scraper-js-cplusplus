import json
from datetime import datetime
from pathlib import Path

import requests

from cplusplus.emails import parse_message_page
from cplusplus.models import Proposal
from cplusplus.proposals import parse_content, scrape_year


def test_proposal_counts():
    files = list(Path("cplusplus/data").glob("ids_*.txt"))

    for file in files:
        year = int(file.stem.split("_")[1])
        proposals = scrape_year({}, year)
        proposals.update(scrape_year(proposals, year + 1))

        data_ids = set()
        for proposal_id in proposals.keys():
            proposal = proposals[proposal_id]
            for revision in proposal.revisions:
                if revision.created_at.year == year:
                    data_ids.add(proposal_id)
                    break
        ids = set()
        with open(file, "r") as f:
            for line in f:
                if line[0] == "#":
                    continue
                ids.add(line.strip())
        missing = ids - data_ids
        extra = data_ids - ids

        assert not missing, f"Missing proposals for year {year}: {missing}"
        assert not extra, f"Extra proposals for year {year}: {extra}"


def test_proposals():
    with open("cplusplus/tests/data/proposals.json", "r") as f:
        expected_proposals = json.load(f)
        for expected_proposal in expected_proposals:
            proposal_id = expected_proposal["proposal_id"]

            found_in_list_of_years = expected_proposal["found_in_list_of_years"]
            proposals: dict[str, Proposal] = {}
            for year in found_in_list_of_years:
                proposals.update(scrape_year(proposals, year))
            proposal = proposals[proposal_id]

            if "amount_of_revisions" in expected_proposal:
                expected_count = expected_proposal["amount_of_revisions"]
                count = len(proposal.revisions)
                assert count == expected_count, (
                    f"Proposal {proposal_id} has {count} revisions, expected {expected_count}"
                )

            if "title" in expected_proposal:
                expected_title = expected_proposal["title"]
                title = proposal.revisions[0].title.strip()
                assert title == expected_title, (
                    f"Proposal {proposal_id} has title '{title}', expected '{expected_title}'"
                )

            if "authors" in expected_proposal:
                expected_authors = set(
                    [a.strip() for a in expected_proposal["authors"]]
                )
                authors = set(
                    [
                        a.strip()[0] + "..." + a.strip()[-1]
                        for a in proposal.revisions[0].authors
                    ]
                )
                assert authors == expected_authors, (
                    f"Proposal {proposal_id} has authors '{authors}', expected '{expected_authors}'"
                )

            if "revisions" in expected_proposal:
                expected_dates = set(
                    [d["date"].strip() for d in expected_proposal["revisions"]]
                )
                dates = set()
                for revision in proposal.revisions:
                    dates.add(revision.created_at.strftime("%Y-%m-%d %H:%M:%S"))
                assert dates == expected_dates, (
                    f"Proposal {proposal_id} has dates '{dates}', expected '{expected_dates}'"
                )


def test_statusses():
    # Not feasible to unit test as everything will have to be fetched for this
    pass


def test_content():
    with open("cplusplus/tests/data/proposals.json", "r") as f:
        expected_proposals = json.load(f)
        for expected_proposal in expected_proposals:
            proposal_id = expected_proposal["proposal_id"]

            if "content" in expected_proposal:
                expected_content = expected_proposal["content"]
                url = expected_proposal["content_url"]
                content = parse_content(url)
                assert content.startswith(expected_content.split("...")[0]), (
                    f"Proposal {proposal_id} has content that does not start with '{expected_content.split('...')[0]}'"
                )
                assert content.endswith(expected_content.split("...")[1]), (
                    f"Proposal {proposal_id} has content that does not end with '{expected_content.split('...')[1]}'"
                )


def test_comments():
    with open("cplusplus/tests/data/comments.json", "r", encoding="utf-8") as f:
        comments = json.load(f)
        for expected_comment in comments:
            url = expected_comment["url"]
            response = requests.get(url)
            html = response.text
            comment = parse_message_page(
                "https://lists.isocpp.org/std-proposals/2026/02/17268.php", html
            )

            assert expected_comment["message_id"] == comment.message_id, (
                f"Comment at {url} has message_id {comment.message_id}, expected {expected_comment['message_id']}"
            )
            assert (
                expected_comment["reply_to_message_id"] == comment.reply_to_message_id
            ), (
                f"Comment at {url} has reply_to_message_id {comment.reply_to_message_id}, expected {expected_comment['reply_to_message_id']}"
            )
            assert (
                expected_comment["author_name"]["starts_with"] == comment.author_name[0]
            ), (
                f"Comment at {url} has author_name starting with '{comment.author_name[0]}', expected '{expected_comment['author_name']['starts_with']}'"
            )
            assert (
                expected_comment["author_name"]["ends_with"] == comment.author_name[-1]
            ), (
                f"Comment at {url} has author_name ending with '{comment.author_name[-1]}', expected '{expected_comment['author_name']['ends_with']}'"
            )
            assert (
                expected_comment["author_email"]["starts_with"]
                == comment.author_email[0]
            ), (
                f"Comment at {url} has author_email starting with '{comment.author_email[0]}', expected '{expected_comment['author_email']['starts_with']}'"
            )
            assert (
                expected_comment["author_email"]["ends_with"]
                == comment.author_email[-1]
            ), (
                f"Comment at {url} has author_email ending with '{comment.author_email[-1]}', expected '{expected_comment['author_email']['ends_with']}'"
            )
            assert (
                datetime.strptime(expected_comment["date"], "%Y-%m-%d %H:%M:%S")
                == comment.date
            ), (
                f"Comment at {url} has date {comment.date}, expected {expected_comment['date']}"
            )
            assert comment.content.startswith(
                expected_comment["content"]["starts_with"]
            ), (
                f"Comment at {url} has content that does not start with '{expected_comment['content']['starts_with']}'"
            )
            assert comment.content.endswith(expected_comment["content"]["ends_with"]), (
                f"Comment at {url} has content that does not end with '{expected_comment['content']['ends_with']}'"
            )
