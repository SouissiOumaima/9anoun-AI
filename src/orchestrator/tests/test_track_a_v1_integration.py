"""Official DS1 boundary tests against the delivered DS4 v1 implementation."""

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.orchestrator.track_a_adapter import TrackAAdapter
from src.orchestrator.tool_contracts import ToolContractError
from src.orchestrator.web_app import chat
from src.orchestrator.track_a_requests import build_track_a_request_from_case_card
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


def case_card():
    cards = json.loads((ROOT / 'data/mock_cards/orchestrator_cards_demo.json').read_text(encoding='utf-8'))
    return next(card for card in cards if card['card_id'] == 'case-demo-001')


def mapped_case(card, version):
    return build_track_a_request_from_case_card(
        request_id='date-boundary', case_id=card['card_id'], language='fr',
        case_card=card, contract_version=version,
    )


@pytest.mark.parametrize('reason', ['Date non précisée dans la pièce.', 'التاريخ غير مذكور في الوثيقة.'])
def test_v1_unknown_date_preserves_uncertainty_and_matches_official_schemas(reason):
    card = case_card()
    card['data']['events'][0].update(date=None, date_precision='unknown', date_reason=reason)
    saved = deepcopy(card)
    card_schema = json.loads((ROOT / 'data/mock_cards/schemas/orchestrator_case_card.v0.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(card_schema, format_checker=FormatChecker()).validate(card)
    request = mapped_case(card, 'track_a.v1')
    schema = json.loads((ROOT / 'data/mock_cards/schemas/track_a_request.v1.schema.json').read_text(encoding='utf-8-sig'))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(request)
    assert request['events'][0]['date'] is None
    assert request['events'][0]['date_precision'] == 'unknown'
    assert request['events'][0]['date_reason'] == reason
    assert request['events'][0]['evidence_ids'] == card['data']['events'][0]['evidence_ids']
    assert card == saved


def test_v0_still_rejects_unknown_date_even_with_valid_v1_metadata():
    card = case_card()
    card['data']['events'][0].update(date=None, date_precision='unknown', date_reason='Pièce non datée.')
    with pytest.raises(ValueError, match='no exact date for Track A v0'):
        mapped_case(card, 'track_a.v0')


@pytest.mark.parametrize('metadata', [
    {}, {'date_precision': 'unknown'}, {'date_reason': 'Date absente.'},
    {'date_precision': 'exact', 'date_reason': 'Date absente.'},
    {'date_precision': 'unknown', 'date_reason': None},
    {'date_precision': 'unknown', 'date_reason': '   '},
])
def test_v1_unknown_date_requires_explicit_valid_metadata(metadata):
    card = case_card()
    event = card['data']['events'][0]
    event.pop('date_precision', None)
    event.pop('date_reason', None)
    event.update(date=None, **metadata)
    with pytest.raises(ValueError, match='schema-valid'):
        mapped_case(card, 'track_a.v1')


@pytest.mark.parametrize('version', ['track_a.v0', 'track_a.v1'])
def test_exact_dates_remain_unchanged_for_both_contracts(version):
    card = case_card()
    request = mapped_case(card, version)
    assert [e['date'] for e in request['events']] == [e['date'] for e in card['data']['events']]
    if version == 'track_a.v0':
        assert all('date_precision' not in e and 'date_reason' not in e for e in request['events'])


def test_v1_does_not_accept_an_invalid_exact_date():
    card = case_card()
    card['data']['events'][0].update(date='2026-02-30', date_precision='exact')
    with pytest.raises(ValueError, match='schema-valid'):
        mapped_case(card, 'track_a.v1')


def test_official_chat_preserves_missing_information_and_declared_contradictions(monkeypatch):
    from src.orchestrator import web_app

    cards = deepcopy(web_app._demo_cards())
    card = next(c for c in cards if c['card_id'] == 'case-demo-001')
    evidence_ids = [e['evidence_id'] for e in card['data']['evidence']]
    card['data']['missing_information'] = [{
        'missing_id': 'missing-sector', 'field_name': 'sector', 'reason': 'Secteur à confirmer.',
    }]
    card['data']['contradictions'] = [{
        'contradiction_id': 'declared-salary-gap', 'description': 'Montants déclarés différents.',
        'source_ids': evidence_ids[:2],
    }]
    monkeypatch.setattr(web_app, '_demo_cards', lambda: cards)
    response = chat({'message': 'Analyse les preuves de ce dossier', 'language': 'fr', 'card_id': 'case-demo-001'})
    assert response['user_response']['status'] == 'success'
    answer = response['answer']
    assert answer['legal_conclusion'] is None
    assert response['citations'] == []
    assert {'reference_id': 'missing-sector', 'reason': 'MISSING_INFORMATION: sector: Secteur à confirmer.'} in answer['uncertain_information']
    assert {'reference_id': 'declared-salary-gap', 'reason': 'DECLARED_CONTRADICTION: Montants déclarés différents.'} in answer['uncertain_information']
    pairs = [(i['reference_id'], i['reason']) for i in answer['uncertain_information']]
    assert len(pairs) == len(set(pairs))


@pytest.mark.parametrize('location', ['params', 'context'])
def test_client_cannot_activate_pdf_verification_in_official_ds1_adapter(location):
    envelope = payload()
    envelope[location]['pdf_root'] = '/client-controlled-directory'
    saved = deepcopy(envelope)
    calls = []

    def handler(request, **kwargs):
        calls.append(kwargs)
        return handle_v1(request)

    response = TrackAAdapter(handler)(envelope)
    assert response['status'] == 'success'
    assert calls == [{}]  # No server-side PDF option can come from the client envelope.
    assert response['data']['result']['legal_conclusion'] is None
    assert envelope == saved
