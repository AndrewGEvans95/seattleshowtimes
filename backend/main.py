import logging
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.cache import read_all_showtimes, write_venue_cache
from backend.models import ShowtimesResponse, Venue
from backend.scheduler import setup_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — running initial scrape and starting scheduler")
    scheduler = setup_scheduler()
    scheduler.start()
    # Trigger immediate scrape on startup
    from backend.scheduler import refresh_all
    await refresh_all()
    yield
    scheduler.shutdown()
    logger.info("Scheduler shut down")


app = FastAPI(title="Seattle Showtimes", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/showtimes", response_model=ShowtimesResponse)
async def get_showtimes(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    venue: Optional[Venue] = Query(default=None),
):
    showtimes, last_updated, stale_venues = read_all_showtimes()

    if date_from:
        showtimes = [s for s in showtimes if s.show_date >= date_from]
    if date_to:
        showtimes = [s for s in showtimes if s.show_date <= date_to]
    if venue:
        showtimes = [s for s in showtimes if s.venue == venue]

    showtimes.sort(key=lambda s: (s.show_date, s.show_time))

    return ShowtimesResponse(
        showtimes=showtimes,
        last_updated=last_updated,
        stale_venues=stale_venues,
    )


@app.post("/api/refresh")
async def trigger_refresh():
    """Manually trigger a full scrape refresh (useful for testing)."""
    from backend.scheduler import refresh_all
    await refresh_all()
    return {"status": "ok"}


# Serve the frontend static files at root (must be last)
import os
from pathlib import Path

frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
