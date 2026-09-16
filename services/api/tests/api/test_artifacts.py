from datetime import datetime, timedelta
from uuid import UUID, uuid7

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import DataError

from src.db import repositories
from src.db.models import Artifact, SourceFile


def test_create_artifact(client, session) -> None:
    response = client.post("/v1/artifacts", json={"title": "季度经营分析"})
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "季度经营分析"
    assert body["status"] == "draft"
    assert body["sourceCount"] == 0
    assert UUID(body["id"]).version == 7
    assert datetime.fromisoformat(body["createdAt"]).utcoffset() == timedelta(0)
    assert datetime.fromisoformat(body["updatedAt"]).utcoffset() == timedelta(0)
    assert session.get(Artifact, body["id"]).title == "季度经营分析"
    assert client.get(f'/v1/artifacts/{body["id"]}').json() == body


def test_get_counts_only_the_artifacts_sources(client, session):
    first = client.post("/v1/artifacts", json={"title": "First"}).json()
    second = client.post("/v1/artifacts", json={"title": "Second"}).json()
    for artifact_id in (first["id"], first["id"], second["id"]):
        session.add(SourceFile(artifact_id=artifact_id, filename="report.pdf",
                               content_type="application/pdf", size_bytes=42,
                               sha256="a" * 64, storage_key=str(uuid7())))
    session.commit()
    assert client.get(f'/v1/artifacts/{first["id"]}').json()["sourceCount"] == 2
    assert client.get(f'/v1/artifacts/{second["id"]}').json()["sourceCount"] == 1


def test_not_found_has_stable_envelope(client):
    missing = str(uuid7())
    response = client.get(f"/v1/artifacts/{missing}")
    assert response.status_code == 404
    assert response.json()["code"] == "artifact_not_found"
    assert response.json()["details"] == {"artifactId": missing}
    assert isinstance(response.json()["message"], str)


@pytest.mark.parametrize("payload", [{}, {"title": ""}, {"title": "   "},
                                     {"title": "x" * 301}, {"title": 123},
                                     {"title": "ok", "status": "editable"}])
def test_invalid_create_has_stable_envelope(client, payload):
    response = client.post("/v1/artifacts", json=payload)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert set(response.json()) == {"code", "message", "details"}


def test_integrity_error_is_safe_and_next_request_can_write(client, session, monkeypatch):
    first = client.post("/v1/artifacts", json={"title": "Existing"}).json()
    with monkeypatch.context() as patch:
        patch.setattr(repositories, "new_id", lambda: first["id"])
        response = client.post("/v1/artifacts", json={"title": "Duplicate"})
    assert response.status_code == 409
    assert response.json()["code"] == "integrity_conflict"
    assert response.json()["details"] == {}
    assert "INSERT" not in response.text and "sqlite" not in response.text
    assert client.post("/v1/artifacts", json={"title": "Next"}).status_code == 201
    assert session.scalar(select(func.count()).select_from(Artifact)) == 2


def test_nul_title_is_rejected_before_persistence(client, session):
    response = client.post("/v1/artifacts", json={"title": "Secret\u0000title"})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert set(response.json()) == {"code", "message", "details"}
    assert response.json()["details"] == {}
    assert "Secret" not in response.text
    assert session.scalar(select(func.count()).select_from(Artifact)) == 0
    assert client.post("/v1/artifacts", json={"title": "Valid"}).status_code == 201


def test_data_error_has_sanitized_envelope_and_request_recovers(client, engine):
    def fail_write(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO artifacts"):
            raise DataError("PRIVATE SQL", {"value": "PRIVATE PARAMETER"},
                            RuntimeError("PRIVATE DRIVER DETAIL"))

    event.listen(engine, "before_cursor_execute", fail_write)
    try:
        response = client.post("/v1/artifacts", json={"title": "Valid"})
    finally:
        event.remove(engine, "before_cursor_execute", fail_write)
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert isinstance(response.json()["message"], str)
    assert response.json()["details"] == {}
    assert set(response.json()) == {"code", "message", "details"}
    assert "PRIVATE" not in response.text
    assert client.post("/v1/artifacts", json={"title": "Next"}).status_code == 201
