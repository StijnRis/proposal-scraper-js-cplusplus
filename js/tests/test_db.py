import datetime
import json
import sqlite3


DB_PATH = "./js/output/js_proposals.sqlite3"

def test_temporal_proposal():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    proposal = cur.execute(
        """
        SELECT * FROM Proposal
        WHERE proposal_id = 'Temporal';
        """
    ).fetchone()
    assert proposal is not None, "Temporal proposal not found in database"
    assert proposal[0] == 3
    assert proposal[1] == "Temporal", f"Expected proposal_id 'Temporal', got '{proposal[1]}'"
    assert proposal[2] == None
    assert proposal[3] == None

    proposalRevisions = cur.execute(
        """
        SELECT * FROM ProposalRevision
        WHERE proposal_id = 'Temporal'
        ORDER BY created_at ASC;
        """
    ).fetchall()
    assert len(proposalRevisions) > 0, "No revisions found for Temporal proposal"

    assert proposalRevisions[-1][0] == 3
    assert proposalRevisions[-1][1] == "Temporal"
    assert proposalRevisions[-1][2] != None 
    assert proposalRevisions[-1][3] == "Temporal"
    assert proposalRevisions[-1][4] == "2026-04-03 09:23:09-07:00"
    assert proposalRevisions[-1][5].startswith("<!DOCTYPE html>")
    assert proposalRevisions[-1][5].endswith('<emu-import href="spec/intl.html"></emu-import>\n')

    comments = cur.execute(
        """
        SELECT * FROM Comment
        WHERE proposal_id = 'Temporal'
        ORDER BY created_at ASC;
        """
    ).fetchall()

    assert len(comments) > 100

    author_id = comments[0][1]
    author = cur.execute(
        """
        SELECT full_name FROM Person
        WHERE person_id = ?;
        """,
        (author_id,),
    ).fetchone()[0]

    assert author[0] == "M"
    assert comments[0][2] == 3
    assert comments[0][3] == "Temporal"
    assert comments[0][4] == None
    assert comments[0][5] == "2018-09-27 00:00:00"
    assert comments[0][6].startswith("This API is quite large, but we won't ")

    stageHistory = cur.execute(
        """
        SELECT * FROM StageHistory
        WHERE proposal_id = 'Temporal'
        ORDER BY created_at ASC;
        """
    ).fetchall()

    assert len(stageHistory) > 0
    assert stageHistory[0][0] == 3
    assert stageHistory[0][1] == "Temporal"
    assert stageHistory[0][2] == 0
    assert stageHistory[0][3] == "Stage 1"
    assert stageHistory[0][4] == "draft"
    assert stageHistory[0][5] == "2017-04-03 04:21:18"

    conn.close()


def test_meeting_notes():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    with open("js/data/comments.json", "r", encoding="utf-8") as f:
        meeting_notes = json.load(f)

    for meeting_note in meeting_notes:
        proposal_id = meeting_note["proposal_id"]
        true_comments = meeting_note["comments"]
        date_obj = datetime.datetime.fromisoformat(meeting_note["date"].rstrip("Z")) - datetime.timedelta(days=1)
        date_str = date_obj.isoformat()

        # get comments from the proposal
        comments = cur.execute(
            """
            SELECT author_id, content, created_at FROM Comment
            WHERE proposal_id = ? AND created_at >= ?
            ORDER BY created_at ASC;
            """,
            (proposal_id,date_str),
        ).fetchall()

        # check if the comment content matches the meeting note content
        index = 0
        for true_comment in true_comments:
            comment = comments[index]
            index += 1

            author_id = comment[0]
            author = cur.execute(
                """
                SELECT full_name FROM Person
                WHERE person_id = ?;
                """,
                (author_id,),
            ).fetchone()[0]
            assert author[0] == true_comment["author"], f"Comment author does not match for proposal {proposal_id} at index {index}"
            assert true_comment["content"] == comment[1], f"Comment content does not match for proposal {proposal_id} at index {index}"

    conn.close()



if __name__ == "__main__":
    test_temporal_proposal()
    test_meeting_notes()
    