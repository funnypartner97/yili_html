from pathlib import Path
from io import StringIO

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from src.db.models import Base
from src.db.repositories import ArtifactRepository
from src.db.session import create_db_engine


def test_migration_builds_matching_schema_and_supports_repository(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    command.upgrade(config, "head")
    engine = create_db_engine(url)
    try:
        assert set(inspect(engine).get_table_names()) == {
            "alembic_version", "artifacts", "source_files", "generation_plans", "jobs", "artifact_versions"}
        with engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        with Session(engine) as session:
            artifact = ArtifactRepository(session).create_artifact("Migrated database")
            assert artifact.status == "draft"
        command.downgrade(config, "base")
        assert inspect(engine).get_table_names() == ["alembic_version"]
    finally:
        engine.dispose()


def test_production_migration_compiles_postgresql_jsonb_and_constraints(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/html_office")
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    ddl = output.getvalue()
    assert "payload JSONB NOT NULL" in ddl
    assert "document JSONB NOT NULL" in ddl
    assert "TIMESTAMP WITH TIME ZONE NOT NULL" in ddl
    assert "UNIQUE (artifact_id, version_number)" in ddl
    assert "CREATE INDEX ix_artifacts_status" in ddl
    assert "CREATE INDEX ix_source_files_parse_status" in ddl
    assert "CREATE INDEX ix_jobs_status" in ddl
