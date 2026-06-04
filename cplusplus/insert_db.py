from pathlib import Path

from cplusplus.models import Comment, Proposal
from db import (
    ensure_person,
    ensure_person_identifier,
    get_connection,
    init_db,
    insert_comment,
    insert_project,
    insert_proposal,
    insert_proposal_revision,
    insert_proposal_revision_author,
    insert_stage_history,
)


def save_to_db(
    db_path: Path,
    proposals_v2: dict[str, Proposal],
    meeting_notes: list[Comment],
    project_id: int,
):
    if db_path.exists():
        db_path.unlink()
    init_db(db_path, start_id=project_id * 1_000_000)
    save_proposals_to_db(db_path, proposals_v2, project_id)
    save_comments_to_db(db_path, meeting_notes, project_id)


def save_proposals_to_db(
    db_path: Path, proposals: dict[str, Proposal], project_id: int
):
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
                project_id=project_id,
                proposal_id=proposal.proposal_id,
                topic=None,
                proposal_type=None,
            )

            stage_index = 0
            sorted_stages = sorted(proposal.stages, key=lambda s: s.created_at)
            for stage in sorted_stages:
                normalised_status = get_normalised_status(stage.stage)
                insert_stage_history(
                    conn,
                    project_id=project_id,
                    proposal_id=proposal.proposal_id,
                    stage_index=stage_index,
                    raw_status=stage.stage,
                    normalised_status=normalised_status,
                    created_at=stage.created_at,
                )
                stage_index += 1

            sorted_revisions = sorted(proposal.revisions, key=lambda r: r.created_at)
            index_number = 0
            for revision in sorted_revisions:
                insert_proposal_revision(
                    conn,
                    project_id=project_id,
                    proposal_id=revision.proposal_id,
                    revision_index=index_number,
                    title=revision.title,
                    created_at=revision.created_at,
                    content=revision.content,
                )
                for author in set(revision.authors):
                    person_id = ensure_person(conn, author)
                    insert_proposal_revision_author(
                        conn,
                        project_id=project_id,
                        proposal_id=revision.proposal_id,
                        revision_index=index_number,
                        person_id=person_id,
                    )
                index_number += 1

    conn.close()


def save_comments_to_db(db_path: Path, comments: list[Comment], project_id: int):
    conn = get_connection(db_path)

    comment_map: dict[int, int] = {}

    comments_sorted = sorted(comments, key=lambda c: int(c.message_id))

    # Wrap in a single transaction block for performance
    with conn:
        for comment in comments_sorted:
            person_id = ensure_person(
                conn,
                comment.author_name,
            )
            ensure_person_identifier(
                conn, person_id, comment.source_domain, "email", comment.author_email
            )
            comment_on_comment_id = (
                comment_map[comment.reply_to_message_id]
                if comment.reply_to_message_id
                else None
            )
            comment_id = insert_comment(
                conn,
                author_id=person_id,
                project_id=project_id,
                proposal_id=comment.proposal_id,
                comment_on_comment_id=comment_on_comment_id,
                created_at=comment.date,
                content=comment.content,
            )
            comment_map[comment.message_id] = comment_id

    conn.close()


def get_normalised_status(raw_status: str) -> str:
    raw_status = raw_status.lower()
    if raw_status == "merged":
        return "accepted"
    elif raw_status == "rejected":
        return "rejected"
    elif raw_status == "open":
        return "draft"
    elif raw_status == "accepted":
        return "accepted"
    raise Exception(f"Unknown raw status: {raw_status}")
