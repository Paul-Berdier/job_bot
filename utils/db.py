"""
utils/db.py – Gestion de la base de données SQLite
Garde un historique de toutes les candidatures pour éviter les doublons.
"""

import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, DateTime, Text, Boolean, Integer
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "applications.db")


class Application(Base):
    __tablename__ = "applications"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    job_id       = Column(String(255), unique=True, nullable=False)   # identifiant unique de l'offre
    platform     = Column(String(50),  nullable=False)                # indeed / wttj / hellowork
    job_title    = Column(String(500), nullable=True)
    company      = Column(String(500), nullable=True)
    job_url      = Column(String(1000), nullable=True)
    cover_letter = Column(Text,        nullable=True)
    applied_at   = Column(DateTime,    default=datetime.utcnow)
    status       = Column(String(50),  default="applied")             # applied / error / skipped
    error_msg    = Column(Text,        nullable=True)


class Database:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def already_applied(self, job_id: str) -> bool:
        return self.session.query(Application).filter_by(job_id=job_id).first() is not None

    def save_application(
        self,
        job_id: str,
        platform: str,
        job_title: str = "",
        company: str = "",
        job_url: str = "",
        cover_letter: str = "",
        status: str = "applied",
        error_msg: str = "",
    ) -> Application:
        app = Application(
            job_id=job_id,
            platform=platform,
            job_title=job_title,
            company=company,
            job_url=job_url,
            cover_letter=cover_letter,
            status=status,
            error_msg=error_msg,
            applied_at=datetime.utcnow(),
        )
        self.session.merge(app)
        self.session.commit()
        return app

    def get_stats(self) -> dict:
        total   = self.session.query(Application).count()
        applied = self.session.query(Application).filter_by(status="applied").count()
        errors  = self.session.query(Application).filter_by(status="error").count()
        return {"total": total, "applied": applied, "errors": errors}

    def get_recent(self, limit: int = 10) -> list:
        return (
            self.session.query(Application)
            .order_by(Application.applied_at.desc())
            .limit(limit)
            .all()
        )

    def close(self):
        self.session.close()
