from pathlib import Path

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
from js import proposal_revisions
from js.proposal_meeting_notes import MeetingNote


def save_to_db(
    db_path: Path,
    proposals_v2: dict[str, proposal_revisions.ProposalV2],
    meeting_notes: dict[str, MeetingNote],
    project_id: int,
):
    # Delete existing database if it exists
    if db_path.exists():
        db_path.unlink()
    init_db(db_path)

    conn = get_connection(db_path)

    # Wrap operations in a single transaction block for massive performance gains
    with conn:
        insert_project(
            conn,
            1,  # Kept as 1 based on your original implementation
            "JavaScript",
            "tc39",
            "UNKNOWN",
        )

        for proposal_id, proposal in proposals_v2.items():
            insert_proposal(
                conn,
                proposal.project_id,
                proposal.proposal_id,
                proposer_id=None,
                topic=None,
                proposal_type=None,
            )

            stage_index = 0
            for stage in proposal.stages:
                insert_stage_history(
                    conn,
                    proposal.project_id,
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
                    revision.project_id,
                    revision.proposal_id,
                    index_number,
                    revision.title,
                    revision.created_at,
                    revision.content,
                    revision.implemented_at_version,
                )
                if revision.author:
                    person_id = insert_or_get_person(conn, revision.author)
                    insert_proposal_revision_author(
                        conn,
                        revision.project_id,
                        revision.proposal_id,
                        index_number,
                        person_id,
                    )
                index_number += 1

            for location in proposal.meeting_notes_locations:
                if (
                    location
                    == "2017-09/sep-26.md#12ia-intlnumberformatprototypeformattoparts-for-stage-4"
                ):
                    location = "2017-09/sept-26.md#12ia-intlnumberformatprototypeformattoparts-for-stage-4"
                elif location == "2021-10/oct-27.md#call-this-operator-for-stage-1":
                    location = "2021-10/oct-27.md#bind-this-operator-for-stage-1"
                if location not in meeting_notes:
                    print(
                        f"Warning: meeting note location {location} not found in mapping for proposal {proposal.proposal_id}"
                    )
                    continue

                note = meeting_notes[location]
                author_id = None
                insert_comment(
                    conn,
                    author_id=author_id,
                    project_id=project_id,
                    proposal_id=proposal.proposal_id,
                    content=note.content,
                    created_at=note.created_at,
                    comment_on_comment_id=None,
                )

    conn.close()
