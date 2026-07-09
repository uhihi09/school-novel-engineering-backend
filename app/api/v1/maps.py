from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.db.models import NewsPin
from app.services.maps_service import maps_service
from app.services.gemini_service import gemini_service
from app.services.news_collector_service import store_pins

# Stored news pins older than this are considered stale for the map view.
NEWS_STORED_WINDOW_HOURS = 48
NEWS_STORED_LIMIT = 12

router = APIRouter()

@router.get("/grid")
def read_grid(
    ne_lat: float = Query(..., description="North-East Latitude"),
    ne_lng: float = Query(..., description="North-East Longitude"),
    sw_lat: float = Query(..., description="South-West Latitude"),
    sw_lng: float = Query(..., description="South-West Longitude"),
    zoom: int = Query(14, description="Map zoom level"),
    dimension: str = Query("income", description="Inequality category dimension (income/healthcare/climate/education)"),
    db: Session = Depends(get_db)
):
    """F-1 & F-4: Fetches GeoJSON 3D grid layers with Gini/equity calculations for Mapbox/Leaflet visualization."""
    return maps_service.get_local_grid_geojson(
        db, ne_lat=ne_lat, ne_lng=ne_lng, sw_lat=sw_lat, sw_lng=sw_lng, zoom=zoom, dimension=dimension
    )


@router.get("/regions")
def read_region_choropleth(
    ne_lat: float = Query(..., description="North-East Latitude"),
    ne_lng: float = Query(..., description="North-East Longitude"),
    sw_lat: float = Query(..., description="South-West Latitude"),
    sw_lng: float = Query(..., description="South-West Longitude"),
    dimension: str = Query("income", description="Inequality dimension (income/healthcare/climate/education)"),
    db: Session = Depends(get_db),
):
    """F-1: Real 시군구 boundary polygons within the viewport, coloured by real per-region stats.

    Preferred over /grid — returns true administrative shapes (GeoJSON) instead of a synthetic 5x5 grid.
    """
    return maps_service.get_region_choropleth(
        db, ne_lat=ne_lat, ne_lng=ne_lng, sw_lat=sw_lat, sw_lng=sw_lng, dimension=dimension
    )

@router.get("/spi")
def read_satellite_poverty_index(
    lat: float = Query(..., description="Target latitude"),
    lng: float = Query(..., description="Target longitude"),
    region_name: str = Query("대상 지역", description="Human-readable region label")
):
    """F-4: Satellite Poverty Index. Gemini Vision reads satellite imagery into a poverty grade report."""
    return maps_service.get_satellite_poverty_index(lat=lat, lng=lng, region_name=region_name)

