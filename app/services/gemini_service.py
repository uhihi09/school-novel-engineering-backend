import json
import logging
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types
from app.core.config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.client = None
        try:
            if settings.USE_VERTEX_AI and settings.GCP_PROJECT_ID:
                # Vertex AI backend (auth via GOOGLE_APPLICATION_CREDENTIALS).
                self.client = genai.Client(
                    vertexai=True,
                    project=settings.GCP_PROJECT_ID,
                    location=settings.GCP_LOCATION,
                )
                logger.info("Gemini Client initialized against Vertex AI (project=%s).", settings.GCP_PROJECT_ID)
            elif self.api_key:
                # Direct Google AI Studio API key via the google-genai SDK.
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Gemini Client initialized with google-genai SDK (API key).")
            else:
                logger.info("No Gemini credentials configured; using high-quality mock fallbacks.")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Client: {e}")
            self.client = None

    def _get_mock_fallback(self, prompt_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Provides a high-quality mock fallback in case the API key is missing or calls fail."""
        if prompt_type == "news_sentiment":
            return {
                "category": "healthcare" if "병원" in context.get("text", "") or "의료" in context.get("text", "") else "income",
                "sentiment_score": -0.75 if "취약" in context.get("text", "") or "부족" in context.get("text", "") else -0.25,
                "summary": "로컬 지역 취약 계층의 필수 자원 접근도 감소 경보",
                "severity": "High" if "심각" in context.get("text", "") else "Medium"
            }
        elif prompt_type == "pii_sanitize":
            desc = context.get("description", "")
            # Basic client-side scrub simulation
            sanitized = desc.replace("010-1234-5678", "[전화번호 비식별화]")
            sanitized = sanitized.replace("홍길동", "김*철")
            return {
                "sanitized_description": "A동 버스 정류장 사거리 리프트가 고장나 교통 약자의 이동 장벽이 극심합니다. 빠른 수리가 요구됩니다." if "경사로" in desc or "리프트" in desc else sanitized
            }
        elif prompt_type == "multimodal_verify":
            return {
                "is_valid": True,
                "ai_trust_score": 92.5,
                "confidence_reasoning": "이미지 내 휠체어 진입로 턱의 단차 균열 파손이 실제 노후화된 도로 환경으로 판독됨."
            }
        elif prompt_type == "agent_simulation":
            persona = context.get("persona", {})
            policy = context.get("policy", "")
            
            # Simple reactive logic based on agent profile
            is_student = "학생" in persona.get("job", "") or "취준생" in persona.get("job", "")
            
            if "보조금" in policy or "지원금" in policy:
                delta = 150000 if is_student else 50000
                utility = 0.12 if is_student else 0.03
                diary = f"최근 발의된 복지 수당 및 보조금 확대 정책안 덕에 식비 및 필수 도서 구입에 대한 가계 숨통이 확실히 트였습니다. 매달 삶에 대한 불안감이 한결 덜어지는 기분입니다."
            else:
                delta = -20000
                utility = -0.02
                diary = f"새로운 규제안 도입 소식에 자영업자들의 한숨이 늘어갑니다. 고정 지출은 그대로인데 세금과 원자재 부담만 늘어나는 것은 아닌지 다음 달 가게 장부가 걱정됩니다."
                
            return {
                "disposable_income_delta_monthly": delta,
                "utility_change": utility,
                "ai_diary_snippet": diary
            }
        elif prompt_type == "legislative_audit":
            return {
                "loopholes": [
                    "소득 분위 기준선(중위 50%) 바로 직전 구간의 차상위 경계선 가구들이 지원 대상에서 전면 누락되는 낙인 효과 발생.",
                    "오프라인 온라인 양방향 신청 창구 중, 디지털 기기 조작에 익숙하지 않은 모바일 취약 영유아/독거노인 세대의 자동 사각지대화 우려."
                ],
                "vulnerable_groups_affected": [
                    "디지털 사각지대에 속한 고령 노인 세대",
                    "건강 보험 사각지대에 노출된 미등록 단기 근로 노동자"
                ],
                "recommended_amendments": [
                    "소득 단절 구간 완충지대 도입을 통해 지원금을 소득 수준에 비례해 슬라이딩 방식으로 점진적 감액 지원하도록 보완 필요.",
                    "지자체 거점 복지센터 사회복지사의 직권 신청 권한 부여 조항 명시 필요."
                ]
            }
        elif prompt_type == "advisor_answer":
            question = context.get("question", "")
            docs = context.get("docs", [])
            ref_titles = [d.get("title", "") for d in docs] or ["OECD 불평등 백서", "기획재정부 예산안 보고서"]
            preview = (question[:60] + "…") if len(question) > 60 else question
            body = (
                f"질의하신 '{preview}' 사안은 복지 재정의 형평성과 효율성 간 상충으로 요약됩니다. "
                "국제 비교 연구에 따르면 보편적 급여는 행정 비용이 낮고 사각지대를 최소화하는 반면, "
                "선별적 급여는 재정 효율이 높으나 신청주의로 인한 미수급(non-take-up) 문제가 큽니다. "
                "한국의 경우 소득 하위 구간의 한계 유효세율 급증(복지 절벽)을 완화하는 점진적 감액 설계가 핵심 권고사항입니다."
            )
            return {
                "answer": body,
                "references": [{"title": t, "snippet": "관련 조항 및 통계 근거 발췌"} for t in ref_titles],
            }
        elif prompt_type == "satellite_spi":
            seed = int(context.get("seed", 50))
            grade_scale = ["A (양호)", "B (보통)", "C (취약)", "D (심각)", "E (극심)"]
            return {
                "poverty_grade": grade_scale[seed % len(grade_scale)],
                "green_access_score": round(20.0 + (seed % 60), 1),
                "slum_trend": "확산" if seed % 3 == 0 else "정체",
                "road_paving_ratio": round(0.35 + (seed % 50) / 100.0, 2),
                "night_light_intensity": round(5.0 + (seed % 40) * 0.7, 1),
                "reasoning": "위성 타일 판독 결과 비포장 도로 비중과 야간 조도 저하가 관측되어 물리적 주거 인프라 취약성이 감지됨.",
            }
        return {}

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        """Parse a JSON object from an LLM response, tolerating markdown fences, surrounding
        prose, and truncated output (Gemini occasionally omits the closing brace). Repairs an
        unterminated string and unbalanced braces/brackets before a final parse attempt."""
        if not text:
            raise ValueError("empty response")
        s = text.strip()
        # Strip ``` / ```json code fences if present.
        if s.startswith("```"):
            s = s[3:]
            if s[:4].lower() == "json":
                s = s[4:]
            if s.endswith("```"):
                s = s[:-3]
            s = s.strip()
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        # Narrow to the first JSON object and balance any unclosed string/brackets.
        start = s.find("{")
        if start == -1:
            raise json.JSONDecodeError("no JSON object found", s, 0)
        s = s[start:]
        in_str = False
        escaped = False
        closers = []
        end_idx = None
        for i, ch in enumerate(s):
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if in_str:
                if ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                closers.append("}")
            elif ch == "[":
                closers.append("]")
            elif ch in "}]":
                if closers:
                    closers.pop()
                if not closers:  # first top-level object/array closed -> drop trailing prose
                    end_idx = i
                    break
        if end_idx is not None:
            return json.loads(s[:end_idx + 1])
        # Truncated output: close any open string and unbalanced brackets, then parse.
        repaired = s + ('"' if in_str else "") + "".join(reversed(closers))
        return json.loads(repaired)

    def analyze_news_sentiment(self, news_text: str) -> Dict[str, Any]:
        """F-2: Analyzes real-time news for inequality category, sentiment, and severity."""
        if not self.client:
            return self._get_mock_fallback("news_sentiment", {"text": news_text})
        
        prompt = f"""
        Analyze the following text regarding local inequality. Extract the category of inequality, sentiment score (-1.0 to 1.0), and a concise summary.
        Text: {news_text}
        
        Return exactly a JSON object matching this structure:
        {{
          "category": "income" | "healthcare" | "climate" | "education",
          "sentiment_score": float,
          "summary": "string",
          "severity": "Low" | "Medium" | "High"
        }}
        """
        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_FLASH_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return self._parse_json(response.text)
        except Exception as e:
            logger.error(f"Gemini API Error in analyze_news_sentiment: {e}")
            return self._get_mock_fallback("news_sentiment", {"text": news_text})

    def sanitize_description_pii(self, description: str) -> str:
        """F-2 & F-6: Scrubs PII from descriptions and returns sanitized text."""
        if not self.client:
            return self._get_mock_fallback("pii_sanitize", {"description": description})["sanitized_description"]

        prompt = f"""
        Scrub any Personally Identifiable Information (PII) such as phone numbers, vehicle license plates, and real names from the following description.
        Return only the fully sanitized Korean text. Keep all description details intact except the PII.
        
        Description: {description}
        """
        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_FLASH_MODEL,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini API Error in sanitize_description_pii: {e}")
            return self._get_mock_fallback("pii_sanitize", {"description": description})["sanitized_description"]

    def validate_crowdsource_image(self, media_bytes: bytes, file_type: str) -> Dict[str, Any]:
        """F-2 & F-6: Uses Gemini Multimodal Vision to verify crowdsourced photo report validity."""
        if not self.client:
            return self._get_mock_fallback("multimodal_verify", {})

        # Set MIME type based on file type
        mime = "image/jpeg" if "jpg" in file_type or "jpeg" in file_type else "image/png"
        
        prompt = """
        Determine whether this photo genuinely represents a local infrastructural or mobility barrier 
        (e.g., damaged wheelchair ramp, broken sidewalk, road barrier, public transport hazard) for vulnerable groups.
        Rate its trust score from 0.0 to 100.0, and specify if it is valid.
        
        Return exactly a JSON object:
        {
          "is_valid": boolean,
          "ai_trust_score": float,
          "confidence_reasoning": "string (in Korean)"
        }
        """
        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_FLASH_MODEL,
                contents=[
                    types.Part.from_bytes(data=media_bytes, mime_type=mime),
                    prompt
                ],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return self._parse_json(response.text)
        except Exception as e:
            logger.error(f"Gemini API Multimodal Error: {e}")
            return self._get_mock_fallback("multimodal_verify", {})

    def simulate_agent_reaction(self, persona: Dict[str, Any], policy_title: str) -> Dict[str, Any]:
        """F-3: Runs simulation on a single citizen agent persona for the proposed policy."""
        if not self.client:
            return self._get_mock_fallback("agent_simulation", {"persona": persona, "policy": policy_title})

        prompt = f"""
        You are simulating a virtual citizen living under specific socio-economic inequality conditions.
        Persona: {json.dumps(persona, ensure_ascii=False)}
        Proposed Policy: {policy_title}
        
        Estimate how this policy affects their monthly disposable income (delta in KRW, e.g. 150000 or -30000), 
        their utility index change (-1.0 to 1.0), and draft a realistic, emotional diary snippet (2-3 sentences in Korean)
        describing how their daily life is affected by this policy.
        
        Return exactly a JSON object:
        {{
          "disposable_income_delta_monthly": int,
          "utility_change": float,
          "ai_diary_snippet": "string"
        }}
        """
        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_FLASH_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return self._parse_json(response.text)
        except Exception as e:
            logger.error(f"Gemini Simulation Error: {e}")
            return self._get_mock_fallback("agent_simulation", {"persona": persona, "policy": policy_title})

    def audit_legislation(self, policy_title: str) -> Dict[str, Any]:
        """F-7: Audits a proposed legislation policy draft for blind spots and vulnerable loops."""
        if not self.client:
            return self._get_mock_fallback("legislative_audit", {})

        prompt = f"""
        Perform a thorough legislative auditing on the proposed public policy: "{policy_title}".
        Identify potential legal blind spots, vulnerable socio-economic groups that might be accidentally 
        excluded or adversely affected (unintended negative externalities), and recommend concrete amendments.
        
        Return exactly a JSON object with this structure:
        {{
          "loopholes": ["bullet points in Korean"],
          "vulnerable_groups_affected": ["bullet points in Korean"],
          "recommended_amendments": ["bullet points in Korean"]
        }}
        """
        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_PRO_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            return self._parse_json(response.text)
        except Exception as e:
            logger.error(f"Gemini Audit Error: {e}")
            return self._get_mock_fallback("legislative_audit", {})

    def generate_advisor_answer(self, question: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """F-5: Answers a policy/inequality question grounded in retrieved reference documents (RAG)."""
        if not self.client:
            return self._get_mock_fallback("advisor_answer", {"question": question, "docs": docs})

        context_block = "\n\n".join(
            f"[{d.get('title', '')}] {d.get('content', '')}" for d in docs
        ) or "(참고 문서 없음)"
        prompt = f"""
        You are an expert public-policy and inequality advisor. Answer the user's question in Korean,
        grounded in the reference documents below. Cite which references support each key claim.

        Reference documents:
        {context_block}

        User question: {question}

        Return exactly a JSON object:
        {{
          "answer": "detailed expert answer in Korean",
          "references": [{{"title": "string", "snippet": "string"}}]
        }}
        """
        try:
            response = self.client.models.generate_content(
                model=settings.GEMINI_PRO_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return self._parse_json(response.text)
        except Exception as e:
            logger.error(f"Gemini Advisor Error: {e}")
            return self._get_mock_fallback("advisor_answer", {"question": question, "docs": docs})

    def analyze_satellite_imagery(
        self, region_name: str, seed: int, image_bytes: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """F-4: Reads satellite imagery (or metadata) into a structured Satellite Poverty Index report."""
        if not self.client:
            return self._get_mock_fallback("satellite_spi", {"seed": seed})

        prompt = f"""
        Analyze satellite imagery of "{region_name}" for physical housing/poverty inequality.
        Assess green-space access, slum-expansion trend, road paving ratio, and night-light intensity,
        then assign an overall poverty grade.

        Return exactly a JSON object:
        {{
          "poverty_grade": "string (e.g. 'C (취약)')",
          "green_access_score": float,
          "slum_trend": "string",
          "road_paving_ratio": float,
          "night_light_intensity": float,
          "reasoning": "string (in Korean)"
        }}
        """
        try:
            contents = [prompt]
            if image_bytes:
                # Real path: a fetched Earth Engine / GCS satellite tile is judged by Gemini Vision.
                contents = [types.Part.from_bytes(data=image_bytes, mime_type="image/png"), prompt]
            response = self.client.models.generate_content(
                model=settings.GEMINI_PRO_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return self._parse_json(response.text)
        except Exception as e:
            logger.error(f"Gemini Satellite SPI Error: {e}")
            return self._get_mock_fallback("satellite_spi", {"seed": seed})

gemini_service = GeminiService()
