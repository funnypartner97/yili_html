from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.orm import Session

from src.core.settings import get_settings


def create_db_engine(url: str | URL) -> Engine:
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


@lru_cache
def get_engine() -> Engine:
    return create_db_engine(get_settings().database_url)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


SessionDep = Annotated[Session, Depends(get_session)]
