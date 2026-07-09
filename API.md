# EquiScope 백엔드 — API 레퍼런스

불평등 시각화 플랫폼 EquiScope의 FastAPI 백엔드입니다. 기본 URL: `http://localhost:8000`, 모든 엔드포인트는 `/api/v1` 하위. 인터랙티브 문서(Swagger)는 `/docs`, ReDoc은 `/redoc`.

**실행:** `./run.sh` (또는 `python -m uvicorn app.main:app --reload`). `.env`가 비어 있어도 **로컬 SQLite + Gemini 목(mock) 폴백**으로 그대로 동작합니다(클라우드 자격증명 불필요). `.env.example`을 `.env`로 복사해 값을 채우면 실제 Gemini/Vertex/Cloud SQL로 전환됩니다.

**인증 모델:** JWT Bearer 토큰. `maps` · `simulator` · `crowdsourcing` 엔드포인트는 **토큰 없이도 사용 가능**(없으면 공용 데모 유저로 처리), `Authorization: Bearer <token>`을 붙이면 실제 계정으로 동작합니다. `/auth/me`만 토큰 필수.

---

## 인증 · 사용자 (Auth & Users)

### `POST /api/v1/auth/register` → 201
회원가입 후 토큰 발급.
- 요청: `{ "email": str, "password": str(6자 이상), "nickname": str? }`
- 응답: `{ access_token, token_type: "bearer", user: { user_id, email, nickname } }`
- 이미 가입된 이메일이면 400.

### `POST /api/v1/auth/login` → 200
- 요청: `{ "email": str, "password": str }` → 위와 동일한 토큰 응답
- 이메일/비밀번호 불일치 시 401.

### `GET /api/v1/auth/me` → 200  *(토큰 필수)*
- 헤더: `Authorization: Bearer <token>`
- 응답: `{ user_id, email, nickname }`. 토큰 없거나 무효면 401/403.

---

## 지도 · 뉴스 그리드 (Maps)

### `GET /api/v1/maps/grid`  *(F-1 다차원 공간 시각화)*
- 쿼리: `ne_lat, ne_lng, sw_lat, sw_lng, zoom=14, dimension=income|healthcare|climate|education`
- 응답: GeoJSON `FeatureCollection` (5×5 격자). 각 셀에 `index_value`, `grade`, 차원별 속성(예: `average_income`, `doctor_count_per_10k`, `pm25_micrograms`, `school_count_per_10k`). 해당 격자 내 검증된 시민 제보가 있으면 점수를 하향 보정.

### `GET /api/v1/maps/news`  *(F-2 실시간 이슈 탐지기)*
- 쿼리: `ne_lat, ne_lng, sw_lat, sw_lng`
- 응답: `{ bounding_box, pins: [{ pin_id, headline, category, sentiment_score, summary, severity, latitude, longitude }] }`. 헤드라인을 Gemini가 분석(목 폴백).

### `GET /api/v1/maps/spi`  *(F-4 위성 빈곤지수 SPI)*
- 쿼리: `lat, lng, region_name="대상 지역"`
- 응답: `{ region_name, latitude, longitude, poverty_grade, green_access_score, slum_trend, road_paving_ratio, night_light_intensity, reasoning }`. 목 모드에선 좌표별 결정적 값, 실 모드에선 Gemini Vision이 위성 타일을 판독.

---

## 정책 시뮬레이터 · RAG (Simulator)

### `POST /api/v1/simulator/run`  *(F-3 페르소나 시뮬레이터)*
- 요청: `{ title, description, policies: [{ category: "subsidy|minimum_wage|tax", param_value: float }] }`
- 응답: `{ simulation_id, gini_before, gini_after, disparity_delta_percent, winners[], losers[], agent_samples[] }`. 1,000명 페르소나로 시뮬레이션하며, 샘플 8명은 Gemini가 생성한 일기(diary) 스니펫 포함.
- `agent_samples[]` 각 항목: `{ persona_id, name, age, disposable_income_delta_monthly, utility_change, ai_diary_snippet }`.

### `POST /api/v1/simulator/sonify`  *(F-6 데이터 소니피케이션)*
- 요청: `{ "diary_text": str }`
- 응답: `{ sonified_audio_url: "data:audio/wav;base64,…", text }`. 일기 텍스트를 base64 오디오 스트림으로 변환.

### `GET /api/v1/simulator/audit`  *(F-7 법안 사각지대 감사)*
- 쿼리: `policy_title`
- 응답: `{ loopholes[], vulnerable_groups_affected[], recommended_amendments[], references_consulted[] }`. 로컬 법안 KB에서 관련 문서를 RAG로 조회.

---

## AI 정책 어드바이저 (Advisor)

### `POST /api/v1/advisor/chat`  *(F-5 AI 불평등 어드바이저)*
- 요청: `{ "question": str }`
- 응답: `{ question, answer, references: [{ title, snippet }], references_consulted: [str] }`. 로컬 법안 KB로 RAG를 수행해 근거를 인용한 Gemini 답변 생성.

