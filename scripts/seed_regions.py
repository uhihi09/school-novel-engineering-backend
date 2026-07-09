"""Seed real per-region inequality statistics (F-1) into the DB.

Seoul's 25 자치구 with REAL centroid coordinates; the four socio-economic metrics are pulled from
public web statistics via Gemini + Google Search grounding (computed once here, served fast at runtime).

Run on a host with a real GEMINI_API_KEY configured:
    python scripts/seed_regions.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import Base, SessionLocal, engine
from app.db import models  # noqa: F401  (register models)
from app.db.models import RegionStat
from app.services.gemini_service import gemini_service

# (region_id, 구 이름, 실제 중심 위도, 실제 중심 경도)
DISTRICTS = [
    ("seoul-jongno", "종로구", 37.5735, 126.9790),
    ("seoul-jung", "중구", 37.5636, 126.9976),
    ("seoul-yongsan", "용산구", 37.5326, 126.9906),
    ("seoul-seongdong", "성동구", 37.5634, 127.0369),
    ("seoul-gwangjin", "광진구", 37.5385, 127.0823),
    ("seoul-dongdaemun", "동대문구", 37.5744, 127.0396),
    ("seoul-jungnang", "중랑구", 37.6063, 127.0925),
    ("seoul-seongbuk", "성북구", 37.5894, 127.0167),
    ("seoul-gangbuk", "강북구", 37.6396, 127.0257),
    ("seoul-dobong", "도봉구", 37.6688, 127.0471),
    ("seoul-nowon", "노원구", 37.6542, 127.0568),
    ("seoul-eunpyeong", "은평구", 37.6027, 126.9291),
    ("seoul-seodaemun", "서대문구", 37.5791, 126.9368),
    ("seoul-mapo", "마포구", 37.5663, 126.9019),
    ("seoul-yangcheon", "양천구", 37.5170, 126.8666),
    ("seoul-gangseo", "강서구", 37.5509, 126.8495),
    ("seoul-guro", "구로구", 37.4954, 126.8874),
    ("seoul-geumcheon", "금천구", 37.4569, 126.8955),
    ("seoul-yeongdeungpo", "영등포구", 37.5264, 126.8963),
    ("seoul-dongjak", "동작구", 37.5124, 126.9393),
    ("seoul-gwanak", "관악구", 37.4784, 126.9516),
    ("seoul-seocho", "서초구", 37.4836, 127.0327),
    ("seoul-gangnam", "강남구", 37.5172, 127.0473),
    ("seoul-songpa", "송파구", 37.5145, 127.1059),
    ("seoul-gangdong", "강동구", 37.5301, 127.1238),
]


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

    db = SessionLocal()
    total = 0
    for batch in _chunks(DISTRICTS, 6):
        names = ", ".join(d[1] for d in batch)
        prompt = f"""
        서울특별시 자치구 {names} 각각의 실제 최신 공개 통계를 웹에서 조사해줘. 지표:
        - avg_income_manwon: 월 평균 가구소득(만원)
        - doctors_per_1k: 인구 1천명당 의사 수
        - pm25: 연평균 초미세먼지 PM2.5 (㎍/㎥)
        - education_index: 교육 자원·접근 종합지수 0~100 (학교/도서관/사교육 인프라 종합)
        실제 공개 데이터·통계에 근거해 값을 채우고, 다른 말 없이 JSON만 반환:
        {{"districts":[{{"name":"종로구","avg_income_manwon":0,"doctors_per_1k":0,"pm25":0,"education_index":0}}]}}
        """
        data = gemini_service.research_json(prompt)
        rows = (data or {}).get("districts") if isinstance(data, dict) else None
        by_name = {r.get("name"): r for r in rows} if rows else {}
        for rid, name, lat, lng in batch:
            s = by_name.get(name, {})
            db.merge(RegionStat(
                RegionId=rid, RegionName=name, CenterLat=lat, CenterLng=lng,
                AvgIncomeManwon=_f(s.get("avg_income_manwon")),
                DoctorsPer1k=_f(s.get("doctors_per_1k")),
                Pm25=_f(s.get("pm25")),
                EducationIndex=_f(s.get("education_index")),
                Source="Gemini grounded search (public web statistics)",
            ))
            total += 1
        db.commit()
        print(f"  seeded: {names}  ({'OK' if by_name else 'no stats -> coords only'})")
    print(f"Total regions seeded: {total}")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
