def test_advisor_chat_returns_grounded_answer(client):
    resp = client.post(
        "/api/v1/advisor/chat",
        json={"question": "청년 주거 지원 정책의 사각지대는 무엇인가요?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"]
    assert isinstance(data["references"], list)
    assert isinstance(data["references_consulted"], list)
    # The KB doc about 청년 주거 지원 should be retrieved as a reference.
    assert any("청년 주거" in title for title in data["references_consulted"])


def test_advisor_chat_requires_question(client):
    resp = client.post("/api/v1/advisor/chat", json={})
    assert resp.status_code == 422


def test_advisor_chat_survives_schema_deviant_gemini(client, monkeypatch):
    """Real Gemini path may return null/bare-string refs; endpoint must coerce, not 500."""
    from app.services import gemini_service as gs

    monkeypatch.setattr(
        gs.gemini_service,
        "generate_advisor_answer",
        lambda question, docs: {"answer": None, "references": ["출처 제목만", {"snippet": "본문"}]},
    )
    resp = client.post("/api/v1/advisor/chat", json={"question": "테스트"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["answer"] == ""
    assert len(data["references"]) == 2
    assert data["references"][0]["title"] == "출처 제목만"