---

## 크라우드소싱 제보 (Crowdsourcing)

### `POST /api/v1/crowdsourcing/report` → 201  *(F-2 / F-6)*
- `multipart/form-data`: `category, raw_title, description, latitude, longitude, media?(파일)`
- 제목/설명의 개인정보(PII)를 Gemini로 비식별화하고, 이미지가 있으면 Gemini Vision으로 검증 후 저장. 응답은 아래 **제보 형태**.

### `GET /api/v1/crowdsourcing/reports`
- 쿼리: `ne_lat, ne_lng, sw_lat, sw_lng, category?, valid_only=false`
- 응답: `{ count, reports: [제보] }`. 경계 상자 내 제보 목록 — 지도 핀·모바일 피드용.

### `GET /api/v1/crowdsourcing/reports/{report_id}`
- 단건 제보 반환, 없으면 404.

**제보 형태:** `{ report_id, user_id, category, raw_title, sanitized_description, latitude, longitude, is_valid, ai_trust_score, media_url, created_at }`

---

## 설정 (`.env`)

| 변수 | 기본값 | 용도 |
|---|---|---|
| `GEMINI_API_KEY` | *(비어 있음)* | Google AI Studio 키. 비우면 목 폴백으로 동작 |
| `USE_VERTEX_AI` | `false` | Gemini를 Vertex AI로 라우팅 (`GOOGLE_APPLICATION_CREDENTIALS` + `GCP_PROJECT_ID` 필요) |
| `GCP_PROJECT_ID` / `GCP_LOCATION` | *(비어 있음)* / `asia-northeast3` | Vertex 프로젝트/리전 |
| `GEMINI_FLASH_MODEL` / `GEMINI_PRO_MODEL` | `gemini-3.5-flash` / `gemini-3.1-pro` | 사용할 Gemini 모델 id |
| `GCS_BUCKET` | `equiscope-reports` | 제보 미디어 저장 버킷 |
| `DATABASE_URL` | 로컬 SQLite | SQLAlchemy URL. Cloud SQL/Cloud SQL 등으로 교체 |
| `SECRET_KEY` | 개발용 자리표시자 | **운영 환경에선 반드시 변경** (`openssl rand -hex 32`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` (7일) | JWT 만료 시간(분) |

> **모델 id 주의:** `GEMINI_FLASH_MODEL` / `GEMINI_PRO_MODEL` 값이 실제 존재하는 모델이어야 실 Gemini 호출이 성공합니다. 없는 id면 호출이 실패하고 목 폴백으로 떨어집니다.

---

## 데이터베이스 — Cloud SQL for PostgreSQL

기본은 로컬 SQLite(무설정 실행용)이고, 실제 DB는 **Cloud SQL PostgreSQL 18**을 사용합니다.
- 인스턴스 연결 이름: `iceu-578:asia-northeast3:school-hackathon-db`
- 공개 IP: `34.64.248.130` · 포트: `5432` · 리전: 서울(asia-northeast3)
- 드라이버: `pg8000` (순수 파이썬, 빌드 불필요 — `requirements.txt`에 포함)

**연결 방법 (둘 중 하나):**

```bash
# A) 공개 IP 직결 — 먼저 콘솔의 Connections > Networking > "승인된 네트워크"에 본인 IP 추가
DATABASE_URL=postgresql+pg8000://postgres:비밀번호@34.64.248.130:5432/postgres

# B) Cloud SQL Auth Proxy — 승인된 네트워크 불필요
#   cloud-sql-proxy iceu-578:asia-northeast3:school-hackathon-db --port 5432
DATABASE_URL=postgresql+pg8000://postgres:비밀번호@127.0.0.1:5432/postgres
```

**연결 확인 + 테이블 생성:**
```bash
python scripts/init_db.py
# → "Connection OK" 및 테이블 3개(users, inequality_reports, simulation_logs) 생성 확인
```

- `session.py`는 `pool_pre_ping=True`로 Cloud SQL 유휴 커넥션 끊김을 자동 복구합니다.
- DB가 잠깐 안 닿아도 서버 시작은 실패하지 않고 경고만 남깁니다(DB 의존 엔드포인트만 요청 시 오류).

---

## 테스트

```bash
python -m pytest -q          # 19개 통과, ~0.2초
```
테스트는 **완전히 격리(hermetic)** 되어 있습니다 — `.env`에 실제 Gemini 키나 Cloud SQL URL이 있어도, 테스트는 인메모리 SQLite + Gemini 목으로 강제되어 외부 네트워크를 호출하지 않습니다(`tests/conftest.py`).

> **참고:** `User` 테이블에 `HashedPassword` 컬럼이 추가되었습니다. 인증 도입 이전에 만들어진 로컬 `equiscope.db`가 있다면 삭제(`rm equiscope.db`) 후 재생성하세요(시작 시 자동 생성, 테스트 DB는 항상 새로 만들어짐).
