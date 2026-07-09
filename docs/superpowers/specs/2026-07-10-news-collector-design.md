# 뉴스 지속 수집기 (News Collector) 설계

날짜: 2026-07-10 · 상태: 승인됨

## 목적

불평등 뉴스를 Gemini + Google 검색 그라운딩으로 **주기적으로 수집해 DB에 누적**한다.
현재 `/maps/news`는 요청마다 10~30초 걸리는 실시간 검색인데, 이를 DB 우선 조회로 바꿔
① 즉시 응답 ② 뉴스 시계열 자산 축적을 얻는다.

## 결정 사항 (사용자 확정)

| 항목 | 결정 |
|---|---|
| 수집 대상 | 불평등 뉴스 (지역 통계·정책 코퍼스는 제외) |
| 수집 단위 | 전국 17개 시도 (시도별 대표 bbox) |
| 수집 주기 | **15분** (config로 조절 가능) — 하루 약 1,632회 그라운딩 호출이므로 쿼터 방어 필수 |
| 서빙 방식 | `/maps/news`는 DB 우선, 비었으면 기존 라이브 검색 폴백(+결과 저장) |
| 실행 방식 | FastAPI 프로세스 내 asyncio 백그라운드 루프 (lifespan에서 시작) |

## 구성 요소

### 1. 테이블 `news_pins` (`app/db/models.py`)

```
PinId(PK) · RegionName · Headline · Category · SentimentScore · Severity ·
Summary · Latitude · Longitude · DedupeKey(unique) · CollectedAt(index)
```

- `DedupeKey` = sha256(정규화된 headline) — 같은 뉴스 재수집 시 insert 스킵
- 삭제 없음(누적) — 시계열 데이터 자산

### 2. 수집기 `app/services/news_collector_service.py`

- `PROVINCES`: 17개 시도 이름 + 근사 bbox 상수
- `store_pins(db, region_name, pins, bounds)`: 좌표 클램프 + 중복 제거 + insert, 삽입 수 반환
- `run_collection_cycle(db)`: 시도 순회, 시도별 try/except(한 지역 실패가 사이클을 죽이지 않음),
  시도 사이 짧은 sleep, **연속 3회 실패 시 사이클 중단**(쿼터 소진/장애 휴리스틱 —
  `gemini_service.fetch_local_news`가 예외를 삼키고 None을 반환하므로 상태코드 대신 연속 실패로 감지)
- `collector_loop()`: async 무한 루프 — `asyncio.to_thread`로 사이클 실행(블로킹 SDK 호출 격리),
  사이클 완료 후 `NEWS_COLLECT_INTERVAL_MINUTES` 대기

### 3. 설정 (`app/core/config.py`)

- `NEWS_COLLECTOR_ENABLED: bool = False` — 기본 꺼짐. VM 환경변수로만 켠다 (로컬/테스트 쿼터 보호)
- `NEWS_COLLECT_INTERVAL_MINUTES: int = 15`

### 4. 스케줄러 (`app/main.py` lifespan)

- enabled면 `asyncio.create_task(collector_loop())`, shutdown 시 cancel + await

### 5. `/maps/news` 변경 (`app/api/v1/maps.py`)

1. bbox 내 + 최근 48시간 `news_pins` 조회 (최신순, limit 12) → 있으면
   `source: "stored-live-search"`로 즉시 응답
2. 비었으면 기존 라이브 검색 → 응답과 동시에 `store_pins`로 저장 (다음 요청부턴 즉시)
3. 라이브도 실패하면 기존 static 폴백 유지
- 핀 스키마는 기존과 동일 — 프론트 수정 불필요

## 에러 처리

- 지역 단위 격리: 한 지역 예외/파싱 실패 → 로그만 남기고 다음 지역
- 쿼터/장애: 연속 3회 실패 → 남은 지역 포기, 다음 사이클 대기
- DB 불가: 사이클 전체 try/except — 서버는 계속 산다

## 테스트 (`tests/test_news_collector.py`)

- `store_pins` 중복 제거: 같은 headline 2회 저장 → 1건만 insert
- `/maps/news` DB 우선: bbox 내 핀을 미리 넣으면 `stored-live-search`로 반환
- `/maps/news` 폴백 유지: DB 비고 Gemini 없음(테스트 환경) → 기존 `static` 폴백
- 수집 루프는 테스트에서 항상 비활성 (conftest에서 env 고정)

## 문서 갱신

- API.md: `/maps/news`에 `stored-live-search` 소스와 "저장분 있으면 빠름" 반영
- DATA.md: §4 실시간 뉴스에 `news_pins` 누적 수집 반영
