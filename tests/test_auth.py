def test_register_login_and_me_flow(client):
    # Register
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "citizen@equiscope.kr", "password": "s3cret-pass", "nickname": "홍길동"},
    )
    assert reg.status_code == 201
    reg_data = reg.json()
    assert reg_data["token_type"] == "bearer"
    assert reg_data["access_token"]
    assert reg_data["user"]["email"] == "citizen@equiscope.kr"
    assert reg_data["user"]["user_id"].startswith("user_")

    # Duplicate registration is rejected
    dup = client.post(
        "/api/v1/auth/register",
        json={"email": "citizen@equiscope.kr", "password": "another", "nickname": "중복"},
    )
    assert dup.status_code == 400

    # Login with correct credentials
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "citizen@equiscope.kr", "password": "s3cret-pass"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    # Wrong password is rejected
    bad = client.post(
        "/api/v1/auth/login",
        json={"email": "citizen@equiscope.kr", "password": "wrong"},
    )
    assert bad.status_code == 401

    # /me with a valid token returns the profile
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "citizen@equiscope.kr"


def test_me_requires_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)


def test_authenticated_simulation_uses_real_user(client):
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "sim@equiscope.kr", "password": "pw123456", "nickname": "정책가"},
    )
    token = reg.json()["access_token"]
    payload = {
        "title": "청년 교통비 보조금 확대 조례안",
        "description": "매월 5만원 교통 지원",
        "policies": [{"category": "subsidy", "param_value": 50000}],
    }
    resp = client.post(
        "/api/v1/simulator/run",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "simulation_id" in resp.json()
