from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from database.models import Base
from config.settings import settings

class DatabaseRepository:
    def __init__(self):
        self.engine = create_engine(settings.DATABASE_URL)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def get_session(self) -> Session:
        return self.SessionLocal()
    
    def save(self, obj):
        with self.get_session() as session:
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return obj

repository = DatabaseRepository()
