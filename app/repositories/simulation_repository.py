from typing import List
from sqlalchemy.orm import Session
from app.db.models import SimulationLog
from app.repositories.base_repository import BaseRepository

class SimulationRepository(BaseRepository[SimulationLog]):
    def __init__(self):
        super().__init__(SimulationLog)

    def get_by_user(self, db: Session, user_id: str) -> List[SimulationLog]:
        return db.query(SimulationLog).filter(SimulationLog.UserId == user_id).all()

simulation_repository = SimulationRepository()
