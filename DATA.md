# EquiScope 데이터 명세 (Data Provenance)

이 프로젝트가 사용하는 **모든 데이터의 출처·성격(실데이터/합성/폴백)·저장 위치·재생성 방법**을 기록합니다.
원칙: 실데이터는 실데이터로, 합성/폴백은 명확히 표기.

| 범례 | 의미 |
|---|---|
| 🟢 실데이터 | 실제 공개 출처 또는 실시간 수집 |
| 🧮 계산 | 실제 수식으로 산출 |
| 🧪 합성 | 데모용 생성 모델(가짜 아님, 규칙 기반 시뮬레이션) |
| 🟡 폴백 | 실데이터 사용 불가 시에만 쓰는 하드코딩 |

---

## 1. 불평등 지도 데이터 (F-1) — `region_stats` 테이블

| 항목 | 성격 | 출처 |
|---|---|---|
| 행정구역 목록 · 중심좌표 (전국 250개 시군구) | 🟢 | **southkorea-maps GeoJSON (KOSTAT 2018)** 경계 폴리곤에서 중심좌표 계산 |
| 소득·의사밀도·PM2.5·교육지수·시도명 | 🟢 | **Gemini + Google 검색 그라운딩** (실제 공개 웹 통계 기반, 1회 수집·DB 저장) |
| 격자별 지수/등급 | 🧮 | 위 실통계를 최근접 지역 매핑 + 정규화 |
| 제보 감점 (검증 제보 수) | 🟢 | `inequality_reports` 실데이터 |

- **소스 URL**: `https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2018/json/skorea-municipalities-2018-geo.json`
- **재생성**: `python scripts/seed_regions.py` (그라운딩이라 ~10분, nohup 권장)
- **응답 플래그**: `/maps/grid` 응답의 `data_source` = `real-region-stats`(시딩됨) / `synthetic-fallback`(미시딩)
- ⚠️ 통계는 "실제 웹 출처 기반 근사치"이지 KOSIS 공식 확정치는 아님. 정밀도 필요 시 KOSIS/공공데이터포털 CSV로 교체 가능.

## 2. 정책 RAG 코퍼스 (F-5·F-7) — `policy_docs` 테이블

| 항목 | 성격 | 출처 |
|---|---|---|
| 정책 문서 16건(제목·본문·카테고리) | 🟢 | 실제 한국 공개 정책 정보 (`scripts/seed_policies.py` 내 CORPUS) |
| 임베딩 벡터 (3072차원) | 🟢 | **`gemini-embedding-001`** 로 산출 |
| 검색 | 🧮 | 코사인 유사도 벡터 검색 |
| 폴백 KB 3건 | 🟡 | `rag_service.legislation_kb` (벡터 미시딩 시에만) |

**수록 정책 16건**: 청년 주거 지원 저리대출 / 교통약자 이동편의 증진법 / 대기환경보전법 미세먼지 저감 / 기초연금 / 국민기초생활보장 생계급여 / 청년내일채움공제 / 아동수당 / 노인장기요양보험 / 교육급여·교육비 지원 / 긴급복지지원제도 / 최저임금제 / 국민건강보험 지역가입자 / 장애인 활동지원 서비스 / 주거취약계층 주거상향 지원 / 에너지바우처(냉난방비) / 다문화가족 지원

- **재생성**: `python scripts/seed_policies.py`

## 3. 시뮬레이터 페르소나 (F-3) — 런타임 생성 (`simulator_service`)

| 항목 | 성격 | 설명 |
|---|---|---|
| 1,000명 가상 시민 | 🧪 | 9개 직업 템플릿 기반 생성(numpy seed=42 확률 변동). **실존 인물 아님** — 인구통계 시뮬레이션 |
| 지니계수 | 🧮 | 표준 절대차 공식으로 실제 계산 |
| 정책 소득 보정 규칙 | 🧪 | subsidy/minimum_wage/tax 규칙 기반 통계 모델 |
| winners/losers | 🧮 | 브래킷별 실제 소득 변화에서 산출 |
| 페르소나 일기 | 🟢 | 실 Gemini 생성 |

**직업 템플릿(월 평균소득, 계층)**: 쿠팡 배달 단기근로(180만·low) / 대학생 편의점 알바(95만·low) / 노년 한부모 기초수급(70만·low) / 의원실 보좌관(420만·mid) / IT 스타트업 개발자(510만·mid) / 프리랜서 디자이너(280만·mid) / 프랜차이즈 자영업(210만·mid) / 대기업 부장(750만·high) / 강남 임대업주(1,800만·high)

