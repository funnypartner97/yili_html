import hashlib
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import UploadFile
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from src.core.errors import DomainError
from src.db.models import SourceFile
from src.files.service import FileService
from src.files.storage import MemoryStorage, get_storage
from src.main import app


@pytest.fixture
def storage(client):
    storage = MemoryStorage()
    app.dependency_overrides[get_storage] = lambda: storage
    yield storage


@pytest.fixture
def artifact_id(client):
    return client.post('/v1/artifacts', json={'title': 'Files'}).json()['id']


def upload(client, artifact_id, filename='sales.csv', data=b'Month,Revenue\nJan,120\n'):
    return client.post(f'/v1/artifacts/{artifact_id}/files', files={'file': (filename, data, 'application/octet-stream')})


def test_upload_signature_rejected_without_persisting(client, artifact_id, storage, session):
    response = upload(client, artifact_id, 'report.pdf', b'not-a-pdf')
    assert response.status_code == 422
    assert response.json()['code'] == 'unsupported_file_signature'
    assert session.scalar(select(func.count()).select_from(SourceFile)) == 0
    assert storage.objects == {}


def test_upload_queues_safe_file_and_lists_status(client, artifact_id, storage, session):
    response = upload(client, artifact_id, '../../folder\\sales.csv')
    assert response.status_code == 202
    source_id = response.json()['sourceId']
    assert response.json()['parseStatus'] == 'queued'
    row = session.get(SourceFile, source_id)
    assert row.filename == 'sales.csv'
    assert row.content_type == 'text/csv'
    assert row.sha256 == hashlib.sha256(b'Month,Revenue\nJan,120\n').hexdigest()
    assert row.storage_key == f'artifacts/{artifact_id}/sources/{source_id}/sales.csv'
    assert storage.objects[row.storage_key] == b'Month,Revenue\nJan,120\n'
    listing = client.get(f'/v1/artifacts/{artifact_id}/files')
    assert listing.status_code == 200
    assert listing.json()[0]['sourceId'] == source_id
    assert listing.json()[0]['filename'] == 'sales.csv'
    assert listing.json()[0]['parseStatus'] == 'queued'
    assert 'storageKey' not in listing.json()[0]
    assert client.get(f'/v1/artifacts/{artifact_id}').json()['sourceCount'] == 1


def test_file_limit_is_scoped_to_artifact(client, artifact_id, storage):
    for _ in range(10):
        assert upload(client, artifact_id).status_code == 202
    response = upload(client, artifact_id)
    assert response.status_code == 422
    assert response.json()['code'] == 'source_count_limit'
    assert len(storage.objects) == 10
    other = client.post('/v1/artifacts', json={'title': 'Other'}).json()['id']
    assert upload(client, other).status_code == 202
    assert len(client.get(f'/v1/artifacts/{other}/files').json()) == 1


def test_concurrent_uploads_cannot_exceed_ten(client, artifact_id, storage, engine, tmp_path):
    for _ in range(9):
        assert upload(client, artifact_id).status_code == 202
    def attempt(_):
        with Session(engine) as session:
            try:
                FileService(session, storage, temp_root=tmp_path).upload(
                    artifact_id, UploadFile(io.BytesIO(b'a,b\n1,2\n'), filename='a.csv'))
                return 'queued'
            except DomainError as error:
                return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))
    assert sorted(outcomes) == ['queued', 'source_count_limit']
    assert len(storage.objects) == 10


def test_byte_limit_uses_stream_not_content_length(client, artifact_id, storage, session, tmp_path):
    class LargeStream(io.BytesIO):
        def __init__(self):
            super().__init__()
            self.remaining = 50 * 1024 * 1024 + 1
        def read(self, size=-1):
            count = min(size, self.remaining)
            self.remaining -= count
            return b'a' * count
    with pytest.raises(DomainError) as error:
        FileService(session, storage, temp_root=tmp_path).upload(
            artifact_id, UploadFile(LargeStream(), filename='a.csv', size=1))
    assert error.value.code == 'file_too_large'
    assert list(tmp_path.iterdir()) == [tmp_path / 'test.db']
    assert not storage.objects


