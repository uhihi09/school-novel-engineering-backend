from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from app.api.deps import get_db, get_current_user_id
from app.services.simulator_service import simulator_service
from app.services.tts_service import tts_service
from app.services.rag_service import rag_service

router = APIRouter()

class PolicyVariable(BaseModel):
    category: str = Field(..., description="Policy parameter category (subsidy/minimum_wage/tax)")
    param_value: float = Field(..., description="Parameter parameter numeric value")

class SimulationRequest(BaseModel):
    title: str = Field(..., description="Proposed policy title")
    description: str = Field(..., description="Proposed policy descriptions")
    policies: List[PolicyVariable] = Field(..., description="Policy list modifiers")

class SimulationResponse(BaseModel):
    simulation_id: str
    gini_before: float
    gini_after: float
    disparity_delta_percent: float
    winners: List[str]
    losers: List[str]
    agent_samples: List[Dict[str, Any]]

class AuditResponse(BaseModel):
    loopholes: List[str]
    vulnerable_groups_affected: List[str]
    recommended_amendments: List[str]
    references_consulted: List[str]

@router.post("/run", response_model=SimulationResponse)
def run_simulation(
    req: SimulationRequest = Body(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """F-3: Runs multi-agent policy simulation across 1,000 diverse citizen personas in parallel."""
    # Run the core simulator logic
    result = simulator_service.run_simulation(
        db, 
        user_id=user_id, 
        title=req.title, 
        description=req.description, 
        policies=[p.model_dump() for p in req.policies]
    )
    return result

@router.post("/sonify")
def sonify_diary(
    diary_text: str = Body(..., embed=True, description="The AI diary text to sonify into raw base64 wave audio")
):
    """F-6: Sonification core. Turns a representative persona's qualitative diary snippet into speech audio stream."""
    audio_uri = tts_service.synthesize_speech(diary_text)
    return {
        "sonified_audio_url": audio_uri,
        "text": diary_text
    }

@router.get("/audit", response_model=AuditResponse)
def audit_policy(
    policy_title: str = Query(..., description="Title of the legislation policy draft to audit")
):
    """F-5 & F-7: Legislative audit engine. Uses local RAG policy indexes and Gemini Pro to detect vulnerable loop holes."""
    result = rag_service.audit_policy_blindspots(policy_title)
    return result
