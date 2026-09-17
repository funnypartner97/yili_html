import asyncio

from arq.connections import RedisSettings

from src.worker.enqueue import GENERATE_JOB, ArqJobEnqueuer


class FakePool:
    def __init__(self):
        self.calls: list[tuple] = []

    async def enqueue_job(self, function, *args, **kwargs):
        self.calls.append((function, args, kwargs))


def test_enqueuer_uses_the_job_id_as_the_idempotency_key():
    enqueuer = ArqJobEnqueuer("redis://localhost:6379/0")
    pool = FakePool()
    enqueuer._pool = pool  # bypass the lazy Redis connection
    asyncio.run(enqueuer.enqueue("job-123"))
    assert pool.calls == [(GENERATE_JOB, ("job-123",), {"_job_id": "job-123"})]


def test_worker_entrypoint_registers_the_generation_job():
    from src.worker.arq_settings import WorkerSettings
    from src.worker.jobs import generate_document_job

    assert WorkerSettings.functions == [generate_document_job]
    assert isinstance(WorkerSettings.redis_settings, RedisSettings)
    assert WorkerSettings.max_tries == 3
    assert WorkerSettings.job_timeout >= 60
