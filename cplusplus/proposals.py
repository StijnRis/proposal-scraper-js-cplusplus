import asyncio
import logging
import re
from datetime import datetime
from typing import List, Tuple

import fitz
import requests
from bs4 import BeautifulSoup
from requests.compat import urljoin
from tqdm.asyncio import tqdm_asyncio

from cplusplus.models import Proposal, ProposalRevision

YEAR_URL_TEMPLATE = "https://www.open-std.org/jtc1/sc22/wg21/docs/papers/{year}/"

revisions_to_fetch: List[Tuple[ProposalRevision, str]] = []


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def is_proposal(num_text: str) -> bool:
    # Recognize revision ids like P3039R1
    m = re.match(r"^(P\d+)(?:R(\d+))?$", num_text)
    if m:
        return True

    # Recognize N1234
    m = re.match(r"^(N\d+)$", num_text)
    if m:
        return True

    return False


def parse_content(url: str) -> str:
    resp = requests.get(url, timeout=15)
    ctype = resp.headers.get("Content-Type", "")
    if "text/html" in ctype:
        s = BeautifulSoup(resp.content, "html5lib")
        return s.get_text(separator="\n", strip=True)
    elif "application/pdf" in ctype:
        try:
            doc = fitz.open(stream=resp.content, filetype="pdf")
            content = ""
            for page in doc:
                content += str(page.get_text())
            return content
        except Exception as e:
            logging.error(f"Failed to parse PDF content from {url}: {e}")
            return ""
    elif "application/pgp-keys" in ctype or "text/plain" in ctype:
        return resp.text
    else:
        logging.warning(f"Unknown content type {ctype} for URL {url}, treating as text")
        return resp.text


async def fetch_all_contents():
    logging.info(
        f"Fetching content for {len(revisions_to_fetch)} revisions with concurrency"
    )
    semaphore = asyncio.Semaphore(30)

    async def fetch_revision_content(revision, href):
        async with semaphore:
            content = await asyncio.to_thread(parse_content, href)
            revision.content = content

    await tqdm_asyncio.gather(
        *(fetch_revision_content(rev, href) for rev, href in revisions_to_fetch)
    )


