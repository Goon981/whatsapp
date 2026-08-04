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
    _auto_migrate()


def _auto_migrate() -> None:
    """Ajoute les colonnes manquantes aux tables existantes (SQLite uniquement).

    Dépannage léger pour le développement : évite de réinitialiser la base après
    l'ajout d'un champ. En production (PostgreSQL/MySQL), utiliser Alembic.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    # Colonnes ajoutées après la première version (nom -> définition SQLite).
    additions = {
        "subscriptions": {
            "amount": "INTEGER DEFAULT 0",
            "grace_days": "INTEGER DEFAULT 3",
            "auto_suspend": "BOOLEAN DEFAULT 1",
            "last_payment_at": "DATETIME",
            "suspended_for_nonpayment": "BOOLEAN DEFAULT 0",
        },
    }
    with engine.begin() as conn:
        for table, cols in additions.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in cols.items():
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
