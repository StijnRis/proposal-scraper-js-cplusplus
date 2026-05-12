import asyncio
import logging
from pathlib import Path
from typing import Dict

from pydantic import TypeAdapter

from cplusplus.emails import fetch_all_emails
from cplusplus.insert_db import save_to_db
from cplusplus.models import Comment, Proposal
from cplusplus.proposal_stages import add_proposal_stages
from cplusplus.proposals import fetch_all_contents, scrape_year

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def main():
    project_id = 4
    start_year = 1992
    end_year = 2026
    proposals = {}

    proposals_path = Path("cplusplus/output/proposals.json")
    proposals_with_stages_path = Path("cplusplus/output/proposals_with_stages.json")
    comments_path = Path("./cplusplus/output/comments.json")
    db_path = Path("cplusplus/output/cplusplus_proposals.sqlite3")

    adapter = TypeAdapter(Dict[str, Proposal])
    adapter_comments = TypeAdapter(list[Comment])

    if not proposals_path.exists():
        logging.info("Finding proposals...")
        for year in range(start_year, end_year + 1):
            logging.info(f"Processing year {year}...")
            proposals.update(scrape_year(proposals, year))
            logging.info(f"After processing {year}, total proposals: {len(proposals)}")
        asyncio.run(fetch_all_contents())
        proposals_path.write_bytes(adapter.dump_json(proposals, indent=2))
        logging.debug(f"Wrote {len(proposals)} proposals to proposals.json")

    if not proposals_with_stages_path.exists():
        logging.info("Adding stages to proposals...")
        proposals = adapter.validate_json(proposals_path.read_bytes())
        proposals_with_stages = add_proposal_stages(proposals)
        proposals_with_stages_path.write_bytes(
            adapter.dump_json(proposals_with_stages, indent=2)
        )

    if not comments_path.exists():
        logging.info("Fetching and parsing emails...")
        comments = asyncio.run(fetch_all_emails())
        comments_path.write_bytes(adapter_comments.dump_json(comments, indent=2))
        logging.info(f"Wrote {len(comments)} comments to {comments_path}")

    # Save to DB
    logging.info("Saving to database...")
    comments = adapter_comments.validate_json(comments_path.read_bytes())
    proposals_with_stages = adapter.validate_json(
        proposals_with_stages_path.read_bytes()
    )
    save_to_db(db_path, proposals_with_stages, comments, project_id=project_id)


if __name__ == "__main__":
    main()
