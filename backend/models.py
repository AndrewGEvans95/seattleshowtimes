from __future__ import annotations

from pydantic import BaseModel
from datetime import date, time, datetime
from typing import Optional
import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum
    class StrEnum(str, Enum):
        pass


class Venue(StrEnum):
    SIFF = "SIFF"
    NWFF = "Northwest Film Forum"
    GRAND_ILLUSION = "Grand Illusion Cinema"
    BEACON = "The Beacon"


class Showtime(BaseModel):
    id: str
    title: str
    venue: Venue
    show_date: date
    show_time: time
    poster_url: Optional[str] = None
    description: Optional[str] = None
    director: Optional[str] = None
    year: Optional[int] = None
    runtime_minutes: Optional[int] = None
    ticket_url: Optional[str] = None
    film_url: Optional[str] = None
    scraped_at: datetime
    source_url: str


class ScrapeResult(BaseModel):
    venue: Venue
    success: bool
    showtimes: list[Showtime]
    error: Optional[str] = None
    scraped_at: datetime


class ShowtimesResponse(BaseModel):
    showtimes: list[Showtime]
    last_updated: dict[str, str]
    stale_venues: list[str]
