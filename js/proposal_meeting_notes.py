import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict

import git
from pydantic import BaseModel


class MeetingNote(BaseModel):
    content: str
    created_at: datetime
    index: int
    author: str


REPO_URL = "https://github.com/tc39/notes.git"
LOCAL_DIR = Path("js/output/tc39-notes")
OUT_FILE = Path("js/output/tc39_notes_mapping.json")


def ensure_repo():
    if not LOCAL_DIR.exists():
        print(f"Cloning {REPO_URL} to {LOCAL_DIR}")
        git.Repo.clone_from(REPO_URL, LOCAL_DIR)


ANCHOR_RE = re.compile(r"#(.+?)\n", flags=re.MULTILINE)


def build_mapping() -> dict[str, list[MeetingNote]]:
    ensure_repo()

    mapping: dict[str, list[MeetingNote]] = {}
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

            markdown_files = list(md_path.glob("*.md"))
            logging.info(
                f"Processing {len(markdown_files)} meeting notes in folder {year:04d}-{month:02d}"
            )

            for md_file in markdown_files:
                if md_file.stem.count("-") != 1:
                    continue
                day = md_file.stem.split("-")[1]
                date = datetime(year=year, month=month, day=int(day))
                md_content = md_file.read_text(encoding="utf-8")
                file_url = f"{year:04d}-{month:02d}/{md_file.name}"

                header_content_map = create_header_to_content_map(md_content, date)
                for anchor, notes in header_content_map.items():
                    mapping[f"{file_url}{anchor}"] = notes

    return mapping


def create_header_to_content_map(
    markdown_text: str, date: datetime
) -> dict[str, list[MeetingNote]]:
    # Regex to match headers (lines starting with one or more #)
    header_pattern = re.compile(r"^(#+)\s+(.+)$", re.MULTILINE)
    matches = list(header_pattern.finditer(markdown_text))

    header_map = {}

    mapping = build_abbreviations_to_names_mapping(markdown_text)

    for i, match in enumerate(matches):
        level, title = match.group(1), match.group(2).strip()

        # Generate the anchor link format (GitHub-flavored)
        anchor = title.lower()
        anchor = re.sub(r"\s+", "-", anchor)
        anchor = re.sub(r"[^\w\s-]", "", anchor)

        # Determine the content boundaries
        start_idx = match.end()
        if i + 1 < len(matches):
            end_idx = matches[i + 1].start()
        else:
            end_idx = len(markdown_text)

        content = markdown_text[start_idx:end_idx].strip()

        notes = parse_text_to_meeting_notes(content, mapping, date)

        header_map[f"#{anchor}"] = notes

    return header_map


def parse_text_to_meeting_notes(
    text: str, abbreviations_to_names: dict[str, str], date: datetime
) -> list[MeetingNote]:
    notes = []
    lines = text.split("\n")
    current_speaker = None
    current_content = []

    index = 0
    for line in lines:
        stripped = line.strip()

        # Check if line starts with an abbreviation
        speaker_found = False
        for abbrev in abbreviations_to_names.keys():
            if (
                stripped.startswith(abbrev + ":")
                or stripped.startswith(abbrev + " ")
                or stripped.startswith(abbrev + ".")
                or stripped.startswith(abbrev + ",")
                or stripped == abbrev
            ):
                # Save previous speaker's note if exists
                if current_speaker and current_content:
                    note_text = "\n".join(current_content).strip()
                    if note_text:
                        name = abbreviations_to_names[current_speaker]
                        notes.append(
                            MeetingNote(
                                content=note_text,
                                created_at=date,
                                index=index,
                                author=name,
                            )
                        )
                        index += 1

                # Start new speaker's content
                current_speaker = abbrev
                # Extract content after abbreviation
                content_start = len(abbrev)
                if stripped[content_start : content_start + 1] in (":", " ", ".", ","):
                    content_start += 1
                current_content = [stripped[content_start:]]
                speaker_found = True
                break

        # If no abbreviation found and we have a current speaker, append to their content
        if not speaker_found and current_speaker:
            if stripped:  # Only add non-empty lines
                current_content.append(line)

    # Don't forget the last speaker's note
    if current_speaker and current_content:
        note_text = "\n".join(current_content).strip()
        if note_text:
            name = abbreviations_to_names[current_speaker]
            notes.append(
                MeetingNote(
                    content=note_text, created_at=date, index=index, author=name
                )
            )
            index += 1

    return notes


def parse_table(md: str) -> Dict[str, str]:
    header_re = re.compile(r"^\s*\|.*name.*\|.*abbrev", re.IGNORECASE | re.MULTILINE)
    m = header_re.search(md)
    if not m:
        return {}

    start = m.start()
    lines = md[start:].splitlines()
    if not lines:
        return {}

    start_index = None
    for i in range(10):
        line = lines[i]
        if line.strip().startswith("|") and line.strip().endswith("|"):
            start_index = i
            break
    if start_index is None:
        return {}
    header = lines[start_index]

    # Table rows follow header and a separator (---|---)
    # Collect rows while they start with '|'
    rows = []
    for line in lines[start_index + 2 :]:
        if not line.strip().startswith("|"):
            break
        rows.append(line)

    headers = [h.strip() for h in header.strip().strip("|").split("|")]
    name_i = abbr_i = org_i = None
    for i, h in enumerate(headers):
        lh = h.lower()
        if "name" in lh:
            name_i = i
        if "abbrev" in lh or "abbreviation" in lh:
            abbr_i = i
        if "organ" in lh:
            org_i = i

    results: Dict[str, str] = {}
    for r in rows:
        cols = [c.strip() for c in r.strip().strip("|").split("|")]
        if name_i is None or name_i >= len(cols):
            continue
        name = cols[name_i]
        abbr = cols[abbr_i] if (abbr_i is not None and abbr_i < len(cols)) else ""
        org = cols[org_i] if (org_i is not None and org_i < len(cols)) else ""
        results[abbr] = name
    return results


def parse_parenthetical(md: str) -> Dict[str, str]:
    # Matches patterns like: Name S. Last (ABC)
    # Name part accepts letters, dots, hyphens, apostrophes and spaces; unicode letters included
    pattern = re.compile(
        r"([A-Z][A-Za-zÀ-ÖØ-öø-ÿ'\.\- ]{1,120}?)\s*\(\s*([A-Z]{1,6})\s*\)"
    )
    matches = pattern.findall(md)
    results: Dict[str, str] = {}
    seen = set()
    for name, abbr in matches:
        name = name.strip().strip(",")
        key = (name, abbr)
        if key in seen:
            continue
        seen.add(key)
        results[abbr] = name
    return results


def build_abbreviations_to_names_mapping(md: str) -> Dict[str, str]:
    if "May 22, 2012 Meeting Notes" in md:
        md = os.environ.get("TC39_2012_05_22_mapping", "")
    elif "May 23, 2012 Meeting Notes" in md:
        md = os.environ.get("TC39_2012_05_23_mapping", "")
    table = parse_table(md)
    if table:
        return table
    return parse_parenthetical(md)