def test_storage_failure_rolls_back_row_and_cleans_temp(client, artifact_id, session, tmp_path):
    class FailingStorage(MemoryStorage):
        def put_file(self, key, path, content_type):
            super().put_file(key, path, content_type)
            raise OSError('secret storage credentials')
    storage = FailingStorage()
    with pytest.raises(DomainError) as error:
        FileService(session, storage, temp_root=tmp_path).upload(
            artifact_id, UploadFile(io.BytesIO(b'a,b\n1,2\n'), filename='a.csv'))
    assert error.value.code == 'source_storage_unavailable'
    assert 'secret' not in error.value.message
    assert session.scalar(select(func.count()).select_from(SourceFile)) == 0
    assert not storage.objects
    assert list(tmp_path.iterdir()) == [tmp_path / 'test.db']


def test_database_commit_failure_compensates_stored_object(client, artifact_id, session, storage, tmp_path):
    def fail_commit(connection):
        raise RuntimeError('database secret')
    event.listen(session.bind, 'commit', fail_commit)
    try:
        with pytest.raises(DomainError) as error:
            FileService(session, storage, temp_root=tmp_path).upload(
                artifact_id, UploadFile(io.BytesIO(b'a,b\n1,2\n'), filename='a.csv'))
        assert error.value.code == 'source_persistence_failed'
    finally:
        event.remove(session.bind, 'commit', fail_commit)
    assert not storage.objects
    assert session.scalar(select(func.count()).select_from(SourceFile)) == 0
    assert list(tmp_path.iterdir()) == [tmp_path / 'test.db']


def test_temp_cleanup_failure_does_not_commit_a_dangling_source(client, artifact_id, session, storage, tmp_path, monkeypatch):
    import tempfile
    import src.files.service as module
    class FailedCleanup(tempfile.TemporaryDirectory):
        def cleanup(self):
            super().cleanup()
            raise OSError('temporary directory cleanup failed')
    monkeypatch.setattr(module, 'TemporaryDirectory', FailedCleanup)
    with pytest.raises(DomainError):
        FileService(session, storage, temp_root=tmp_path).upload(
            artifact_id, UploadFile(io.BytesIO(b'a,b\n1,2\n'), filename='a.csv'))
    assert session.scalar(select(func.count()).select_from(SourceFile)) == 0
    assert not storage.objects


def test_parse_hooks_persist_canonical_content_and_safe_failure(client, artifact_id, session, storage, tmp_path):
    source_id = upload(client, artifact_id).json()['sourceId']
    service = FileService(session, storage, temp_root=tmp_path)
    service.parse_source(artifact_id, source_id)
    row = session.get(SourceFile, source_id)
    assert row.parse_status == 'parsed'
    assert row.parsed_content['kind'] == 'csv'
    assert row.parsed_content['tables'][0]['rows'][1] == ['Jan', '120']
    assert row.parsed_content['title'] == 'sales'
    assert 'startRow' in row.parsed_content['tables'][0]
    broken_id = upload(client, artifact_id, 'broken.pdf', b'%PDF-1.7\ninvalid').json()['sourceId']
    service.parse_source(artifact_id, broken_id)
    failed = client.get(f'/v1/artifacts/{artifact_id}/files').json()[1]
    assert failed['parseStatus'] == 'failed'
    assert failed['error']['code'] == 'source_parse_failed'
    assert 'MuPDF' not in failed['error']['message']
    assert list(tmp_path.iterdir()) == [tmp_path / 'test.db']


def test_parse_checks_stored_hash(client, artifact_id, session, storage, tmp_path):
    source_id = upload(client, artifact_id).json()['sourceId']
    row = session.get(SourceFile, source_id)
    storage.objects[row.storage_key] = b'a,b\n3,4\n'
    FileService(session, storage, temp_root=tmp_path).parse_source(artifact_id, source_id)
    assert row.parse_status == 'failed'
    assert row.error['code'] == 'source_integrity_failed'
    assert row.parsed_content is None


def test_files_reject_missing_artifact_and_wrong_source_scope(client, artifact_id, session, storage):
    missing = '0199390e-8b00-7000-8000-000000000099'
    assert upload(client, missing).status_code == 404
    assert client.get(f'/v1/artifacts/{missing}/files').status_code == 404
    source_id = upload(client, artifact_id).json()['sourceId']
    with pytest.raises(DomainError) as error:
        FileService(session, storage).mark_failed(missing, source_id, 'source_parse_failed')
    assert error.value.status_code == 404
    assert session.get(SourceFile, source_id).parse_status == 'queued'


