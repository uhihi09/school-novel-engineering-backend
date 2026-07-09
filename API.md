# EquiScope 백엔드 — 프론트엔드 연동 API 문서

> 웹(Next.js) · 앱(React Native)에서 바로 붙일 수 있도록 정리한 REST API 레퍼런스입니다.

## 기본 정보

| 항목 | 값 |
|---|---|
| **Base URL** | `http://34.67.12.246:8080` |
| 공통 prefix | `/api/v1` (단, `/`, `/docs`, `/media/*` 제외) |
| 응답 포맷 | JSON (제보 등록만 `multipart/form-data` 요청) |
| 인터랙티브 문서 | `GET /docs` (Swagger) · `GET /redoc` |
| OpenAPI 스키마 | `GET /api/v1/openapi.json` |

**CORS**: 모든 origin 허용, **credentials(쿠키) 미사용**. 인증은 쿠키가 아니라 **`Authorization: Bearer <token>` 헤더**로 보냅니다.

**인증 정책**: `maps` · `simulator` · `crowdsourcing`은 **토큰 없이도 호출 가능**(없으면 공용 데모 유저로 기록). 토큰을 붙이면 본인 계정으로 동작. `GET /auth/me`만 토큰 필수.

### ⏱️ 응답 속도 (로딩 UI 필수 구분)

실 Gemini/검색을 쓰는 엔드포인트는 느립니다. **반드시 로딩 스피너**를 두세요.

