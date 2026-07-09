"""Seed the policy/legislation corpus for real vector-search RAG (F-5/F-7).

Loads a corpus of real Korean public policies, computes Gemini embeddings for each, and stores
them in the policy_docs table. Run on a host with a real GEMINI_API_KEY:
    python scripts/seed_policies.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import Base, SessionLocal, engine
from app.db import models  # noqa: F401
from app.db.models import PolicyDoc
from app.services.gemini_service import gemini_service

# Real Korean public policies (public information), used as the RAG corpus.
CORPUS = [
    ("policy-youth-housing", "청년 주거 지원 저리 대출", "housing",
     "중위소득 이하 만 19~34세 무주택 청년을 대상으로 전세자금·월세를 저리로 융자·지원하는 제도. "
     "부모 합산 소득과 부동산 자산 요건 심사가 있으며, 보증금 대출과 월세 지원이 분리 운영된다."),
    ("policy-mobility-act", "교통약자 이동편의 증진법", "transport",
     "장애인·고령자·임산부 등 교통약자의 이동권 보장을 위해 저상버스 도입, 지하철 엘리베이터·휠체어 리프트 설치를 "
     "의무화하는 법. 인구 10만 미만 소도시에는 인프라 의무화 유예 조항이 있어 지역 격차가 발생한다."),
    ("policy-air-act", "대기환경보전법 미세먼지 저감", "climate",
     "고농도 초미세먼지(PM2.5) 비상저감조치 발령 시 차량 운행 제한과 함께 어린이집·경로당 공기청정 설비를 "
     "지원한다. 비인가 미등록 아동시설은 지원 대상에서 누락되는 사각지대가 있다."),
    ("policy-basic-pension", "기초연금", "welfare",
     "만 65세 이상 소득 하위 70% 노인에게 매월 일정액을 지급하는 노후 소득보장 제도. 국민연금 수급액과 연계 감액되며, "
     "부부 동시 수급 시 감액 규정이 적용된다."),
    ("policy-basic-livelihood", "국민기초생활보장 생계급여", "welfare",
     "소득인정액이 기준 중위소득의 일정 비율 이하인 가구에 생계·의료·주거·교육 급여를 지급한다. 부양의무자 기준이 "
     "완화되었으나 신청주의로 인한 미신청 사각지대가 여전히 존재한다."),
    ("policy-youth-account", "청년내일채움공제", "labor",
     "중소기업에 정규직 취업한 청년이 일정 기간 근속하면 본인·기업·정부 적립금을 합쳐 목돈을 마련해주는 자산형성 제도. "
     "잦은 이직이나 기업의 중도 폐업 시 수급이 제한된다."),
    ("policy-child-allowance", "아동수당", "welfare",
     "만 8세 미만 모든 아동에게 매월 지급하는 보편적 현금 급여. 보편 지급으로 사각지대가 적으나, 지급 연령 상한 직전 "
     "구간의 아동은 지원이 단절되는 문제가 있다."),
    ("policy-ltc-insurance", "노인장기요양보험", "healthcare",
     "65세 이상 또는 노인성 질병을 가진 국민에게 요양시설·재가 돌봄 서비스를 제공하는 사회보험. 등급 판정에서 "
     "탈락한 경계선 노인과 독거노인이 돌봄 공백에 노출된다."),
    ("policy-edu-benefit", "교육급여·교육비 지원", "education",
     "저소득층 초·중·고 학생에게 교육활동지원비·교과서비·급식비 등을 지원한다. 학원비 등 사교육 격차는 보전되지 않아 "
     "학습 성취 격차가 누적될 수 있다."),
    ("policy-emergency-welfare", "긴급복지지원제도", "welfare",
     "주소득자의 사망·실직·질병 등 위기 상황 가구에 생계·의료·주거비를 신속 지원한다. 소득·재산 기준이 엄격하고 "
     "지원 기간이 짧아 위기 장기화 가구가 사각지대에 남는다."),
    ("policy-minimum-wage", "최저임금제", "labor",
     "모든 사업장에 적용되는 시간당 임금 하한선. 저임금 노동자의 소득을 보전하지만 급격한 인상은 영세 자영업자의 "
     "고용 축소로 이어질 수 있어 분배 효과와 고용 효과의 상충이 논쟁된다."),
    ("policy-health-insurance", "국민건강보험 지역가입자", "healthcare",
     "직장가입자가 아닌 자영업자·프리랜서 등이 소득·재산에 따라 보험료를 납부하는 제도. 소득 파악이 어려운 "
     "플랫폼 노동자·단기 근로자의 보험료 부담 형평성 문제가 제기된다."),
    ("policy-disability-activity", "장애인 활동지원 서비스", "welfare",
     "일상생활이 어려운 등록 장애인에게 활동지원사의 신체·가사·이동 지원을 제공한다. 서비스 시간 상한과 "
     "본인부담금 때문에 중증 장애인의 실제 필요를 다 채우지 못하는 경우가 있다."),
    ("policy-vulnerable-housing", "주거취약계층 주거상향 지원", "housing",
     "반지하·쪽방·고시원 등에 거주하는 주거취약계층의 공공임대주택 이주와 보증금·이사비를 지원한다. 침수 위험 "
     "반지하 가구의 신속 이주 수요에 비해 공공임대 물량이 부족하다."),
    ("policy-energy-voucher", "에너지바우처(냉난방비 지원)", "welfare",
     "생계·의료급여 수급 가구 중 노인·영유아·장애인 등에게 여름 냉방·겨울 난방 에너지 비용을 바우처로 지원한다. "
     "폭염·한파 취약 계층 대상이나 지원 단가가 실제 에너지 비용에 못 미친다는 지적이 있다."),
    ("policy-multicultural", "다문화가족 지원", "welfare",
     "결혼이민자와 그 자녀에게 한국어 교육, 통·번역, 자녀 학습 지원 등을 제공한다. 미등록 이주민과 중도입국 자녀는 "
     "제도적 지원에서 배제되는 사각지대가 있다."),
]


def main() -> int:
    Base.metadata.create_all(bind=engine)
    if gemini_service.client is None:
        print("No Gemini client (missing key). Cannot compute embeddings. Aborting.")
        return 1

    texts = [f"{title}. {content}" for _id, title, _cat, content in CORPUS]
    print(f"Embedding {len(texts)} policy documents...")
    vectors = gemini_service.embed_texts(texts)
    if not vectors or len(vectors) != len(CORPUS):
        print("Embedding failed or count mismatch. Aborting.")
        return 1

    db = SessionLocal()
    for (doc_id, title, category, content), vec in zip(CORPUS, vectors):
        db.merge(PolicyDoc(
            DocId=doc_id, Title=title, Category=category, Content=content,
            Embedding=vec, Source="Public Korean policy corpus",
        ))
    db.commit()
    n = db.query(PolicyDoc).count()
    db.close()
    print(f"Seeded {n} policy docs with {len(vectors[0])}-dim embeddings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
