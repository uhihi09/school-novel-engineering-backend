"""Backfill real administrative boundary polygons (F-1 choropleth) into region_boundaries.

Fetches the public administrative-boundary GeoJSON (southkorea-maps / KOSTAT 2018, 250 시군구),
simplifies each polygon (rounded + decimated for payload size), computes its bbox, and stores it
keyed to region_stats by RegionId (kr-{code}). No Gemini needed — fast.

    python scripts/seed_boundaries.py
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import Base, SessionLocal, engine
from app.db import models  # noqa: F401
from app.db.models import RegionBoundary

GEOJSON_URL = "https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2018/json/skorea-municipalities-2018-geo.json"
CACHE = Path(__file__).resolve().parent / "_skorea_municipalities.json"
MAX_RING_POINTS = 160


def _simplify(coords):
    """Recursively round coords to 4 decimals (~11m) and decimate long rings for smaller payloads."""
    if coords and isinstance(coords[0], (int, float)):
        return [round(coords[0], 4), round(coords[1], 4)]
    if coords and isinstance(coords[0], list) and coords[0] and isinstance(coords[0][0], (int, float)):
        pts = [[round(p[0], 4), round(p[1], 4)] for p in coords]
        if len(pts) > MAX_RING_POINTS:
            k = len(pts) // MAX_RING_POINTS + 1
            decimated = pts[::k]
            if decimated[-1] != pts[-1]:
                decimated.append(pts[-1])  # keep ring closed
            pts = decimated
        return pts
    return [_simplify(c) for c in coords]


def _bbox(geometry):
    xs, ys = [], []

    def walk(c):
        if c and isinstance(c[0], (int, float)):
            xs.append(c[0]); ys.append(c[1])
        else:
            for x in c:
                walk(x)

    walk(geometry["coordinates"])
    return min(ys), max(ys), min(xs), max(xs)  # minlat, maxlat, minlng, maxlng


def main() -> int:
    Base.metadata.create_all(bind=engine)
    if CACHE.exists():
        raw = CACHE.read_text()
    else:
        with urllib.request.urlopen(GEOJSON_URL, timeout=30) as r:
            raw = r.read().decode("utf-8")
        CACHE.write_text(raw)
    data = json.loads(raw)

    db = SessionLocal()
    n = 0
    for f in data["features"]:
        code = str(f["properties"].get("code"))
        geom = f["geometry"]
        minlat, maxlat, minlng, maxlng = _bbox(geom)
        simplified = {"type": geom["type"], "coordinates": _simplify(geom["coordinates"])}
        db.merge(RegionBoundary(
            RegionId=f"kr-{code}", Boundary=simplified,
            MinLat=round(minlat, 5), MaxLat=round(maxlat, 5),
            MinLng=round(minlng, 5), MaxLng=round(maxlng, 5),
        ))
        n += 1
        if n % 50 == 0:
            db.commit()
            print(f"  {n} boundaries...", flush=True)
    db.commit()
    total = db.query(RegionBoundary).count()
    db.close()
    print(f"Seeded {total} region boundaries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
