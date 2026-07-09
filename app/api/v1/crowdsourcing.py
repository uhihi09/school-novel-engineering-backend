import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, Form, UploadFile, File, Query, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import Optional
from app.api.deps import get_db, get_current_user_id
from app.core.config import settings
from app.db.models import InequalityReport
from app.repositories.report_repository import report_repository
from app.services.gemini_service import gemini_service

router = APIRouter()


def _serialize_report(report: InequalityReport) -> dict:
    """Public JSON shape for a citizen inequality report (map pins / app feed)."""
    return {
        "report_id": report.ReportId,
        "user_id": report.UserId,
        "category": report.Category,
        "raw_title": report.RawTitle,
        "sanitized_description": report.SanitizedDescription,
        "latitude": report.Latitude,
        "longitude": report.Longitude,
        "is_valid": report.IsValid,
        "ai_trust_score": report.AiTrustScore,
        "media_url": report.MediaUrl,
        "created_at": report.CreatedAt.isoformat() if report.CreatedAt else None,
    }

@router.post("/report", status_code=status.HTTP_201_CREATED)
async def create_crowdsource_report(
    request: Request,
    category: str = Form(..., description="Inequality category (transport/housing/labor/healthcare)"),
    raw_title: str = Form(..., description="User-input report title"),
    description: str = Form(..., description="User-input description of the barrier/inequality"),
    latitude: float = Form(..., description="GPS Latitude"),
    longitude: float = Form(..., description="GPS Longitude"),
    media: Optional[UploadFile] = File(None, description="Optional supporting photo evidence"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """F-2 & F-6: Accepts multimodal citizen reports, scrubs PII, and runs Gemini Multimodal verification."""
    report_id = f"rep_{uuid.uuid4().hex[:8]}"
    
    # 1. Privacy Guardrail: Scrub PII from title and description
    sanitized_title = gemini_service.sanitize_description_pii(raw_title)
    sanitized_desc = gemini_service.sanitize_description_pii(description)
    
    # 2. Image Guardrail: Validate image via Gemini Multimodal Vision if uploaded
    is_valid = True
    ai_trust_score = 100.0
    media_url = None
    
    if media:
        media_bytes = await media.read()
        # Guard against a missing/empty upload filename (Starlette allows filename=None)
        filename = media.filename or ""
        file_ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"

        # Call Gemini multimodal verification
        img_check = gemini_service.validate_crowdsource_image(media_bytes, file_ext)
        is_valid = img_check.get("is_valid", True)
        ai_trust_score = img_check.get("ai_trust_score", 90.0)

        # Persist the file to the media directory and expose a real, servable URL (/media/...).
        media_dir = Path(settings.MEDIA_DIR)
        media_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{report_id}.{file_ext}"
        (media_dir / stored_name).write_bytes(media_bytes)
        media_url = f"{str(request.base_url).rstrip('/')}/media/{stored_name}"
    
    # 3. Create ORM record and commit to Database
    report = InequalityReport(
        ReportId=report_id,
        UserId=user_id,
        Category=category,
        RawTitle=sanitized_title,
        SanitizedDescription=sanitized_desc,
        Latitude=latitude,
        Longitude=longitude,
        IsValid=is_valid,
        AiTrustScore=ai_trust_score,
        MediaUrl=media_url
    )
    
    db.add(report)
    db.commit()
    db.refresh(report)

    return _serialize_report(report)


@router.get("/reports")
def list_reports(
    ne_lat: float = Query(..., description="North-East Latitude"),
    ne_lng: float = Query(..., description="North-East Longitude"),
    sw_lat: float = Query(..., description="South-West Latitude"),
    sw_lng: float = Query(..., description="South-West Longitude"),
    category: Optional[str] = Query(None, description="Optional category filter"),
    valid_only: bool = Query(False, description="Return only AI-validated reports"),
    db: Session = Depends(get_db),
):
    """F-2 feed: lists citizen reports within a bounding box for map pins / the mobile feed."""
    reports = report_repository.get_by_bounds(
        db, ne_lat=ne_lat, ne_lng=ne_lng, sw_lat=sw_lat, sw_lng=sw_lng
    )
    if category:
        reports = [r for r in reports if r.Category == category]
    if valid_only:
        reports = [r for r in reports if r.IsValid]
    return {"count": len(reports), "reports": [_serialize_report(r) for r in reports]}


@router.get("/reports/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    """Fetches a single citizen report by id."""
    report = report_repository.get(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return _serialize_report(report)
