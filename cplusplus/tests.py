from datetime import datetime
import json
import sqlite3
from pathlib import Path

import requests

from cplusplus.emails import parse_message_page

DB_PATH = "cplusplus/output/cplusplus_proposals.sqlite3"


def test_proposal_counts():

    conn = sqlite3.connect(DB_PATH)

    files = list(Path("cplusplus/data").glob("ids_*.txt"))

    for file in files:
        year = int(file.stem.split("_")[1])
        cur = conn.cursor()
        proposal_names = cur.execute(
            """
            SELECT proposal_id FROM ProposalRevision
            WHERE strftime('%Y', created_at) = ?;
            """,
            (str(year),),
        ).fetchall()
        data_ids = set(row[0] for row in proposal_names)
        ids = set()
        with open(file, "r") as f:
            for line in f:
                if line[0] == "#":
                    continue
                ids.add(line.strip())
        missing = ids - data_ids
        extra = data_ids - ids
        if missing:
            print(f"❗Missing IDs for year {year}: {sorted(list(missing))}")
        if extra:
            print(f"❗Extra IDs for year {year}: {sorted(list(extra))}")
        if not missing and not extra:
            print(f"All IDs match for year {year}")
    conn.close()


def test_amount_of_revisions():
    with open("cplusplus/data/multiple_revisions.txt", "r") as f:
        for line in f:
            proposal_id, expected_count = line.strip().split()
            expected_count = int(expected_count)

            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            count = cur.execute(
                """
                SELECT COUNT(*) FROM ProposalRevision
                WHERE proposal_id = ?;
                """,
                (proposal_id,),
            ).fetchone()[0]
            conn.close()

            if count != expected_count:
                print(
                    f"❗Proposal {proposal_id} has {count} revisions, expected {expected_count}"
                )
            else:
                print(
                    f"Proposal {proposal_id} has the expected number of revisions: {count}"
                )


