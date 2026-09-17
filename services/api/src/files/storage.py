"""Object storage boundary. Tests inject MemoryStorage; production uses S3."""
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import boto3
from botocore.config import Config

from src.core.settings import get_settings


class ObjectStorage(Protocol):
    def put_file(self, key: str, path: Path, content_type: str) -> None: ...
    def download_file(self, key: str, path: Path, *, max_bytes: int) -> None: ...
    def delete(self, key: str) -> None: ...
    def presign_get(self, key: str, expires_in: int) -> str: ...


class MemoryStorage:
    """Deterministic, explicitly injected fake. Never selected in production."""
    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_file(self, key: str, path: Path, content_type: str) -> None:
        self.objects[key] = path.read_bytes()

    def download_file(self, key: str, path: Path, *, max_bytes: int) -> None:
        data = self.objects[key]
        if len(data) > max_bytes:
            raise ValueError('Stored object exceeds size limit')
        path.write_bytes(data)

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def presign_get(self, key: str, expires_in: int) -> str:
        # Development-only deterministic URL; production returns an S3 presigned URL.
        return f"/v1/exports/memory/{key}?expires_in={expires_in}"


class S3Storage:
    def __init__(self, *, bucket: str, client):
        self.bucket = bucket
        self.client = client

    def put_file(self, key: str, path: Path, content_type: str) -> None:
        # Single PUT is bounded at 50 MiB and avoids abandoned multipart uploads.
        with path.open('rb') as body:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type)

    def download_file(self, key: str, path: Path, *, max_bytes: int) -> None:
        body = self.client.get_object(Bucket=self.bucket, Key=key)['Body']
        try:
            with path.open('wb') as output:
                total = 0
                while chunk := body.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError('Stored object exceeds size limit')
                    output.write(chunk)
        finally:
            body.close()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def presign_get(self, key: str, expires_in: int) -> str:
        return self.client.generate_presigned_url(
            'get_object', Params={'Bucket': self.bucket, 'Key': key}, ExpiresIn=expires_in)


@lru_cache
def get_storage() -> ObjectStorage:
    settings = get_settings()
    return S3Storage(bucket=settings.s3_bucket, client=boto3.client(
        's3', endpoint_url=settings.s3_endpoint_url, region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id, aws_secret_access_key=settings.s3_secret_access_key,
        config=Config(signature_version='s3v4', connect_timeout=5, read_timeout=30,
                      retries={'max_attempts': 2}, s3={'addressing_style': 'path'})))
