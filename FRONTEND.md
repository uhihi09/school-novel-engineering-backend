# 프론트엔드 핸드오프 (Web · App)

백엔드는 배포 완료 · 14개 API 라이브. 이 문서 하나로 연동 시작하세요. (상세 스펙: [API.md](API.md))

## 🚀 지금 바로

| 항목 | 값 |
|---|---|
| **Base URL** | `http://34.67.12.246:8080` |
| 라이브 API 문서(Swagger) | http://34.67.12.246:8080/docs |
| 상세 연동 가이드 | [API.md](API.md) (요청/응답 JSON 예시 전부) |
| 데이터 출처·성격 | [DATA.md](DATA.md) |

서버는 항상 떠 있습니다(systemd 상시 구동). 별도 실행 필요 없음.

## 🔑 인증 (딱 3가지만)

1. 인증은 **쿠키 아님** → `Authorization: Bearer <token>` **헤더**로.
2. `maps`·`simulator`·`crowdsourcing`은 **토큰 없이도 호출됨**(익명 데모). 로그인 붙이면 본인 계정으로 기록.
3. 로그인 흐름: `POST /auth/register` 또는 `/auth/login` → `access_token` 저장(웹 localStorage / 앱 SecureStore) → 이후 요청 헤더에 부착. 만료 7일. 토큰 없을 때 `/auth/me`는 **401**.

## 🗺️ 지도는 이걸 쓰세요

- **채색 지도**: `GET /maps/regions` ⭐ — **실제 시군구 경계(GeoJSON) + 실데이터 색**. (`/grid`는 인공 격자라 데모용, 안 쓰는 게 좋음)
  - Google Maps: `map.data.addGeoJson(res)` / Mapbox: `fill-extrusion`
  - `properties.index_value`(0~100)로 색/높이, `properties.region`으로 라벨
  - `dimension` = `income`·`healthcare`·`climate`·`education` (경제/의료/환경/교육)
- **뉴스 핀**: `GET /maps/news` (실시간, 느림)
- **지역 상세(빈곤지수)**: `GET /maps/spi?lat=&lng=&region_name=` (느림)

## ⏱️ 로딩 스피너 필수 (실 AI라 10~30초)

`maps/news` · `maps/spi` · `simulator/run` · `simulator/audit` · `advisor/chat`
→ 반드시 로딩 UI. 나머지(auth·maps/regions·crowdsourcing·media)는 빠름.

## 📱 화면 → 엔드포인트 매핑

| 화면 | 엔드포인트 |
|---|---|
| 로그인/회원가입 | `POST /auth/register`·`/auth/login`, `GET /auth/me` |
| 불평등 지도 | `GET /maps/regions`(채색) + `/maps/news`(핀) + `/maps/spi`(상세) |
| 정책 시뮬레이터 | `POST /simulator/run`(지니·페르소나 일기) + `/simulator/sonify`(일기 음성) |
| AI 정책 상담 | `POST /advisor/chat` + `GET /simulator/audit`(사각지대 감사) |
| 시민 제보(앱) | `POST /crowdsourcing/report`(멀티파트) + `GET /crowdsourcing/reports`(피드) + `/media/{file}`(사진) |

## ⚠️ 함정 3가지 (꼭)

1. **한글 쿼리 파라미터**(`region_name`, `policy_title`)는 `encodeURIComponent()` 필수. URL 쿼리는 자동 인코딩 안 됨.
2. **제보 등록은 `multipart/form-data`** (JSON 아님). `FormData` 쓰고 **`Content-Type` 헤더 직접 지정 금지**(브라우저가 boundary 설정). 사진은 `media` 필드.
3. **CORS는 모든 origin 허용**이지만 credentials(쿠키) 미사용 → 토큰은 헤더로만.

## 🎨 응답 필드 핵심

- 지도(`/maps/regions`): `features[].properties` = `{region, index_value(0~100), grade, average_income|doctor_count_per_10k|pm25_micrograms|education_index}`
- 시뮬레이터(`/simulator/run`): `{gini_before, gini_after, disparity_delta_percent, winners[], losers[], agent_samples[]{name, age, disposable_income_delta_monthly, ai_diary_snippet}}`
- 어드바이저/감사: `{answer, references_consulted[]}` / `{loopholes[], vulnerable_groups_affected[], recommended_amendments[], references_consulted[]}`
- sonify: `{sonified_audio_url}` → `<audio src=...>`에 바로
- 제보: `{report_id, category, sanitized_description, latitude, longitude, is_valid, ai_trust_score, media_url, created_at}`

## 🧪 데이터 성격 (데모 시 오해 방지)

- 지역 **좌표는 실제**, **통계값은 실 웹출처 기반 AI 추정치**(방향은 정확: 강남 소득 740만 vs 영양군 212만). KOSIS 공식 확정치는 아님 — 데모에서 "실측"이라 단정하진 말 것.
- 정책 RAG(어드바이저/감사)는 **실제 벡터 검색**. 시뮬레이터 페르소나는 합성 모델. 상세는 [DATA.md](DATA.md).

## 📌 상태

- 완료: 전국 250개 시군구 지도, 인증, 시뮬레이터, 어드바이저(벡터 RAG), 제보+미디어, 실 TTS, 실뉴스
- 로드맵: F-8 AI 신문고(제보→민원서), KOSIS 공식데이터

문의: 백엔드 담당자. 엔드포인트 추가/필드 변경 필요하면 요청 주세요.