@router.get("/news")
def read_news_pins(
    ne_lat: float = Query(..., description="North-East Latitude"),
    ne_lng: float = Query(..., description="North-East Longitude"),
    sw_lat: float = Query(..., description="South-West Latitude"),
    sw_lng: float = Query(..., description="South-West Longitude"),
    db: Session = Depends(get_db),
):
    """F-2: Inequality news pins. Serves pins accumulated by the background collector (instant);
    falls back to a live Gemini + Google Search lookup (stored for next time), then to static scenarios."""
    bounding_box = {"ne_lat": ne_lat, "ne_lng": ne_lng, "sw_lat": sw_lat, "sw_lng": sw_lng}
    lo_lat, hi_lat = min(sw_lat, ne_lat), max(sw_lat, ne_lat)
    lo_lng, hi_lng = min(sw_lng, ne_lng), max(sw_lng, ne_lng)

    # 1) Stored pins from the continuous collector: instant response, no grounding call.
    cutoff = datetime.now(timezone.utc) - timedelta(hours=NEWS_STORED_WINDOW_HOURS)
    stored = (
        db.query(NewsPin)
        .filter(
            NewsPin.Latitude >= lo_lat, NewsPin.Latitude <= hi_lat,
            NewsPin.Longitude >= lo_lng, NewsPin.Longitude <= hi_lng,
            NewsPin.CollectedAt >= cutoff,
        )
        .order_by(NewsPin.CollectedAt.desc())
        .limit(NEWS_STORED_LIMIT)
        .all()
    )
    if stored:
        pins = [{
            "pin_id": row.PinId,
            "headline": row.Headline,
            "category": row.Category,
            "sentiment_score": row.SentimentScore,
            "summary": row.Summary or "",
            "severity": row.Severity,
            "latitude": row.Latitude,
            "longitude": row.Longitude,
        } for row in stored]
        return {"bounding_box": bounding_box, "pins": pins, "source": "stored-live-search"}

    # 2) Nothing stored for this viewport yet: live grounded search, persisted for next time.
    real = gemini_service.fetch_local_news(ne_lat, ne_lng, sw_lat, sw_lng, limit=4)
    if real:
        mid_lat, mid_lng = (lo_lat + hi_lat) / 2, (lo_lng + hi_lng) / 2
        pins = []
        for idx, n in enumerate(real):
            try:
                score = float(n.get("sentiment_score", -0.5))
            except (ValueError, TypeError):
                score = -0.5
            try:
                lat = min(hi_lat, max(lo_lat, float(n.get("latitude", mid_lat))))
                lng = min(hi_lng, max(lo_lng, float(n.get("longitude", mid_lng))))
            except (ValueError, TypeError):
                lat, lng = mid_lat, mid_lng
            pins.append({
                "pin_id": f"pin_news_{idx + 100}",
                "headline": n.get("headline", ""),
                "category": n.get("category", "income"),
                "sentiment_score": score,
                "summary": n.get("summary", ""),
                "severity": n.get("severity", "Medium"),
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
            })
        try:
            store_pins(db, "viewport", real, sw_lat=sw_lat, sw_lng=sw_lng, ne_lat=ne_lat, ne_lng=ne_lng)
        except Exception:  # noqa: BLE001 — persistence is best-effort; never break the response
            db.rollback()
        return {"bounding_box": bounding_box, "pins": pins, "source": "live-search"}

    # 3) Fallback: static scenarios still analyzed by Gemini sentiment.
    pins = []

    # Generate 4 distinct fallback local news pins within the bounding box
    news_scenarios = [
        {
            "headline": "A구 중앙의원, 응급실 야간 전문의 확보 실패로 격주 휴업 결정... 환자 장거리 이동 불가피",
            "lat_offset": 0.2,
            "lng_offset": 0.3
        },
        {
            "headline": "인구 고령화 극심한 B동, 노후 주택 폭염 속 냉방 기본 인프라 취약해 실내 온열 질환자 작년 대비 30% 증가",
            "lat_offset": 0.7,
            "lng_offset": 0.1
        },
        {
            "headline": "청년 주거 타운 앞 비인가 미등록 돌봄 지원 시설 예산 삭감으로 전면 잠정 폐쇄 결정... 학부모 발 구동",
            "lat_offset": 0.4,
            "lng_offset": 0.6
        },
        {
            "headline": "소도시 비정규직 노동 지대, 교통 차별 장벽 극심... 퇴근 길 배차 간격 40분으로 이동 피로 심화",
            "lat_offset": 0.5,
            "lng_offset": 0.8
        }
    ]
    
    for idx, sc in enumerate(news_scenarios):
        # Calculate latitude and longitude within bounding box
        lat = sw_lat + (ne_lat - sw_lat) * sc["lat_offset"]
        lng = sw_lng + (ne_lng - sw_lng) * sc["lng_offset"]
        
        # Analyze using Gemini Service
        analysis = gemini_service.analyze_news_sentiment(sc["headline"])
        
        # Cast sentiment_score to float to resolve TypeError: '<=' not supported between float and str
        score = analysis.get("sentiment_score", -0.5)
        try:
            score = float(score)
        except (ValueError, TypeError):
            score = -0.5
            
        pins.append({
            "pin_id": f"pin_news_{idx + 100}",
            "headline": sc["headline"],
            "category": analysis.get("category", "income"),
            "sentiment_score": score,
            "summary": analysis.get("summary", "지역내 취약점 감지"),
            "severity": analysis.get("severity", "Medium"),
            "latitude": round(lat, 6),
            "longitude": round(lng, 6)
        })
        
    return {"bounding_box": bounding_box, "pins": pins, "source": "static"}
