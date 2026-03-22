from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup

from backend.models import Showtime, Venue
from backend.scrapers.base import BaseScraper, parse_12h_time

logger = logging.getLogger(__name__)

BASE_URL = "https://thebeacon.film/calendar"
SITE_BASE = "https://thebeacon.film"
USER_AGENT = "SeattleShowtimes/1.0 (personal aggregator)"

SKIP_TITLES = {"RENT THE BEACON"}


def _parse_beacon_date(date_str: str) -> date | None:
    """Parse 'Sun, Mar 22' → date, inferring year."""
    date_str = date_str.strip()
    # Strip leading weekday: "Sun, Mar 22" → "Mar 22"
    date_str = re.sub(r"^\w+,\s*", "", date_str)
    today = date.today()
    for year in (today.year, today.year + 1):
        try:
            d = datetime.strptime(f"{date_str} {year}", "%b %d %Y").date()
            if d >= today - timedelta(days=1):
                return d
        except ValueError:
            continue
    logger.warning("Could not parse beacon date: %r", date_str)
    return None


def _scrape_page() -> list[Showtime]:
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(BASE_URL, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Beacon fetch failed: %s", e)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    scraper = BeaconScraper()
    showtimes: list[Showtime] = []

    today = date.today()
    cutoff = today + timedelta(days=7)

    for cell in soup.select("section.calendarCell"):
        # Date
        date_el = cell.select_one(".ordinal .date") or cell.select_one(".date")
        if not date_el:
            continue
        show_date = _parse_beacon_date(date_el.get_text(strip=True))
        if not show_date or show_date < today or show_date > cutoff:
            continue

        # Title + time + film URL
        showtime_link = cell.select_one(".showtime a")
        if not showtime_link:
            continue

        time_el = showtime_link.select_one(".time") or showtime_link.find("span")
        time_text = time_el.get_text(strip=True) if time_el else ""

        full_text = showtime_link.get_text(separator=" ", strip=True)
        title = full_text.replace(time_text, "").strip()
        if not title:
            title = full_text

        if title.upper() in SKIP_TITLES:
            continue

        show_time = parse_12h_time(time_text)
        if show_time is None:
            logger.warning("Could not parse time %r for %r", time_text, title)
            continue

        href = showtime_link.get("href", "")
        film_url = (SITE_BASE + href) if href.startswith("/") else (href or None)

        img = cell.select_one("img")
        poster_url = None
        if img:
            src = img.get("src", "")
            poster_url = (SITE_BASE + src) if src.startswith("/") else (src or None)

        ticket_link = cell.select_one('a[href*="buy.php"]')
        ticket_url = None
        if ticket_link:
            href_t = ticket_link.get("href", "")
            ticket_url = (SITE_BASE + href_t) if href_t.startswith("/") else (href_t or None)

        showtimes.append(
            scraper.build_showtime(
                title=title,
                show_date=show_date,
                show_time=show_time,
                film_url=film_url,
                poster_url=poster_url,
                ticket_url=ticket_url,
            )
        )

    return showtimes


class BeaconScraper(BaseScraper):
    venue = Venue.BEACON
    source_url = BASE_URL

    async def scrape(self) -> list[Showtime]:
        showtimes = await asyncio.get_event_loop().run_in_executor(None, _scrape_page)
        logger.info("Beacon: scraped %d showtimes", len(showtimes))
        return showtimes