| 빠름 (~즉시) | 느림 (실 AI, 10~30초) |
|---|---|
| auth/*, maps/grid, crowdsourcing/reports·{id}, media, sonify(~5초) | **maps/news, maps/spi, simulator/run, simulator/audit, advisor/chat** |

---

## 1. 인증 (Auth)

### `POST /api/v1/auth/register` → 201
```jsonc
// 요청 body (application/json)
{ "email": "user@example.com", "password": "secret123", "nickname": "홍길동" }  // password 6자 이상
// 응답
{ "access_token": "eyJhbGci...", "token_type": "bearer",
  "user": { "user_id": "user_da21f19c0984", "email": "user@example.com", "nickname": "홍길동" } }
```
- 이메일 중복 시 `400 {"detail": "..."}`

### `POST /api/v1/auth/login` → 200
```jsonc
// 요청
{ "email": "user@example.com", "password": "secret123" }
// 응답: register와 동일 (access_token + user)
```
- 실패 시 `401 {"detail": "Incorrect email or password."}`

### `GET /api/v1/auth/me` → 200 *(토큰 필수)*
```
Authorization: Bearer <access_token>
```
```json
{ "user_id": "user_da21f19c0984", "email": "user@example.com", "nickname": "홍길동" }
```
- 토큰 없음/무효 → **`401`** (403 아님)

> **토큰 사용법**: 로그인 후 `access_token`을 저장(웹: localStorage, 앱: SecureStore) → 이후 모든 요청 헤더에 `Authorization: Bearer <token>` 부착. 만료 7일.

---

## 2. 지도 (Maps)

### `GET /api/v1/maps/grid` (F-1) — 불평등 3D 격자
지도 화면 영역을 5×5 격자로 나눠 **실제 지역 통계**를 GeoJSON으로 반환. **전국 250개 시군구** 실데이터.

**쿼리 파라미터**
| 이름 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `ne_lat`,`ne_lng`,`sw_lat`,`sw_lng` | float | ✅ | 화면 바운딩 박스 |
| `zoom` | int | | 기본 14 (격자는 항상 5×5) |
| `dimension` | string | | `income`(기본)·`healthcare`·`climate`·`education` |

```jsonc
// 응답 (Google Maps/Mapbox에 그대로 렌더)
{
  "type": "FeatureCollection",
  "dimension": "income",
  "data_source": "real-region-stats",   // 또는 "synthetic-fallback"(미시딩 지역)
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Polygon", "coordinates": [[[126.98,37.57],[...],[126.98,37.57]]] },
      "properties": {
        "grid_id": "grid_0_0",
        "region": "서울특별시 종로구",   // 해당 격자의 실제 행정구역
        "index_value": 62.4,             // 0~100, 높을수록 양호
        "grade": "B (양호)",             // A(우수)/B(양호)/C(취약)/D(심각), 제보 있으면 "· 제보 N건 반영"
        "average_income": 5200000         // ↓ dimension별 추가 필드
      }
    }
  ]
}
```
**dimension별 추가 property**: `income`→`average_income`(원) · `healthcare`→`doctor_count_per_10k` · `climate`→`pm25_micrograms` · `education`→`education_index`

> 렌더 팁: `index_value`로 색상/높이(extrusion)를 매핑. `data_source==="synthetic-fallback"`이면 그 지역은 아직 실데이터 미시딩(현재 전국 시군구 시딩 완료).

### `GET /api/v1/maps/regions` (F-1) — 실제 시군구 경계 코로플레스 ⭐권장
`/grid`의 인공 5×5 격자 대신, **실제 행정구역 경계 폴리곤**을 실데이터 색으로 반환. 화면에 걸치는 시군구만 반환.

**쿼리**: `ne_lat`,`ne_lng`,`sw_lat`,`sw_lng`(필수), `dimension`(income/healthcare/climate/education, 기본 income)

```jsonc
{
  "type": "FeatureCollection",
  "dimension": "education",
  "data_source": "real-region-boundaries",
  "region_count": 47,
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "MultiPolygon", "coordinates": [[[[126.98,37.57], ...]]] },  // 실제 경계
      "properties": {
        "region_id": "kr-11010",
        "region": "서울특별시 종로구",
        "index_value": 68.3,          // 0~100, 전국 정규화 (지역마다 다름)
        "grade": "B (양호)",
        "education_index": 82.0        // dimension별 추가 필드 (grid와 동일)
      }
    }
  ]
}
```
- `index_value`는 **전국 기준 정규화**라 어느 뷰에서든 같은 지역은 같은 색.
- Google Maps `data.addGeoJson()` / Mapbox `fill-extrusion`에 그대로. 응답 ~100~150KB(광역 뷰 기준).
- 확대해도 화면에 걸친 시군구가 반환됩니다(빈 화면 없음). **지도 채색은 이 엔드포인트 사용을 권장**하고, `/grid`는 격자형 데모용으로 유지.

### `GET /api/v1/maps/news` (F-2) — 실시간 불평등 뉴스 핀 ⏱️느림
```jsonc
// 쿼리: ne_lat, ne_lng, sw_lat, sw_lng (필수)
// 응답
{
  "bounding_box": { "ne_lat": 37.6, "ne_lng": 127.05, "sw_lat": 37.5, "sw_lng": 126.95 },
  "source": "live-search",   // 실 검색 뉴스. 그라운딩 실패 시 "static"(폴백 4건)
  "pins": [
    { "pin_id": "pin_news_100", "headline": "서울 아파트 공시가격 초양극화...",
      "category": "income", "sentiment_score": -0.6, "summary": "...",
      "severity": "High", "latitude": 37.55, "longitude": 126.99 }
  ]
}
```

### `GET /api/v1/maps/spi` (F-4) — 위성 빈곤지수 리포트 ⏱️느림
```jsonc
// 쿼리: lat, lng (필수), region_name (기본 "대상 지역")
// ⚠️ region_name에 한글 쓰면 URL 인코딩 필수 (encodeURIComponent)
// 응답
{ "region_name": "서울 종로구", "latitude": 37.5665, "longitude": 126.978,
  "poverty_grade": "C (취약)", "green_access_score": 82.0, "slum_trend": "정체",
  "road_paving_ratio": 0.98, "night_light_intensity": 41.0, "reasoning": "..." }
```

---

## 3. 정책 시뮬레이터 (Simulator)

### `POST /api/v1/simulator/run` (F-3) — 정책 시뮬레이션 ⏱️느림(~15초)
```jsonc
// 요청 body
{ "title": "청년 교통비 보조금 확대", "description": "월 5만원 지원",
  "policies": [ { "category": "subsidy", "param_value": 50000 } ] }
// category: "subsidy"(저소득 보조금) | "minimum_wage"(최저소득 하한) | "tax"(고소득 세율 %)
// 응답
{
  "simulation_id": "sim_965b6853b405",
  "gini_before": 0.514, "gini_after": 0.502, "disparity_delta_percent": -2.31,
  "winners": ["저소득층"], "losers": ["고소득층"],   // 실제 소득변화 기반
  "agent_samples": [
    { "persona_id": "persona_001", "name": "시민 1", "age": 21,
      "disposable_income_delta_monthly": 50000, "utility_change": 0.12,
      "ai_diary_snippet": "이번 보조금으로 교통비 부담이 줄었다..." }
  ]  // 대표 8명 (실 Gemini 생성 일기)
}
```

### `POST /api/v1/simulator/sonify` (F-6) — 일기 음성 합성
```jsonc
// 요청 body
{ "diary_text": "매달 월세 부담이 줄어 숨통이 트였습니다." }
// 응답 (실 TTS WAV, <audio src>에 바로 사용)
{ "sonified_audio_url": "data:audio/wav;base64,UklGRi...", "text": "매달..." }
```

### `GET /api/v1/simulator/audit` (F-7) — 법안 사각지대 감사 ⏱️느림
```jsonc
// 쿼리: policy_title (필수, 한글이면 encodeURIComponent)
// 응답
{ "loopholes": ["...", "..."],
  "vulnerable_groups_affected": ["...", "..."],
  "recommended_amendments": ["...", "..."],
  "references_consulted": ["교통약자 이동편의 증진법", "장애인 활동지원 서비스"] }  // 벡터검색된 근거 정책
```

---

## 4. AI 정책 어드바이저 (Advisor)

### `POST /api/v1/advisor/chat` (F-5) — 불평등/정책 상담 ⏱️느림
```jsonc
// 요청 body
{ "question": "저소득 고령층 의료 접근성 정책의 사각지대는?" }
// 응답
{ "question": "저소득 고령층...",
  "answer": "제시된 참고 자료에 따르면...",   // 출처 인용 전문가 답변
  "references": [ { "title": "노인장기요양보험", "snippet": "..." } ],
  "references_consulted": ["노인장기요양보험", "기초연금"] }
```
> 메신저 UI: `question` 보내고 `answer` 표시, `references_consulted`를 출처 칩으로.

---

## 5. 크라우드소싱 제보 (Crowdsourcing)

### `POST /api/v1/crowdsourcing/report` → 201 — 제보 등록 (멀티모달)
**`multipart/form-data`** (JSON 아님):
| 필드 | 타입 | 필수 |
|---|---|---|
| `category` | text | ✅ (transport/housing/labor/healthcare 등) |
| `raw_title` | text | ✅ |
| `description` | text | ✅ |
| `latitude`,`longitude` | text(float) | ✅ |
| `media` | file(이미지) | 선택 |

```jsonc
// 응답 (= 제보 객체)
{ "report_id": "rep_5f104051", "user_id": "user_hackathon_equiscope_01",
  "category": "transport", "raw_title": "경사로 파손",        // PII 비식별화됨
  "sanitized_description": "휠체어 진입 불가...",              // PII 비식별화됨
  "latitude": 37.5, "longitude": 127.0,
  "is_valid": true, "ai_trust_score": 92.5,                   // 사진 있으면 Gemini Vision 판정
  "media_url": "http://34.67.12.246:8080/media/rep_5f104051.png",  // 사진 없으면 null
  "created_at": "2026-07-09T11:28:58.123456+00:00" }
```
> RN 앱: 카메라 촬영 → `FormData`에 `media` append → 전송. `media_url`을 즉시 지도 핀 썸네일로.

### `GET /api/v1/crowdsourcing/reports` → 200 — 영역 내 제보 목록 (지도 핀/피드)
```jsonc
// 쿼리: ne_lat, ne_lng, sw_lat, sw_lng (필수), category(선택 필터), valid_only(기본 false)
// 응답
{ "count": 3, "reports": [ { /* 위 제보 객체와 동일 스키마 */ } ] }
```

### `GET /api/v1/crowdsourcing/reports/{report_id}` → 200 — 제보 단건
- 없으면 `404 {"detail": "Report not found."}`

### `GET /media/{filename}` — 업로드 이미지 서빙
제보의 `media_url`을 `<img src>` / RN `<Image source>`에 그대로 사용.

---

## 6. 에러 규약

| 코드 | 의미 | 프론트 처리 |
|---|---|---|
| `400` | 잘못된 요청(이메일 중복 등) | `detail` 메시지 표시 |
| `401` | 인증 필요/토큰 만료 | 로그인 화면 유도 |
| `404` | 리소스 없음 | not-found UI |
| `422` | 검증 실패(파라미터 타입/누락) | 폼 검증 |
| `5xx` | 서버 오류 | 재시도 안내 |

모든 에러 응답은 `{"detail": "..."}` 형태(422는 `detail` 배열).

---

## 7. 프론트 연동 스니펫

```ts
// fetch 래퍼 예시 (웹/RN 공통)
const BASE = "http://34.67.12.246:8080";
let token: string | null = null;

