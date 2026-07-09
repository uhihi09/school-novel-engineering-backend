"""Background inequality-news collector (F-2).

Every NEWS_COLLECT_INTERVAL_MINUTES, sweeps the 17 provinces (시도) and asks Gemini
(Google Search grounding) for recent local inequality news, accumulating deduplicated
pins in the news_pins table. /maps/news then serves from the DB instantly instead of
paying a 10-30s live search per request.

Quota defense: fetch_local_news swallows API errors and returns None, so HTTP status
codes are invisible here — instead, 3 consecutive failed provinces abort the cycle
(the likely cause is exhausted quota or an outage, and hammering on won't help).
"""
import hashlib
import logging
import time
import uuid
import asyncio
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import NewsPin
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)

# Approximate mainland bounding boxes per province — coarse on purpose: they only
# steer the grounded search and clamp pin coordinates, they are not authoritative.
PROVINCES: List[Dict] = [
    {"name": "서울특별시",     "sw_lat": 37.42, "sw_lng": 126.76, "ne_lat": 37.70, "ne_lng": 127.18},
    {"name": "부산광역시",     "sw_lat": 35.05, "sw_lng": 128.83, "ne_lat": 35.39, "ne_lng": 129.30},
    {"name": "대구광역시",     "sw_lat": 35.60, "sw_lng": 128.35, "ne_lat": 36.02, "ne_lng": 128.77},
    {"name": "인천광역시",     "sw_lat": 37.33, "sw_lng": 126.37, "ne_lat": 37.62, "ne_lng": 126.80},
    {"name": "광주광역시",     "sw_lat": 35.05, "sw_lng": 126.65, "ne_lat": 35.26, "ne_lng": 127.02},
    {"name": "대전광역시",     "sw_lat": 36.18, "sw_lng": 127.25, "ne_lat": 36.50, "ne_lng": 127.56},
    {"name": "울산광역시",     "sw_lat": 35.32, "sw_lng": 128.97, "ne_lat": 35.72, "ne_lng": 129.47},
    {"name": "세종특별자치시", "sw_lat": 36.41, "sw_lng": 127.14, "ne_lat": 36.73, "ne_lng": 127.42},
    {"name": "경기도",         "sw_lat": 36.89, "sw_lng": 126.39, "ne_lat": 38.29, "ne_lng": 127.86},
    {"name": "강원특별자치도", "sw_lat": 37.02, "sw_lng": 127.09, "ne_lat": 38.62, "ne_lng": 129.36},
    {"name": "충청북도",       "sw_lat": 36.01, "sw_lng": 127.26, "ne_lat": 37.25, "ne_lng": 128.63},
    {"name": "충청남도",       "sw_lat": 35.97, "sw_lng": 125.90, "ne_lat": 37.06, "ne_lng": 127.58},
    {"name": "전북특별자치도", "sw_lat": 35.30, "sw_lng": 126.39, "ne_lat": 36.16, "ne_lng": 127.90},
    {"name": "전라남도",       "sw_lat": 33.90, "sw_lng": 125.06, "ne_lat": 35.50, "ne_lng": 127.55},
    {"name": "경상북도",       "sw_lat": 35.56, "sw_lng": 127.79, "ne_lat": 37.55, "ne_lng": 129.59},
    {"name": "경상남도",       "sw_lat": 34.55, "sw_lng": 127.57, "ne_lat": 35.91, "ne_lng": 129.29},
    {"name": "제주특별자치도", "sw_lat": 33.10, "sw_lng": 126.14, "ne_lat": 33.61, "ne_lng": 126.98},
]

# Give up on the cycle after this many provinces fail in a row (quota/outage heuristic).
_CONSECUTIVE_FAILURE_LIMIT = 3
# Pause between province calls so cycles don't spike the API.
_INTER_REGION_SLEEP_SECONDS = 2.0


