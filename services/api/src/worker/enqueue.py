"""ARQ enqueue boundary for confirmed generation jobs.

Confirming a plan durably records a `queued` job row; this boundary hands that job
to the ARQ worker queue. The job id is used as the ARQ `_job_id`, so enqueue is
idempotent and matches the durable job's own idempotency key. Tests inject a fake;
production connects lazily to Redis, so an unreachable queue surfaces as a clean
`queue_unavailable` error at the API edge while the job row stays `queued` and can
be re-enqueued by confirming again.
"""
from __future__ import annotations

from typing import Protocol

from arq.connections import ArqRedis, RedisSettings, create_pool

from src.worker.settings import WorkerSettings as WorkerConfig

GENERATE_JOB = "generate_document_job"


class JobEnqueuer(Protocol):
    async def enqueue(self, job_id: str) -> None: ...


class ArqJobEnqueuer:
    """Lazily connects an ARQ pool and enqueues generation jobs by id."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._pool: ArqRedis | None = None

    async def enqueue(self, job_id: str) -> None:
        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(self.redis_url))
        await self._pool.enqueue_job(GENERATE_JOB, job_id, _job_id=job_id)


_enqueuer: ArqJobEnqueuer | None = None


async def get_enqueuer() -> JobEnqueuer:
    global _enqueuer
    if _enqueuer is None:
        _enqueuer = ArqJobEnqueuer(WorkerConfig().redis_url)
    return _enqueuer
