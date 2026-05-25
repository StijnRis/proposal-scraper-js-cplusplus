import asyncio
import datetime
import logging
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from cplusplus.models import Comment

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

BASE = "https://lists.isocpp.org/std-proposals/"


async def fetch(client: httpx.AsyncClient, url: str, timeout: float = 30.0) -> str:
    resp = await client.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


async def list_month_messages(client: httpx.AsyncClient, month_url: str) -> list[str]:
    logging.info(f"Fetching month index {month_url}")
    html = await fetch(client, month_url)
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/\d{4}/\d{2}/\d+\.php$", href) or re.match(r"^\d+\.php$", href):
            if href.startswith("http"):
                urls.append(href)
            elif href.startswith("/"):
                urls.append("https://lists.isocpp.org" + href)
            else:
                base_dir = month_url.rsplit("/", 1)[0]
                urls.append(base_dir + "/" + href)
    return sorted(dict.fromkeys(urls))


def parse_message_page(url: str, html: str) -> Comment:
    logging.info(f"Parsing message {url}")
    soup = BeautifulSoup(html, "html.parser")

    # Extract From: line
    address_field = soup.find("address")
    if not address_field:
        raise RuntimeError(f"Could not find address field in message {url}")
    groups = re.search(
        r"^From:\s*(.+)<(.+)>$", address_field.get_text(), flags=re.MULTILINE
    )
    if not groups:
        raise RuntimeError(f"Could not parse From line in message {url}")
    author_name = groups.group(1).strip()
    author_email = groups.group(2).strip()

    # Date: prefer 'Received on'
    date_item = soup.find(class_="received")
    if not date_item:
        raise RuntimeError(f"Could not find Received on line in message {url}")
    date_string = date_item.get_text(strip=True)
    date_string = date_string.replace("Received on", "").strip()
    date = datetime.datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")

    # Content: take text between the Date: line (or From:) and 'Received on' or 'Last message date' or end
    content_item = soup.find(id="start")
    if not content_item:
        raise RuntimeError(f"Could not find content in message {url}")
    content = content_item.get_text(strip=True)

    reply_to_message_id = None
    message_id = url.rstrip("/").rsplit("/", 1)[-1].replace(".php", "")
    list_items = soup.find_all("li")
    for li in list_items:
        if "In reply to:" in li.get_text():
            link = li.find("a")
            if not link:
                raise RuntimeError(
                    f"Could not find link in In reply to line in message {url}"
                )

            reply_to_message_id = int(link["href"].replace(".php", "").split("/")[-1])

    return Comment(
        proposal_id=None,
        message_id=int(message_id),
        url=url,
        reply_to_message_id=reply_to_message_id,
        author_name=author_name,
        source_domain="isocpp.org",
        author_email=author_email,
        date=date,
        content=content,
    )


async def fetch_and_parse(
    client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore
) -> Optional[Comment]:
    async with semaphore:
        html = await fetch(client, url)
        # Offload synchronous parsing to a thread to keep async event loop responsive
        return await asyncio.to_thread(parse_message_page, url, html)


async def fetch_all_emails() -> list[Comment]:

    logging.info("Fetching archive index to list months")

    start_year = 2019
    start_month = 4

    end_year = datetime.datetime.now().year
    end_month = datetime.datetime.now().month

    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Pre-populate all the month URLs we need
        all_month_urls = []
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                if (year == start_year and month < start_month) or (
                    year == end_year and month > end_month
                ):
                    continue
                all_month_urls.append(BASE + f"{year}/{month:02d}/")

        # 1. Fetch month URLs in parallel
        month_tasks = [list_month_messages(client, url) for url in all_month_urls]
        all_results = await asyncio.gather(*month_tasks)

        # Flatten and deduplicate the list of message URLs
        message_urls = sorted(
            list(dict.fromkeys([url for res in all_results for url in res]))
        )
        logging.info(f"Found {len(message_urls)} total messages to fetch.")

        # 2. Use a semaphore to limit concurrent HTTP requests
        semaphore = asyncio.Semaphore(50)
        tasks = [fetch_and_parse(client, url, semaphore) for url in message_urls]

        results = await asyncio.gather(*tasks)

    comments: list[Comment] = [c for c in results if c is not None]

    return comments
