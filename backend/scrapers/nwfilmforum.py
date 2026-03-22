from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup

from backend.models import Showtime, Venue
from backend.scrapers.base import BaseScraper, make_id, utc_now

logger = logging.getLogger(__name__)

CALENDAR_URL = "https://nwfilmforum.org/calendar"
USER_AGENT = "SeattleShowtimes/1.0 (personal aggregator)"
HEADERS = {"User-Agent": USER_AGENT}


def _get_week_starts(num_weeks: int = 3) -> list[date]:
    today = date.today()
    # NWFF uses Sunday-anchored weeks based on observed ?start= param behavior
    # Start from today's Sunday
    sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    return [sunday + timedelta(weeks=i) for i in range(num_weeks)]


def _scrape_week(week_start: date, cutoff: date) -> list[Showtime]:
    today = date.today()
    url = f"{CALENDAR_URL}?start={week_start.isoformat()}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("NWFF: failed to fetch %s: %s", url, e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    showtimes: list[Showtime] = []

    for item in soup.find_all(class_='calendar__item'):
        classes = item.get('class', [])
        # Only include film screenings
        if 'calendar__item--film' not in classes:
            continue

        # Title from schema.org meta
        title_meta = item.find('meta', itemprop='name')
        if not title_meta or not title_meta.get('content'):
            continue
        title = title_meta['content'].strip()

        # Start datetime from schema.org meta: "2026-03-21T16:00:00"
        start_meta = item.find('meta', itemprop='startDate')
        if not start_meta or not start_meta.get('content'):
            continue
        try:
            dt = datetime.fromisoformat(start_meta['content'])
        except ValueError:
            logger.warning("NWFF: could not parse startDate %r for %r", start_meta['content'], title)
            continue

        show_date = dt.date()
        if show_date < today or show_date > cutoff:
            continue

        show_time = dt.time()

        # Film URL
        link = item.find('a', class_='calendar__item__link')
        film_url = link['href'] if link and link.get('href') else None

        # Poster image
        poster_el = item.find(attrs={'component-graceful-image-load': True})
        poster_url: str | None = None
        if poster_el:
            poster_url = poster_el.get('component-graceful-image-load') or None

        # Runtime
        duration_meta = item.find('meta', itemprop='duration')
        runtime_minutes: int | None = None
        if duration_meta and duration_meta.get('content'):
            import re
            m = re.match(r'PT(\d+)M', duration_meta['content'])
            if m:
                runtime_minutes = int(m.group(1))

        showtime_id = make_id(Venue.NWFF, title, show_date, show_time)
        showtimes.append(Showtime(
            id=showtime_id,
            title=title,
            venue=Venue.NWFF,
            show_date=show_date,
            show_time=show_time,
            poster_url=poster_url,
            film_url=film_url,
            ticket_url=film_url,
            runtime_minutes=runtime_minutes,
            scraped_at=utc_now(),
            source_url=url,
        ))

    return showtimes


class NWFFScraper(BaseScraper):
    venue = Venue.NWFF
    source_url = CALENDAR_URL

    async def scrape(self) -> list[Showtime]:
        cutoff = date.today() + timedelta(days=7)
        all_showtimes: list[Showtime] = []
        seen_ids: set[str] = set()

        for week_start in _get_week_starts(num_weeks=2):
            result = await asyncio.get_event_loop().run_in_executor(
                None, _scrape_week, week_start, cutoff
            )
            for st in result:
                if st.id not in seen_ids:
                    seen_ids.add(st.id)
                    all_showtimes.append(st)
            await asyncio.sleep(1)

        logger.info("NWFF: scraped %d showtimes", len(all_showtimes))
        return all_showtimes
