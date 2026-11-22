"""Official DS1 boundary tests against the delivered DS4 v1 implementation."""

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.orchestrator.track_a_adapter import TrackAAdapter
from src.orchestrator.tool_contracts import ToolContractError
from src.orchestrator.web_app import chat
from src.track_a_legal.v1_handler import handle_v1

ROOT = Path(__file__).resolve().parents[3]


def payload():
    request = json.loads((ROOT / 'docs/ds4_track_a_v1_delivery/example_request_v1.json').read_text(encoding='utf-8-sig'))
    return {
        'request_id': request['request_id'], 'agent': 'track_a_legal',
        'operation': 'analyze_case', 'read_only': True,
        'context': {'card_id': request['case_id'], 'card_type': 'case'},
        'params': {'track_a_request': request},
    }


@pytest.mark.parametrize('language,message', [
    ('fr', 'Analyse les preuves de ce dossier'),
    ('ar', 'حلل أدلة هذه القضية.'),
])
def test_official_chat_returns_preparatory_v1_result(language, message):
    response = chat({'message': message, 'language': language, 'card_id': 'case-demo-001'})
    assert response['user_response']['status'] == 'success'
    assert response['answer']['kind'] == 'case_preparatory'
    assert response['answer']['legal_conclusion'] is None
    assert response['answer']['timeline']
    assert response['citations'] == []


def test_v1_adapter_preserves_document_facts_and_legal_sources_without_promoting_them():
    original = payload()
    saved = deepcopy(original)
    response = TrackAAdapter()(original)
    assert original == saved
    assert response['status'] == 'success'
    assert response['data']['result']['legal_conclusion'] is None
    assert response['citations'] == []


@pytest.mark.parametrize('invalid', ['foreign_case', 'write', 'unknown_version'])
def test_official_adapter_rejects_context_and_version_before_handler(invalid):
    request = payload()
    if invalid == 'foreign_case':
        request['context']['card_id'] = 'foreign-case'
    elif invalid == 'write':
        request['read_only'] = False
    else:
        request['params']['track_a_request']['contract_version'] = 'track_a.v9'
    calls = []
    with pytest.raises(ToolContractError):
        TrackAAdapter(lambda req: calls.append(req))(request)
    assert not calls


def test_v1_adapter_rejects_unauthorized_legal_conclusion():
    def unsafe_handler(request):
        response = handle_v1(request)
        response['result']['legal_conclusion'] = 'Conclusion non validée'
        return response
    with pytest.raises(ToolContractError):
        TrackAAdapter(unsafe_handler)(payload())


@pytest.mark.parametrize('kind', ['request', 'response', 'refusal'])
def test_delivery_examples_match_corrected_official_schemas(kind):
    folder = ROOT / 'docs/ds4_track_a_v1_delivery'
    schema_kind = 'request' if kind == 'request' else 'response'
    schema = json.loads((ROOT / 'data/mock_cards/schemas' / f'track_a_{schema_kind}.v1.schema.json').read_text(encoding='utf-8-sig'))
    example = json.loads((folder / f'example_{kind}_v1.json').read_text(encoding='utf-8-sig'))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(example)
    assert schema['$id'] == f'track_a_{schema_kind}.v1.schema.json'