def find_malformed_ids():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM Proposal
        WHERE NOT (proposal_id GLOB 'N[0-9][0-9][0-9][0-9]' OR proposal_id GLOB 'P[0-9][0-9][0-9][0-9]' OR proposal_id GLOB 'P[0-9][0-9][0-9][0-9]R[0-9]');
        """
    )
    rows = cur.fetchall()
    if rows:
        print("Malformed proposal IDs:")
        for row in rows:
            print(f"Proposals: {row}")
    else:
        print("All proposal IDs are well-formed.")
    conn.close()


def check_titles():
    with open("cplusplus/data/titles.txt", "r") as f:
        for line in f:
            if line[0] == "#":
                continue
            proposal_id, expected_title = line.strip().split(" ", 1)
            expected_title = expected_title.strip()

            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            title = cur.execute(
                """
                SELECT title FROM ProposalRevision
                WHERE proposal_id = ?
                ORDER BY created_at ASC
                LIMIT 1;
                """,
                (proposal_id,),
            ).fetchone()[0]
            conn.close()

            if title != expected_title:
                print(
                    f"❗Proposal {proposal_id} has title '{title}', expected '{expected_title}'"
                )
            else:
                print(f"Proposal {proposal_id} has the expected title: '{title}'")


def check_authors():
    with open("cplusplus/data/authors.txt", "r") as f:
        for line in f:
            if line[0] == "#":
                continue
            proposal_id, expected_authors = line.strip().split(" ", 1)
            expected_authors = set([a.strip() for a in expected_authors.split(",")])

            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            authors_str = cur.execute(
                """
                SELECT Person.full_name
                FROM ProposalRevisionAuthor
                JOIN Person ON ProposalRevisionAuthor.author_id = Person.person_id
                WHERE ProposalRevisionAuthor.proposal_id = ?
                """,
                (proposal_id,),
            ).fetchall()
            conn.close()

            authors = set(a[0].strip()[0]+"..."+a[0].strip()[-1] for a in authors_str)
            if authors != expected_authors:
                print(
                    f"❗Proposal {proposal_id} has authors '{authors}', expected '{expected_authors}'"
                )
            else:
                print(f"Proposal {proposal_id} has the expected authors: '{authors}'")

def check_dates():
    with open("cplusplus/data/dates.txt", "r") as f:
        for line in f:
            if line[0] == "#":
                continue
            proposal_id, revision_index, expected_date, time = line.strip().split()
            expected_date = expected_date.strip()
            time = time.strip()

            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            date = cur.execute(
                """
                SELECT created_at FROM ProposalRevision
                WHERE proposal_id = ? AND revision_index = ?
                ORDER BY created_at ASC
                LIMIT 1;
                """,
                (proposal_id, revision_index),
            ).fetchone()[0]
            conn.close()

            if date != f"{expected_date} {time}":
                print(
                    f"❗Proposal {proposal_id} has date '{date}', expected '{expected_date} {time}'"
                )
            else:
                print(f"Proposal {proposal_id} has the expected date: '{date}'")

def check_proposal_content():
    # get all files in proposals directory
    with open("cplusplus/data/proposals.json", "r") as f:
        proposals = json.load(f)
    for proposal_id, expected_content in proposals.items():
        start, end = expected_content.split("...")

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        content = cur.execute(
            """
            SELECT content FROM ProposalRevision
            WHERE proposal_id = ?
            ORDER BY created_at ASC
            LIMIT 1;
            """,
            (proposal_id,),
        ).fetchone()[0]
        conn.close()

        if not content.startswith(start) or not content.endswith(end):
            print(
                f"❗Proposal {proposal_id} has content that does not match the expected content."
            )
        else:
            print(f"Proposal {proposal_id} has the expected content.")

def test_proposal_stages():
    with open("cplusplus/data/stages.txt", "r") as f:
        for line in f:
            if line[0] == "#":
                continue
            proposal_id, expected_stages = line.strip().split(" ", 1)
            expected_stages = [s.strip() for s in expected_stages.split(",")]

            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            stages_str = cur.execute(
                """
                SELECT raw_status, created_at
                FROM StageHistory
                WHERE proposal_id = ?
                ORDER BY created_at ASC;
                """,
                (proposal_id,),
            ).fetchall()
            conn.close()

            stages = [s[1] + " " + s[0].strip() for s in stages_str]
            if stages != expected_stages:
                print(
                    f"❗Proposal {proposal_id} has stages '{stages}', expected '{expected_stages}'"
                )
            else:
                print(f"Proposal {proposal_id} has the expected stages: '{stages}'")

def test_email_17268():
    response = requests.get("https://lists.isocpp.org/std-proposals/2026/02/17268.php")
    html = response.text
    comment = parse_message_page(
        "https://lists.isocpp.org/std-proposals/2026/02/17268.php", html
    )
    assert comment.message_id == 17268
    assert comment.reply_to_message_id == 17267
    assert comment.author_name[0] == "A"
    assert comment.author_name[-1] == "r"
    assert comment.author_email[0] == "a"
    assert comment.author_email[-1] == "]"
    assert comment.date == datetime(2026, 2, 27, 16, 32, 2)
    assert comment.content.startswith("On Fri, Feb 27, 2026 at ")
    assert comment.content.endswith("–Arthur")


def check_all_number_exist():
    # get all ids from database, then check if ther are any missing numbers in the sequence
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    ids = cur.execute(
        """
        SELECT comment_id FROM Comment
        ORDER BY comment_id ASC;
        """
    ).fetchall()
    conn.close()
    ids = [id[0] for id in ids]
    for i in range(ids[0], ids[-1] + 1):
        if i not in ids:
            print(f"❗Missing comment id {i}")


if __name__ == "__main__":
    test_proposal_counts()
    find_malformed_ids()
    check_proposal_content()
    test_amount_of_revisions()
    check_dates()
    check_titles()
    check_authors()
    test_proposal_stages()
    test_email_17268()
    check_all_number_exist()
