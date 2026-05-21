import datetime
from pathlib import Path
from typing import List

from db import (
    ensure_person,
    get_connection,
    init_db,
    insert_comment,
    insert_project,
    insert_proposal,
    insert_proposal_revision,
    insert_proposal_revision_author,
    insert_stage_history,
)
from js import proposal_revisions
from js.proposal_meeting_notes import MeetingNote


def save_to_db(
    db_path: Path,
    proposals_v2: dict[str, proposal_revisions.ProposalV2],
    meeting_notes: dict[str, List[MeetingNote]],
    project_id: int,
):
    # Delete existing database if it exists
    if db_path.exists():
        db_path.unlink()
    init_db(db_path, start_id=project_id * 1_000_000)

    conn = get_connection(db_path)

    # Wrap operations in a single transaction block for massive performance gains
    with conn:
        insert_project(
            conn,
            project_id,
            "JavaScript",
            "tc39",
            "UNKNOWN",
        )

        for proposal_id, proposal in proposals_v2.items():
            insert_proposal(
                conn,
                project_id=project_id,
                proposal_id=proposal.proposal_id,
                topic=None,
                proposal_type=None,
            )

            stage_index = 0
            for stage in proposal.stages:
                normalised_status = get_normalised_status(stage.status)
                insert_stage_history(
                    conn,
                    project_id=project_id,
                    proposal_id=proposal.proposal_id,
                    stage_index=stage_index,
                    raw_status=stage.status,
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
                    proposal_id=proposal.proposal_id,
                    revision_index=index_number,
                    title=revision.title,
                    created_at=revision.created_at,
                    content=revision.content,
                    implemented_at_version=revision.implemented_at_version,
                )
                if revision.author:
                    person_id = ensure_person(conn, revision.author)
                    insert_proposal_revision_author(
                        conn,
                        project_id=project_id,
                        proposal_id=proposal.proposal_id,
                        revision_index=index_number,
                        person_id=person_id,
                    )
                index_number += 1

            for location in proposal.meeting_notes_locations:
                if location not in meeting_notes:
                    print(
                        f"Warning: meeting note location {location} not found in mapping for proposal {proposal.proposal_id}"
                    )
                    continue

                notes = meeting_notes[location]
                sorted_notes = sorted(notes, key=lambda n: n.index)
                previous_note_id = None
                index = 0
                for note in sorted_notes:
                    author_id = ensure_person(conn, note.author)
                    # No email attached
                    previous_note_id = insert_comment(
                        conn,
                        author_id=author_id,
                        project_id=project_id,
                        proposal_id=proposal.proposal_id,
                        content=note.content,
                        created_at=note.created_at + datetime.timedelta(seconds=index),
                        comment_on_comment_id=previous_note_id,
                    )
                    index += 1

    conn.close()


def get_normalised_status(raw_stage: str) -> str:
    raw_stage = raw_stage.lower()
    if raw_stage == "stage 0":
        return "draft"
    elif raw_stage == "stage 1":
        return "draft"
    elif raw_stage == "stage 2":
        return "draft"
    elif raw_stage == "stage 2.7":
        return "review"
    elif raw_stage == "stage 3":
        return "review"
    elif raw_stage == "stage 4":
        return "accepted"
    elif raw_stage == "inactive proposals":
        return "withdrawn"
    raise ValueError(f"Unknown stage: {raw_stage}")
