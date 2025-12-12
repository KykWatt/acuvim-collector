"""Database bootstrap with a guard against incompatible SQLAlchemy versions."""

from importlib import metadata
from pathlib import Path

from packaging.version import Version
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from meter_ui.models import Base

DB_PATH = Path(__file__).resolve().parent.parent / "meters.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"


def _require_sqlalchemy_version(min_version: str = "2.0.36") -> None:
    """
    Prevents startup with an older SQLAlchemy that triggers the Python 3.13
    TypingOnly assertion. If the installed version is too old, raise a clear
    error telling the user to reinstall the pinned requirements.
    """

    installed = Version(metadata.version("sqlalchemy"))
    required = Version(min_version)

    if installed < required:
        raise RuntimeError(
            "SQLAlchemy %s is too old for Python 3.13. "
            "Please run 'pip install --upgrade --force-reinstall -r requirements.txt' "
            "to install version %s or newer."
            % (installed, required)
        )


# Abort early with a clear message before importing the rest of SQLAlchemy
_require_sqlalchemy_version()

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    """Create tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
