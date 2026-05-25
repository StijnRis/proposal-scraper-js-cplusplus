import datetime
import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional


def init_db(db_path: Path, start_id: int) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True) if os.path.dirname(
        db_path
    ) else None
    with open("db_init.sql", "r", encoding="utf-8") as f:
        sql = f.read()
    conn = sqlite3.connect(db_path)
    conn.executescript(sql)
    conn.commit()

    set_all_autoincrement_starts(conn, start_id)
    conn.close()
    logging.info("Database initialized at %s", db_path)


def set_all_autoincrement_starts(conn: sqlite3.Connection, start_id: int) -> None:
    tables = ["Project", "Person", "Organisation", "Comment"]

    new_val = start_id - 1

    cur = conn.cursor()
    for table in tables:
        cur.execute(
            "INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES (?, ?)",
            (table, new_val),
        )

    conn.commit()
    logging.info("All table auto-increments reset to start at %d", start_id)


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Optimize SQLite for much faster I/O operations
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")

    return conn


def insert_project(
    conn: sqlite3.Connection,
    project_id: int,
    project_name: str,
    enhancement_proposal_name: str,
    copyright_text: str,
) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO Project (project_id, project_name, enhancement_proposal_name, copyright) VALUES (?, ?, ?, ?)",
        (project_id, project_name, enhancement_proposal_name, copyright_text),
    )
    return project_id


def insert_proposal(
    conn: sqlite3.Connection,
    project_id: int,
    proposal_id: str,
    topic: Optional[str],
    proposal_type: Optional[str],
) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO Proposal (project_id, proposal_id, topic, proposal_type) VALUES (?, ?, ?, ?)",
        (project_id, proposal_id, topic, proposal_type),
    )


def insert_stage_history(
    conn: sqlite3.Connection,
    project_id: int,
    proposal_id: str,
    stage_index: int,
    normalised_status: str,
    raw_status: Optional[str],
    created_at: datetime.datetime,
) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ProposalStatus (project_id, proposal_id, status_index, raw_status, normalised_status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            project_id,
            proposal_id,
            stage_index,
            raw_status,
            normalised_status,
            created_at.isoformat(),
        ),
    )


def insert_proposal_revision(
    conn: sqlite3.Connection,
    project_id: int,
    proposal_id: str,
    revision_index: int,
    title: str,
    created_at: datetime.datetime,
    content: Optional[str],
    implemented_at_version: Optional[str] = None,
) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ProposalRevision (project_id, proposal_id, revision_index, title, created_at, content, implemented_at_version) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            project_id,
            proposal_id,
            revision_index,
            title,
            created_at.isoformat(),
            content,
            implemented_at_version,
        ),
    )


def insert_proposal_revision_author(
    conn: sqlite3.Connection,
    project_id: int,
    proposal_id: str,
    revision_index: int,
    person_id: int,
) -> None:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ProposalRevisionAuthor (project_id, proposal_id, revision_index, author_id) VALUES (?, ?, ?, ?)",
        (
            project_id,
            proposal_id,
            revision_index,
            person_id,
        ),
    )


def ensure_person_identifier(
    conn: sqlite3.Connection,
    person_id: int,
    domain: str,
    identifier_type: str,
    identifier: str,
) -> None:
    """
    Insert a PersonIdentifier row if it does not already exist. Domain may be NULL.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM PersonIdentifier WHERE person_id = ? AND identifier_type = ? AND identifier = ? AND domain = ?",
        (person_id, identifier_type, identifier, domain),
    )
    if cur.fetchone():
        return
    cur.execute(
        "INSERT INTO PersonIdentifier (person_id, domain, identifier_type, identifier) VALUES (?, ?, ?, ?)",
        (person_id, domain, identifier_type, identifier),
    )


def ensure_person(conn: sqlite3.Connection, full_name: Optional[str]) -> int:
    """
    Find a person by identifier if provided, otherwise by full_name. If not found, create a new Person.
    If an identifier is provided, ensure it is recorded in PersonIdentifier for the returned person_id.
    """
    cur = conn.cursor()

    if full_name:
        cur.execute("SELECT person_id FROM Person WHERE full_name = ?", (full_name,))
        row = cur.fetchone()
        if row:
            person_id = row[0]
            return person_id

    # Create new person
    cur.execute("INSERT INTO Person (full_name) VALUES (?)", (full_name,))
    if cur.lastrowid is None:
        raise Exception("Failed to insert person, lastrowid is None")
    person_id = cur.lastrowid

    return person_id


def insert_comment(
    conn: sqlite3.Connection,
    author_id: int,
    project_id: int,
    proposal_id: str | None,
    comment_on_comment_id: Optional[int],
    created_at: Optional[datetime.datetime],
    content: str,
) -> int:
    cur = conn.cursor()
    created_at_val = created_at.isoformat() if created_at is not None else None
    cur.execute(
        "INSERT INTO Comment (author_id, project_id, proposal_id, comment_on_comment_id, created_at, content) VALUES (?, ?, ?, ?, ?, ?)",
        (
            author_id,
            project_id,
            proposal_id,
            comment_on_comment_id,
            created_at_val,
            content,
        ),
    )
    if cur.lastrowid is None:
        raise Exception("Failed to insert comment, lastrowid is None")
    return cur.lastrowid
