import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.db.models import Base
from src.db.session import create_db_engine, get_session
from src.main import app


@pytest.fixture
def engine(tmp_path):
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine):
    def isolated_session():
        with Session(engine) as session:
            yield session

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_session] = isolated_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
