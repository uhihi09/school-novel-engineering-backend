from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from app.db.session import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: str) -> Optional[ModelType]:
        # Resolve the primary key via the mapper (order-independent) rather than assuming
        # the first declared column is the PK. Parameterized internally by SQLAlchemy.
        pk_col = inspect(self.model).primary_key[0]
        return db.query(self.model).filter(pk_col == id).first()

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: ModelType) -> ModelType:
        db.add(obj_in)
        db.commit()
        db.refresh(obj_in)
        return obj_in

    def remove(self, db: Session, *, id: str) -> Optional[ModelType]:
        obj = self.get(db, id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj
