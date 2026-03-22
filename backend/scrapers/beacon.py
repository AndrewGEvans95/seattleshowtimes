from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup

from backend.models import Showtime, Venue
from backend.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://thebeacon.film/calendar"
USER_AGENT = "SeattleShowtimes/1.0 (personal aggregator)"

SKIP_TITLES = {"RENT THE BEACON"}


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

    # Each section.showtime is one screening; it has schema.org itemprop attributes
    for showing in soup.select("section.showtime"):
        # ISO datetime from content attribute: "2026-03-23T16:30"
        time_el = showing.select_one("section.time[content]")
        if not time_el:
            continue
        iso_dt = time_el.get("content", "")
        try:
            dt = datetime.fromisoformat(iso_dt)
        except ValueError:
            logger.warning("Beacon: could not parse datetime %r", iso_dt)
            continue

        show_date = dt.date()
        if show_date < today or show_date > cutoff:
            continue

        show_time = dt.time()

        # Title
        title_el = showing.select_one("[itemprop='name']")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title or title.upper() in SKIP_TITLES:
            continue

        # Film URL
        link = showing.select_one("a[href]")
        film_url = link.get("href") if link else None

        # Poster (img is hidden but has the src)
        img = showing.select_one("img[itemprop='image']")
        poster_url = img.get("src") if img else None

        # Ticket URL
        ticket_link = showing.select_one("[itemprop='offers'] a[itemprop='url']")
        ticket_url = ticket_link.get("href") if ticket_link else None

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

    logger.info("Beacon: scraped %d showtimes", len(showtimes))
    return showtimes


class BeaconScraper(BaseScraper):
    venue = Venue.BEACON
    source_url = BASE_URL

    async def scrape(self) -> list[Showtime]:
        return await asyncio.get_event_loop().run_in_executor(None, _scrape_page)