def test_multipart_ingress_is_bounded_even_for_unexpected_file_fields(client, artifact_id, storage):
    def body():
        yield b'--boundary\r\nContent-Disposition: form-data; name="unexpected"; filename="large.pdf"\r\n\r\n'
        for _ in range(52):
            yield b'x' * (1024 * 1024)
        yield b'\r\n--boundary--\r\n'
    response = client.post(f'/v1/artifacts/{artifact_id}/files', content=body(), headers={
        'Content-Type': 'multipart/form-data; boundary=boundary', 'Content-Length': '1'})
    assert response.status_code == 413
    assert response.json()['code'] == 'file_too_large'
    assert not storage.objects


def test_hook_rejects_mutated_payload_without_changing_status(client, artifact_id, session, storage):
    from src.files.types import ParsedSource
    source_id = upload(client, artifact_id).json()['sourceId']
    parsed = ParsedSource(kind='csv', title='valid')
    parsed.title = 'invalid\x00text'
    with pytest.raises(DomainError):
        FileService(session, storage).mark_parsed(artifact_id, source_id, parsed)
    assert session.get(SourceFile, source_id).parse_status == 'queued'


def test_parse_failure_can_retry_but_cannot_overwrite_success(client, artifact_id, session, storage):
    source_id = upload(client, artifact_id).json()['sourceId']
    service = FileService(session, storage)
    attempt_id = service.claim_parse(artifact_id, source_id)
    service.mark_failed(artifact_id, source_id, attempt_id=attempt_id)
    service.parse_source(artifact_id, source_id)
    assert session.get(SourceFile, source_id).parse_status == 'parsed'
    with pytest.raises(DomainError) as error:
        service.mark_failed(artifact_id, source_id)
    assert error.value.code == 'source_state_conflict'
    assert session.get(SourceFile, source_id).parse_status == 'parsed'


def test_parse_final_commit_failure_releases_attempt_and_allows_retry(client, artifact_id, session, storage):
    source_id = upload(client, artifact_id).json()['sourceId']
    service = FileService(session, storage)
    commits = 0
    def fail_final_commit_once(connection):
        nonlocal commits
        commits += 1
        if commits == 2:
            raise RuntimeError('one-time final persistence failure')
    event.listen(session.bind, 'commit', fail_final_commit_once)
    try:
        with pytest.raises(RuntimeError):
            service.parse_source(artifact_id, source_id)
        assert session.get(SourceFile, source_id).parse_status == 'queued'
        service.parse_source(artifact_id, source_id)
    finally:
        event.remove(session.bind, 'commit', fail_final_commit_once)
    row = session.get(SourceFile, source_id)
    assert row.parse_status == 'parsed'
    assert row.parsed_content['tables'][0]['rows'][1] == ['Jan', '120']
    assert row.parse_attempt_id is None


def test_active_parse_claim_cannot_be_stolen_or_completed_without_ownership(client, artifact_id, session, storage):
    source_id = upload(client, artifact_id).json()['sourceId']
    service = FileService(session, storage)
    owner = service.claim_parse(artifact_id, source_id)
    with pytest.raises(DomainError) as error:
        service.claim_parse(artifact_id, source_id)
    assert error.value.code == 'source_state_conflict'
    with pytest.raises(DomainError):
        service.mark_failed(artifact_id, source_id)
    with pytest.raises(DomainError):
        service.mark_failed(artifact_id, source_id, attempt_id='another-owner')
    row = session.get(SourceFile, source_id)
    assert row.parse_attempt_id == owner
    assert row.parse_status == 'parsing'


def test_completion_requires_an_attempt_even_when_source_is_queued(client, artifact_id, session, storage):
    from src.files.types import ParsedSource
    source_id = upload(client, artifact_id).json()['sourceId']
    service = FileService(session, storage)
    with pytest.raises(DomainError):
        service.mark_parsed(artifact_id, source_id, ParsedSource(kind='csv', title='Unowned'))
    with pytest.raises(DomainError):
        service.mark_failed(artifact_id, source_id)
    assert session.get(SourceFile, source_id).parse_status == 'queued'


