from typing import Optional
from sqlalchemy.orm import Session
from app.db.models import User
from app.repositories.base_repository import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.Email == email).first()

user_repository = UserRepository()
