import copy
import json
from pathlib import Path
from uuid import uuid7

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from src.core.errors import DomainError
from src.db.models import Artifact, ArtifactVersion, GenerationPlan, Job, SourceFile
from src.db.repositories import ArtifactRepository
from src.documents.contracts import DocumentGraphModel, GenerationPlanModel, validate_schema

FIXTURES = json.loads((Path(__file__).resolve().parents[4] /
                      "packages/contracts/tests/fixtures.json").read_text(encoding="utf-8"))


def payload(name, artifact_id):
    data = copy.deepcopy(FIXTURES[name])
    data["artifactId"] = artifact_id
    return data


def test_plan_snapshots_use_canonical_contract_and_new_revisions(session):
    repo = ArtifactRepository(session)
    artifact = repo.create_artifact("Report")
    data = payload("GenerationPlan", artifact.id)
    first = repo.save_plan(GenerationPlanModel.model_validate(data))
    first.status = "confirmed"
    session.commit()
    data["audience"] = "Board"
    second = repo.save_plan(data)
    session.expire_all()
    rows = session.scalars(select(GenerationPlan).order_by(GenerationPlan.revision)).all()
    assert [row.revision for row in rows] == [1, 2]
    assert rows[0].status == "confirmed"
    assert rows[0].payload["audience"] != "Board"
    assert second.payload == data
    assert first.id != second.id
    validate_schema("GenerationPlan", first.payload)
    validate_schema("GenerationPlan", second.payload)
    assert session.get(Artifact, artifact.id).status == "plan_ready"


def test_document_versions_preserve_snapshots_and_artifact_isolation(session):
    repo = ArtifactRepository(session)
    artifact = repo.create_artifact("Report")
    other = repo.create_artifact("Other")
    data = payload("DocumentGraph", artifact.id)
    first = repo.save_document(DocumentGraphModel.model_validate(data), "generation")
    data["title"] = "Edited"
    second = repo.save_document(data, "manual")
    repo.save_document(payload("DocumentGraph", other.id), "generation")
    session.expire_all()
    rows = repo.get_versions(artifact.id)
    assert [row.version_number for row in rows] == [2, 1]
    assert [row.origin for row in rows] == ["manual", "generation"]
    assert rows[1].document["title"] != "Edited"
    assert rows[0].document == data
    assert first.id != second.id
    for row in rows:
        validate_schema("DocumentGraph", row.document)
    assert session.get(Artifact, artifact.id).status == "editable"
    assert session.get(Artifact, artifact.id).latest_version == 2


@pytest.mark.parametrize("name,method", [("GenerationPlan", "save_plan"),
                                        ("DocumentGraph", "save_document")])
def test_invalid_contract_never_persists_or_advances_counters(session, name, method):
    repo = ArtifactRepository(session)
    artifact = repo.create_artifact("Report")
    data = payload(name, artifact.id)
    data["outputModes"] = ["dashboard"]
    with pytest.raises(ValueError):
        getattr(repo, method)(data, *(["generation"] if name == "DocumentGraph" else []))
    assert session.get(Artifact, artifact.id).latest_version == 0
    assert session.get(Artifact, artifact.id).plan_revision == 0
    assert repo.get_versions(artifact.id) == []


def test_invalid_origin_never_persists(session):
    repo = ArtifactRepository(session)
    artifact = repo.create_artifact("Report")
    with pytest.raises(ValueError, match="origin"):
        repo.save_document(payload("DocumentGraph", artifact.id), "untrusted")
    assert repo.get_versions(artifact.id) == []


def test_missing_artifact_rejected_for_all_repository_reads_and_writes(session):
    repo = ArtifactRepository(session)
    missing = str(uuid7())
    operations = [lambda: repo.get_artifact(missing), lambda: repo.get_versions(missing),
                  lambda: repo.save_plan(payload("GenerationPlan", missing)),
                  lambda: repo.save_document(payload("DocumentGraph", missing), "generation")]
    for operation in operations:
        with pytest.raises(DomainError) as error:
            operation()
        assert error.value.code == "artifact_not_found"
    assert repo.create_artifact("Still usable").status == "draft"


def test_artifact_state_is_validated_in_python_and_database(session):
    with pytest.raises(ValueError, match="status"):
        Artifact(title="Bad", status="published")
    artifact = ArtifactRepository(session).create_artifact("Valid")
    with pytest.raises(IntegrityError):
        session.execute(update(Artifact).where(Artifact.id == artifact.id).values(status="published"))
        session.commit()
    session.rollback()
    assert session.get(Artifact, artifact.id).status == "draft"


def test_duplicate_version_and_foreign_keys_enforced(session):
    repo = ArtifactRepository(session)
    artifact = repo.create_artifact("Report")
    graph = payload("DocumentGraph", artifact.id)
    repo.save_document(graph, "generation")
    with pytest.raises(IntegrityError):
        session.execute(insert(ArtifactVersion).values(artifact_id=artifact.id,
                        version_number=1, document=graph, origin="manual"))
        session.commit()
    session.rollback()
    with pytest.raises(IntegrityError):
        session.add(Job(artifact_id=str(uuid7()), kind="generate_document"))
        session.commit()
    session.rollback()
    assert len(repo.get_versions(artifact.id)) == 1


def test_version_failure_rolls_back_counter_and_session_remains_usable(session):
    repo = ArtifactRepository(session)
    artifact = repo.create_artifact("Report")
    graph = payload("DocumentGraph", artifact.id)
    repo.save_document(graph, "generation")
    # Force the database's NOT NULL constraint after version allocation.
    from sqlalchemy import event
    def break_insert(mapper, connection, target):
        target.origin = None
    event.listen(ArtifactVersion, "before_insert", break_insert)
    try:
        with pytest.raises(IntegrityError):
            repo.save_document(graph, "manual")
    finally:
        event.remove(ArtifactVersion, "before_insert", break_insert)
    assert session.get(Artifact, artifact.id).latest_version == 1
    assert repo.save_document(graph, "manual").version_number == 2


def test_source_and_job_json_payloads_round_trip(session):
    artifact = ArtifactRepository(session).create_artifact("Report")
    source = SourceFile(artifact_id=artifact.id, filename="report.pdf",
                        content_type="application/pdf", size_bytes=42, sha256="a" * 64,
                        storage_key="source/report.pdf", parsed_content={"segments": ["hello"]})
    job = Job(artifact_id=artifact.id, kind="generate_document", progress=30,
              stage="generating_structure", payload={"attempt": 1})
    session.add_all([source, job])
    session.commit()
    session.expire_all()
    assert session.get(SourceFile, source.id).parsed_content == {"segments": ["hello"]}
    assert session.get(Job, job.id).payload == {"attempt": 1}
    assert job.progress == 30
