from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import date, time, datetime, timezone
from typing import Optional

from backend.models import Showtime, Venue


def make_id(venue: Venue, title: str, show_date: date, show_time: time) -> str:
    raw = f"{venue}:{title}:{show_date.isoformat()}:{show_time.isoformat()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_12h_time(time_str: str) -> Optional[time]:
    """Parse times like '7:15pm', '12:00 PM', '9:30am'."""
    import re
    time_str = time_str.strip().lower().replace(" ", "")
    match = re.match(r"(\d{1,2}):?(\d{2})?(am|pm)", time_str)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2)) if match.group(2) else 0
    period = match.group(3)
    if period == "pm" and hour != 12:
        hour += 12
    elif period == "am" and hour == 12:
        hour = 0
    try:
        return time(hour, minute)
    except ValueError:
        return None


class BaseScraper(ABC):
    venue: Venue
    source_url: str

    def build_showtime(
        self,
        title: str,
        show_date: date,
        show_time: time,
        ticket_url: Optional[str] = None,
        film_url: Optional[str] = None,
        poster_url: Optional[str] = None,
        description: Optional[str] = None,
        director: Optional[str] = None,
        year: Optional[int] = None,
        runtime_minutes: Optional[int] = None,
    ) -> Showtime:
        return Showtime(
            id=make_id(self.venue, title, show_date, show_time),
            title=title,
            venue=self.venue,
            show_date=show_date,
            show_time=show_time,
            ticket_url=ticket_url,
            film_url=film_url,
            poster_url=poster_url,
            description=description,
            director=director,
            year=year,
            runtime_minutes=runtime_minutes,
            scraped_at=utc_now(),
            source_url=self.source_url,
        )

    @abstractmethod
    async def scrape(self) -> list[Showtime]:
        pass
