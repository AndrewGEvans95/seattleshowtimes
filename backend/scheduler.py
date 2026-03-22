from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.cache import write_venue_cache
from backend.models import Venue
from backend.scrapers.grand_illusion import GrandIllusionScraper
from backend.scrapers.nwfilmforum import NWFFScraper
from backend.scrapers.siff import SIFFScraper

logger = logging.getLogger(__name__)


async def _run_scraper(scraper_cls, venue_key: str) -> None:
    scraper = scraper_cls()
    try:
        showtimes = await scraper.scrape()
        write_venue_cache(venue_key, showtimes)
        logger.info("%s: cached %d showtimes", venue_key, len(showtimes))
    except Exception as e:
        logger.error("%s: scrape failed: %s", venue_key, e, exc_info=True)
        write_venue_cache(venue_key, [], error=str(e))


async def refresh_grand_illusion() -> None:
    await _run_scraper(GrandIllusionScraper, Venue.GRAND_ILLUSION)


async def refresh_siff() -> None:
    await _run_scraper(SIFFScraper, Venue.SIFF)


async def refresh_nwff() -> None:
    await _run_scraper(NWFFScraper, Venue.NWFF)


async def refresh_all() -> None:
    # Run sequentially to be polite and conserve RAM
    await refresh_grand_illusion()
    await refresh_siff()
    await refresh_nwff()


def setup_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(refresh_grand_illusion, "interval", hours=6, id="grand_illusion")
    scheduler.add_job(refresh_siff, "interval", hours=3, id="siff")
    scheduler.add_job(refresh_nwff, "interval", hours=3, id="nwff")
    return scheduler
