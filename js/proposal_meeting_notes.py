from datetime import datetime
import logging
import os
import re
from pathlib import Path

import git
from pydantic import BaseModel

import re

class MeetingNote(BaseModel):
    content: str
    created_at: datetime


REPO_URL = "https://github.com/tc39/notes.git"
LOCAL_DIR = Path("js/output/tc39-notes")
OUT_FILE = Path("js/output/tc39_notes_mapping.json")


def ensure_repo():
    if not LOCAL_DIR.exists():
        print(f"Cloning {REPO_URL} to {LOCAL_DIR}")
        git.Repo.clone_from(REPO_URL, LOCAL_DIR)


ANCHOR_RE = re.compile(r"#(.+?)\n", flags=re.MULTILINE)





def create_header_content_map(markdown_text):
    # Regex to match headers (lines starting with one or more #)
    header_pattern = re.compile(r'^(#+)\s+(.+)$', re.MULTILINE)
    matches = list(header_pattern.finditer(markdown_text))
    
    header_map = {}
    
    for i, match in enumerate(matches):
        level, title = match.group(1), match.group(2).strip()
        
        # Generate the anchor link format (GitHub-flavored)
        anchor = title.lower()
        anchor = re.sub(r'\s+', '-', anchor)
        anchor = re.sub(r'[^\w\s-]', '', anchor)
        
        # Determine the content boundaries
        start_idx = match.end()
        if i + 1 < len(matches):
            end_idx = matches[i+1].start()
        else:
            end_idx = len(markdown_text)
            
        content = markdown_text[start_idx:end_idx].strip()
        
        header_map[f'#{anchor}'] = content
        
    return header_map


def build_mapping() -> dict[str, MeetingNote]:
    ensure_repo()

    mapping: dict[str, MeetingNote] = {}
    meetings_dir = LOCAL_DIR / "meetings"
    if not meetings_dir.exists():
        raise RuntimeError(f"Expected meetings directory at {meetings_dir} not found")
    start_year = 2012
    end_year = datetime.now().year
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            md_path = meetings_dir / f"{year:04d}-{month:02d}"
            if not md_path.exists():
                continue
            logging.info(f"Processing meeting notes in folder {year:04d}-{month:02d}")

            markdown_files = list(md_path.glob("*.md"))
            for md_file in markdown_files:
                if  md_file.stem.count("-") != 1:
                    continue
                logging.info(f"Processing {md_file}")
                day = md_file.stem.split("-")[1]
                date = datetime(year=year, month=month, day=int(day))
                md_content = md_file.read_text(encoding="utf-8")
                file_url = f"{year:04d}-{month:02d}/{md_file.name}"

                header_content_map = create_header_content_map(md_content)
                for anchor, content in header_content_map.items():
                    mapping[f"{file_url}{anchor}"] = MeetingNote(content=content, created_at=date)
    
    return mapping

            
