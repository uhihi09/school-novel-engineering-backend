def test_run_simulation_success(client):
    payload = {
        "title": "청년 교통비 보조금 확대 조례안",
        "description": "교통 취약 지역 청년들을 위해 매월 5만원 상당의 대중교통 카드를 충전 지원해주는 패키지 조례안",
        "policies": [
            {
                "category": "subsidy",
                "param_value": 50000
            }
        ]
    }
    response = client.post("/api/v1/simulator/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "simulation_id" in data
    assert "gini_before" in data
    assert "gini_after" in data
    assert "disparity_delta_percent" in data
    assert "winners" in data
    assert len(data["agent_samples"]) > 0
    
    # Check that individual agent results are properly returned
    first_agent = data["agent_samples"][0]
    assert "persona_id" in first_agent
    assert "name" in first_agent
    assert "age" in first_agent
    assert "disposable_income_delta_monthly" in first_agent
    assert "ai_diary_snippet" in first_agent

def test_sonify_diary_speech(client):
    payload = "매월 주택 수당으로 15만 원이 추가 지급되니 월세 부담이 크게 덜어집니다."
    # Fix body matching Body(..., embed=True) which expects {"diary_text": ...}
    response = client.post("/api/v1/simulator/sonify", json={"diary_text": payload})
    assert response.status_code == 200
    data = response.json()
    assert "sonified_audio_url" in data
    assert data["text"] == payload
    assert data["sonified_audio_url"].startswith("data:audio/wav;base64,")

def test_audit_policy_blindspots(client):
    response = client.get(
        "/api/v1/simulator/audit",
        params={"policy_title": "교통약자 이동 편의 증진법 시행령 개정안"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "loopholes" in data
    assert "vulnerable_groups_affected" in data
    assert "recommended_amendments" in data
    assert "references_consulted" in data
    assert "교통약자 이동 편의 증진법 시행령" in data["references_consulted"]
