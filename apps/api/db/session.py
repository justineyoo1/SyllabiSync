from __future__ import annotations

from typing import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from packages.common.config import get_settings


settings = get_settings()
engine = create_engine(settings.database_url.unicode_string(), pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Iterator:
    """Context manager for DB sessions for non-dependency usage.

    Example:
        with db_session() as db:
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


