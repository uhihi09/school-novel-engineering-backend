import io

def test_create_crowdsource_report_no_image(client):
    payload = {
        "category": "transport",
        "raw_title": "010-1234-5678 A동 장애인 경사로 파손 방치",
        "description": "경사로 단차가 너무 높아서 휠체어가 올라갈 수 없어요. 관리인 홍길동씨는 신경도 쓰지 않습니다.",
        "latitude": 37.5665,
        "longitude": 126.9780
    }
    # Send as form-data
    response = client.post("/api/v1/crowdsourcing/report", data=payload)
    assert response.status_code == 201
    data = response.json()
    assert "report_id" in data
    assert data["category"] == "transport"
    
    # Check that privacy scrubbing (PII scrubber) worked
    assert "010-1234-5678" not in data["raw_title"]
    assert "홍길동" not in data["sanitized_description"]
    assert data["latitude"] == 37.5665
    assert data["longitude"] == 126.9780
    assert data["is_valid"] is True
    assert data["ai_trust_score"] == 100.0
    assert data["media_url"] is None

def test_create_crowdsource_report_with_image(client):
    # Create a mock image file in memory
    file_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    # CORRECT TUPLE ORDER: (filename, fileobj, content_type)
    media_file = ("ramp_broken.png", io.BytesIO(file_data), "image/png")
    
    payload = {
        "category": "housing",
        "raw_title": "B구 지하방 수해 장벽 극심",
        "description": "반지하 가구의 차수판이 고장나 침수 위험이 높습니다.",
        "latitude": 37.4812,
        "longitude": 126.8921
    }
    
    response = client.post(
        "/api/v1/crowdsourcing/report",
        data=payload,
        files={"media": media_file}
    )
    assert response.status_code == 201
    data = response.json()
    assert "report_id" in data
    assert data["is_valid"] is True
    assert data["ai_trust_score"] > 0.0
    assert "/media/" in data["media_url"]
    assert ".png" in data["media_url"]
