import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from pydantic import SecretStr

from src.core.errors import DomainError
from src.generation.china_provider import ChinaProvider, ProviderSettings, resolve_policy
from src.generation.provider import DocumentProviderRequest, EditProviderRequest, PlanProviderRequest, SourceInput

FIXTURES = json.loads((Path(__file__).resolve().parents[4] / 'packages/contracts/tests/fixtures.json').read_text(encoding='utf-8'))


def request():
    return PlanProviderRequest(artifact_id=FIXTURES['GenerationPlan']['artifactId'], instruction='报告',
        parameters={'outputModes': ['document', 'presentation']}, sources=[SourceInput(
        source_id='01993f2f-2b79-7000-8000-000000000003', sha256='a' * 64,
        parsed_sha256='b' * 64, content={'kind': 'csv', 'title': 'private-source'})], failed_count=0)


def encoded(value, **kwargs):
    return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}], **kwargs}).encode()


def settings(**kwargs):
    return ProviderSettings(api_key=SecretStr('test-secret'), **kwargs)


@pytest.mark.parametrize('kwargs', [
    {'provider': 'openai'}, {'provider': 'Qwen'}, {'provider': 'anthropic'}, {'provider': 'google'},
    {'provider': 'deepseek'}, {'provider': 'doubao'},
    {'endpoint': 'https://api.openai.com/v1/chat/completions'},
    {'endpoint': 'http://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'},
    {'endpoint': 'https://dashscope.aliyuncs.com.evil.test/compatible-mode/v1/chat/completions'},
    {'endpoint': 'https://user@dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'},
    {'endpoint': 'https://127.0.0.1/compatible-mode/v1/chat/completions'},
    {'endpoint': 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions'},
    {'max_model': 'gpt-4'}, {'max_model': 'qwen-max-latest'}, {'flash_model': 'qwen-flash'},
])
def test_policy_rejects_unapproved_configuration_before_io(kwargs):
    with pytest.raises(DomainError) as error:
        ChinaProvider(settings(**kwargs))
    assert error.value.code == 'provider_configuration_invalid'
    assert 'test-secret' not in str(error.value)


def test_server_task_policy_selects_pinned_max_and_flash():
    for task in ['plan', 'document', 'complex_edit']:
        assert resolve_policy(settings(), task).model == 'qwen3.7-max-2026-05-20'
    for task in ['summary', 'classification', 'local_rewrite', 'validation_repair']:
        assert resolve_policy(settings(), task).model == 'qwen3.7-flash-2026-07-15'
    with pytest.raises(DomainError):
        resolve_policy(settings(), 'gpt-4')


def test_production_adapter_sends_canonical_schema_and_audits_without_source_text():
    calls = []
    async def transport(policy, body, key):
        calls.append((policy, body))
        return encoded(FIXTURES['GenerationPlan'])
    result = asyncio.run(ChinaProvider(settings(), transport=transport).create_plan(request()))
    policy, body = calls[0]
    assert len(calls) == 1
    assert body['model'] == 'qwen3.7-max-2026-05-20'
    schema = body['response_format']['json_schema']['schema']
    Draft7Validator(schema).validate(FIXTURES['GenerationPlan'])
    broken = deepcopy(FIXTURES['GenerationPlan']); broken['extra'] = 'bad'
    assert not Draft7Validator(schema).is_valid(broken)
    assert body['response_format']['type'] == 'json_schema'
    assert body['response_format']['json_schema']['strict'] is True
    assert 'private-source' in body['messages'][1]['content']
    assert result.audit['model'] == body['model']
    assert result.audit['schemaSha256'] and result.audit['sources'][0]['parsedSha256'] == 'b' * 64
    assert 'private-source' not in str(result.audit) and 'test-secret' not in str(result.audit)


@pytest.mark.parametrize('reply', [b'not json', encoded({'unexpected': True}),
    b'{"choices":[]}', b'{"choices":[{"finish_reason":"length","message":{"content":"{}"}}]}',
    b'{"choices":[{"finish_reason":"stop","message":{"content":"```json {} ```"}}]}',
    b'x' * (2 * 1024 * 1024 + 1)], ids=['not-json', 'wrong-schema', 'empty', 'truncated', 'markdown', 'oversized'])
def test_malformed_truncated_or_oversized_response_rejected_once(reply):
    count = 0
    async def transport(*args):
        nonlocal count
        count += 1
        return reply
    with pytest.raises(DomainError) as error:
        asyncio.run(ChinaProvider(settings(), transport=transport).create_plan(request()))
    assert error.value.code == 'provider_output_invalid'
    assert count == 1


def test_transport_errors_are_sanitized_and_not_retried():
    count = 0
    async def transport(*args):
        nonlocal count
        count += 1
        raise RuntimeError('test-secret private-source')
    with pytest.raises(DomainError) as error:
        asyncio.run(ChinaProvider(settings(), transport=transport).create_plan(request()))
    assert error.value.code == 'provider_unavailable'
    assert 'test-secret' not in str(error.value) and 'private-source' not in str(error.value)
    assert count == 1


def test_document_and_edit_boundaries_validate_contracts_and_policy():
    bodies = []
    async def transport(policy, body, key):
        bodies.append(body)
        return encoded(FIXTURES['DocumentGraph'] if len(bodies) == 1 else [FIXTURES['EditCommand']])
    provider = ChinaProvider(settings(), transport=transport)
    plan_request = request()
    document_request = DocumentProviderRequest(plan=FIXTURES['GenerationPlan'], sources=plan_request.sources)
    graph = asyncio.run(provider.create_document(document_request))
    edit_request = EditProviderRequest(document=graph.value.model_dump(by_alias=True, mode='json'),
        instruction='更新摘要', sources=plan_request.sources, task='local_rewrite')
    commands = asyncio.run(provider.create_edit_commands(edit_request))
    assert commands.value[0].model_dump(by_alias=True)['kind'] == 'replaceText'
    assert bodies[1]['model'] == 'qwen3.7-flash-2026-07-15'
    Draft7Validator(bodies[1]['response_format']['json_schema']['schema']).validate([FIXTURES['EditCommand']])


def test_production_transport_rejects_private_dns_before_connection(monkeypatch):
    from src.generation import china_provider
    async def resolve(host):
        return '127.0.0.1'
    monkeypatch.setattr(china_provider, '_resolve_address', resolve)
    def forbidden(*args):
        pytest.fail('Private address reached socket transport')
    monkeypatch.setattr(china_provider, '_post_pinned', forbidden)
    with pytest.raises(DomainError) as error:
        asyncio.run(ChinaProvider(settings()).create_plan(request()))
    assert error.value.code == 'provider_unavailable'


@pytest.mark.parametrize('status,length,stream_size,encoding', [
    (302, None, 0, 'identity'), (429, None, 0, 'identity'),
    (200, '2097153', 0, 'identity'), (200, None, 2097153, 'identity'),
    (200, None, 0, 'gzip'),
])
def test_https_rejects_redirects_compression_and_bounded_streams(monkeypatch, status, length, stream_size, encoding):
    from src.generation import china_provider as module
    class Connection:
        sock = None
        active_socket = None
        def __init__(self, *args, **kwargs):
            self.status, self.read_bytes, self.closed = status, 0, False
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return self
        def getheader(self, name, default=None):
            return {'Content-Length': length, 'Content-Encoding': encoding}.get(name, default)
        def read1(self, count):
            result = b'x' * min(count, stream_size - self.read_bytes)
            self.read_bytes += len(result)
            return result
        def close(self):
            self.closed = True
    connection = Connection()
    monkeypatch.setattr(module, '_PinnedConnection', lambda *args, **kwargs: connection)
    with pytest.raises(ValueError):
        module._post_pinned(resolve_policy(settings(), 'plan'), b'{}', SecretStr('key'), '8.8.8.8')
    assert connection.closed
    assert connection.read_bytes <= 2097153
    if status != 200 or length or encoding != 'identity':
        assert connection.read_bytes == 0


def test_total_deadline_interrupts_stalled_header_read(monkeypatch):
    import threading
    from src.generation import china_provider as module
    interrupted = threading.Event()
    class Socket:
        def shutdown(self, how):
            interrupted.set()
        def close(self):
            pass
        def settimeout(self, value):
            pass
    class Connection:
        sock = active_socket = Socket()
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            if interrupted.wait(0.3):
                raise OSError('connection interrupted')
            raise AssertionError('Total deadline did not close the active socket')
        def close(self):
            pass
    monkeypatch.setattr(module, '_PinnedConnection', lambda *args, **kwargs: Connection())
    monkeypatch.setattr(module, 'TOTAL_TIMEOUT', 0.03)
    with pytest.raises(OSError):
        module._post_pinned(resolve_policy(settings(), 'plan'), b'{}', SecretStr('key'), '8.8.8.8')
    assert interrupted.is_set()


def test_fake_document_and_commands_are_deterministic_valid_contracts():
    from src.generation.fake_provider import FakeProvider
    provider = FakeProvider()
    req = DocumentProviderRequest(plan=FIXTURES['GenerationPlan'], sources=request().sources)
    first = asyncio.run(provider.create_document(req))
    second = asyncio.run(provider.create_document(req))
    assert first.value == second.value
    assert first.value.presentation.stage.width == 1920
    edit = EditProviderRequest(document=first.value.model_dump(by_alias=True), instruction='Edited', sources=request().sources)
    result = asyncio.run(provider.create_edit_commands(edit))
    assert result.value[0].model_dump(by_alias=True)['text'] == 'Edited'


def test_oversized_inputs_are_rejected_without_silent_truncation():
    from dataclasses import replace
    async def forbidden(*args):
        pytest.fail('Oversized request reached transport')
    req = replace(request(), instruction='x' * (8 * 1024 * 1024))
    with pytest.raises(DomainError) as error:
        asyncio.run(ChinaProvider(settings(), transport=forbidden).create_plan(req))
    assert error.value.code == 'provider_input_too_large'


def test_response_reporting_different_model_cannot_masquerade_as_pinned_model():
    async def transport(*args):
        return encoded(FIXTURES['GenerationPlan'], model='unapproved-model')
    with pytest.raises(DomainError) as error:
        asyncio.run(ChinaProvider(settings(), transport=transport).create_plan(request()))
    assert error.value.code == 'provider_output_invalid'


@pytest.mark.parametrize('address', ['127.0.0.1', '10.1.2.3', '169.254.169.254', '::1', 'ff02::1', '224.0.0.1'])
def test_dns_resolution_rejects_non_unicast_public_addresses(monkeypatch, address):
    import socket
    from src.generation.china_provider import _resolve_address
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, 443))])
    with pytest.raises(ValueError):
        asyncio.run(_resolve_address('dashscope.aliyuncs.com'))
