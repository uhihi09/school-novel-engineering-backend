"""Tests for the background news collector (F-2) and the DB-first /maps/news path."""
from app.db.models import NewsPin
from app.services.news_collector_service import PROVINCES, dedupe_key, store_pins

BBOX = {"sw_lat": 37.4, "sw_lng": 126.8, "ne_lat": 37.7, "ne_lng": 127.2}

SAMPLE_PINS = [
    {
        "headline": "서울 A구 야간 응급의료 공백 심화",
        "category": "healthcare",
        "sentiment_score": -0.7,
        "summary": "야간 전문의 부족",
        "severity": "High",
        "latitude": 37.55,
        "longitude": 127.0,
    },
    {
        "headline": "B동 반지하 침수 대비 예산 전액 삭감",
        "category": "climate",
        "sentiment_score": -0.6,
        "summary": "주거 취약계층 위험",
        "severity": "High",
        "latitude": 37.5,
        "longitude": 126.9,
    },
]


def test_store_pins_inserts_and_dedupes(db):
    inserted = store_pins(db, "서울특별시", SAMPLE_PINS, **BBOX)
    assert inserted == 2

    # Re-storing the same headlines (a later collection cycle) inserts nothing.
    again = store_pins(db, "서울특별시", SAMPLE_PINS, **BBOX)
    assert again == 0
    assert db.query(NewsPin).count() == 2

    row = db.query(NewsPin).filter(NewsPin.Category == "healthcare").one()
    assert row.RegionName == "서울특별시"
    assert row.DedupeKey == dedupe_key(SAMPLE_PINS[0]["headline"])


def test_store_pins_clamps_coordinates_into_bbox(db):
    outside = [{"headline": "bbox 밖 좌표 뉴스", "latitude": 99.0, "longitude": -10.0}]
    assert store_pins(db, "서울특별시", outside, **BBOX) == 1
    row = db.query(NewsPin).one()
    assert BBOX["sw_lat"] <= row.Latitude <= BBOX["ne_lat"]
    assert BBOX["sw_lng"] <= row.Longitude <= BBOX["ne_lng"]


def test_store_pins_skips_blank_headlines(db):
    pins = [{"headline": "   "}, {"headline": ""}, {"latitude": 37.5, "longitude": 127.0}]
    assert store_pins(db, "서울특별시", pins, **BBOX) == 0


def test_news_endpoint_serves_stored_pins_first(client, db):
    store_pins(db, "서울특별시", SAMPLE_PINS, **BBOX)

    res = client.get("/api/v1/maps/news", params={
        "ne_lat": BBOX["ne_lat"], "ne_lng": BBOX["ne_lng"],
        "sw_lat": BBOX["sw_lat"], "sw_lng": BBOX["sw_lng"],
    })
    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "stored-live-search"
    assert len(body["pins"]) == 2
    pin = body["pins"][0]
    for field in ("pin_id", "headline", "category", "sentiment_score", "summary",
                  "severity", "latitude", "longitude"):
        assert field in pin


def test_news_endpoint_ignores_stored_pins_outside_bbox(client, db):
    store_pins(db, "서울특별시", SAMPLE_PINS, **BBOX)

    # Query a viewport far away (Jeju): stored Seoul pins must not appear.
    # Gemini is disabled in tests, so the endpoint falls through to the static scenarios.
    res = client.get("/api/v1/maps/news", params={
        "ne_lat": 33.61, "ne_lng": 126.98, "sw_lat": 33.10, "sw_lng": 126.14,
    })
    assert res.status_code == 200
    assert res.json()["source"] == "static"


def test_news_endpoint_static_fallback_when_db_empty(client):
    res = client.get("/api/v1/maps/news", params={
        "ne_lat": 37.7, "ne_lng": 127.2, "sw_lat": 37.4, "sw_lng": 126.8,
    })
    assert res.status_code == 200
    body = res.json()
    assert body["source"] == "static"
    assert len(body["pins"]) == 4


def test_province_bboxes_are_valid():
    assert len(PROVINCES) == 17
    names = {p["name"] for p in PROVINCES}
    assert len(names) == 17
    for p in PROVINCES:
        assert p["sw_lat"] < p["ne_lat"], p["name"]
        assert p["sw_lng"] < p["ne_lng"], p["name"]
