import copy
import json
from pathlib import Path

import pytest

from src.documents import contracts

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = json.loads((ROOT / 'packages/contracts/tests/fixtures.json').read_text(encoding='utf-8'))
FIXTURES.update(
    PresentationDocument=FIXTURES['DocumentGraph']['presentation'],
    MediaIntent=FIXTURES['DocumentGraph']['assets'][0]['mediaIntent'],
    LayoutRegistry=json.loads((ROOT / 'packages/contracts/registries/core-presentation-layouts.json').read_text(encoding='utf-8')),
)


@pytest.mark.parametrize('name,fixture', FIXTURES.items())
def test_shared_round_trip(name, fixture):
    model = getattr(contracts, name + 'Model').model_validate(fixture)
    assert model.model_dump(by_alias=True, exclude_unset=True, mode='json') == fixture
    contracts.validate_schema(name, fixture)


def test_plan_accepts_multiple_modes():
    plan = contracts.GenerationPlanModel.model_validate(FIXTURES['GenerationPlan'])
    assert plan.output_modes == ['document', 'presentation']


@pytest.mark.parametrize('modes', [[], ['document', 'document'], ['data'], ['dashboard']])
def test_rejects_unavailable_or_duplicate_modes(modes):
    fixture = copy.deepcopy(FIXTURES['GenerationPlan'])
    fixture['outputModes'] = modes
    with pytest.raises(ValueError):
        contracts.GenerationPlanModel.model_validate(fixture)


@pytest.mark.parametrize('name,key', [('TemplatePackage', 'dependencies'), ('TemplatePackage', 'licenseMetadata'), ('ChartPlan', 'alternatives'), ('ChartPlan', 'invariantResults')])
def test_required_metadata(name, key):
    fixture = copy.deepcopy(FIXTURES[name]); del fixture[key]
    with pytest.raises(ValueError):
        getattr(contracts, name + 'Model').model_validate(fixture)


@pytest.mark.parametrize('key', ['rights', 'provenance', 'alt'])
def test_media_requires_metadata(key):
    fixture = copy.deepcopy(FIXTURES['DocumentGraph']['assets'][0]['mediaIntent']); del fixture[key]
    with pytest.raises(ValueError):
        contracts.MediaIntentModel.model_validate(fixture)


@pytest.mark.parametrize('violation', ['layout', 'slot', 'capacity', 'note', 'duplicate', 'stage', 'script', 'source'])
def test_graph_rejects_invalid_semantics(violation):
    graph = copy.deepcopy(FIXTURES['DocumentGraph'])
    slide = graph['presentation']['slides'][0]
    if violation == 'layout': slide['layoutId'] = 'unknown'
    if violation == 'slot': slide['slotAssignments'][0]['slotId'] = 'unknown'
    if violation == 'capacity':
        block = copy.deepcopy(graph['sections'][0]['blocks'][0])
        block.update(id='01993f2f-2b79-7000-8000-000000000099', order=1)
        graph['sections'][0]['blocks'].append(block)
        slide['slotAssignments'][0]['blockIds'].append(block['id'])
    if violation == 'note': slide['speakerNotes']['slideId'] = graph['artifactId']
    if violation == 'duplicate': graph['sections'][0]['blocks'] *= 2
    if violation == 'stage': graph['presentation']['stage']['width'] = 1280
    if violation == 'script': slide['animationTimeline'][0]['script'] = 'alert(1)'
    if violation == 'source': graph['sections'][0]['blocks'][0]['sourceRefs'] = []
    with pytest.raises(ValueError):
        contracts.DocumentGraphModel.model_validate(graph)


def test_slide_reorder_preserves_notes():
    graph = copy.deepcopy(FIXTURES['DocumentGraph'])
    second = copy.deepcopy(graph['presentation']['slides'][0])
    second['id'] = '01993f2f-2b79-7000-8000-000000000020'
    second['speakerNotes']['id'] = '01993f2f-2b79-7000-8000-000000000021'
    second['speakerNotes']['slideId'] = second['id']
    for i, assignment in enumerate(second['slotAssignments']):
        assignment['id'] = f'01993f2f-2b79-7000-8000-00000000002{i + 2}'
    second['animationTimeline'] = []
    graph['presentation']['slides'][0]['order'] = 1
    graph['presentation']['slides'].insert(0, second)
    model = contracts.DocumentGraphModel.model_validate(graph)
    assert model.presentation.slides[0].speaker_notes.slide_id == second['id']


def test_reserved_modes_do_not_enable_service():
    assert contracts.ENABLED_OUTPUT_MODES == ('document', 'presentation')
    for mode in ('data', 'dashboard'):
        fixture = copy.deepcopy(FIXTURES['GenerationPlan']); fixture['outputModes'] = [mode]
        with pytest.raises(ValueError): contracts.GenerationPlanModel.model_validate(fixture)


def test_artifact_identity_cannot_collide_with_child():
    graph = copy.deepcopy(FIXTURES['DocumentGraph'])
    graph['assets'][0]['id'] = graph['artifactId']
    graph['presentation']['slides'][0]['slotAssignments'][1]['assetIds'] = [graph['artifactId']]
    with pytest.raises(ValueError):
        contracts.DocumentGraphModel.model_validate(graph)


def test_schema_and_model_reject_chart_audit_without_reasons():
    chart = copy.deepcopy(FIXTURES['ChartPlan'])
    chart['alternatives'][0]['reasons'] = []
    with pytest.raises(ValueError):
        contracts.validate_schema('ChartPlan', chart)
    with pytest.raises(ValueError):
        contracts.ChartPlanModel.model_validate(chart)
