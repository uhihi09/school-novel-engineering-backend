"""Seed real per-region inequality statistics (F-1) for ALL of South Korea into the DB.

- Region list + REAL centroids: computed from a public administrative-boundary GeoJSON
  (southkorea-maps, KOSTAT 2018) — 250 시군구.
- The four socio-economic metrics + the 시도 name: pulled from public web statistics via
  Gemini + Google Search grounding (batched), computed once here and served fast at runtime.

Run on a host with a real GEMINI_API_KEY:
    python scripts/seed_regions.py
"""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import Base, SessionLocal, engine
from app.db import models  # noqa: F401
from app.db.models import RegionStat
from app.services.gemini_service import gemini_service

GEOJSON_URL = "https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2018/json/skorea-municipalities-2018-geo.json"
CACHE = Path(__file__).resolve().parent / "_skorea_municipalities.json"
BATCH = 10


def _centroid(geometry) -> tuple:
    xs, ys = [], []

    def walk(c):
        if c and isinstance(c[0], (int, float)):
            xs.append(c[0]); ys.append(c[1])
        else:
            for x in c:
                walk(x)

    walk(geometry["coordinates"])
    return (sum(ys) / len(ys), sum(xs) / len(xs))  # (lat, lng)


def _load_regions():
    if CACHE.exists():
        raw = CACHE.read_text()
    else:
        with urllib.request.urlopen(GEOJSON_URL, timeout=30) as r:
            raw = r.read().decode("utf-8")
        CACHE.write_text(raw)
    data = json.loads(raw)
    regions = []
    for f in data["features"]:
        p = f["properties"]
        name = p.get("name")
        code = str(p.get("code"))
        lat, lng = _centroid(f["geometry"])
        regions.append((f"kr-{code}", name, round(lat, 5), round(lng, 5)))
    return regions


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def main() -> int:
    Base.metadata.create_all(bind=engine)
    if gemini_service.client is None:
        print("No Gemini client (missing key). Cannot fetch real statistics. Aborting.")
        return 1

    regions = _load_regions()
    print(f"Loaded {len(regions)} 시군구 with real centroids from public GeoJSON.")

    db = SessionLocal()
    total = 0
    for bi, batch in enumerate(_chunks(regions, BATCH)):
        listing = "\n".join(
            f"  {i}: {name} (위도 {lat}, 경도 {lng})" for i, (_rid, name, lat, lng) in enumerate(batch)
        )
        prompt = f"""
        다음 대한민국 시군구 각각의 실제 최신 공개 통계를 웹에서 조사해줘. 좌표로 어느 시도인지 정확히 판별할 것.
        지표: avg_income_manwon(월 평균 가구소득 만원), doctors_per_1k(인구 1천명당 의사 수),
        pm25(연평균 초미세먼지 ㎍/㎥), education_index(교육 자원·접근 종합지수 0~100), sido(시도 이름).
        지역:
        {listing}
        각 항목의 인덱스(i)를 그대로 echo해서, 다른 말 없이 JSON만 반환:
        {{"regions":[{{"i":0,"sido":"서울특별시","avg_income_manwon":0,"doctors_per_1k":0,"pm25":0,"education_index":0}}]}}
        """
        data = gemini_service.research_json(prompt)
        rows = (data or {}).get("regions") if isinstance(data, dict) else None
        by_i = {int(r["i"]): r for r in rows if "i" in r} if rows else {}
        for i, (rid, name, lat, lng) in enumerate(batch):
            s = by_i.get(i, {})
            sido = s.get("sido") or ""
            display = f"{sido} {name}".strip() if sido else name
            db.merge(RegionStat(
                RegionId=rid, RegionName=display, CenterLat=lat, CenterLng=lng,
                AvgIncomeManwon=_f(s.get("avg_income_manwon")),
                DoctorsPer1k=_f(s.get("doctors_per_1k")),
                Pm25=_f(s.get("pm25")),
                EducationIndex=_f(s.get("education_index")),
                Source="centroid: southkorea-maps GeoJSON (KOSTAT 2018) / stats: Gemini grounded search",
            ))
            total += 1
        db.commit()
        print(f"  batch {bi + 1}: {len(batch)} regions  ({'stats OK' if by_i else 'coords only'})", flush=True)
    print(f"Total regions seeded: {total}")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