def dedupe_key(headline: str) -> str:
    """Stable key for a headline: whitespace-normalized, case-folded sha256."""
    normalized = " ".join((headline or "").split()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def store_pins(
    db: Session,
    region_name: str,
    pins: List[Dict],
    sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float,
) -> int:
    """Insert news pins, clamping coordinates into the bbox and skipping duplicates.

    Returns the number of newly inserted rows. Commits once at the end.
    """
    lo_lat, hi_lat = min(sw_lat, ne_lat), max(sw_lat, ne_lat)
    lo_lng, hi_lng = min(sw_lng, ne_lng), max(sw_lng, ne_lng)
    mid_lat, mid_lng = (lo_lat + hi_lat) / 2, (lo_lng + hi_lng) / 2

    inserted = 0
    seen_keys = set()
    for pin in pins or []:
        headline = (pin.get("headline") or "").strip()
        if not headline:
            continue
        key = dedupe_key(headline)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        if db.query(NewsPin.PinId).filter(NewsPin.DedupeKey == key).first():
            continue

        try:
            score = float(pin.get("sentiment_score", -0.5))
        except (ValueError, TypeError):
            score = -0.5
        try:
            lat = min(hi_lat, max(lo_lat, float(pin.get("latitude", mid_lat))))
            lng = min(hi_lng, max(lo_lng, float(pin.get("longitude", mid_lng))))
        except (ValueError, TypeError):
            lat, lng = mid_lat, mid_lng

        db.add(NewsPin(
            PinId=f"pin_news_{uuid.uuid4().hex[:12]}",
            RegionName=region_name,
            Headline=headline[:500],
            Category=pin.get("category", "income"),
            SentimentScore=score,
            Severity=pin.get("severity", "Medium"),
            Summary=pin.get("summary", ""),
            Latitude=round(lat, 6),
            Longitude=round(lng, 6),
            DedupeKey=key,
        ))
        inserted += 1

    if inserted:
        db.commit()
    return inserted


def run_collection_cycle(db: Session) -> Dict[str, int]:
    """Sweep all provinces once. Province failures are isolated; consecutive failures abort."""
    stats = {"provinces_ok": 0, "provinces_failed": 0, "pins_inserted": 0}
    consecutive_failures = 0

    for province in PROVINCES:
        if consecutive_failures >= _CONSECUTIVE_FAILURE_LIMIT:
            logger.warning(
                "News collector: %d consecutive failures — aborting cycle (quota/outage?)",
                consecutive_failures,
            )
            break
        try:
            pins: Optional[List[Dict]] = gemini_service.fetch_local_news(
                ne_lat=province["ne_lat"], ne_lng=province["ne_lng"],
                sw_lat=province["sw_lat"], sw_lng=province["sw_lng"],
                limit=4,
            )
            if pins:
                inserted = store_pins(
                    db, province["name"], pins,
                    sw_lat=province["sw_lat"], sw_lng=province["sw_lng"],
                    ne_lat=province["ne_lat"], ne_lng=province["ne_lng"],
                )
                stats["provinces_ok"] += 1
                stats["pins_inserted"] += inserted
                consecutive_failures = 0
            else:
                stats["provinces_failed"] += 1
                consecutive_failures += 1
        except Exception:  # noqa: BLE001 — one province must never kill the sweep
            logger.exception("News collector: province %s failed", province["name"])
            db.rollback()
            stats["provinces_failed"] += 1
            consecutive_failures += 1

        time.sleep(_INTER_REGION_SLEEP_SECONDS)

    logger.info("News collector cycle done: %s", stats)
    return stats


async def collector_loop() -> None:
    """Async forever-loop started from the app lifespan when NEWS_COLLECTOR_ENABLED."""
    # Import here so tests (which never enable the collector) don't touch the real engine.
    from app.db.session import SessionLocal

    logger.info(
        "News collector started: %d provinces every %d min",
        len(PROVINCES), settings.NEWS_COLLECT_INTERVAL_MINUTES,
    )
    while True:
        try:
            db = SessionLocal()
            try:
                # The genai SDK is blocking — keep the event loop responsive.
                await asyncio.to_thread(run_collection_cycle, db)
            finally:
                db.close()
        except asyncio.CancelledError:
            logger.info("News collector stopped.")
            raise
        except Exception:  # noqa: BLE001 — the loop itself must survive anything
            logger.exception("News collector cycle crashed; retrying next interval")
        await asyncio.sleep(settings.NEWS_COLLECT_INTERVAL_MINUTES * 60)