def parse_date(date_str: str, year: int) -> datetime:
    if not date_str or date_str.strip() == "":
        logging.warning(f"Empty date string, using default date with year {year}")
        return datetime(year, 1, 1)

    date_str = date_str.replace("??", "01")
    date_str = date_str.replace("'", "")
    date_str = date_str.replace("‐", "-")  # Hyphen
    date_str = date_str.replace("–", "-")  # En dash
    date_str = date_str.replace("—", "-")  # Em dash
    date_str = date_str.replace("\xad10", "")  # Em dash
    if date_str.count("-") == 1:
        date_str += "-01"
    formats = ["%Y-%m-%d", "%Y%m%d", "%Y", "%y-%m-%d"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    logging.warning(
        f"Could not parse date {date_str}, using default date with year {year}"
    )
    return datetime(year, 1, 1)


def parse_table_rows(
    proposals: dict[str, Proposal],
    soup,
    base_url,
    year: int,
    include_PL_number: bool = False,
):

    tables = soup.find_all("table")
    if len(tables) == 0:
        raise ValueError("No tables found on the page")
    for table in tables:
        rows = table.find_all("tr")
        for tr in rows:
            tds = tr.find_all(["td", "th"])

            # check if contains colspan="8"
            if any(td.get("colspan") == "8" for td in tds):
                # This is a header row, skip it
                continue

            # Check if empty
            if len(tds) == 0:
                continue

            # Extract columns similar to the screenshot layout
            # Columns: number, title, author, document date, mailing date, previous version, subgroup, disposition
            proposal_id_cell = tds[0]

            PL_number = tds[1] if include_PL_number else None
            number_offset = 1 if include_PL_number else 0
            title_cell = tds[1 + number_offset]
            author_cell = tds[2 + number_offset]
            doc_date_cell = tds[3 + number_offset]
            mailing_date_cell = tds[4 + number_offset]
            prev_version_cell = tds[5 + number_offset]
            subgroup = ""
            if len(tds) > 6 + number_offset:
                subgroup = tds[6 + number_offset].get_text(strip=True)
            # disposition_cell = tds[7 + number_offset]

            proposal_id = proposal_id_cell.get_text(strip=True)
            if not proposal_id:
                logging.warning("Skipping row with empty proposal id cell")

            if proposal_id in ["WG21 Number"]:
                continue

            logging.debug(f"Processing row: {proposal_id_cell}")

            # If format P1234R1, extract base id P1234
            m = re.match(r"^(P\d+)(?:R\d+)?$", proposal_id)
            if m:
                proposal_id = m.group(1)

            title = title_cell.get_text(strip=True)
            authors = [a.strip() for a in (author_cell.get_text(strip=True).split(","))]
            doc_date_text = doc_date_cell.get_text(strip=True)
            doc_date = parse_date(doc_date_text, year)

            if not is_proposal(proposal_id):
                # skip rows that don't look like proposals
                logging.info(f"Skipping non-proposal row: {proposal_id} - {title}")
                continue

            # Recognize revision ids like P3039R1

            if proposal_id not in proposals:
                proposals[proposal_id] = Proposal(
                    proposal_id=proposal_id,
                    stages=[],
                    subgroup=subgroup,
                    revisions=[],
                )

            # Create revision object
            revision = ProposalRevision(
                proposal_id=proposal_id,
                title=title,
                created_at=doc_date,
                content="",
                authors=set(authors),
            )

            # find the link to the proposal content
            link_tag = proposal_id_cell.find("a")
            if link_tag:
                href = urljoin(base_url, link_tag["href"])
                revisions_to_fetch.append((revision, href))
            else:
                logging.info(
                    f"No link found for proposal {proposal_id} in row, skipping content"
                )

            proposals[proposal_id].revisions.append(revision)

    return proposals


def parse_table_old_rows(proposals: dict[str, Proposal], soup, base_url, year: int):
    tables = soup.find_all("table")
    if len(tables) == 0:
        raise ValueError("No tables found on the page")
    for table in tables:
        for tr in table.find_all("tr"):
            tds = tr.find_all(["td", "th"])

            # check if contains colspan="8"
            if any(td.get("colspan") == "8" for td in tds):
                # This is a header row, skip it
                continue

            # Extract columns similar to the screenshot layout
            # Columns: number, title, author, document date, mailing date, previous version, subgroup, disposition
            proposal_id_cell_1 = tds[0]
            proposal_id_cell_2 = tds[1]
            title_cell = tds[2]
            author_cell = tds[3]

            doc_date = datetime(year, 1, 1)
            if len(tds) > 4:
                doc_date_cell = tds[4]
                doc_date_text = doc_date_cell.get_text(strip=True)
                doc_date = parse_date(doc_date_text, year)

            # Check if proposal_id_cell_1 or 2 is a link
            link_tag_1 = proposal_id_cell_1.find("a")
            link_tag_2 = proposal_id_cell_2.find("a")

            proposal_id_cell = None
            if link_tag_1 and link_tag_2:
                raise ValueError("Unexpected row with two links in proposal id cells")
            elif link_tag_1:
                proposal_id_cell = proposal_id_cell_1
            elif link_tag_2:
                proposal_id_cell = proposal_id_cell_2
            elif proposal_id_cell_2.get_text(strip=True) in ["02-0068"]:
                continue
            else:
                raise ValueError("Proposal row missing link in proposal id cells")

            proposal_id = proposal_id_cell.get_text(strip=True)
            if not proposal_id:
                raise ValueError("Proposal row missing number cell")

            if proposal_id in ["WG21 Number"]:
                continue

            logging.debug(f"Processing row: {proposal_id_cell}")

            # find the link to the proposal content
            link_tag = proposal_id_cell.find("a")
            if not link_tag:
                raise ValueError("Proposal number cell missing link")
            href = urljoin(base_url, link_tag["href"])

            title = title_cell.get_text(strip=True)
            authors = [a.strip() for a in (author_cell.get_text(strip=True).split(","))]

            if not is_proposal(proposal_id):
                # skip rows that don't look like proposals
                logging.info(f"Skipping non-proposal row: {proposal_id} - {title}")
                continue

            # Recognize revision ids like P3039R1

            if proposal_id not in proposals:
                proposals[proposal_id] = Proposal(
                    proposal_id=proposal_id,
                    stages=[],
                    subgroup="",
                    revisions=[],
                )

            # Create revision object
            revision = ProposalRevision(
                proposal_id=proposal_id,
                title=title,
                created_at=doc_date,
                content="",
                authors=set(authors),
            )

            revisions_to_fetch.append((revision, href))

            proposals[proposal_id].revisions.append(revision)

    return proposals


def parse_list(proposals: dict[str, Proposal], soup, base_url, year: int):
    list_items = soup.find_all("li")
    if len(list_items) == 0:
        raise ValueError("No list items found on the page")
    for li in list_items:
        text = li.get_text(strip=True)
        if not text:
            raise ValueError("Empty list item found on the page")

        # If pattern "SD-x" skip
        if re.search(r"SD-\d+", text):
            logging.info(f"Skipping list item with SD- pattern: {text}")
            continue

        # If pattern "SDx" skip
        if re.search(r"SD\d+", text):
            logging.info(f"Skipping list item with SD pattern: {text}")
            continue

        # Look for patterns like "N1233"
        m = re.search(r"(N\d{4})", text)
        if not m:
            raise ValueError(f"Unexpected list item format: {text}")

        proposal_id = m.group(1)

        logging.debug(f"Processing list item: {proposal_id}")

        # title is in bold
        bold = li.find("b")
        title = bold.get_text(strip=True)

        # Authors are in italic comma seperated
        italics = li.find("i")
        authors = italics.get_text(strip=True).split(",")

        if proposal_id not in proposals:
            proposals[proposal_id] = Proposal(
                proposal_id=proposal_id,
                stages=[],
                subgroup="",
                revisions=[],
            )

        # Look link in list item with content [...]
        link_tags = ["[ASCII]", "[ASC]", "[PDF]", "[HTML]"]
        link_tag = None
        for marker in link_tags:
            link_tag = li.find("a", string=marker)
            if link_tag:
                break

        revision = ProposalRevision(
            proposal_id=proposal_id,
            title=title,
            created_at=datetime(year, 1, 1),
            content="",
            authors=set(authors),
        )
        proposals[proposal_id].revisions.append(revision)

        if link_tag:
            href = urljoin(base_url, link_tag["href"])
            revisions_to_fetch.append((revision, href))
        else:
            if li.find("a"):
                raise ValueError(
                    f"List item has a link but no [ASCII] or [PDF] marker: {text}"
                )
            logging.warning(
                f"No content link found for proposal {proposal_id} in list item, skipping content"
            )

    return proposals


def parse_text_blob_by_line(proposals: dict[str, Proposal], soup, base_url):
    pres = soup.find_all("pre")
    if len(pres) == 0:
        raise ValueError("No <pre> blocks found on the page")

    # Try to infer year from base_url (e.g. .../2000/)
    year_match = re.search(r"/(\d{4})/", base_url)
    year = int(year_match.group(1)) if year_match else None
    if not year:
        raise ValueError(f"Could not infer year from URL {base_url}")

    for pre in pres:
        inner_html = pre.decode_contents()
        lines: list[str] = inner_html.splitlines()
        text_lines = pre.get_text().splitlines()

        assert len(lines) == len(text_lines)

        for line_number in range(len(lines)):
            line_text = text_lines[line_number]

            if "<h1>" in lines[line_number]:
                break

            _ = line_text[0:10].strip()
            proposal_id = line_text[10:18].strip()
            if proposal_id == "" or proposal_id.startswith("SD"):
                continue

            soup = BeautifulSoup(lines[line_number], "html5lib")
            link = soup.find("a")
            logging.debug(f"Processing proposal {proposal_id}")

            content_url = None
            if link and link.get("href"):
                content_url = urljoin(base_url, link["href"])

            title = ""
            authors = ""

            for next_line_number in range(line_number, len(lines)):
                next_line = text_lines[next_line_number]
                if next_line[10:18].strip() != "" and next_line_number != line_number:
                    break
                title += " " + next_line[18:60].strip()
                authors += " " + next_line[60:79].strip()

            authors_list = [a.strip() for a in authors.replace(" and ", ",").split(",")]
            if proposal_id not in proposals:
                proposals[proposal_id] = Proposal(
                    proposal_id=proposal_id,
                    stages=[],
                    subgroup="",
                    revisions=[],
                )

            revision = ProposalRevision(
                proposal_id=proposal_id,
                title=title.strip(),
                created_at=datetime(year, 1, 1),
                content="",
                authors=set(authors_list),
            )
            proposals[proposal_id].revisions.append(revision)

            if content_url:
                revisions_to_fetch.append((revision, content_url))
            else:
                logging.warning(
                    f"No content link found for proposal {proposal_id} in text blob, skipping content"
                )

    return proposals


def parse_text_blob_multiple_lines(proposals: dict[str, Proposal], soup, base_url):
    # Similar to parse_text_blob_by_line but proposals can span multiple lines, we look for lines starting with a proposal id and treat following indented lines as continuation until next line starting with proposal id
    pres = soup.find_all("pre")
    if len(pres) == 0:
        raise ValueError("No <pre> blocks found on the page")

    # Try to infer year from base_url (e.g. .../2000/)
    year_match = re.search(r"/(\d{4})/", base_url)
    year = int(year_match.group(1)) if year_match else None
    if not year:
        raise ValueError(f"Could not infer year from URL {base_url}")

    for pre in pres:
        inner_html = pre.decode_contents()
        lines = inner_html.splitlines()

        for line_number in range(0, len(lines)):
            x3j16_number = lines[line_number]
            if not x3j16_number.startswith("X3J16"):
                continue
            wg21_number_line = lines[line_number + 1]
            title_line = lines[line_number + 2]
            author_line = lines[line_number + 3]

            wg21_number_item = BeautifulSoup(
                wg21_number_line.replace("WG21 Number", "").replace(":", "").strip(),
                "html.parser",
            )
            wg21_number = wg21_number_item.get_text(strip=True)
            if wg21_number[0:2] == "SD":
                continue
            logging.debug(f"Processing proposal {wg21_number}")
            proposal_id = wg21_number

            title = title_line.replace("Title", "").strip()
            author = author_line.replace("Author", "").strip()

            if proposal_id not in proposals:
                proposals[proposal_id] = Proposal(
                    proposal_id=proposal_id,
                    stages=[],
                    subgroup="",
                    revisions=[],
                )

            revision = ProposalRevision(
                proposal_id=proposal_id,
                title=title,
                created_at=datetime(year, 1, 1),
                content="",
                authors=set(
                    [a.strip() for a in author.replace(" and ", ",").split(",")]
                ),
            )
            proposals[proposal_id].revisions.append(revision)

            link = wg21_number_item.find("a")
            if link:
                href = urljoin(base_url, link["href"])
                revisions_to_fetch.append((revision, href))
            else:
                logging.warning(
                    f"No content link found for proposal {proposal_id} in text blob, skipping content"
                )

    return proposals


def scrape_year(proposals: dict[str, Proposal], year: int):
    url = YEAR_URL_TEMPLATE.format(year=year)
    logging.debug(f"Fetching {url}")
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html5lib")

    if year == 1995:
        proposals = parse_list(proposals, soup, url, year)
        proposals = parse_text_blob_multiple_lines(proposals, soup, url)
        return proposals
    if year >= 2013:
        return parse_table_rows(proposals, soup, url, year, include_PL_number=False)
    if year >= 2004:
        return parse_table_rows(proposals, soup, url, year, include_PL_number=True)
    elif year >= 2002:
        return parse_table_old_rows(proposals, soup, url, year)
    elif year >= 2001:
        proposals = parse_text_blob_by_line(proposals, soup, url)
        proposals = parse_table_old_rows(proposals, soup, url, year)
        return proposals
    elif year >= 2000:
        return parse_text_blob_by_line(proposals, soup, url)
    elif year >= 1992:
        return parse_list(proposals, soup, url, year)
    raise ValueError(f"Unsupported year format: {year}")
