from typing import List

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from app.services.rag_service import rag_service

router = APIRouter()


class AdvisorReference(BaseModel):
    title: str
    snippet: str = ""


class ChatRequest(BaseModel):
    question: str = Field(..., description="User's inequality/policy question in natural language")


class ChatResponse(BaseModel):
    question: str
    answer: str
    references: List[AdvisorReference] = []
    references_consulted: List[str] = []


@router.post("/chat", response_model=ChatResponse)
def advisor_chat(req: ChatRequest = Body(...)):
    """F-5: Natural-language AI inequality/policy advisor grounded in local RAG references."""
    result = rag_service.answer_policy_question(req.question)
    # Coerce the (possibly LLM-generated) result into the strict response shape so a
    # schema-deviant Gemini reply (missing fields, bare strings, explicit nulls) can't 500.
    raw_refs = result.get("references") or []
    references = [
        AdvisorReference(title=r.get("title", ""), snippet=r.get("snippet", ""))
        if isinstance(r, dict)
        else AdvisorReference(title=str(r))
        for r in raw_refs
    ]
    return ChatResponse(
        question=req.question,
        answer=result.get("answer") or "",
        references=references,
        references_consulted=result.get("references_consulted") or [],
    )
