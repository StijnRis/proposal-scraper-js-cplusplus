import json
import sqlite3
from pathlib import Path

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
        assert not missing, f"Missing proposals for year {year}: {missing}"
        assert not extra, f"Extra proposals for year {year}: {extra}"
    conn.close()


def test_amount_of_revisions():
    with open("cplusplus/data/proposals.json", "r") as f:
        expected_proposals = json.load(f)

    for expected_proposal in expected_proposals:
        proposal_id = expected_proposal["proposal_id"]
        if "revisions" not in expected_proposal:
            continue
        expected_count = len(expected_proposal["revisions"])

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

        assert count == expected_count, (
            f"Proposal {proposal_id} has {count} revisions, expected {expected_count}"
        )


def test_titles():
    with open("cplusplus/data/proposals.json", "r") as f:
        expected_proposals = json.load(f)

    for expected_proposal in expected_proposals:
        proposal_id = expected_proposal["proposal_id"]
        if "title" not in expected_proposal:
            continue
        expected_title = expected_proposal["title"]

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

        assert title == expected_title, (
            f"Proposal {proposal_id} has title '{title}', expected '{expected_title}'"
        )


def test_authors():
    with open("cplusplus/data/proposals.json", "r") as f:
        expected_proposals = json.load(f)

    for expected_proposal in expected_proposals:
        proposal_id = expected_proposal["proposal_id"]
        if "authors" not in expected_proposal:
            continue
        expected_authors = set([a.strip() for a in expected_proposal["authors"]])

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

        authors = set(
            a[0].strip()[0] + "..." + a[0].strip()[-1] for a in authors_str
        )
        assert authors == expected_authors, (
            f"Proposal {proposal_id} has authors '{authors}', expected '{expected_authors}'"
        )


def test_revision_dates():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    with open("cplusplus/data/proposals.json", "r") as f:
        expected_proposals = json.load(f)

    for expected_proposal in expected_proposals:
        proposal_id = expected_proposal["proposal_id"]
        if "revisions" not in expected_proposal:
            continue
        expected_dates = set(
            revision["date"] for revision in expected_proposal["revisions"]
        )

        dates = cur.execute(
            """
            SELECT created_at FROM ProposalRevision
            WHERE proposal_id = ?
            """,
            (proposal_id,),
        ).fetchall()
        dates = set(date[0] for date in dates)
        assert dates == expected_dates, (
            f"Proposal {proposal_id} has dates '{dates}', expected '{expected_dates}'"
        )

    conn.close()


def test_proposal_content():
    with open("cplusplus/data/proposals.json", "r") as f:
        expected_proposals = json.load(f)

    for expected_proposal in expected_proposals:
        proposal_id = expected_proposal["proposal_id"]
        if "content" not in expected_proposal:
            continue
        expected_content = expected_proposal["content"]
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

        assert content.startswith(start), (
            f"Proposal {proposal_id} has content that does not start with '{start}'"
        )
        assert content.endswith(end), (
            f"Proposal {proposal_id} has content that does not end with '{end}'"
        )


def test_proposal_stages():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    with open("cplusplus/data/proposals.json", "r") as f:
        expected_proposals = json.load(f)

    for expected_proposal in expected_proposals:
        proposal_id = expected_proposal["proposal_id"]
        if "stages" not in expected_proposal:
            continue
        expected_stages = [s["status"]+ " " + s["date"] for s in expected_proposal["stages"]]

        
        stages_str = cur.execute(
            """
            SELECT raw_status, created_at
            FROM StageHistory
            WHERE proposal_id = ?
            ORDER BY created_at ASC;
            """,
            (proposal_id,),
        ).fetchall()

        stages = [s[0] + " " + s[1] for s in stages_str]
        assert stages == expected_stages, (
            f"Proposal {proposal_id} has stages '{stages}', expected '{expected_stages}'"
        )

    conn.close()



def test_malformed_ids():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM Proposal
        WHERE NOT (proposal_id GLOB 'N[0-9][0-9][0-9][0-9]' OR proposal_id GLOB 'P[0-9][0-9][0-9][0-9]' OR proposal_id GLOB 'P[0-9][0-9][0-9][0-9]R[0-9]');
        """
    )
    rows = cur.fetchall()
    assert len(rows) == 0, (
        f"Found {len(rows)} proposals with malformed ids: {[row[1] for row in rows]}"
    )
    conn.close()


def test_email_17268():

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    with open("cplusplus/data/comments.json", "r", encoding="utf-8") as f:
        comments = json.load(f)
    for expected_comment in comments:
        comment = cur.execute(
            """
            SELECT * FROM Comment
            WHERE created_at = ?
            ORDER BY created_at ASC
            LIMIT 1;
            """,
            (expected_comment["date"],),
        ).fetchone()

        author_id = comment[1]
        author_name = cur.execute(
            """
            SELECT full_name FROM Person
            WHERE person_id = ?;
            """,
            (author_id,),
        ).fetchone()[0]

        date = comment[5]
        content = comment[6]

        assert expected_comment["author_name"]["starts_with"] == author_name[0], (
            f"Comment with date {expected_comment['date']} has author_name starting with '{author_name[0]}', expected '{expected_comment['author_name']['starts_with']}'"
        )
        assert expected_comment["author_name"]["ends_with"] == author_name[-1], (
            f"Comment with date {expected_comment['date']} has author_name ending with '{author_name[-1]}', expected '{expected_comment['author_name']['ends_with']}'"
        )
        assert expected_comment["date"] == date, (
            f"Comment with date {expected_comment['date']} has date {date}, expected {expected_comment['date']}"
        )
        assert content.startswith(expected_comment["content"]["starts_with"]), (
            f"Comment does not start with '{expected_comment['content']['starts_with']}'"
        )
        assert content.endswith(expected_comment["content"]["ends_with"]), (
            f"Comment does not end with '{expected_comment['content']['ends_with']}'"
        )

    conn.close()


def test_all_number_exist():
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
            assert False, f"❗Missing comment id {i}"
