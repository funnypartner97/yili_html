"""ARQ worker entrypoint.

Run a generation worker with:

    uv run --project services/api arq src.worker.arq_settings.WorkerSettings

The worker consumes `generate_document_job` (see src/worker/jobs.py), which reads
its database URL and provider from server-owned settings and performs its own
bounded retry with exponential backoff. Redis location and the attempt budget come
from the same `WorkerSettings` config dataclass used across the worker.
"""
from __future__ import annotations

from arq.connections import RedisSettings

from src.worker.jobs import generate_document_job
from src.worker.settings import WorkerSettings as WorkerConfig

_config = WorkerConfig()


class WorkerSettings:
    """ARQ worker configuration (attribute container consumed by the arq CLI)."""

    functions = [generate_document_job]
    redis_settings = RedisSettings.from_dsn(_config.redis_url)
    max_tries = _config.max_tries
    job_timeout = 600
    health_check_interval = 30
    allow_abort_jobs = True
