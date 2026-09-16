"""Deterministic, explicitly injected provider for tests and local development."""
import hashlib
from uuid import UUID

from src.documents.contracts import DocumentGraphModel, EditCommandModel, GenerationPlanModel
from src.generation.prompts.plan import PLAN_PROMPT_VERSION
from src.generation.provider import ProviderResult, invocation_audit


class FakeProvider:
    def _result(self, value, task, prompt, contract, sources):
        return ProviderResult(value, invocation_audit('fake', 'deterministic-v1', task, prompt, contract, sources))

    async def create_plan(self, request):
        parameters = {'outputModes': ['document'], 'audience': '管理层', 'lengthPreset': 'standard',
                      'density': 'balanced', 'outputSpec': 'responsive', 'emphasis': [], **request.parameters}
        plan = GenerationPlanModel.model_validate({'artifactId': request.artifact_id, **parameters,
            'outline': [{'id': f'source-{index + 1}', 'title': source.content['title'] or '材料摘要'}
                        for index, source in enumerate(request.sources)],
            'sourceSummary': {'parsed': len(request.sources), 'failed': request.failed_count, 'conflicts': []}})
        return self._result(plan, 'plan', PLAN_PROMPT_VERSION, 'GenerationPlan', request.sources)

    async def create_document(self, request):
        def identity(label):
            return str(UUID(bytes=hashlib.sha256((request.plan['artifactId'] + label).encode()).digest()[:16], version=7))
        sections, slides = [], []
        for index, source in enumerate(request.sources):
            section_id, block_id = identity(f'section-{index}'), identity(f'block-{index}')
            title = (source.content.get('title') or '材料摘要')[:90]
            sections.append({'id': section_id, 'order': index, 'title': title, 'blocks': [{
                'id': block_id, 'order': 0, 'kind': 'richText', 'text': title,
                'sourceRefs': [{'sourceId': source.source_id, 'locator': 'source metadata'}]}]})
            slides.append({'id': identity(f'slide-{index}'), 'order': index, 'sectionId': section_id,
                'kind': 'content', 'layoutId': 'title-body', 'animationTimeline': [],
                'timing': {'plannedSeconds': 60, 'rehearsalEvents': []},
                'slotAssignments': [{'id': identity(f'slot-{index}'), 'order': 0, 'slotId': 'title',
                                     'blockIds': [block_id], 'assetIds': []}]})
        graph = {'schemaVersion': '1.0.0', 'artifactId': request.plan['artifactId'], 'title': '材料报告',
            'outputModes': request.plan['outputModes'], 'theme': {'id': 'core', 'tokens': {}},
            'assets': [], 'sections': sections}
        if 'presentation' in graph['outputModes']:
            graph['presentation'] = {'stage': {'width': 1920, 'height': 1080}, 'slides': slides}
        return self._result(DocumentGraphModel.model_validate(graph), 'document', 'document-v1', 'DocumentGraph', request.sources)

    async def create_edit_commands(self, request):
        block = next(block for section in request.document['sections'] for block in section['blocks'] if block['kind'] == 'richText')
        commands = [EditCommandModel.model_validate({'kind': 'replaceText', 'blockId': block['id'], 'text': request.instruction})]
        return self._result(commands, request.task, 'edit-v1', 'EditCommand', request.sources)
