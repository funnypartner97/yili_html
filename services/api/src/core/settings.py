import os
from dataclasses import dataclass, field
from functools import lru_cache

from sqlalchemy import URL


def database_url() -> str | URL:
    return os.environ.get("DATABASE_URL") or URL.create(
        "postgresql+psycopg",
        username=os.environ.get("POSTGRES_USER", "html_office"),
        password=os.environ.get("POSTGRES_PASSWORD", "html_office_dev_password"),
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DB", "html_office"),
    )


@dataclass(frozen=True)
class Settings:
    database_url: str | URL = field(default_factory=database_url)
    s3_endpoint_url: str | None = field(default_factory=lambda: os.environ.get('S3_ENDPOINT_URL'))
    s3_region: str = field(default_factory=lambda: os.environ.get('S3_REGION', 'us-east-1'))
    s3_bucket: str = field(default_factory=lambda: os.environ.get('S3_BUCKET', os.environ.get('MINIO_BUCKET', 'html-office')))
    s3_access_key_id: str | None = field(default_factory=lambda: os.environ.get('S3_ACCESS_KEY_ID'))
    s3_secret_access_key: str | None = field(default_factory=lambda: os.environ.get('S3_SECRET_ACCESS_KEY'))


@lru_cache
def get_settings() -> Settings:
    return Settings()
