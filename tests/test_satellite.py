def test_satellite_poverty_index(client):
    resp = client.get(
        "/api/v1/maps/spi",
        params={"lat": 37.5665, "lng": 126.9780, "region_name": "A동 취약지구"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["region_name"] == "A동 취약지구"
    assert data["latitude"] == 37.5665
    assert "poverty_grade" in data
    assert "green_access_score" in data
    assert "road_paving_ratio" in data
    assert "reasoning" in data


def test_satellite_spi_is_deterministic_per_coordinate(client):
    params = {"lat": 37.5, "lng": 127.0, "region_name": "테스트"}
    first = client.get("/api/v1/maps/spi", params=params).json()
    second = client.get("/api/v1/maps/spi", params=params).json()
    assert first["poverty_grade"] == second["poverty_grade"]
