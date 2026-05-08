import logging
import os
import sqlite3
from pathlib import Path


def init_db(db_path: Path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True) if os.path.dirname(
        db_path
    ) else None
    with open("db_init.sql", "r", encoding="utf-8") as f:
        sql = f.read()
    conn = sqlite3.connect(db_path)
    conn.executescript(sql)
    conn.commit()
    conn.close()
    logging.info("Database initialized at %s", db_path)


def get_connection(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Optimize SQLite for much faster I/O operations
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    
    return conn


def insert_project(
    conn, project_id, project_name, enhancement_proposal_name, copyright_text
):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO Project (project_id, project_name, enhancement_proposal_name, copyright) VALUES (?, ?, ?, ?)",
        (project_id, project_name, enhancement_proposal_name, copyright_text),
    )
    return cur.lastrowid


def insert_proposal(conn, project_id, proposal_id, proposer_id, topic, proposal_type):
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO Proposal (project_id, proposal_id, proposer_id, topic, proposal_type) VALUES (?, ?, ?, ?, ?)",
        (project_id, proposal_id, proposer_id, topic, proposal_type),
    )


def insert_stage_history(
    conn, project_id, proposal_id, stage_index, status, created_at
):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO StageHistory (project_id, proposal_id, stage_index, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (project_id, proposal_id, stage_index, status, created_at),
    )


def insert_proposal_revision(
    conn,
    project_id,
    proposal_id,
    revision_index,
    title,
    created_at,
    content,
    implemented_at_version=None,
):
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
    conn, project_id, proposal_id, revision_index, person_id
):
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


def insert_or_get_person(conn, full_name):
    cur = conn.cursor()
    cur.execute("SELECT person_id FROM Person WHERE full_name = ?", (full_name,))
    row = cur.fetchone()
    if row:
        return row["person_id"]
    else:
        cur.execute("INSERT INTO Person (full_name) VALUES (?)", (full_name,))
        return cur.lastrowid


def insert_comment(
    conn, author_id, project_id, proposal_id, comment_on_comment_id, created_at, content
):
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
    return cur.lastrowid