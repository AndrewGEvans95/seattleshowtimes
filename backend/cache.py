from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from backend.models import Showtime

logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).parent.parent / "data" / "showtimes_cache.json"


def _ensure_data_dir() -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)


def write_venue_cache(venue_key: str, showtimes: list[Showtime], error: str | None = None) -> None:
    _ensure_data_dir()
    cache = _read_raw()
    cache[venue_key] = {
        "showtimes": [st.model_dump(mode="json") for st in showtimes],
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "error": error,
    }
    try:
        CACHE_FILE.write_text(json.dumps(cache, default=str, indent=2))
    except OSError as e:
        logger.error("Failed to write cache: %s", e)


def _read_raw() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read cache: %s", e)
        return {}


def read_all_showtimes() -> tuple[list[Showtime], dict[str, str], list[str]]:
    """Returns (showtimes, last_updated_per_venue, stale_venues)."""
    cache = _read_raw()
    all_showtimes: list[Showtime] = []
    last_updated: dict[str, str] = {}
    stale_venues: list[str] = []

    for venue_key, data in cache.items():
        last_updated[venue_key] = data.get("scraped_at", "unknown")
        if data.get("error"):
            stale_venues.append(venue_key)
        for raw in data.get("showtimes", []):
            try:
                all_showtimes.append(Showtime.model_validate(raw))
            except Exception as e:
                logger.warning("Skipping invalid showtime entry: %s", e)

    return all_showtimes, last_updated, stale_venues