## 4. 실시간 뉴스 (F-2) — `news_pins` 테이블 + `/maps/news`

| 성격 | 출처 |
|---|---|
| 🟢 실뉴스 (지속 수집) | **백그라운드 수집기**가 15분마다 전국 17개 시도를 Gemini + Google 검색 그라운딩으로 수집, `news_pins`에 중복 없이 누적 (응답 `source: "stored-live-search"`) |
| 🟢 실뉴스 (라이브) | 미수집 영역 첫 조회 시 실시간 검색 후 저장 (응답 `source: "live-search"`) |
| 🟡 폴백 | 4개 하드코딩 시나리오 헤드라인 (`source: "static"`, 그라운딩 실패 시) |

- **수집기 설정**: `NEWS_COLLECTOR_ENABLED`(기본 false, VM에서만 true) · `NEWS_COLLECT_INTERVAL_MINUTES`(기본 15)
- 중복 차단: 헤드라인 정규화 sha256 `DedupeKey` (unique) · 삭제 없이 누적 → 시계열 자산
- 쿼터 방어: 시도 3연속 실패 시 해당 사이클 중단 후 다음 주기 대기

## 5. 위성 빈곤지수 SPI (F-4) — `/maps/spi`

| 성격 | 출처 |
|---|---|
| 🟢 | **Gemini + Google 검색 그라운딩** (실제 지역 데이터 리서치) |
| (확장) | 실 위성 타일 제공 시 Gemini Vision 판독 경로 존재 (Maps Static 키 필요) |

## 6. 크라우드소싱 제보 (F-2·F-6) — `inequality_reports` 테이블 + `/media`

| 항목 | 성격 |
|---|---|
| 제보 레코드(위치·카테고리·설명) | 🟢 사용자 실입력, Postgres 저장 |
| PII 비식별화 | 🟢 실 Gemini |
| 사진 검증(is_valid, ai_trust_score) | 🟢 실 Gemini Vision |
| 업로드 파일 | 🟢 VM 파일시스템 저장 후 `/media/{id}` 실서빙 |

## 7. 사용자·인증 — `users` 테이블

| 항목 | 성격 |
|---|---|
| 계정(이메일·닉네임·관심지역) | 🟢 사용자 실입력, Postgres 저장 |
| 비밀번호 | 🟢 PBKDF2-HMAC-SHA256 해시 저장(평문 미저장) |

---

## 8. AI 모델 (Google Gemini)

| 용도 | 모델 | config 키 |
|---|---|---|
| 경량 태스크(뉴스 감성/PII/사진검증/페르소나/그라운딩) | `gemini-3.5-flash` | `GEMINI_FLASH_MODEL` |
| 심층(감사/어드바이저/SPI) | `gemini-2.5-pro` | `GEMINI_PRO_MODEL` |
| 음성 합성(TTS) | `gemini-2.5-flash-preview-tts` | `GEMINI_TTS_MODEL` |
| 임베딩(RAG) | `gemini-embedding-001` | `GEMINI_EMBED_MODEL` |

## 9. 인프라

| 항목 | 값 |
|---|---|
| DB | Cloud SQL PostgreSQL 18 (`iceu-578:asia-northeast3:school-hackathon-db`) |
| 배포 | GCE VM `34.67.12.246:8080`, systemd `equiscope` |
| 미디어 저장 | VM 로컬 `MEDIA_DIR` → `/media` StaticFiles |

## 10. 데이터 재생성 요약

```bash
# 전국 지역 통계 (실좌표 + 그라운딩 통계)
python scripts/seed_regions.py

# 정책 RAG 코퍼스 + 임베딩
python scripts/seed_policies.py

# DB 연결 확인 + 테이블 생성
python scripts/init_db.py
```

## 11. DB 테이블 요약

| 테이블 | 내용 |
|---|---|
| `users` | 계정 |
| `inequality_reports` | 시민 제보 |
| `simulation_logs` | 정책 시뮬레이션 실행 이력 |
| `region_stats` | 전국 시군구 실통계 (F-1 지도) |
| `policy_docs` | 정책 코퍼스 + 임베딩 (RAG) |
| `news_pins` | 불평등 뉴스 누적 수집 (F-2, 15분 주기 백그라운드 수집기) |

---
*마지막 갱신: 2026-07-10. 실데이터/합성 구분은 코드 기준으로 정확히 표기했습니다.*
