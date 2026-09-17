"""Worker process configuration. Injection seams stay in jobs.py."""
import os
from dataclasses import dataclass, field

from src.core.settings import database_url


def redis_url() -> str:
    return os.environ.get('REDIS_URL', 'redis://localhost:6379/0')


@dataclass(frozen=True)
class WorkerSettings:
    database_url: str = field(default_factory=database_url)
    redis_url: str = field(default_factory=redis_url)
    max_tries: int = 3
    retry_base_delay: float = 5.0
