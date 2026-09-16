"""Typed model boundary. Routes select tasks; model/endpoint never come from clients."""
import hashlib
import json
from dataclasses import dataclass, field
from typing import Generic, Literal, Protocol, TypeVar

from src.documents.contracts import CONTRACT_REFS, SCHEMAS, DocumentGraphModel, EditCommandModel, GenerationPlanModel

TaskPolicy = Literal['plan', 'document', 'complex_edit', 'summary', 'classification', 'local_rewrite', 'validation_repair']
T = TypeVar('T')


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class SourceInput:
    source_id: str
    sha256: str
    parsed_sha256: str
    content: dict = field(repr=False)

    def version(self) -> dict:
        return {'sourceId': self.source_id, 'sha256': self.sha256, 'parsedSha256': self.parsed_sha256}


@dataclass(frozen=True)
class PlanProviderRequest:
    artifact_id: str
    instruction: str = field(repr=False)
    parameters: dict = field(repr=False)
    sources: list[SourceInput] = field(repr=False)
    failed_count: int


@dataclass(frozen=True)
class DocumentProviderRequest:
    plan: dict = field(repr=False)
    sources: list[SourceInput] = field(repr=False)


@dataclass(frozen=True)
class EditProviderRequest:
    document: dict = field(repr=False)
    instruction: str = field(repr=False)
    sources: list[SourceInput] = field(repr=False)
    task: Literal['complex_edit', 'local_rewrite', 'validation_repair'] = 'complex_edit'


@dataclass(frozen=True)
class ProviderResult(Generic[T]):
    value: T = field(repr=False)
    audit: dict = field(repr=False)


class GenerationProvider(Protocol):
    async def create_plan(self, request: PlanProviderRequest) -> ProviderResult[GenerationPlanModel]: ...
    async def create_document(self, request: DocumentProviderRequest) -> ProviderResult[DocumentGraphModel]: ...
    async def create_edit_commands(self, request: EditProviderRequest) -> ProviderResult[list[EditCommandModel]]: ...


def response_schema(contract: str) -> dict:
    """Inline only checked-in local refs, preserving the canonical constraints."""
    filename = CONTRACT_REFS[contract].split('#')[0]
    def expand(value, file):
        if isinstance(value, list):
            return [expand(item, file) for item in value]
        if not isinstance(value, dict):
            return value
        if '$ref' in value:
            target_file, _, pointer = value['$ref'].partition('#')
            target_file = target_file or file
            target = SCHEMAS[target_file]
            for part in pointer.strip('/').split('/') if pointer else []:
                target = target[part]
            return expand(target, target_file)
        return {key: expand(item, file) for key, item in value.items()
                if key not in ('$id', '$schema', 'definitions')}
    schema = expand(SCHEMAS[filename], filename)
    return {'type': 'array', 'minItems': 1, 'maxItems': 100, 'items': schema} if contract == 'EditCommand' else schema


def invocation_audit(provider: str, model: str, task: TaskPolicy, prompt_version: str,
                     contract: str, sources: list[SourceInput]) -> dict:
    return {'provider': provider, 'model': model, 'task': task, 'promptVersion': prompt_version,
            'schemaVersion': '1.0.0', 'schemaSha256': digest(response_schema(contract)),
            'sources': [source.version() for source in sources]}


def get_provider() -> GenerationProvider:
    # No environment-selected fake in production. Tests inject the dependency explicitly.
    from src.generation.china_provider import ChinaProvider, ProviderSettings
    return ChinaProvider(ProviderSettings.from_environment())
