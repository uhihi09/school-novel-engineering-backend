def test_get_maps_grid_income(client):
    response = client.get(
        "/api/v1/maps/grid",
        params={
            "ne_lat": 37.56,
            "ne_lng": 127.00,
            "sw_lat": 37.50,
            "sw_lng": 126.90,
            "zoom": 14,
            "dimension": "income"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert data["dimension"] == "income"
    assert len(data["features"]) > 0
    
    # Check GeoJSON polygon properties
    first_feature = data["features"][0]
    assert first_feature["type"] == "Feature"
    assert first_feature["geometry"]["type"] == "Polygon"
    assert "grid_id" in first_feature["properties"]
    assert "index_value" in first_feature["properties"]
    assert "average_income" in first_feature["properties"]

def test_get_maps_grid_healthcare(client):
    response = client.get(
        "/api/v1/maps/grid",
        params={
            "ne_lat": 37.56,
            "ne_lng": 127.00,
            "sw_lat": 37.50,
            "sw_lng": 126.90,
            "zoom": 14,
            "dimension": "healthcare"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["dimension"] == "healthcare"
    first_feature = data["features"][0]
    assert "doctor_count_per_10k" in first_feature["properties"]

def test_grid_uses_real_region_stats(client, db):
    """When region_stats is seeded, the grid serves real region data (not synthetic)."""
    from app.db.models import RegionStat
    db.add(RegionStat(
        RegionId="t-seoul", RegionName="테스트구", CenterLat=37.55, CenterLng=126.95,
        AvgIncomeManwon=350.0, DoctorsPer1k=2.5, Pm25=20.0, EducationIndex=72.0,
    ))
    db.commit()
    resp = client.get(
        "/api/v1/maps/grid",
        params={"ne_lat": 37.56, "ne_lng": 127.0, "sw_lat": 37.5, "sw_lng": 126.9, "dimension": "income"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data_source"] == "real-region-stats"
    assert data["features"][0]["properties"]["region"] == "테스트구"


def test_get_news_pins(client):
    response = client.get(
        "/api/v1/maps/news",
        params={
            "ne_lat": 37.56,
            "ne_lng": 127.00,
            "sw_lat": 37.50,
            "sw_lng": 126.90
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "bounding_box" in data
    assert "pins" in data
    assert len(data["pins"]) == 4
    
    first_pin = data["pins"][0]
    assert "pin_id" in first_pin
    assert "headline" in first_pin
    assert "category" in first_pin
    assert first_pin["sentiment_score"] <= 1.0
    assert first_pin["latitude"] >= 37.50
    assert first_pin["longitude"] >= 126.90
