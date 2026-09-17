"""Seed a deterministic, ready-to-edit artifact for the end-to-end suite.

Run inside the API environment against a live stack:

    docker compose up -d --wait
    uv run --project services/api python scripts/e2e-seed.py

It parses the checked-in PDF fixture, stores it, runs planning and generation with
the deterministic FakeProvider, and writes the resulting artifact id to
`tests/e2e/.seed.json` so specs can open a known-editable document directly.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from uuid import uuid7

from src.db.models import SourceFile
from src.db.session import get_engine
from src.files.parsers.pdf import PdfParser
from src.files.storage import get_storage
from src.generation.fake_provider import FakeProvider
from src.generation.generator import Generator
from src.generation.planner import Planner
from src.db.repositories import ArtifactRepository
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/quarterly-report.pdf"
SEED_OUTPUT = ROOT / "tests/e2e/.seed.json"


def main() -> None:
    data = FIXTURE.read_bytes()
    parsed = PdfParser().parse(FIXTURE).model_dump(by_alias=True, mode="json")
    storage = get_storage()
    storage_key = f"sources/{uuid7()}.pdf"

    with Session(get_engine()) as session:
        repository = ArtifactRepository(session)
        artifact = repository.create_artifact("E2E 季度经营分析")
        storage.put_file(storage_key, FIXTURE, "application/pdf")
        session.add(SourceFile(
            id=str(uuid7()), artifact_id=artifact.id, filename=FIXTURE.name,
            content_type="application/pdf", size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(), storage_key=storage_key,
            parse_status="parsed", parsed_content=parsed))
        session.commit()

        provider = FakeProvider()
        planner = Planner(session, provider)
        plan = asyncio.run(planner.create_plan(artifact.id, "生成管理层季度经营汇报",
                                               {"outputModes": ["document", "presentation"]}))
        planner.confirm_plan(artifact.id, plan.id)
        version = asyncio.run(Generator(session, provider).generate(plan.id))

    SEED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SEED_OUTPUT.write_text(json.dumps(
        {"artifactId": artifact.id, "version": version.version_number}, ensure_ascii=False),
        encoding="utf-8")
    print(f"Seeded artifact {artifact.id} at version {version.version_number}")


if __name__ == "__main__":
    main()
