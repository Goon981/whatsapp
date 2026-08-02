"""Configuration SQLAlchemy : moteur, session et base déclarative."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

# ``check_same_thread`` n'est requis que pour SQLite (mono-fichier de dev).
_connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Base déclarative commune à tous les modèles."""


def get_db() -> Generator[Session, None, None]:
    """Dépendance FastAPI : fournit une session et la referme systématiquement."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crée les tables manquantes (les migrations réelles utiliseraient Alembic)."""
    from . import models  # noqa: F401  (import pour enregistrer les modèles)

    Base.metadata.create_all(bind=engine)
