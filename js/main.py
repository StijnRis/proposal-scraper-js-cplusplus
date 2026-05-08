import logging
import os
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv
from pydantic import TypeAdapter

from js import proposal_revisions, proposal_stages
from js.insert_db import save_to_db
from js.proposal_meeting_notes import MeetingNote, build_mapping

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def main():

    load_dotenv()
    token = os.environ.get("GITHUB_TOKEN")
    if token is None:
        raise RuntimeError("GITHUB_TOKEN must be set in environment")

    proposal_v1_path = Path("./js/output/proposals_v1.json")
    proposal_v2_path = Path("./js/output/proposals_v2.json")
    meeting_mapping_path = Path("./js/output/meeting_notes_mapping.json")
    db_path = Path("./js/output/js_proposals.sqlite3")

    project_id = 1
    adapter1 = TypeAdapter(Dict[str, proposal_stages.ProposalV1])
    adapter2 = TypeAdapter(Dict[str, proposal_revisions.ProposalV2])
    adapter_meetings_map = TypeAdapter(Dict[str, MeetingNote])

    logging.info("Computing stage history")
    proposals_v1: Dict[str, proposal_stages.ProposalV1] = (
        proposal_stages.compute_stage_history(project_id=project_id)
    )
    json_data = adapter1.dump_json(proposals_v1, indent=2)
    proposal_v1_path.write_bytes(json_data)

    logging.info("Fetching spec revisions")
    proposals_v1 = adapter1.validate_json(proposal_v1_path.read_bytes())
    proposals_v2 = proposal_revisions.fetch_revisions(proposals_v1)
    json_data = adapter2.dump_json(proposals_v2, indent=2)
    proposal_v2_path.write_bytes(json_data)

    logging.info("Finding meeting notes")
    mapping = build_mapping()
    meeting_mapping_path.write_bytes(adapter_meetings_map.dump_json(mapping, indent=2))

    logging.info("Saving to database")
    proposals_v2 = adapter2.validate_json(proposal_v2_path.read_bytes())
    mapping = adapter_meetings_map.validate_json(meeting_mapping_path.read_bytes())
    save_to_db(db_path, proposals_v2, mapping, project_id)


if __name__ == "__main__":
    main()
