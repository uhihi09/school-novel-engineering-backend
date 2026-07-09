from typing import List
from sqlalchemy.orm import Session
from app.db.models import InequalityReport
from app.repositories.base_repository import BaseRepository

class ReportRepository(BaseRepository[InequalityReport]):
    def __init__(self):
        super().__init__(InequalityReport)

    def get_by_bounds(
        self, db: Session, *, ne_lat: float, ne_lng: float, sw_lat: float, sw_lng: float
    ) -> List[InequalityReport]:
        # Using parameterized query internally via SQLAlchemy's filter
        return (
            db.query(InequalityReport)
            .filter(InequalityReport.Latitude >= sw_lat)
            .filter(InequalityReport.Latitude <= ne_lat)
            .filter(InequalityReport.Longitude >= sw_lng)
            .filter(InequalityReport.Longitude <= ne_lng)
            .all()
        )

report_repository = ReportRepository()
