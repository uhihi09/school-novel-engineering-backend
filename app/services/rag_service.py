import re
from typing import Dict, Any, List
from app.services.gemini_service import gemini_service

class RAGService:
    def __init__(self):
        # Local policy and landmark litigation knowledge base for the policy RAG (F-5, F-7)
        self.legislation_kb = [
            {
                "id": "policy_01",
                "title": "청년 주거 지원 저리 대출 시행 세칙",
                "content": "중위소득 120% 이하 만 19세~34세 무주택 청년 대상 전세자금 연 1.5% 저리 융자 지원. 단, 부모 합산 소득 및 부동산 자산 요건 심사 추가."
            },
            {
                "id": "policy_02",
                "title": "교통약자 이동 편의 증진법 시행령",
                "content": "버스 정류장 및 지하철 역사 내 엘리베이터 및 휠체어 단차 극복 리프트 설치 의무화. 인구 10만 명 미만 소도시의 인프라 의무화 유예 조항 존재."
            },
            {
                "id": "policy_03",
                "title": "대기환경보전법 영유아 노약자 보호 조치",
                "content": "고농도 미세먼지(PM2.5) 비상저감 조치 발령 시 어린이집, 경로당 공기청정 설비 무상 점검 지원. 비인가 미등록 아동 교육시설 대책 누락."
            }
        ]

    def search_policies(self, query: str) -> List[Dict[str, Any]]:
        """Performs simple local keyword matching RAG search on legislative documents."""
        results = []
        keywords = re.findall(r'\w+', query.lower())
        for doc in self.legislation_kb:
            score = 0
            doc_text = (doc["title"] + " " + doc["content"]).lower()
            for kw in keywords:
                if kw in doc_text:
                    score += 1
            if score > 0:
                results.append({"doc": doc, "relevance_score": score})
        
        # Sort by match score
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return [r["doc"] for r in results]

    def audit_policy_blindspots(self, policy_title: str) -> Dict[str, Any]:
        """F-7: Executes policy audit by pulling relevant docs via RAG and invoking Gemini analysis."""
        # Step 1: Query knowledge base
        relevant_policies = self.search_policies(policy_title)

        # Step 2: Use Gemini service to perform legislative audit
        audit_results = gemini_service.audit_legislation(policy_title)

        # Merge RAG references
        audit_results["references_consulted"] = [p["title"] for p in relevant_policies]
        return audit_results

    def answer_policy_question(self, question: str) -> Dict[str, Any]:
        """F-5: Retrieves relevant reference docs and generates a cited advisor answer via Gemini."""
        # Step 1: Retrieve grounding documents from the local knowledge base.
        relevant_policies = self.search_policies(question)

        # Step 2: Generate a grounded, cited answer.
        result = gemini_service.generate_advisor_answer(question, relevant_policies)

        # Step 3: Surface which KB documents were consulted for transparency.
        result["references_consulted"] = [p["title"] for p in relevant_policies]
        return result

rag_service = RAGService()
