from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime, time, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from backend.models import Showtime, Venue
from backend.scrapers.base import BaseScraper, make_id, utc_now

logger = logging.getLogger(__name__)

IN_THEATERS_URL = "https://www.siff.net/cinema/in-theaters"
FILM_BASE_URL = "https://www.siff.net"
USER_AGENT = "SeattleShowtimes/1.0 (personal aggregator)"
HEADERS = {"User-Agent": USER_AGENT}


def _parse_epoch_ms(epoch_str: str) -> datetime | None:
    """Parse /Date(1774120500000)/ format from SIFF's data-screening JSON."""
    match = re.search(r"/Date\((\d+)\)/", epoch_str)
    if not match:
        return None
    ms = int(match.group(1))
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _fetch_film_showtimes(film_path: str, film_title: str, cutoff_date: date) -> list[Showtime]:
    """Fetch a single SIFF film detail page and extract screenings."""
    url = FILM_BASE_URL + film_path
    today = date.today()
    scraper = SIFFScraper()

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("SIFF: failed to fetch %s: %s", url, e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    showtimes: list[Showtime] = []

    # Get poster and description from the film page
    poster_url: str | None = None
    img = soup.select_one('.img-wrap img, .hero-image img, article img')
    if img and img.get('src'):
        src = img['src']
        if src.startswith('/'):
            poster_url = FILM_BASE_URL + src
        elif src.startswith('http'):
            poster_url = src

    description: str | None = None
    desc_el = soup.select_one('.field-body p, .description p, article p')
    if desc_el:
        description = desc_el.get_text(strip=True)[:500] or None

    screenings_div = soup.find(class_='screenings')
    if not screenings_div:
        return []

    for day_div in screenings_div.find_all(class_='day'):
        # Date header: <p class="h3 uppercase margin-third">Saturday, March 21, 2026</p>
        date_el = day_div.find(class_=lambda c: c and 'h3' in c.split() if c else False)
        if not date_el:
            date_el = day_div.find('p', class_=re.compile(r'\bh3\b'))
        if not date_el:
            continue

        date_text = date_el.get_text(strip=True)
        try:
            show_date = datetime.strptime(date_text, "%A, %B %d, %Y").date()
        except ValueError:
            logger.warning("SIFF: could not parse date %r", date_text)
            continue

        if show_date < today or show_date > cutoff_date:
            continue

        for screening_link in day_div.find_all('a', attrs={'data-screening': True}):
            try:
                screening_data = json.loads(screening_link['data-screening'])
            except (json.JSONDecodeError, KeyError):
                continue

            showtime_str = screening_data.get('Showtime', '')
            dt = _parse_epoch_ms(showtime_str)
            if dt is None:
                # Fall back to link text (e.g., "7:45 PM")
                time_text = screening_link.get_text(strip=True)
                try:
                    t = datetime.strptime(time_text, "%I:%M %p").time()
                except ValueError:
                    continue
            else:
                # Convert UTC epoch to Pacific time (approximate: UTC-7 or UTC-8)
                # Use the date we already know from the section header to avoid DST issues
                t = time(dt.hour, dt.minute)
                # Simple Pacific adjustment: subtract 7 or 8 hours
                # Better: just use the link text which is already local time
                time_text = screening_link.get_text(strip=True)
                try:
                    t = datetime.strptime(time_text, "%I:%M %p").time()
                except ValueError:
                    pass  # keep the UTC-derived time as fallback

            showtime_id = make_id(Venue.SIFF, film_title, show_date, t)
            showtimes.append(Showtime(
                id=showtime_id,
                title=film_title,
                venue=Venue.SIFF,
                show_date=show_date,
                show_time=t,
                poster_url=poster_url,
                description=description,
                ticket_url=url,
                film_url=url,
                scraped_at=utc_now(),
                source_url=url,
            ))

    return showtimes


class SIFFScraper(BaseScraper):
    venue = Venue.SIFF
    source_url = IN_THEATERS_URL

    async def scrape(self) -> list[Showtime]:
        today = date.today()
        cutoff = today + timedelta(days=7)

        try:
            resp = requests.get(IN_THEATERS_URL, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("SIFF: failed to fetch in-theaters page: %s", e)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")

        # Collect all film paths from the in-theaters listing
        film_paths: list[tuple[str, str]] = []  # (path, title)
        for item in soup.find_all('div', class_='item'):
            h3 = item.find('h3')
            if not h3:
                continue
            a = h3.find('a', href=True)
            if not a:
                continue
            title = h3.get_text(strip=True)
            path = a['href']
            # Only include cinema and programs paths (not festival, external, etc.)
            if path.startswith('/cinema/') or path.startswith('/programs-and-events/'):
                film_paths.append((path, title))

        logger.info("SIFF: found %d films on in-theaters page", len(film_paths))

        all_showtimes: list[Showtime] = []
        seen_ids: set[str] = set()

        for path, title in film_paths:
            result = await asyncio.get_event_loop().run_in_executor(
                None, _fetch_film_showtimes, path, title, cutoff
            )
            for st in result:
                if st.id not in seen_ids:
                    seen_ids.add(st.id)
                    all_showtimes.append(st)
            await asyncio.sleep(0.5)

        logger.info("SIFF: scraped %d showtimes total", len(all_showtimes))
        return all_showtimes