async function api(path: string, init: RequestInit = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}

// 로그인
const { access_token } = await api("/api/v1/auth/login",
  { method: "POST", body: JSON.stringify({ email, password }) });
token = access_token;

// 지도 격자
const grid = await api(`/api/v1/maps/grid?ne_lat=37.6&ne_lng=127.1&sw_lat=37.4&sw_lng=126.9&dimension=income`);

// 제보 등록 (multipart — Content-Type 헤더 직접 지정 금지, 브라우저가 boundary 설정)
const fd = new FormData();
fd.append("category", "transport"); fd.append("raw_title", "..."); fd.append("description", "...");
fd.append("latitude", "37.5"); fd.append("longitude", "127.0"); fd.append("media", file);
const report = await fetch(`${BASE}/api/v1/crowdsourcing/report`, { method: "POST", body: fd })
  .then(r => r.json());
```

> **한글 쿼리 파라미터**(`region_name`, `policy_title`)는 반드시 `encodeURIComponent(...)`. fetch/axios가 body는 자동 인코딩하지만 URL 쿼리는 직접 처리 필요.

---

## 8. 전체 엔드포인트 요약

| 메서드 | 경로 | 인증 | 속도 |
|---|---|---|---|
| POST | `/api/v1/auth/register` | — | 빠름 |
| POST | `/api/v1/auth/login` | — | 빠름 |
| GET | `/api/v1/auth/me` | 필수 | 빠름 |
| GET | `/api/v1/maps/regions` ⭐ | 선택 | 빠름 |
| GET | `/api/v1/maps/grid` | 선택 | 빠름 |
| GET | `/api/v1/maps/news` | 선택 | ⏱️느림 |
| GET | `/api/v1/maps/spi` | 선택 | ⏱️느림 |
| POST | `/api/v1/simulator/run` | 선택 | ⏱️느림 |
| POST | `/api/v1/simulator/sonify` | 선택 | 보통 |
| GET | `/api/v1/simulator/audit` | 선택 | ⏱️느림 |
| POST | `/api/v1/advisor/chat` | 선택 | ⏱️느림 |
| POST | `/api/v1/crowdsourcing/report` | 선택 | 보통 |
| GET | `/api/v1/crowdsourcing/reports` | 선택 | 빠름 |
| GET | `/api/v1/crowdsourcing/reports/{id}` | 선택 | 빠름 |
| GET | `/media/{filename}` | — | 빠름 |

*데이터 출처·성격은 [DATA.md](DATA.md) 참고. 마지막 갱신: 2026-07-09.*
