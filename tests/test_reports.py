def _create_report(client, lat, lng, category="transport"):
    return client.post(
        "/api/v1/crowdsourcing/report",
        data={
            "category": category,
            "raw_title": "테스트 제보",
            "description": "휠체어 진입 턱이 높습니다.",
            "latitude": lat,
            "longitude": lng,
        },
    )


def test_list_reports_within_bounds(client):
    created = _create_report(client, 37.50, 127.00)
    assert created.status_code == 201
    report_id = created.json()["report_id"]

    resp = client.get(
        "/api/v1/crowdsourcing/reports",
        params={"ne_lat": 37.60, "ne_lng": 127.10, "sw_lat": 37.40, "sw_lng": 126.90},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert any(r["report_id"] == report_id for r in data["reports"])


def test_list_reports_category_filter(client):
    _create_report(client, 37.51, 127.01, category="housing")
    resp = client.get(
        "/api/v1/crowdsourcing/reports",
        params={
            "ne_lat": 37.60,
            "ne_lng": 127.10,
            "sw_lat": 37.40,
            "sw_lng": 126.90,
            "category": "housing",
        },
    )
    assert resp.status_code == 200
    assert all(r["category"] == "housing" for r in resp.json()["reports"])


def test_get_single_report(client):
    created = _create_report(client, 37.52, 127.02)
    report_id = created.json()["report_id"]

    ok = client.get(f"/api/v1/crowdsourcing/reports/{report_id}")
    assert ok.status_code == 200
    assert ok.json()["report_id"] == report_id

    missing = client.get("/api/v1/crowdsourcing/reports/rep_does_not_exist")
    assert missing.status_code == 404
