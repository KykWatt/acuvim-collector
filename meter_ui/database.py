from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from meter_ui.models import Base

DB_PATH = Path(__file__).resolve().parent.parent / "meters.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    """Create tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
