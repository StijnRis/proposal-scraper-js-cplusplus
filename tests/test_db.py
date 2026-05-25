import json
import sqlite3

CPLUSPLUS_DB_PATH = "cplusplus/output/cplusplus_proposals.sqlite3"
JS_DB_PATH = "js/output/js_proposals.sqlite3"


def test():
    # show js proposal with name has regexp

    conn = sqlite3.connect(JS_DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM ProposalRevision
        WHERE title LIKE '%regexp%';
        """
    )
    rows = cur.fetchall()
    print(rows)


def test_js_amount_of_revisions():
    check_amount_of_revisions("js")


def test_cplusplus_amount_of_revisions():
    check_amount_of_revisions("cplusplus")


def check_amount_of_revisions(project: str):
    conn = sqlite3.connect(f"{project}/output/{project}_proposals.sqlite3")
    cur = conn.cursor()

    with open(f"{project}/tests/data/proposals.json", "r") as f:
        expected_proposals = json.load(f)

    for expected_proposal in expected_proposals:
        proposal_id = expected_proposal["proposal_id"]
        if "revisions" not in expected_proposal:
            continue
        expected_count = len(expected_proposal["revisions"])

        count = cur.execute(
            """
            SELECT COUNT(*) FROM ProposalRevision
            WHERE proposal_id = ?;
            """,
            (proposal_id,),
        ).fetchone()[0]

        assert count == expected_count, (
            f"Proposal {proposal_id} has {count} revisions, expected {expected_count}"
        )
    conn.close()


def test_js_titles():
    check_titles("js")


def test_cplusplus_titles():
    check_titles("cplusplus")


def check_titles(project: str):
    conn = sqlite3.connect(f"{project}/output/{project}_proposals.sqlite3")
    cur = conn.cursor()

    with open(f"{project}/tests/data/proposals.json", "r") as f:
        expected_proposals = json.load(f)

    for expected_proposal in expected_proposals:
        proposal_id = expected_proposal["proposal_id"]
        if "title" not in expected_proposal:
            continue
        expected_title = expected_proposal["title"]

        title = cur.execute(
            """
            SELECT title FROM ProposalRevision
            WHERE proposal_id = ?
            ORDER BY created_at ASC
            LIMIT 1;
            """,
            (proposal_id,),
        ).fetchone()[0]

        assert title == expected_title, (
            f"Proposal {proposal_id} has title '{title}', expected '{expected_title}'"
        )

    conn.close()


def test_js_authors():
    check_authors("js")


def test_cplusplus_authors():
    check_authors("cplusplus")


def check_authors(project: str):
    conn = sqlite3.connect(f"{project}/output/{project}_proposals.sqlite3")
    cur = conn.cursor()

    with open(f"{project}/tests/data/proposals.json", "r") as f:
        expected_proposals = json.load(f)

    for expected_proposal in expected_proposals:
        proposal_id = expected_proposal["proposal_id"]
        if "authors" not in expected_proposal:
            continue
        expected_authors = set([a.strip() for a in expected_proposal["authors"]])

        authors_str = cur.execute(
            """
            SELECT Person.full_name
            FROM ProposalRevisionAuthor
            JOIN Person ON ProposalRevisionAuthor.author_id = Person.person_id
            WHERE ProposalRevisionAuthor.proposal_id = ?
            """,
            (proposal_id,),
        ).fetchall()

        authors = set(a[0].strip()[0] + "..." + a[0].strip()[-1] for a in authors_str)
        assert authors == expected_authors, (
            f"Proposal {proposal_id} has authors '{authors}', expected '{expected_authors}'"
        )

    conn.close()


def test_js_revision_dates():
    check_revision_dates("js")


def test_cplusplus_revision_dates():
    check_revision_dates("cplusplus")


def check_revision_dates(project: str):
    conn = sqlite3.connect(f"{project}/output/{project}_proposals.sqlite3")
    cur = conn.cursor()

    with open(f"{project}/tests/data/proposals.json", "r") as f:
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


def test_js_proposal_content():
    check_proposal_content("js")


def test_cplusplus_proposal_content():
    check_proposal_content("cplusplus")


def check_proposal_content(project: str):
    conn = sqlite3.connect(f"{project}/output/{project}_proposals.sqlite3")
    cur = conn.cursor()

    with open(f"{project}/tests/data/proposals.json", "r") as f:
        expected_proposals = json.load(f)

    for expected_proposal in expected_proposals:
        proposal_id = expected_proposal["proposal_id"]
        if "content" not in expected_proposal:
            continue
        expected_content = expected_proposal["content"]
        start, end = expected_content.split("...")

        content = cur.execute(
            """
            SELECT content FROM ProposalRevision
            WHERE proposal_id = ?
            ORDER BY created_at ASC
            LIMIT 1;
            """,
            (proposal_id,),
        ).fetchone()[0]

        assert content.startswith(start), (
            f"Proposal {proposal_id} has content that does not start with '{start}'"
        )
        assert content.endswith(end), (
            f"Proposal {proposal_id} has content that does not end with '{end}'"
        )

    conn.close()


def test_js_proposal_stages():
    check_proposal_stages("js")


def test_cplusplus_proposal_statusses():
    check_proposal_stages("cplusplus")


def check_proposal_stages(project: str):
    conn = sqlite3.connect(f"{project}/output/{project}_proposals.sqlite3")
    cur = conn.cursor()

    with open(f"{project}/tests/data/proposals.json", "r") as f:
        expected_proposals = json.load(f)

    for expected_proposal in expected_proposals:
        proposal_id = expected_proposal["proposal_id"]
        if "statusses" not in expected_proposal:
            continue
        expected_stages = [
            s["raw_status"] + " " + s["date"] for s in expected_proposal["statusses"]
        ]

        stages_str = cur.execute(
            """
            SELECT raw_status, created_at
            FROM ProposalStatus
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
