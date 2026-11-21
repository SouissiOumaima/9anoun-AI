"""Two-step orchestration tests use injected service fixtures, never a remote API."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.document_intelligence.evaluation.fictive_documents import DOCS_DIR
from src.document_intelligence.service import handle_request
from src.document_intelligence.tests.test_document_intelligence_gemini import _perfect_client
from src.legal_retrieval.contract.handler import handle as ds2_handle
from src.orchestrator.card_repository import MockCardRepository
from src.orchestrator.case_integration import CaseIntegrationWorkflow, CaseWorkflowError
from src.orchestrator.models import ActiveContext, CardType, UserIdentity
from src.orchestrator.audit import AuditTrail

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def setup_flow(tmp_path):
    scenario = json.loads((ROOT / 'data/mock_cards/orchestrator_case_e2e_demo.json').read_text(encoding='utf-8'))
    card = scenario['card']
    doc = card['data']['documents'][0]
    target = tmp_path / 'cards' / card['card_id'] / 'documents' / doc['document_id'] / doc['file_name']
    target.parent.mkdir(parents=True)
    target.write_bytes((DOCS_DIR / doc['file_name']).read_bytes())
    actor = UserIdentity('org-demo', 'test-user', 'lawyer', frozenset({card['card_id']}))
    context = ActiveContext('org-demo', card['card_id'], CardType.CASE, {
        'document_id': doc['document_id'], 'document_file_name': doc['file_name'],
        'document_mime_type': doc['mime_type'], 'document_storage_ref': doc['storage_ref'],
    })
    calls = []

    def ds3(request):
        calls.append('ds3')
        return handle_request(request, storage_root_dir=tmp_path, client=_perfect_client('DS3-01'))

    def ds2(request, *, live):
        calls.append('ds2')
        # Injected schema-valid fixture, explicitly simulated for this test only.
        mocked = ds2_handle({**request, 'sector': 'btp'}, live=False)
        mocked['mode'] = 'live'
        mocked['computed_by'] = 'legal_retrieval.search.live'
        return mocked

    flow = CaseIntegrationWorkflow(ds3=ds3, ds2=ds2, audit=AuditTrail())
    common = dict(actor=actor, context=context, repository=MockCardRepository.from_payload([card]))
    return flow, scenario, common, calls


def prepare(setup_flow):
    flow, scenario, common, calls = setup_flow
    result = flow.prepare(**common, subject_id=scenario['subject_id'], evidence_id=scenario['evidence_id'],
                          legal_request=scenario['legal_request'], language='fr')
    return result


def test_no_retrieval_or_ds4_before_confirmation(setup_flow):
    result = prepare(setup_flow)
    assert result['status'] == 'pending_confirmation'
    assert setup_flow[3] == ['ds3']
    assert all(f['user_confirmed'] is False for f in result['facts'])
    assert all(f['citation']['document_id'] == result['document_id'] for f in result['facts'])


def test_full_flow_transmits_only_selected_confirmed_facts_and_is_idempotent(setup_flow):
    flow, _, common, calls = setup_flow
    prepared = prepare(setup_flow)
    fact_id = next(f['fact_id'] for f in prepared['facts'] if f['selectable'])
    kwargs = dict(**common, review_id=prepared['review_id'], confirmed_fact_ids=[fact_id], confirm_document_link=True)
    result = flow.complete(**kwargs)
    assert result['status'] == 'completed'
    assert len(result['confirmed_facts']) == 1
    assert result['confirmed_facts'][0]['user_confirmed'] is True
    assert result['analysis']['legal_conclusion'] is None
    assert result['legal_sources']
    assert flow.complete(**kwargs) == result
    assert calls == ['ds3', 'ds2']
    assert [e.details['agent'] for e in flow.audit.events()] == ['document_intelligence', 'legal_retrieval', 'track_a_legal']
    assert all('value' not in e.details and 'query' not in e.details for e in flow.audit.events())


@pytest.mark.parametrize('selection,link', [([], True), (['invented'], True), (None, True), ([], False)])
def test_invalid_or_missing_confirmation_never_calls_ds2(setup_flow, selection, link):
    flow, _, common, calls = setup_flow
    prepared = prepare(setup_flow)
    with pytest.raises(CaseWorkflowError, match='CONFIRMATION'):
        flow.complete(**common, review_id=prepared['review_id'], confirmed_fact_ids=selection, confirm_document_link=link)
    assert calls == ['ds3']


def test_foreign_user_cannot_confirm_review(setup_flow):
    flow, _, common, _ = setup_flow
    prepared = prepare(setup_flow)
    actor = UserIdentity('org-demo', 'other-user', 'lawyer', common['actor'].authorized_card_ids)
    with pytest.raises(CaseWorkflowError, match='CONTEXT_MISMATCH'):
        flow.complete(**{**common, 'actor': actor}, review_id=prepared['review_id'],
                      confirmed_fact_ids=[prepared['facts'][0]['fact_id']], confirm_document_link=True)


def test_mock_ds2_is_blocked_and_can_be_retried(setup_flow):
    flow, _, common, _ = setup_flow
    prepared = prepare(setup_flow)
    real_handler = flow.ds2
    flow.ds2 = lambda request, **_: {'mode': 'mock', 'request_id': request['request_id']}
    kwargs = dict(**common, review_id=prepared['review_id'],
                  confirmed_fact_ids=[prepared['facts'][0]['fact_id']], confirm_document_link=True)
    with pytest.raises(CaseWorkflowError, match='DS2_LIVE'):
        flow.complete(**kwargs)
    flow.ds2 = real_handler
    assert flow.complete(**kwargs)['status'] == 'completed'


def test_response_from_another_document_is_rejected(setup_flow):
    flow, _, _, _ = setup_flow
    original = flow.ds3
    def foreign(request):
        result = original(request)
        result['document_id'] = 'other-document'
        return result
    flow.ds3 = foreign
    with pytest.raises(CaseWorkflowError, match='PROVENANCE'):
        prepare(setup_flow)


def test_low_confidence_field_cannot_be_confirmed(setup_flow):
    flow, _, common, calls = setup_flow
    original = flow.ds3
    def weak(request):
        result = original(request)
        result['result']['fields']['base_salary']['confidence'] = 0.5
        return result
    flow.ds3 = weak
    prepared = prepare(setup_flow)
    fact = next(f for f in prepared['facts'] if f['field_name'] == 'base_salary')
    assert fact['selectable'] is False
    with pytest.raises(CaseWorkflowError, match='CONFIRMATION'):
        flow.complete(**common, review_id=prepared['review_id'], confirmed_fact_ids=[fact['fact_id']], confirm_document_link=True)
    assert calls == ['ds3']


def test_fictitious_case_matches_official_card_schema(setup_flow):
    from jsonschema import Draft202012Validator, FormatChecker
    schema = json.loads((ROOT / 'data/mock_cards/schemas/orchestrator_case_card.v0.schema.json').read_text(encoding='utf-8'))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(setup_flow[1]['card'])
