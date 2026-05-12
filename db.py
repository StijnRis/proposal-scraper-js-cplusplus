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
    """
    Resets the auto-increment counter for all primary key tables
    to begin at the specified start_id.
    """
    # List of tables in your schema that use an internal AUTOINCREMENT ID
    tables = ["Project", "Person", "Organisation", "Comment"]

    cur = conn.cursor()
    new_val = start_id - 1

    for table in tables:
        # We use INSERT OR REPLACE to handle both new and existing entries in the system table
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
    if cur.lastrowid is None:
        raise Exception("Failed to insert project, lastrowid is None")
    return cur.lastrowid


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
        "INSERT INTO StageHistory (project_id, proposal_id, stage_index, normalised_status, raw_status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            project_id,
            proposal_id,
            stage_index,
            normalised_status,
            raw_status,
            created_at,
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
            created_at,
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


def insert_or_get_person(conn: sqlite3.Connection, full_name: Optional[str]) -> int:
    cur = conn.cursor()
    cur.execute("SELECT person_id FROM Person WHERE full_name = ?", (full_name,))
    row = cur.fetchone()
    if row:
        return row["person_id"]
    else:
        cur.execute("INSERT INTO Person (full_name) VALUES (?)", (full_name,))
        if cur.lastrowid is None:
            raise Exception("Failed to insert person, lastrowid is None")
        return cur.lastrowid


def insert_if_not_exists_person_username(
    conn: sqlite3.Connection, person_id: int, domain: str, username: str
):
    cur = conn.cursor()
    cur.execute(
        "SELECT username FROM PersonUsername WHERE person_id = ? AND domain = ? AND username = ?",
        (person_id, domain, username),
    )
    row = cur.fetchone()
    if row:
        return
    else:
        cur.execute(
            "INSERT INTO PersonUsername (person_id, domain, username) VALUES (?, ?, ?)",
            (person_id, domain, username),
        )
        if cur.lastrowid is None:
            raise Exception("Failed to insert person username, lastrowid is None")
        return


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
    cur.execute(
        "INSERT INTO Comment (author_id, project_id, proposal_id, comment_on_comment_id, created_at, content) VALUES (?, ?, ?, ?, ?, ?)",
        (
            author_id,
            project_id,
            proposal_id,
            comment_on_comment_id,
            created_at,
            content,
        ),
    )
    if cur.lastrowid is None:
        raise Exception("Failed to insert comment, lastrowid is None")
    return cur.lastrowid