def test_expired_attempt_can_recover_but_stale_owner_cannot_complete(client, artifact_id, session, storage):
    from datetime import timedelta
    from src.db.models import utc_now
    from src.files.types import ParsedSource
    source_id = upload(client, artifact_id).json()['sourceId']
    now = utc_now()
    service = FileService(session, storage, clock=lambda: now)
    old_owner = service.claim_parse(artifact_id, source_id)
    now += timedelta(minutes=6)
    with pytest.raises(DomainError):
        service.mark_failed(artifact_id, source_id, attempt_id=old_owner)
    new_owner = service.claim_parse(artifact_id, source_id)
    assert old_owner != new_owner
    for finish in (
        lambda: service.mark_failed(artifact_id, source_id, attempt_id=old_owner),
        lambda: service.mark_parsed(artifact_id, source_id, ParsedSource(kind='csv', title='Stale'), attempt_id=old_owner),
    ):
        with pytest.raises(DomainError):
            finish()
    assert session.get(SourceFile, source_id).parse_attempt_id == new_owner
    service.mark_parsed(artifact_id, source_id, ParsedSource(kind='csv', title='Current'), attempt_id=new_owner)
    assert session.get(SourceFile, source_id).parsed_content['title'] == 'Current'


def test_parse_lease_renewal_preserves_owner_and_blocks_expiry_takeover(client, artifact_id, session, storage):
    from datetime import timedelta
    from src.db.models import utc_now
    source_id = upload(client, artifact_id).json()['sourceId']
    now = utc_now()
    service = FileService(session, storage, clock=lambda: now)
    owner = service.claim_parse(artifact_id, source_id)
    now += timedelta(minutes=4)
    service.renew_parse(artifact_id, source_id, owner)
    now += timedelta(minutes=2)
    with pytest.raises(DomainError):
        service.claim_parse(artifact_id, source_id)
    assert session.get(SourceFile, source_id).parse_attempt_id == owner
    service.mark_failed(artifact_id, source_id, attempt_id=owner)
    assert session.get(SourceFile, source_id).parse_status == 'failed'


def test_concurrent_parse_claimants_have_exactly_one_owner(client, artifact_id, engine, storage):
    source_id = upload(client, artifact_id).json()['sourceId']
    def claim(_):
        with Session(engine) as session:
            try:
                return FileService(session, storage).claim_parse(artifact_id, source_id)
            except DomainError as error:
                return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, range(2)))
    assert results.count('source_state_conflict') == 1
    with Session(engine) as session:
        assert session.get(SourceFile, source_id).parse_attempt_id in results


def test_failed_result_and_release_commits_recover_after_lease_expiry(client, artifact_id, session, storage):
    from datetime import timedelta
    from src.db.models import utc_now
    source_id = upload(client, artifact_id).json()['sourceId']
    now = utc_now()
    service = FileService(session, storage, clock=lambda: now)
    commits = 0
    def fail_result_and_release(connection):
        nonlocal commits
        commits += 1
        if commits in (2, 3):
            raise RuntimeError('database unavailable')
    event.listen(session.bind, 'commit', fail_result_and_release)
    try:
        with pytest.raises(RuntimeError):
            service.parse_source(artifact_id, source_id)
        assert session.get(SourceFile, source_id).parse_status == 'parsing'
        now += timedelta(minutes=6)
        service.parse_source(artifact_id, source_id)
    finally:
        event.remove(session.bind, 'commit', fail_result_and_release)
    assert session.get(SourceFile, source_id).parse_status == 'parsed'


def test_stale_parse_completion_and_release_cannot_change_new_owner(client, artifact_id, session, engine, storage):
    from datetime import timedelta
    from src.db.models import utc_now
    source_id = upload(client, artifact_id).json()['sourceId']
    now = utc_now()
    new_owner = None
    class ReclaimedStorage(MemoryStorage):
        def download_file(self, key, path, *, max_bytes):
            nonlocal now, new_owner
            super().download_file(key, path, max_bytes=max_bytes)
            now += timedelta(minutes=6)
            with Session(engine) as newer_session:
                new_owner = FileService(newer_session, self, clock=lambda: now).claim_parse(artifact_id, source_id)
    reclaimed = ReclaimedStorage()
    reclaimed.objects = storage.objects.copy()
    service = FileService(session, reclaimed, clock=lambda: now)
    with pytest.raises(DomainError) as error:
        service.parse_source(artifact_id, source_id)
    assert error.value.code == 'source_state_conflict'
    row = session.get(SourceFile, source_id)
    assert row.parse_status == 'parsing'
    assert row.parse_attempt_id == new_owner
    assert row.parsed_content is None
