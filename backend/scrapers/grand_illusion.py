from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from backend.models import Showtime, Venue
from backend.scrapers.base import BaseScraper, parse_12h_time

logger = logging.getLogger(__name__)

BASE_URL = "https://grandillusioncinema.org/calendar/"
FILM_URL_BASE = "https://grandillusioncinema.org/?p="
USER_AGENT = "SeattleShowtimes/1.0 (personal aggregator)"


def _parse_date_str(date_str: str) -> date | None:
    """Parse 'Monday, March 2, 2026' → date object."""
    try:
        return date.fromisoformat(
            __import__("datetime").datetime.strptime(date_str.strip(), "%A, %B %d, %Y").strftime("%Y-%m-%d")
        )
    except ValueError:
        logger.warning("Could not parse date: %r", date_str)
        return None


def _get_month_url(target: date) -> str:
    return f"{BASE_URL}?month={target.strftime('%Y-%m')}"


def _scrape_month(target: date) -> list[Showtime]:
    url = _get_month_url(target)
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Grand Illusion fetch failed for %s: %s", url, e)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    showtimes: list[Showtime] = []
    scraper = GrandIllusionScraper()

    today = date.today()
    cutoff = today + timedelta(days=7)

    for day_li in soup.select("li.day:not(.heading)"):
        date_el = day_li.select_one(".date-display--day__full")
        if not date_el:
            continue
        show_date = _parse_date_str(date_el.get_text(strip=True))
        if not show_date:
            continue
        # Only include dates within the next 7 days
        if show_date < today or show_date > cutoff:
            continue

        for film_btn in day_li.select("button.film"):
            title_el = film_btn.select_one(".film-title")
            times_el = film_btn.select_one(".film-times")
            film_id = film_btn.get("data-filmid")

            if not title_el or not times_el:
                continue

            title = title_el.get_text(strip=True)
            times_text = times_el.get_text(strip=True)
            film_url = f"{FILM_URL_BASE}{film_id}" if film_id else None

            # Times field may contain multiple times separated by commas or newlines
            for raw_time in re.split(r"[,\n]", times_text):
                show_time = parse_12h_time(raw_time.strip())
                if show_time is None:
                    logger.warning("Could not parse time %r for %r", raw_time, title)
                    continue

                showtimes.append(
                    scraper.build_showtime(
                        title=title,
                        show_date=show_date,
                        show_time=show_time,
                        film_url=film_url,
                        ticket_url="https://grandillusioncinema.org/tickets-and-info/",
                    )
                )

    return showtimes


class GrandIllusionScraper(BaseScraper):
    venue = Venue.GRAND_ILLUSION
    source_url = BASE_URL

    async def scrape(self) -> list[Showtime]:
        showtimes: list[Showtime] = []

        today = date.today()
        months_to_scrape = {today.replace(day=1)}
        # If we're within 7 days of end of month, also scrape next month
        next_month_start = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        if (next_month_start - today).days <= 7:
            months_to_scrape.add(next_month_start)

        for month_start in sorted(months_to_scrape):
            result = await asyncio.get_event_loop().run_in_executor(
                None, _scrape_month, month_start
            )
            showtimes.extend(result)
            await asyncio.sleep(1)

        logger.info("Grand Illusion: scraped %d showtimes", len(showtimes))
        return showtimes
