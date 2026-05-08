from pathlib import Path

from cplusplus.models import Comment, Proposal
from db import (
    get_connection,
    init_db,
    insert_comment,
    insert_or_get_person,
    insert_project,
    insert_proposal,
    insert_proposal_revision,
    insert_proposal_revision_author,
    insert_stage_history,
)


def save_proposals_to_db(
    db_path: Path, proposals: dict[str, Proposal], project_id: int
):
    if db_path.exists():
        db_path.unlink()
    init_db(db_path)

    conn = get_connection(db_path)

    # Wrap in a single transaction block for performance
    with conn:
        insert_project(
            conn,
            project_id,
            "C++",
            "ISO C++",
            "UNKNOWN",
        )

        for proposal_id, proposal in proposals.items():
            insert_proposal(
                conn,
                project_id,
                proposal.proposal_id,
                proposer_id=None,
                topic=None,
                proposal_type=None,
            )
            stage_index = 0
            for stage in proposal.stages:
                insert_stage_history(
                    conn,
                    project_id,
                    proposal.proposal_id,
                    stage_index,
                    stage.stage,
                    stage.created_at,
                )
                stage_index += 1
            sorted_revisions = sorted(proposal.revisions, key=lambda r: r.created_at)
            index_number = 0
            for revision in sorted_revisions:
                insert_proposal_revision(
                    conn,
                    project_id,
                    revision.proposal_id,
                    index_number,
                    revision.title,
                    revision.created_at,
                    revision.content,
                    None,
                )
                index_number += 1
                for author in set(revision.authors):
                    person_id = insert_or_get_person(conn, author)
                    insert_proposal_revision_author(
                        conn,
                        project_id,
                        revision.proposal_id,
                        index_number,
                        person_id,
                    )

    conn.close()


def save_comments_to_db(db_path: Path, comments: list[Comment], project_id: int):
    if db_path.exists():
        db_path.unlink()
    init_db(db_path)

    conn = get_connection(db_path)

    comment_map = {}

    comments_sorted = sorted(comments, key=lambda c: int(c.message_id))

    # Wrap in a single transaction block for performance
    with conn:
        for comment in comments_sorted:
            person_id = insert_or_get_person(conn, comment.author_email)
            comment_on_comment_id = (
                comment_map[comment.reply_to_message_id]
                if comment.reply_to_message_id
                else None
            )
            comment_id = insert_comment(
                conn,
                person_id,
                project_id,
                comment_on_comment_id,
                comment.message_id,
                comment.date,
                comment.content,
            )
            comment_map[comment.message_id] = comment_id
            
    conn.close()